"""Docker sandbox: where the explorer's own code runs.

The explorer writes Python; this module runs it isolated: one ephemeral container per experiment, datasets
mounted read-only, a writable scratch dir for outputs, hard resource caps, and by default no network, so
agent-written code only sees the local datasets we mount. Experiments run in parallel. Docker is used
directly when the shell is in the docker group, else through `sg docker -c`. Nothing runs as root: the
container runs as the host uid/gid so output files are host-owned.
"""
from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import tempfile
import threading
import time
import selectors
import codecs
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

_HERE = Path(__file__).resolve().parent
DOCKERFILE = _HERE / "sandbox.Dockerfile"
IMAGE = "explorer-sandbox:latest"
# Standalone helper modules (e.g. geoharmonize) mounted read-only at /opt/sandbox_lib in every run and put
# on PYTHONPATH, so experiment code can `import geoharmonize` without importing dnhacksbio. Mounted, not
# baked, so edits need no image rebuild, and only this dir is exposed.
SANDBOX_LIB = _HERE / "sandbox_lib"
SANDBOX_LIB_MNT = "/opt/sandbox_lib"
# Cap on captured stdout/stderr per experiment. Large because full output is fed back to the agent;
# bounded so a runaway print cannot OOM.
_STREAM_CAP = 1_000_000
DATA_DIR = Path(__file__).resolve().parents[3] / "data"   # repo data/, mounted read-only at /data

_native: bool | None = None     # cached: can we reach the docker daemon without sg?


# --- docker command construction (pure / testable) -----------------------------------------------
def _docker_argv(args: list[str], native: bool) -> list[str]:
    """Wrap a docker sub-command. Native -> ['docker', ...]. Stale-group -> ['sg','docker','-c', <str>]
    (sg runs the command under the docker group the user is a member of but the shell hasn't picked up)."""
    if native:
        return ["docker", *args]
    return ["sg", "docker", "-c", shlex.join(["docker", *args])]


def _build_run_argv(name: str, image: str, jobdir: str, data_dir: str | None, timeout: int,
                    memory: str, cpus, network: str, uid: int, gid: int,
                    extra_mounts: list[tuple[str, str, bool]] | None,
                    cache_dir: str | None = None, scratch_dir: str | None = None) -> list[str]:
    """The `docker run ...` argument list, pure so it is unit-testable without Docker. It encodes the
    safety posture: --rm (ephemeral), --network (default none), --memory/--cpus/--pids-limit (caps),
    --user (host-owned outputs, non-root), a read-only data mount, and an in-container `timeout`. The
    container is ephemeral, but `cache_dir` (mounted read-write at /cache) persists across experiments so
    a downloaded dataset is fetched once."""
    nthreads = str(max(1, int(float(cpus))))
    argv = ["run", "--rm", "--name", name,
            "--network", network,
            "--memory", memory, "--cpus", str(cpus), "--pids-limit", "512",
            "--user", f"{uid}:{gid}",
            "-e", f"OMP_NUM_THREADS={nthreads}", "-e", f"OPENBLAS_NUM_THREADS={nthreads}",
            "-e", f"MKL_NUM_THREADS={nthreads}", "-e", f"NUMEXPR_NUM_THREADS={nthreads}",
            # writable HOME so tools that cache under $HOME (matplotlib, numba) work as non-root
            "-e", "HOME=/tmp", "-e", "MPLCONFIGDIR=/tmp", "-e", "PYTHONDONTWRITEBYTECODE=1",
            # helper modules in /opt/sandbox_lib (mounted below) importable without any sys.path fiddling
            "-e", f"PYTHONPATH={SANDBOX_LIB_MNT}", "-e", "PYTHONUNBUFFERED=1",
            "-e", "DN_ARTIFACT_DIR=/work/output",
            "-v", f"{jobdir}:/work", "-w", "/work"]
    if data_dir:
        argv += ["-v", f"{data_dir}:/data:ro"]
    if cache_dir:
        argv += ["-v", f"{cache_dir}:/cache"]          # read-write, persistent across experiments
    if scratch_dir:
        # Per-branch writable space. /cache is shared by every branch in the fork tree, right for
        # accession-keyed downloads and wrong for anything derived, where siblings would overwrite each
        # other's files under the same names.
        argv += ["-v", f"{scratch_dir}:/scratch"]
    for host, cont, ro in (extra_mounts or []):
        argv += ["-v", f"{host}:{cont}" + (":ro" if ro else "")]
    argv += [image] + (["timeout", "--signal=KILL", str(timeout)] if timeout is not None else []) + ["python", "/work/code.py"]
    return argv


# --- daemon detection ----------------------------------------------------------------------------
def _detect_native() -> bool:
    try:
        p = subprocess.run(["docker", "version", "--format", "{{.Server.Version}}"],
                           capture_output=True, text=True, timeout=15)
        return p.returncode == 0 and bool(p.stdout.strip())
    except Exception:
        return False


def _is_native() -> bool:
    global _native
    if _native is None:
        _native = _detect_native()
    return _native


def docker_ok() -> bool:
    """True if docker is reachable either natively or via sg."""
    if _is_native():
        return True
    try:
        p = subprocess.run(_docker_argv(["version", "--format", "{{.Server.Version}}"], False),
                           capture_output=True, text=True, timeout=15)
        return p.returncode == 0 and bool(p.stdout.strip())
    except Exception:
        return False


def _run(args: list[str], timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(_docker_argv(args, _is_native()), capture_output=True, text=True, timeout=timeout)


def _kill(name: str) -> None:
    try:
        subprocess.run(_docker_argv(["kill", name], _is_native()), capture_output=True, timeout=20)
    except Exception:
        pass


# --- image build ---------------------------------------------------------------------------------
def image_exists(image: str = IMAGE) -> bool:
    try:
        p = _run(["images", "-q", image], timeout=30)
        return bool(p.stdout.strip())
    except Exception:
        return False


def build_image(image: str = IMAGE, dockerfile: Path | str = DOCKERFILE,
                timeout: int = 1800) -> subprocess.CompletedProcess:
    """Build the sandbox image. Context = the explorer dir (only the Dockerfile is used; no repo files
    are copied in)."""
    return _run(["build", "-f", str(dockerfile), "-t", image, str(_HERE)], timeout=timeout)


def ensure_image(image: str = IMAGE, dockerfile: Path | str = DOCKERFILE) -> bool:
    if image_exists(image):
        return True
    r = build_image(image, dockerfile)
    return r.returncode == 0


# --- run -----------------------------------------------------------------------------------------
@dataclass
class RunResult:
    ok: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_s: float
    timed_out: bool
    artifacts: list[dict] = field(default_factory=list)


def stream_process(cmd, timeout, *, on_output=None, cancel=None, stop=None):
    """Drain both pipes incrementally with bounded retained tails and explicit offsets."""
    tails = {"stdout": "", "stderr": ""}
    offsets = {"stdout": 0, "stderr": 0}
    sent = {"stdout": 0, "stderr": 0}
    decoder = {s: codecs.getincrementaldecoder("utf-8")("replace") for s in tails}
    timed_out = False
    stopped = False
    start = time.monotonic()
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as proc:
        try:
            with selectors.DefaultSelector() as selector:
                for name in tails:
                    selector.register(getattr(proc, name), selectors.EVENT_READ, name)
                while selector.get_map():
                    if not stopped and ((cancel and cancel.is_set()) or (timeout is not None and time.monotonic() - start > timeout)):
                        stopped = True
                        timed_out = not (cancel and cancel.is_set())
                        if stop:
                            stop()
                        proc.kill()
                    for key, _ in selector.select(0.1):
                        raw = os.read(key.fileobj.fileno(), 4096)
                        name = key.data
                        chunk = decoder[name].decode(raw, final=not raw)
                        if not raw:
                            selector.unregister(key.fileobj)
                        tails[name] = (tails[name] + chunk)[-_STREAM_CAP:]
                        if on_output and raw and sent[name] < _STREAM_CAP:
                            on_output({"stream": name, "offset": offsets[name], "text": chunk})
                            sent[name] += len(raw)
                        offsets[name] += len(raw)
                proc.wait(timeout=5)
        except BaseException:
            if stop:
                stop()
            proc.kill()
            proc.wait()
            raise
    for name in tails:
        if offsets[name] > _STREAM_CAP:
            tails[name] = f"[Earlier output truncated; {offsets[name]} bytes produced]\n" + tails[name]
            if on_output:
                on_output({"stream": name, "offset": offsets[name], "truncated": True,
                           "text": "[Live output capped; final retained tail is in recorded output]"})
    return proc.returncode, tails["stdout"], tails["stderr"], timed_out


def run_code(code: str, *, image: str = IMAGE, timeout: int | None = 600, memory: str = "8g", cpus=4,
             network: str = "none", data_dir: Path | str | None = DATA_DIR,
             extra_mounts: list[tuple[str, str, bool]] | None = None,
             cache_dir: Path | str | None = None, job_base: str | None = None,
             scratch_dir: Path | str | None = None, progress=None, journal=None, cancel=None) -> RunResult:
    """Run `code` in a fresh container and return its outcome. `network='none'` (default) isolates it;
    pass 'bridge' only for an experiment that must fetch. Defaults (600 s, 8g, 4 cpu) let a dataset
    download plus analysis fit.

    Two persistent mounts:
      - `cache_dir` -> /cache      shared by every branch in the fork tree; raw downloads only, which are
                                   keyed by accession and identical whoever fetched them.
      - `scratch_dir` -> /scratch  private to one branch; anything the experiment derives."""
    jobdir = Path(tempfile.mkdtemp(prefix="explorer-job-", dir=job_base))
    try:
        (jobdir / "code.py").write_text(code)
        (jobdir / "output").mkdir()
        name = "explorer-" + uuid4().hex[:12]
        # Always expose the standalone helper library (read-only) so `import geoharmonize` works.
        extra_mounts = list(extra_mounts or [])
        if SANDBOX_LIB.is_dir() and not any(c == SANDBOX_LIB_MNT for _, c, _ in extra_mounts):
            extra_mounts.append((str(SANDBOX_LIB.resolve()), SANDBOX_LIB_MNT, True))
        dd = str(Path(data_dir)) if data_dir and Path(data_dir).exists() else None

        def _host_dir(p) -> str | None:
            # docker -v needs an absolute host path; a relative one is read as a named volume and rejected
            if not p:
                return None
            rp = Path(p).resolve()
            rp.mkdir(parents=True, exist_ok=True)                # host-owned, so the non-root container can write
            return str(rp)

        argv = _build_run_argv(name, image, str(jobdir), dd, timeout, memory, cpus, network,
                               os.getuid(), os.getgid(), extra_mounts,
                               cache_dir=_host_dir(cache_dir), scratch_dir=_host_dir(scratch_dir))
        cmd = _docker_argv(argv, _is_native())
        t0 = time.monotonic()
        timed_out = False
        if progress:
            progress("experiment.started", {"status": "running"})
        rc, out, err, timed_out = stream_process(cmd, None if timeout is None else timeout + 30, cancel=cancel, stop=lambda: _kill(name),
                    on_output=(lambda payload: progress("experiment.output", payload)) if progress else None)
        dur = round(time.monotonic() - t0, 2)
        if timeout is not None and (rc == 124 or (rc == 137 and dur >= timeout)):  # early 137 may be OOM/cancel, not timeout
            timed_out = True
        artifacts = []
        if journal:
            from .artifacts import collect
            artifacts = collect(jobdir / "output", journal)
        return RunResult(ok=(rc == 0 and not timed_out), exit_code=rc, stdout=out or "",
                         stderr=err or "", duration_s=dur, timed_out=timed_out,
                         artifacts=artifacts)
    finally:
        shutil.rmtree(jobdir, ignore_errors=True)


MAX_TREE_CONTAINERS = 6     # tree-wide ceiling on concurrent containers (~8g each)


class SandboxPool:
    """One tree-wide allowance of concurrent containers, shared by reference across every branch (the
    same shape as `ForkBudget` for branches). It is a queue, not a
    quota: every experiment still runs, fewer at once. A branch never holds a slot while awaiting
    something that needs one, so it cannot deadlock."""

    def __init__(self, total: int = MAX_TREE_CONTAINERS):
        self.total = max(1, int(total))
        self._sem = threading.BoundedSemaphore(self.total)

    @contextmanager
    def slot(self):
        self._sem.acquire()
        try:
            yield
        finally:
            self._sem.release()


def run_many(codes: list[str], *, max_parallel: int = 4, pool: "SandboxPool | None" = None,
             progress=None, **kw) -> list[RunResult]:
    """Run several experiments concurrently (the explorer's divergent fan-out). Order preserved.

    Blocking; call it off the event loop (`asyncio.to_thread`). `max_parallel` bounds this branch's
    fan-out; `pool`, when supplied, also bounds the whole fork tree."""
    from concurrent.futures import ThreadPoolExecutor
    if not codes:
        return []

    def one(item) -> RunResult:
        i, c = item
        args = dict(kw, progress=(lambda kind, payload: progress(i, kind, payload)) if progress else None)
        if kw.get("cancel") and kw["cancel"].is_set():
            return RunResult(False, -9, "", "Cancelled before execution", 0, False)
        if pool is None:
            return run_code(c, **args)
        with pool.slot():
            if kw.get("cancel") and kw["cancel"].is_set():
                return RunResult(False, -9, "", "Cancelled before execution", 0, False)
            return run_code(c, **args)

    with ThreadPoolExecutor(max_workers=max(1, min(max_parallel, len(codes)))) as ex:
        return list(ex.map(one, enumerate(codes)))
