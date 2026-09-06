"""Jobs — long-running work started from the UI, watched from the UI.

A corpus build takes minutes to hours and spends real LLM tokens. That rules out doing it inside an
HTTP request. It also rules out doing it in a server thread.

So a job is a **detached subprocess** plus **two files**:

    jobs/<job_id>.json     the record   — what was launched, its pid, its terminal status
    jobs/<job_id>.jsonl    the progress — one JSON event per line, append-only
    jobs/<job_id>.log      the child's stderr, for when something breaks outside our event stream

The child only ever appends to the JSONL. The server only ever reads it. That is the same lock-free
arrangement the engine's reasoning traces already use, and it is why the live view cannot deadlock
against the thing it is watching: there is no shared lock, no queue, and no socket to keep alive.

Liveness is not taken on trust. A record saying "running" is believed only while `os.kill(pid, 0)`
says the process is still there; a vanished process with no terminal event is reported as `failed`,
not left spinning forever in the UI.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from uuid import uuid4
from pathlib import Path
from typing import Iterator

from . import projects

ROOT = projects.ROOT

# How long a watcher waits for a new line before emitting a heartbeat, and when it gives up on a
# finished job. The heartbeat exists so an idle SSE connection isn't reaped by a proxy or the client.
_POLL_S = 0.4
_HEARTBEAT_S = 10.0
_LINGER_AFTER_EXIT_S = 3.0     # keep tailing briefly after the process exits, to flush last writes

BUILD_KINDS = ("build",)
KINDS = BUILD_KINDS + ("run",)        # every kind of job that can occupy a project

# A run_id is a path-encoded lineage key (explorer/lineage.py) whose separator is `~`; the base id
# must never contain one. Project ids are already [a-z0-9_-], so the timestamp is the only new part.
RUN_ID_FMT = "%Y%m%d-%H%M%S"
STEPS_MIN = 1
# Low enough not to be a writing test, high enough that "?" or a bare gene name cannot pass for a question.
MIN_GOAL_CHARS = 12


# --- writing (child side) ---------------------------------------------------

class Progress:
    """The child's handle on its own progress file. One line per event, flushed immediately.

    Flushing matters: buffered progress is invisible progress, and the entire point of this file is
    that somebody is watching it while the work happens."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.path, "a", buffering=1, encoding="utf-8")

    def emit(self, stage: str, status: str = "progress", msg: str = "", **fields) -> None:
        ev = {"ts": time.time(), "stage": stage, "status": status, "msg": str(msg)[:2000]}
        ev.update({k: v for k, v in fields.items() if v is not None})
        self._fh.write(json.dumps(ev, default=str) + "\n")
        self._fh.flush()
        os.fsync(self._fh.fileno())

    def start(self, stage: str, msg: str = "", **f):
        self.emit(stage, "start", msg, **f)

    def done(self, stage: str, msg: str = "", **f):
        self.emit(stage, "done", msg, **f)

    def error(self, stage: str, msg: str, **f):
        self.emit(stage, "error", msg, **f)

    def close(self) -> None:
        try:
            self._fh.close()
        except OSError:
            pass


# --- launching (server side) ------------------------------------------------

def _job_paths(pid_project: str, job_id: str) -> tuple[Path, Path, Path]:
    d = projects.jobs_dir(pid_project)
    return d / f"{job_id}.json", d / f"{job_id}.jsonl", d / f"{job_id}.log"


def _new_job_id(kind: str) -> str:
    return f"{kind}-{time.strftime('%Y%m%d-%H%M%S')}-{os.getpid() % 1000:03d}"


def _python() -> str:
    """The interpreter to run the child with — ours, so it inherits the same venv."""
    return sys.executable or "python3"


def start_build(project_id: str, *, mode: str = "build", dry: bool = False) -> dict:
    """Launch a corpus build for a project. Refuses if one is already running.

    `dry=True` runs discovery + triage only and stops before extraction, spending no LLM tokens: the
    cheap rehearsal that tells you whether your queries find the right papers."""
    if mode not in BUILD_KINDS:
        raise ValueError(f"mode must be one of {BUILD_KINDS}")
    rec = projects.load(project_id)
    if rec.get("adopted"):
        raise ValueError("this corpus was built outside the console and cannot be rebuilt here")
    projects.validate_spec(rec["spec"], for_build=True)     # fail before spawning, with a real reason

    argv = [_python(), "-m", "dnhacksbio.litmap.corpus_build",
            "--project", project_id]
    if dry:
        argv.append("--dry")
    job = _spawn(project_id, mode, argv, extra={"dry": bool(dry)})
    try:
        projects.update(project_id, {"status": "building"})
    except (ValueError, KeyError):
        pass
    return job


def start_run(project_id: str, *, goal: str = "", steps: int = 18) -> dict:
    """Launch an explorer run against this project's graph.

    Same detached-subprocess shape as a build, pointed at `scripts/run_explorer.py`. The run needs a
    graph to reason over and a corpus card for its framing; the card is written next to the graph at
    build time, and `run_explorer.py` infers it from `--db`, so nothing else has to be passed.

    The question is required: the corpus card carries no goal, so an empty question would fall through
    to `run_explorer.DEFAULT_GOAL`, a generic brief."""
    rec = projects.load(project_id)
    db = projects.kg_path(project_id)
    if rec.get("adopted"):
        db = Path(rec["kg_db"]) if rec.get("kg_db") else db
    if not db.exists():
        raise ValueError("this analysis has no corpus yet — build one before running the engine")

    try:
        steps = int(steps)
    except (TypeError, ValueError):
        raise ValueError("steps must be a whole number")
    if steps < STEPS_MIN:
        raise ValueError("checkpoint interval must be positive")
    goal = str(goal or "").strip()[:4000]
    if len(goal) < MIN_GOAL_CHARS:
        raise ValueError(
            "a run needs a question — say what you want the engine to find out from this corpus")

    run_id = f"{project_id}-{time.strftime(RUN_ID_FMT)}-{uuid4().hex[:8]}"
    argv = [_python(), str(ROOT / "scripts" / "run_explorer.py"),
            "--run-id", run_id, "--db", str(db), "--steps", str(steps), "--goal", goal]
    from dnhacksbio.explorer.runtime import Journal
    journal = Journal(ROOT / "data" / "processed")
    manifest = journal.register(run_id, goal, project=project_id, config={"steps": steps})
    journal.append(run_id, "launch", "lifecycle", {**manifest, "lifecycle": "queued", "reason": "Waiting for worker startup"})
    try:
        job = _spawn(project_id, "run", argv, extra={"run_id": run_id, "goal": goal, "steps": steps})
        from dnhacksbio.explorer.runtime import process_identity
        journal.append(run_id, "launch", "worker.registered", {"pid": job["pid"],
                       "process_identity": process_identity(job["pid"])})
    except Exception as exc:
        journal.append(run_id, "launch", "lifecycle", {"lifecycle": "failed", "reason": f"Launch failed: {exc}"})
        raise

    # Record the run on the project so the console can list it before the run has written enough
    # rows for `data.project_of_run` to resolve it from the graph.
    try:
        projects.update(project_id, {"runs": list(rec.get("runs") or []) + [run_id]})
    except (ValueError, KeyError):
        pass
    return job


def _spawn(project_id: str, kind: str, argv: list[str], *, extra: dict | None = None) -> dict:
    from .deployment import lease
    with lease() as fd:
        return _spawn_leased(project_id, kind, argv, extra=extra, lease_fd=fd)


def _spawn_leased(project_id: str, kind: str, argv: list[str], *, extra: dict | None = None,
                  lease_fd: int | None = None) -> dict:
    """Start one detached child, with its record + progress + log files. Refuses to overlap.

    One job at a time per project, whatever the kind: a build rewrites the very graph a run reads,
    and two builds race on the same DuckDB file."""
    running = [j for j in list_jobs(project_id) if j.get("status") == "running"]
    if running:
        raise RuntimeError(f"a job is already running for this project ({running[0]['id']})")

    job_id = _new_job_id(kind)
    rec_path, prog_path, log_path = _job_paths(project_id, job_id)
    rec_path.parent.mkdir(parents=True, exist_ok=True)
    prog_path.touch()
    argv = list(argv) + ["--progress", str(prog_path)]

    log = open(log_path, "ab", buffering=0)
    try:
        proc = subprocess.Popen(
            argv, cwd=str(ROOT), stdout=log, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            # Own process group: a Ctrl-C in the server's terminal must not take the child with it,
            # and cancelling the child must not signal the server.
            start_new_session=True,
            pass_fds=() if lease_fd is None else (lease_fd,),
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
    finally:
        log.close()

    from dnhacksbio.explorer.runtime import process_identity
    job = {"id": job_id, "kind": kind, "project": project_id, "argv": argv, "pid": proc.pid,
           "process_identity": process_identity(proc.pid),
           "dry": False, "started": time.time(), "status": "running",
           "finished": None, "exit_code": None, "error": None, **(extra or {})}
    projects._write_atomic(rec_path, job)
    return job


def cancel(project_id: str, job_id: str) -> dict:
    job = get_job(project_id, job_id)
    if job.get("status") != "running":
        return job
    pid = job.get("pid")
    from dnhacksbio.explorer.runtime import process_identity
    if pid and job.get("process_identity") and process_identity(pid) != job["process_identity"]:
        pid = None  # never signal a reused PID belonging to another process
    if pid:
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)   # the whole group: the child forks workers
        except (ProcessLookupError, PermissionError, OSError):
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass
    job.update(status="cancelled", finished=time.time(), error="cancelled by user")
    if job.get("run_id"):
        from dnhacksbio.explorer.runtime import Journal
        journal = Journal(ROOT / "data" / "processed", create=False)
        if journal.path.exists():
            for run in journal.snapshot(job["run_id"])["runs"].values():
                if run.get("lifecycle") in {"queued", "running", "waiting"}:
                    journal.append(run["run_id"], run.get("attempt_id", "launch"), "lifecycle",
                                   {"lifecycle": "cancelled", "reason": "Cancelled by user"}, producer="supervisor")
    rec_path, _, _ = _job_paths(project_id, job_id)
    projects._write_atomic(rec_path, job)
    return job


# --- reading (server side) --------------------------------------------------

def _alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except (ProcessLookupError, ValueError, TypeError):
        return False
    except PermissionError:
        return True      # exists, owned by someone else


def _terminal_event(prog_path: Path) -> dict | None:
    """The last `finish`/`fail` event in the stream, if the child wrote one."""
    if not prog_path.is_file():
        return None
    last = None
    try:
        with open(prog_path, "r", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                if '"stage": "finish"' in line or '"stage": "fail"' in line:
                    last = line
    except OSError:
        return None
    if not last:
        return None
    try:
        return json.loads(last)
    except ValueError:
        return None


def _reconcile(job: dict) -> dict:
    """Turn the stored record, the process and the stream into one status.

    The stored record is a claim, not evidence. A crashed child leaves `running` on disk, so a status
    that says running must be backed by a live pid; otherwise the job has died."""
    if job.get("status") != "running":
        return job
    _, prog_path, _ = _job_paths(job["project"], job["id"])
    term = _terminal_event(prog_path)
    if term:
        job["status"] = "done" if term.get("stage") == "finish" else "failed"
        job["finished"] = term.get("ts")
        job["summary"] = term.get("summary")
        if term.get("stage") == "fail":
            job["error"] = term.get("msg")
        projects._write_atomic(_job_paths(job["project"], job["id"])[0], job)
        return job
    if not _alive(job.get("pid")):
        job["status"] = "failed"
        job["finished"] = time.time()
        job["error"] = job.get("error") or "the build process exited without finishing (see the log)"
        projects._write_atomic(_job_paths(job["project"], job["id"])[0], job)
    return job


def get_job(project_id: str, job_id: str) -> dict:
    rec_path, prog_path, log_path = _job_paths(project_id, job_id)
    if not rec_path.is_file():
        raise FileNotFoundError(f"no such job: {job_id}")
    try:
        job = json.loads(rec_path.read_text())
    except (OSError, ValueError) as exc:
        raise FileNotFoundError(f"unreadable job record {job_id}: {exc}")
    job = _reconcile(job)
    job["has_log"] = log_path.is_file() and log_path.stat().st_size > 0
    job["n_events"] = sum(1 for _ in open(prog_path, "rb")) if prog_path.is_file() else 0
    return job


def list_jobs(project_id: str) -> list[dict]:
    d = projects.jobs_dir(project_id)
    if not d.exists():
        return []
    out = []
    for p in sorted(d.glob("*.json")):
        try:
            out.append(get_job(project_id, p.stem))
        except (FileNotFoundError, ValueError):
            continue
    out.sort(key=lambda j: -(j.get("started") or 0))
    return out


def active_job(project_id: str) -> dict | None:
    for j in list_jobs(project_id):
        if j.get("status") == "running":
            return j
    return None


def events(project_id: str, job_id: str, from_line: int = 0) -> list[dict]:
    """The whole progress stream from a line offset (the non-streaming read)."""
    _, prog_path, _ = _job_paths(project_id, job_id)
    if not prog_path.is_file():
        return []
    out = []
    with open(prog_path, "r", encoding="utf-8", errors="ignore") as fh:
        for i, line in enumerate(fh):
            if i < from_line:
                continue
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def log_tail(project_id: str, job_id: str, max_bytes: int = 20000) -> str:
    _, _, log_path = _job_paths(project_id, job_id)
    if not log_path.is_file():
        return ""
    size = log_path.stat().st_size
    with open(log_path, "rb") as fh:
        if size > max_bytes:
            fh.seek(size - max_bytes)
        return fh.read().decode("utf-8", errors="replace")


def tail(project_id: str, job_id: str, from_line: int = 0) -> Iterator[tuple[int, dict]]:
    """Yield (line_no, event) as the child appends them; ends shortly after the job finishes.

    Partial-line safe: a reader can catch the child mid-write, so a line that does not parse is
    rewound and retried rather than dropped."""
    _, prog_path, _ = _job_paths(project_id, job_id)
    lineno = 0
    last_beat = time.time()
    exited_at = None
    with open(prog_path, "a+", encoding="utf-8", errors="ignore") as _ensure:
        _ensure  # noqa: B018 — opening in a+ guarantees the file exists before we tail it
    fh = open(prog_path, "r", encoding="utf-8", errors="ignore")
    try:
        while True:
            pos = fh.tell()
            line = fh.readline()
            if line and line.endswith("\n"):
                lineno += 1
                if lineno > from_line:
                    s = line.strip()
                    if s:
                        try:
                            ev = json.loads(s)
                        except ValueError:
                            continue
                        yield lineno, ev
                        if ev.get("stage") in ("finish", "fail"):
                            return
                continue
            fh.seek(pos)     # incomplete line — wait for the writer to finish it
            try:
                job = get_job(project_id, job_id)
                running = job.get("status") == "running"
            except FileNotFoundError:
                running = False
            if not running:
                if exited_at is None:
                    exited_at = time.time()
                elif time.time() - exited_at > _LINGER_AFTER_EXIT_S:
                    return
            if time.time() - last_beat > _HEARTBEAT_S:
                last_beat = time.time()
                yield lineno, {"_heartbeat": True, "ts": time.time()}
            time.sleep(_POLL_S)
    finally:
        fh.close()
