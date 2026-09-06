"""Data-access layer for the engine web UI.

Everything the frontend shows is derived here from the engine's on-disk state: the per-step reasoning
traces (data/processed/reasoning_<run_id>.jsonl, append-only, tailed for the live view) and the DuckDB
files (KG claims/evidence, exploration log, engine_tests verdicts). DuckDB takes a single-writer lock,
so a run that is actively writing its DB blocks a read-only open; `_connect_ro` falls back to a snapshot
copy. Stdlib + duckdb only.
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import shutil
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Iterator

import duckdb

from dnhacksbio.explorer import lineage as LIN

from . import projects as projects_mod

# --- Locations -------------------------------------------------------------

# This file lives at src/dnhacksbio/webui/data.py → project root is parents[3].
ROOT = Path(__file__).resolve().parents[3]
PROCESSED = ROOT / "data" / "processed"
CORPORA = ROOT / "data" / "corpora"

# Where we drop lock-safe copies of DuckDB files that are open for writing, and how coarsely we
# re-snapshot them (a copy can be large, so this bounds the cost of watching a live run).
_SNAPSHOT_BUCKET_S = 5
_CACHE = Path(tempfile.gettempdir()) / "diverge_webui_cache"

# `~` is the lineage separator in a forked branch's run_id (root~1~3~0, see explorer/lineage.py), so it
# must be allowed or every forked branch trace is unreachable (skipped here, 400 at the server).
RUN_ID_RE = re.compile(r"^[A-Za-z0-9._~-]+$")

# Smoke/test/scratch traces shouldn't clutter a demo console. Hidden by default;
# `list_runs(include_all=True)` (server: /api/runs?all=1) shows everything.
SKIP_RUN_RE = re.compile(r"(test|smoke|demo|e2e|probe|dummy|sample|scratch|tmp)", re.I)

# A run is treated as "active" if its trace file changed within this window. Sized to the slowest
# legitimate step: an experiment can sit in the sandbox up to its 600s timeout without writing anything.
ACTIVE_WINDOW_S = 660


# --- Action → phase taxonomy ----------------------------------------------
# The explorer's concrete actions fold into a few display families so the UI can colour and group
# them. The family drives the colour; the raw action is still shown verbatim.
_ACTION_PHASE: dict[str, tuple[str, str]] = {
    # (phase label, family)  — family maps to a CSS state color
    "search_kg":       ("Retrieve", "retrieve"),
    "neighbors":       ("Retrieve", "retrieve"),   # structural KG reads
    "subgraph":        ("Retrieve", "retrieve"),
    "path":            ("Retrieve", "retrieve"),
    "recall":          ("Retrieve", "retrieve"),
    "search_papers":   ("Retrieve", "retrieve"),
    "fetch_papers":    ("Retrieve", "retrieve"),
    "read_paper":      ("Retrieve", "retrieve"),
    "find_datasets":   ("Retrieve", "retrieve"),
    "search_skills":   ("Retrieve", "retrieve"),
    "get_skill":       ("Retrieve", "retrieve"),
    "run_experiments": ("Execute",  "execute"),
    "submit":          ("Falsify",  "falsify"),
    "fork":            ("Fork",     "fork"),      # recursive beam divergence
    "reflect":         ("Generate", "generate"),
    "log":             ("Note",     "note"),
    "note":            ("Note",     "note"),
    "done":            ("Grade",    "grade"),
}


def phase_for(action: str) -> tuple[str, str]:
    return _ACTION_PHASE.get((action or "").strip(), ("Act", "note"))


# --- DuckDB helpers --------------------------------------------------------

def _connect_ro(path: Path) -> duckdb.DuckDBPyConnection:
    """Open a DuckDB file read-only, falling back to a copy if it is locked.

    Raises FileNotFoundError if the path does not exist.
    """
    if not path.exists():
        raise FileNotFoundError(str(path))
    try:
        return duckdb.connect(str(path), read_only=True)
    except (duckdb.IOException, duckdb.Error):
        pass    # held read-write by a live run — fall through to a snapshot copy

    # While DuckDB holds the lock, writes land in the `.wal` sidecar and the main file's mtime does not
    # move, so key the snapshot on the WAL (time-bucketed, to bound how often we copy) and copy the WAL
    # with it.
    wal = path.with_name(path.name + ".wal")
    if wal.exists():
        ws = wal.stat()
        key = f"{int(ws.st_mtime // _SNAPSHOT_BUCKET_S)}-{ws.st_size}"
    else:
        key = str(int(path.stat().st_mtime))
    _CACHE.mkdir(parents=True, exist_ok=True)
    identity = hashlib.sha256(str(path.resolve()).encode()).hexdigest()[:16]
    prefix = f"{path.stem}.{identity}."
    dst = _CACHE / f"{prefix}{key}.duckdb"
    if not dst.exists():
        shutil.copy2(path, dst)
        if wal.exists():
            shutil.copy2(wal, dst.with_name(dst.name + ".wal"))
        for old_copy in _CACHE.glob(f"{prefix}*"):      # keep only the newest snapshot per database
            if not old_copy.name.startswith(dst.name):
                try:
                    old_copy.unlink()
                except OSError:
                    pass
    # Opened read-write: replaying the WAL requires write access, and this is our own throwaway copy.
    return duckdb.connect(str(dst))


def _views(con: duckdb.DuckDBPyConnection) -> set[str]:
    return {v for (v,) in con.execute(
        "select view_name from duckdb_views() where not internal").fetchall()}


def _tables(con: duckdb.DuckDBPyConnection) -> set[str]:
    return {
        t
        for (t,) in con.execute(
            "select table_name from information_schema.tables "
            "where table_schema='main'"
        ).fetchall()
    }


def _rows(con: duckdb.DuckDBPyConnection, sql: str, params: list | None = None) -> list[dict]:
    cur = con.execute(sql, params or [])
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


# --- Run discovery + parsing ----------------------------------------------

def _trace_path(run_id: str) -> Path:
    return PROCESSED / f"reasoning_{run_id}.jsonl"


def _read_last_line(path: Path) -> dict | None:
    """Cheaply read the final JSON object of a possibly-large JSONL file."""
    try:
        with open(path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            end = fh.tell()
            block = min(end, 8192)
            fh.seek(end - block)
            tail = fh.read().splitlines()
        for raw in reversed(tail):
            raw = raw.strip()
            if raw:
                return json.loads(raw)
    except (OSError, ValueError):
        return None
    return None


def _count_lines(path: Path) -> int:
    n = 0
    with open(path, "rb") as fh:
        for _ in fh:
            n += 1
    return n


def _iter_fork_records(path: Path) -> Iterator[dict]:
    """Yield the structured `fork` beam records from a trace (one per fork step). Cheap: a fork line
    always carries the substring `"fork":`, so we JSON-parse only those lines, not the whole file."""
    try:
        with open(path, "rb") as fh:
            for raw in fh:
                if b'"fork":' not in raw:
                    continue
                try:
                    obj = json.loads(raw)
                except ValueError:
                    continue
                fk = obj.get("fork")
                if isinstance(fk, dict) and fk.get("children"):
                    yield fk
    except OSError:
        return


def _beam_badge(run_id: str) -> dict | None:
    """The beam badge for one branch, read from its parent's trace only (cheaper than scanning every trace
    via _fork_index). None for a root run or if the parent recorded no fork metadata for it."""
    parent = LIN.parent(run_id)
    if not parent:
        return None
    for fk in _iter_fork_records(_trace_path(parent)):
        for c in fk.get("children", []):
            if c.get("run_id") == run_id:
                return {"parent": parent, "adversarial": bool(c.get("adversarial")),
                        "kept": bool(c.get("kept")), "rank": c.get("rank"),
                        "angle": c.get("angle", ""), "reason": c.get("reason", ""),
                        "n_submitted": c.get("n_submitted", 0)}
    return None


def _fork_index() -> dict[str, dict]:
    """Map every forked branch run_id -> the badge its PARENT recorded for it (adversarial, kept/pruned,
    promise rank, angle). Built by scanning all traces' fork records once. A child appears in exactly one
    parent's fork record, so this is the authoritative per-branch beam outcome."""
    idx: dict[str, dict] = {}
    for p in glob.glob(str(PROCESSED / "reasoning_*.jsonl")):
        for fk in _iter_fork_records(Path(p)):
            parent = fk.get("parent")
            for c in fk["children"]:
                rid = c.get("run_id")
                if not rid:
                    continue
                idx[rid] = {
                    "parent": parent,
                    "adversarial": bool(c.get("adversarial")),
                    "kept": bool(c.get("kept")),          # deepened (True) vs pruned (False)
                    "rank": c.get("rank"),
                    "angle": c.get("angle", ""),
                    "reason": c.get("reason", ""),
                    "n_submitted": c.get("n_submitted", 0),
                }
    return idx


def list_runs(include_all: bool = False, project: str | None = None) -> list[dict]:
    """One summary row per reasoning trace on disk, newest activity first.

    Each row is annotated with its lineage (root/depth/parent) and — for a forked branch — the beam
    badge its parent recorded (adversarial / deepened-vs-pruned / promise rank / angle). Smoke/test
    traces are hidden unless include_all is set.

    `project` restricts the list to runs against that project's corpus. An investigation belongs to
    the graph it reasoned over, so switching project switches which runs the console shows; another
    analysis's runs never appear in the investigation picker.
    """
    out = []
    now = time.time()
    forks = _fork_index()
    for p in glob.glob(str(PROCESSED / "reasoning_*.jsonl")):
        path = Path(p)
        run_id = path.stem[len("reasoning_"):]
        if not RUN_ID_RE.match(run_id):
            continue
        if not include_all and SKIP_RUN_RE.search(run_id):
            continue
        st = path.stat()
        last = _read_last_line(path) or {}
        # Count records by line.
        steps = _count_lines(path)
        depth = LIN.depth(run_id)
        row = {
            "run_id": run_id,
            "root": LIN.root(run_id),
            "depth": depth,
            "parent": LIN.parent(run_id),
            "is_branch": depth > 0,
            "steps": steps,
            "last_action": last.get("action", ""),
            "updated_at": st.st_mtime,
            # `done` is the agent's terminal action; the clock only decides for runs that have not said it.
            "active": (now - st.st_mtime) < ACTIVE_WINDOW_S and last.get("action") != "done",
            "size": st.st_size,
            "beam": forks.get(run_id),   # the parent's badge for this branch (None for a root/unforked run)
        }
        out.append(row)
    from dnhacksbio.explorer.runtime import Journal
    journal = Journal(PROCESSED, create=False)
    by_run = {r["run_id"]: r for r in out}
    snapshots = {}
    for m in journal.manifests():
        rid = m["run_id"]
        if not include_all and SKIP_RUN_RE.search(rid):
            continue
        root = m["investigation_id"]
        if root not in snapshots:
            snapshots[root] = journal.snapshot(root)
        live = snapshots[root]["runs"].get(rid, {})
        row = by_run.setdefault(rid, {"run_id": rid, "root": root, "depth": LIN.depth(rid),
                                     "parent": LIN.parent(rid), "is_branch": bool(LIN.parent(rid)),
                                     "steps": 0, "last_action": "", "size": 0})
        row.update(runtime=True, lifecycle=live.get("lifecycle", "queued"),
                   active=live.get("lifecycle") in {"running", "waiting"},
                   updated_at=live.get("updated_at", m["created_at"]), goal=m["original_question"],
                   project=m.get("project_id"), objective=m["branch_objective"])
    out = list(by_run.values())
    out.sort(key=lambda r: r["updated_at"], reverse=True)
    if project:
        out = [r for r in out if r.get("project") == project or (not r.get("runtime") and project_of_run(r["run_id"]) == project)]
    for r in out:
        if not r.get("runtime"):
            r["project"] = project_of_run(r["run_id"])
    return out


def investigations(include_all: bool = False, project: str | None = None) -> list[dict]:
    """Group the flat run list into investigation TREES — one entry per root run_id — newest-active
    first. The frontend renders each tree from the per-run `parent` pointers; here we just cluster and
    roll up. A branch trace with no visible root (e.g. its root was filtered) still forms its own group
    under that root id so nothing is dropped."""
    runs = list_runs(include_all=include_all, project=project)
    trees: dict[str, dict] = {}
    for r in runs:
        root = r["root"]
        t = trees.setdefault(root, {"root": root, "runs": [], "updated_at": 0.0, "active": False})
        t["runs"].append(r)
        t["updated_at"] = max(t["updated_at"], r["updated_at"])
        t["active"] = t["active"] or r["active"]
    out = []
    for t in trees.values():
        t["runs"].sort(key=lambda r: (r["depth"], r["run_id"]))     # root first, then branches by lineage
        root_row = next((r for r in t["runs"] if r["depth"] == 0), None)
        t["n_runs"] = len(t["runs"])
        t["n_branches"] = sum(1 for r in t["runs"] if r["is_branch"])
        t["has_forks"] = t["n_branches"] > 0
        t["root_run"] = root_row
        t["last_action"] = (root_row or t["runs"][0]).get("last_action", "")
        # The question lives on the launch job, not on the corpus definition.
        # Surface it so the UI need not use an opaque filesystem run id as its title.
        t["goal"] = (root_row or {}).get("goal", "")
        t["runtime"] = bool((root_row or {}).get("runtime"))
        job_ref = _job_for_run(t["root"])
        if job_ref and not t["goal"]:
            from . import jobs as _jobs
            try:
                t["goal"] = _jobs.get_job(*job_ref).get("goal", "")
            except (FileNotFoundError, ValueError):
                pass
        out.append(t)
    out.sort(key=lambda t: t["updated_at"], reverse=True)
    return out


def _normalize_step(obj: dict) -> dict:
    action = obj.get("action", "")
    phase, family = phase_for(action)
    args = obj.get("args", {})
    if not isinstance(args, (dict, list)):
        args = {"value": args}
    return {
        "step": obj.get("step"),
        "action": action,
        "phase": phase,
        "family": family,
        "ts": obj.get("ts"),
        "dt_s": obj.get("dt_s"),
        # `reasoning` = the model's self-reported thought; `thinking` = raw extended-thinking blocks.
        "reasoning": obj.get("reasoning", ""),
        "thinking": obj.get("thinking", ""),
        "args": args,
        "observation": obj.get("observation", ""),
        # structured beam tree for a `fork` step (explorer._act_fork); None on every non-fork step.
        "fork": obj.get("fork"),
    }


def parse_run(run_id: str) -> dict:
    """Full parsed run: every step plus derived tallies and any DB verdicts."""
    path = _trace_path(run_id)
    if not path.exists():
        raise FileNotFoundError(run_id)

    steps: list[dict] = []
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                steps.append(_normalize_step(json.loads(raw)))
            except ValueError:
                continue

    st = path.stat()
    tallies = _tallies(steps)
    tests = _run_tests(run_id)

    return {
        "run_id": run_id,
        # lineage of this run within its investigation tree (so the detail view can show where a branch
        # sits and link up to its parent). `beam` = the parent's badge for this branch (None for a root).
        "root": LIN.root(run_id),
        "depth": LIN.depth(run_id),
        "parent": LIN.parent(run_id),
        "beam": _beam_badge(run_id),
        # Same rule as list_runs: a trace whose last action is `done` has stopped, whatever its mtime says.
        "last_action": (steps[-1].get("action") if steps else ""),
        "active": ((time.time() - st.st_mtime) < ACTIVE_WINDOW_S
                   and (steps[-1].get("action") if steps else "") != "done"),
        "updated_at": st.st_mtime,
        "n_steps": len(steps),
        # Complete lines now on disk: the offset the live stream resumes from (matches tail_run).
        "resume_line": _count_complete_lines(path),
        "steps": steps,
        "tallies": tallies,
        "tests": tests,
    }


def _tree_pred(run_id: str, col: str = "run_id") -> tuple[str, list]:
    """Every run in the investigation tree `run_id` belongs to, so opening any run in a fork tree shows the
    whole tree's verdicts, each attributable by run_id. `lineage` owns the predicate; it is also what the
    verify queue drains on, so the two cannot drift."""
    return LIN.tree_sql(run_id, col)


def _db_for_run(run_id: str) -> Path | None:
    """Resolve the DuckDB that holds this run's rows. The engine writes engine_tests into the
    corpus graph it was pointed at, and forked children share their parent's DB, so probe every graph
    and return the first that contains a row for this run's tree."""
    seen: set[str] = set()
    candidates = [*kg_sources().values(),
                  *sorted(p for p in CORPORA.glob("*/*.duckdb") if ".bak" not in p.name)]
    frag, params = _tree_pred(run_id)
    for db in candidates:
        key = str(db)
        if key in seen or not db.exists():
            continue
        seen.add(key)
        try:
            con = _connect_ro(db)
        except (FileNotFoundError, duckdb.Error):
            continue
        try:
            tabs = _tables(con)
            # Probe every table a run writes: a live run has queued submissions and exploration entries
            # long before its first verdict exists.
            for tab in ("engine_tests", "verification_queue", "exploration"):
                if tab not in tabs:
                    continue
                n = con.execute(f"select count(*) from {tab} where {frag}", params).fetchone()[0]
                if n:
                    return db
        except duckdb.Error:
            continue
        finally:
            con.close()
    return None


def _count_complete_lines(path: Path) -> int:
    n = 0
    with open(path, "rb") as fh:
        for raw in fh:
            if raw.endswith(b"\n"):
                n += 1
    return n


def _tallies(steps: list[dict]) -> dict:
    """Counts the UI surfaces as run vitals: phase mix + experiment/submit load."""
    by_family: dict[str, int] = {}
    by_action: dict[str, int] = {}
    durations = [s["dt_s"] for s in steps if isinstance(s.get("dt_s"), (int, float))]
    stamps = [s["ts"] for s in steps if isinstance(s.get("ts"), (int, float))]
    for s in steps:
        by_family[s["family"]] = by_family.get(s["family"], 0) + 1
        by_action[s["action"]] = by_action.get(s["action"], 0) + 1
    return {
        "steps": len(steps),
        "experiments": by_action.get("run_experiments", 0),
        "submissions": by_action.get("submit", 0),
        "retrievals": by_family.get("retrieve", 0),
        # Timing rollup — present only when steps carry durations.
        "has_timing": bool(durations),
        "busy_s": round(sum(durations), 1) if durations else None,   # summed step time
        "wall_s": round(max(stamps) - min(stamps), 1) if len(stamps) > 1 else None,  # first→last span
        "slowest_s": round(max(durations), 1) if durations else None,
        "by_family": by_family,
        "by_action": by_action,
    }


def _run_tests(run_id: str) -> list[dict]:
    """engine_tests verdicts for a run's whole INVESTIGATION TREE. Best-effort. Resolves the DB where the
    verdicts actually live (the shared corpus KG, not a per-run file) and filters to the tree so a fork's
    branches are all shown. Each row carries its run_id so the UI attributes a verdict to the branch that
    produced it."""
    db = _db_for_run(run_id)
    if db is None:
        return []
    try:
        con = _connect_ro(db)
    except (FileNotFoundError, duckdb.Error):
        return []
    try:
        if "engine_tests" not in _tables(con):
            return []
        frag, params = _tree_pred(run_id)
        return _rows(
            con,
            "select run_id, subject, object, method, expected_sign, observed_sign, "
            "effect, effect_size, p_null, status, kill_reason, "
            f"verdict_note, hypothesis, human_review, novelty_verdict "
            f"from engine_tests where {frag} order by test_id",
            params,
        )
    finally:
        con.close()


def _job_for_run(run_id: str) -> tuple[str, str] | None:
    """(project_id, job_id) of the console job that launched this run's investigation, if any. None
    when the project cannot be resolved (yet) or no job record names this run — e.g. a run started
    outside the console — in which case the caller has no job status to check against."""
    from . import jobs as _jobs
    project = project_of_run(run_id)
    if not project:
        return None
    root = LIN.root(run_id)
    for j in _jobs.list_jobs(project):
        if j.get("run_id") == root:
            return project, j.get("id")
    return None


def tail_run(run_id: str, from_line: int = 0) -> Iterator[tuple[int, dict]]:
    """Yield (line_number, step) for lines after `from_line` as they are appended.

    Line-number keyed (not step-field keyed) so it is robust to traces whose
    `step` counter resets. Yields already-present lines first, then follows the
    file. The SSE handler drives it, tags each event with the line number, and
    resumes from Last-Event-ID on reconnect. Heartbeats keep the socket alive
    and carry liveness; they reuse the last line number as their id.

    Ends once the console job that launched this run is no longer `running` (same check
    `jobs.tail` uses), so a finished investigation's stream terminates rather than heartbeating
    forever. A run with no matching job record (started outside the console) has nothing to check
    against, so it keeps following the trace file indefinitely.
    """
    path = _trace_path(run_id)
    if not path.exists():
        return
    pos = 0
    lineno = 0
    job_ref = _job_for_run(run_id)
    while True:
        try:
            size = path.stat().st_size
        except OSError:
            return
        if size > pos:
            # Binary readline + manual offset: text-mode iteration disables
            # tell(), and readline() lets us detect an incomplete final line.
            with open(path, "rb") as fh:
                fh.seek(pos)
                while True:
                    raw = fh.readline()
                    if not raw:
                        break
                    if not raw.endswith(b"\n"):
                        # Partial final line — leave pos before it, retry later.
                        break
                    pos += len(raw)
                    lineno += 1
                    if lineno <= from_line:
                        continue
                    s = raw.strip()
                    if not s:
                        continue
                    try:
                        obj = json.loads(s.decode("utf-8"))
                    except (ValueError, UnicodeDecodeError):
                        continue
                    yield lineno, _normalize_step(obj)
        active = (time.time() - path.stat().st_mtime) < ACTIVE_WINDOW_S
        yield lineno, {"_heartbeat": True, "active": active}
        if job_ref is not None:
            from . import jobs as _jobs
            try:
                status = _jobs.get_job(*job_ref).get("status")
            except FileNotFoundError:
                status = None
            if status is not None and status != "running":
                return
        time.sleep(1.0)


# --- Knowledge graph -------------------------------------------------------

# Whitelist of KG databases the UI may open, by short key. The key is also the PROJECT id: a graph
# built by the console lives at data/projects/<id>/kg.duckdb, and a graph placed under data/corpora/
# by a script is adopted under its directory name (webui/projects.py `_adopted`).
def _projects_dir() -> Path:
    """Derived from PROCESSED rather than ROOT so a fixture that redirects PROCESSED also redirects
    the projects directory."""
    return PROCESSED.parent / "projects"


def kg_sources() -> dict[str, Path]:
    srcs: dict[str, Path] = {}
    for p in sorted(_projects_dir().glob("*/kg.duckdb")):
        srcs[p.parent.name] = p
    for p in sorted(CORPORA.glob("*/*_kg.duckdb")):
        srcs.setdefault(p.parent.name, p)     # data/corpora/<name>/<name>_kg.duckdb -> key <name>
    return srcs


def _facet(con: duckdb.DuckDBPyConnection, expr: str, sql_from: str = "claim_edges") -> list[dict]:
    """Counts of one closed-vocabulary column over the whole collection, most common first."""
    try:
        rows = con.execute(
            f"select {expr} as k, count(*) as n from {sql_from} "
            f"where {expr} is not null and cast({expr} as varchar) <> '' group by 1 order by 2 desc, 1"
        ).fetchall()
    except duckdb.Error:
        return []
    return [{"value": k if not isinstance(k, (int, float)) else int(k), "n": int(n)} for k, n in rows]


def _kg_summary(con: duckdb.DuckDBPyConnection, total_claims: int) -> dict:
    """The collection in numbers: what is stored, so the view can say what it is a subset of."""
    tabs = _tables(con)
    one = lambda sql: int(con.execute(sql).fetchone()[0])          # noqa: E731
    out = {"claims": int(total_claims), "entities": 0, "evidence": None, "papers": None,
           "papers_full_text": None, "experiments": None, "deferrals": None, "tests": None,
           "vectors": None}
    try:
        out["entities"] = one("select count(*) from (select subject_id e from claim_edges "
                              "union select object_id from claim_edges)")
        if "evidence" in tabs:
            out["evidence"] = one("select count(*) from evidence")
        if "papers" in tabs:
            out["papers"] = one("select count(*) from papers")
            try:
                out["papers_full_text"] = one("select count(*) from papers where is_full_text")
            except duckdb.Error:
                pass
        if "experiments" in tabs:
            out["experiments"] = one("select count(*) from experiments")
        if "deferrals" in tabs:
            out["deferrals"] = one("select count(*) from deferrals")
        if "engine_tests" in tabs:
            out["tests"] = one("select count(*) from engine_tests")
        if "claim_vectors" in tabs:
            out["vectors"] = one("select count(*) from claim_vectors")
    except duckdb.Error:
        pass
    return out


def _tested_overlay(con: duckdb.DuckDBPyConnection, claim_ids: list[str]) -> dict[str, dict]:
    """How the engine has treated each shown claim: counts of its engine_tests rows by outcome.

    `candidate` = passed the verifier's soundness checks and awaits a person; `validated` /
    `rejected` = the person's decision; `killed` = failed a soundness check. None of these is a
    literature fact, which is why they travel separately from the claim row."""
    if not claim_ids or "engine_tests" not in _tables(con):
        return {}
    marks = ",".join("?" * len(claim_ids))
    rows = con.execute(
        f"""select kg_claim_id, count(*) as n,
                   count(*) filter (where status = 'candidate' and coalesce(human_review, '') = '') as candidate,
                   count(*) filter (where human_review = 'validated') as validated,
                   count(*) filter (where human_review = 'rejected') as rejected,
                   count(*) filter (where status <> 'candidate') as killed
            from engine_tests where kg_claim_id in ({marks}) group by 1""",
        claim_ids,
    ).fetchall()
    return {r[0]: {"n": int(r[1]), "candidate": int(r[2]), "validated": int(r[3]),
                   "rejected": int(r[4]), "killed": int(r[5])} for r in rows}


_KG_STATUSES = ("disputed", "established", "reported")
_KG_RELATION_CLASSES = ("causal", "correlational", "temporal", "predictive", "unclassed")


def kg_graph(source: str, limit: int = 220, status: str | None = None, q: str | None = None,
             polarity: str | int | None = None, kind: str | None = None,
             relation_class: str | None = None, predicate: str | None = None) -> dict:
    """Nodes (entities) + edges (claims) for the Evidence view.

    Disputed claims come first, then the most-supported, so a capped view stays legible rather than a
    hairball. Every filter but `q` is an equality test on a closed vocabulary (unknown values are
    ignored, never guessed); `q` is a case-insensitive substring match over labels, identifiers,
    predicate, aspect and mechanism, run in the database so search covers the whole collection and
    not just the rows already loaded. Facets and the summary describe the unfiltered collection, the
    `matched` count describes the filter, and `shown` the rows returned.
    """
    srcs = kg_sources()
    if source not in srcs:
        raise KeyError(source)
    path = srcs[source]
    con = _connect_ro(path)
    try:
        where: list[str] = []
        params: list = []
        if status in _KG_STATUSES:
            where.append("status = ?")
            params.append(status)
        if str(polarity) in ("1", "0", "-1"):
            where.append("polarity = ?")
            params.append(int(polarity))
        if kind:
            where.append("(subject_kind = ? or object_kind = ?)")
            params += [kind, kind]
        if relation_class in _KG_RELATION_CLASSES:
            where.append("coalesce(relation_class, '') = ?")
            params.append("" if relation_class == "unclassed" else relation_class)
        if predicate:
            where.append("predicate = ?")
            params.append(predicate)
        q = (q or "").strip().lower()
        if q:
            like = f"%{q}%"
            cols = ("subject_label", "object_label", "predicate", "coalesce(mechanism, '')",
                    "coalesce(object_function, '')", "coalesce(subject_curie, '')",
                    "coalesce(object_curie, '')")
            where.append("(" + " or ".join(f"lower({c}) like ?" for c in cols) + ")")
            params += [like] * len(cols)
        clause = ("where " + " and ".join(where)) if where else ""
        limit = max(10, min(int(limit), 800))
        claims = _rows(
            con,
            f"""
            select claim_id, abstract_key,
                   subject_id, subject_label, subject_curie, subject_kind,
                   predicate, object_id, object_label, object_curie, object_kind,
                   object_function, relation_class, polarity, mechanism,
                   n_sources, first_year, status, dispute_kind, confidence
            from claim_edges {clause}
            order by (status='disputed') desc, n_sources desc, claim_id
            limit {limit}
            """,
            params,
        )
        matched = int(con.execute(f"select count(*) from claim_edges {clause}", params).fetchone()[0])
        total = int(con.execute("select count(*) from claim_edges").fetchone()[0])
        status_counts = _status_counts(con)
        facets = {
            "status": [{"value": k, "n": v} for k, v in sorted(status_counts.items())],
            "polarity": _facet(con, "polarity"),
            "relation_class": _facet(con, "coalesce(nullif(relation_class, ''), 'unclassed')"),
            "predicate": _facet(con, "predicate"),
            "kind": _facet(
                con, "kind",
                "(select distinct subject_id as id, subject_kind as kind from claim_edges "
                "union select distinct object_id, object_kind from claim_edges)",
            ),
        }
        summary = _kg_summary(con, total)
        tested = _tested_overlay(con, [c["claim_id"] for c in claims])
    finally:
        con.close()

    nodes: dict[str, dict] = {}

    def touch(nid: str, label: str, curie: str, kind: str, role: str) -> str:
        nid = nid or label
        if nid not in nodes:
            nodes[nid] = {"id": nid, "label": label or nid, "curie": curie or "",
                          "kind": kind or "", "degree": 0, "n_out": 0, "n_in": 0}
        node = nodes[nid]
        node["degree"] += 1
        node["n_out" if role == "subject" else "n_in"] += 1
        if not node["kind"] and kind:
            node["kind"] = kind
        return nid

    edges = []
    for c in claims:
        s = touch(c["subject_id"], c["subject_label"], c.get("subject_curie"), c.get("subject_kind"), "subject")
        o = touch(c["object_id"], c["object_label"], c.get("object_curie"), c.get("object_kind"), "object")
        edges.append(
            {
                "claim_id": c["claim_id"],
                "abstract_key": c.get("abstract_key") or "",
                "source": s,
                "target": o,
                "predicate": c["predicate"],
                "object_function": c.get("object_function") or "",
                "relation_class": c.get("relation_class") or "",
                "polarity": c["polarity"],
                "mechanism": c.get("mechanism") or "",
                "status": c["status"],
                "dispute_kind": c.get("dispute_kind") or "",
                "n_sources": c["n_sources"],
                "first_year": c.get("first_year"),
                "confidence": c["confidence"],
                "tested": tested.get(c["claim_id"]),
            }
        )

    try:
        as_of = path.stat().st_mtime
    except OSError:
        as_of = None
    return {
        "source": source,
        "sources": list(srcs.keys()),
        "nodes": list(nodes.values()),
        "edges": edges,
        "total_claims": total,
        "matched": matched,
        "status_counts": status_counts,
        "facets": facets,
        "summary": summary,
        "as_of": as_of,
        "shown": len(edges),
    }


# --- Human review: the promotion gate -------------------------------------
# Promotion gate (litmap/promote.py) contract. The WORKING graph is where the engine writes tested
# edges; the human validates in the UI, and only VALIDATED edges are copied into the MASTER graph. The
# UI collects decisions into the decisions file and then triggers apply (the real promote logic).
WORKING_KG = PROCESSED / "litmap_kg.duckdb"
MASTER_KG = PROCESSED / "litmap_master_kg.duckdb"
PROMOTION_DECISIONS_PATH = PROCESSED / "litmap_promotion_decisions.json"


def _write_json_atomic(path: Path, obj) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False))
    tmp.replace(path)  # atomic swap


def working_kg(project: str | None = None) -> Path:
    """The graph a review decision acts on.

    An analysis owns its graph, so its review queue is the candidates in that graph. Without a project
    the default graph (litmap_kg.duckdb) is used, so a run outside any project keeps working."""
    if project:
        db = kg_sources().get(project)
        if db is not None:
            return db
    return WORKING_KG


def promotion_decisions_path(project: str | None = None) -> Path:
    """Where a project's pending verdicts are collected before they are applied.

    Per-project, because the decisions file names test_ids that only mean something inside one
    graph — pooling them would apply one analysis's verdicts to another's edges."""
    if project:
        try:
            return projects_mod.project_dir(project) / "promotion_decisions.json"
        except ValueError:
            pass
    return PROMOTION_DECISIONS_PATH


def promotion_cards(project: str | None = None) -> list[dict]:
    """Discovery cards for candidates awaiting a promotion verdict.

    Reads the analysis's WORKING graph — the same store the promotion gate uses — read-only and
    lock-safe (snapshot copy if a run holds the DB).
    """
    db = working_kg(project)
    if not db.exists():
        return []
    try:
        con = _connect_ro(db)
    except (FileNotFoundError, duckdb.Error):
        return []
    try:
        if "engine_tests" not in _tables(con):
            return []
        from dnhacksbio.litmap import promote
        cards = []
        for r in _rows(
            con,
            "select test_id, run_id, subject, object, method, source, hypothesis, "
            "effect, effect_size, p_null, expected_sign, observed_sign, "
            "novelty_verdict, novelty_detail, kg_claim_id "
            "from engine_tests where status='candidate' and coalesce(human_review,'')='' "
            "order by test_id",
        ):
            lit = None
            cid = r.get("kg_claim_id")
            if cid:
                claim = _rows(
                    con,
                    "select subject_label, predicate, object_label, object_function, "
                    "polarity, status, confidence from claim_edges where claim_id=?",
                    [cid],
                )
                if claim:
                    quotes = [
                        e["quote"] for e in _rows(
                            con,
                            "select quote from evidence where claim_id=? "
                            "and quote is not null limit 3", [cid],
                        ) if e.get("quote")
                    ]
                    lit = {"claim": claim[0], "quotes": quotes}
            r["edge"] = f"{r.get('subject')} ~ {r.get('object')}"
            r["literature"] = lit
            r["recommended_action"] = promote._recommend(r.get("novelty_verdict"))
            cards.append(r)
        return cards
    finally:
        con.close()


def read_promotion_decisions(project: str | None = None) -> dict:
    """UI-written promotion decisions: {test_id: {decision, note}}."""
    path = promotion_decisions_path(project)
    if not path.exists():
        return {}
    try:
        d = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    return d.get("decisions", d) if isinstance(d, dict) else {}


def review_queue(project: str | None = None) -> dict:
    """Everything awaiting a human verdict: the promotion candidates and the decisions recorded so far."""
    return {
        "project": project,
        "candidates": promotion_cards(project),
        "promo_decided": read_promotion_decisions(project),
    }


def _record_promotion_decision(test_id, decision: str, note: str = "",
                              project: str | None = None) -> dict:
    """Record one promotion verdict into litmap_promotion_decisions.json.

    Every decision requires a written note, validated and rejected alike; the
    gate skips any unexplained verdict, so we reject it here rather than write a
    decision the gate would silently drop.
    """
    from dnhacksbio.litmap import promote
    if decision not in promote.ACTIONS:
        raise ValueError(f"decision must be one of {promote.ACTIONS}")
    note = (note or "").strip()
    if not note:
        raise ValueError("a written note is required for every decision")
    if len(note) > 400:
        raise ValueError("Decision notes must be 400 characters or fewer")
    try:
        test_id = int(test_id)
    except (TypeError, ValueError):
        raise ValueError("test_id must be an integer")
    db = working_kg(project)
    if project and project not in kg_sources():
        raise FileNotFoundError("Review collection not found")
    con = _connect_ro(db)
    try:
        rows = _rows(con, "SELECT status, human_review, review_note FROM engine_tests WHERE test_id=?", [test_id])
    finally:
        con.close()
    if not rows:
        raise FileNotFoundError("Candidate not found in this collection")
    row = rows[0]
    decisions = read_promotion_decisions(project)
    previous = decisions.get(str(test_id))
    if previous and (previous.get("decision") != decision or previous.get("note") != note):
        raise RuntimeError("A different decision is already saved; refresh to see it")
    if row.get("human_review"):
        if row["human_review"] != decision or row.get("review_note") != note:
            raise RuntimeError("This candidate already has a human decision; refresh to see it")
        # A pending receipt can outlive the working verdict if publication failed.
        # Retry it before claiming the complete promotion has been applied.
        if not previous:
            return {"ok": True, "test_id": test_id, "decision": decision, "applied": True}
    if str(row["status"]).lower() != "candidate":
        raise ValueError("Only an automated candidate can receive a promotion decision")
    decisions[str(test_id)] = previous or {"decision": decision, "note": note, "recorded_at": time.time()}
    promotion_decisions_path(project).parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(promotion_decisions_path(project), {"decisions": decisions})
    return {"ok": True, "test_id": test_id, "decision": decision, "pending": len(decisions)}


def _apply_promotions(project: str | None = None, test_id: int | None = None) -> dict:
    from contextlib import nullcontext
    from .membership import project_lease
    # Saving a decision precedes this nonblocking lease, so busy collections
    # retain the decision without racing build/run/membership writers.
    with project_lease(project) if project else nullcontext():
        return _apply_promotions_leased(project, test_id)


def _apply_promotions_leased(project: str | None = None, test_id: int | None = None) -> dict:
    """Apply all recorded decisions via the real litmap/promote.apply_decisions:
    stamp the working graph, copy VALIDATED edges into the master graph, and push
    each note to the explorer as feedback / CORRECTION. Clears the decisions file
    on success. Raises RuntimeError (→409) if the working graph is locked.
    """
    from dnhacksbio.litmap import promote
    from dnhacksbio.litmap.store import KGStore
    decisions = read_promotion_decisions(project)
    if test_id is not None:
        decisions = {str(test_id): decisions[str(test_id)]} if str(test_id) in decisions else {}
    if not decisions:
        return {"promoted": 0, "rejected": 0, "skipped": 0, "rejections": [],
                "note": "no decisions to apply"}
    try:
        working = KGStore(working_kg(project))
    except (duckdb.IOException, duckdb.Error) as exc:
        raise RuntimeError(
            "the working graph is locked — a run is likely active. "
            "Apply once it finishes."
        ) from exc
    try:
        try:
            master = KGStore(MASTER_KG)
        except duckdb.Error as exc:
            raise RuntimeError("The master graph is unavailable or locked. Your decision is saved; retry application later.") from exc
        try:
            # Commit the master first: after a crash, insert_promoted is idempotent,
            # and the working verdict/feedback transaction can safely be retried.
            working.con.execute("BEGIN TRANSACTION")
            master_transaction = False
            try:
                master.con.execute("BEGIN TRANSACTION")
                master_transaction = True
                summary = promote.apply_decisions(working, master, decisions)
                master.con.execute("COMMIT")
                master_transaction = False
                working.con.execute("COMMIT")
            except Exception:
                if master_transaction:
                    master.con.execute("ROLLBACK")
                working.con.execute("ROLLBACK")
                raise
            from dnhacksbio.explorer.human_review import publish_reviews
            from dnhacksbio.explorer.runtime import Journal
            try:
                publish_reviews(working, Journal(PROCESSED))
            except Exception as exc:
                raise RuntimeError("Your decision is saved, but runtime publication is pending. Retry application to finish.") from exc
        finally:
            master.close()
    finally:
        working.close()
    # Clear only applied decisions; a scoped review must not consume unrelated cards.
    remaining = read_promotion_decisions(project)
    for key in decisions:
        remaining.pop(key, None)
    _write_json_atomic(promotion_decisions_path(project), {"decisions": remaining})
    return summary


def record_promotion_decision(test_id, decision: str, note: str = "", project: str | None = None) -> dict:
    from .candidate_review import decision_lock
    with decision_lock(project):
        return _record_promotion_decision(test_id, decision, note, project)


def apply_promotions(project: str | None = None) -> dict:
    from .candidate_review import decision_lock
    with decision_lock(project):
        return _apply_promotions(project)


def _count_where(db: Path | None, table: str, frag: str = "", params: list | None = None) -> int:
    if db is None:
        return 0
    try:
        con = _connect_ro(db)
    except (FileNotFoundError, duckdb.Error):
        return 0
    try:
        if table not in _tables(con):
            return 0
        sql = f"select count(*) as n from {table}" + (f" where {frag}" if frag else "")
        rows = _rows(con, sql, params or [])
        return int(rows[0]["n"]) if rows else 0
    finally:
        con.close()


# --- The investigation event stream ---------------------------------------
# One ordered, timestamped list of everything that happened across a whole fork tree. This is what the
# Workflow view replays: the same list drives live-follow and sped-up playback, so there is no second code
# path that can disagree. Every event carries a real wall-clock `t`, so replay preserves the rhythm of the
# run, including the silence while an experiment runs in the sandbox.

def _iso_to_unix(s) -> float | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s)).timestamp()
    except (ValueError, TypeError):
        return None


def tree_runs(run_id: str) -> list[str]:
    """Every run in this investigation tree that actually has a trace on disk, root first."""
    r = LIN.root(run_id)
    out = {r} if _trace_path(r).exists() else set()
    for p in PROCESSED.glob(f"reasoning_{r}{LIN.SEP}*.jsonl"):
        rid = p.name[len("reasoning_"):-len(".jsonl")]
        if RUN_ID_RE.match(rid) and LIN.root(rid) == r:
            out.add(rid)
    return sorted(out, key=lambda x: (LIN.depth(x), x))


def _trace_steps(run_id: str) -> list[dict]:
    path = _trace_path(run_id)
    if not path.exists():
        return []
    steps = []
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                steps.append(_normalize_step(json.loads(raw)))
            except ValueError:
                continue
    return steps


# Replay pacing: each gap is capped.
MAX_GAP_S = 2.5


def run_events(run_id: str) -> dict:
    """The whole investigation as one ordered event list, plus the branch roster it implies.

    Built in passes: read every trace, learn when each branch was forked, correct any branch whose clock
    predates its own fork, then emit and order."""
    runs = tree_runs(run_id)
    if not runs:
        raise FileNotFoundError(run_id)
    clock_fixed: list[str] = []

    # --- A. every run's steps, with a time on each --------------------------------------------------
    steps_by_run: dict[str, list[dict]] = {}
    for rid in runs:
        steps_by_run[rid] = [s for s in _trace_steps(rid) if s.get("ts") is not None]

    # --- B. when was each branch forked, and with what metadata? -----------------------------------
    meta: dict[str, dict] = {}
    forked_at: dict[str, float] = {}
    seen_forks: set[tuple] = set()
    fork_seq = 0
    fork_records: list[dict] = []
    for rid in runs:
        for s in steps_by_run[rid]:
            fk = s.get("fork")
            if not (isinstance(fk, dict) and fk.get("children")):
                continue
            sig = (rid, tuple(sorted(c.get("run_id") or "" for c in fk["children"])))
            if sig in seen_forks:
                continue
            seen_forks.add(sig)
            fork_seq += 1
            # A step's `ts` is stamped when it completes, and a fork step does not complete until every
            # child has run, so the fork begins when the step begins: ts - dt_s.
            dt = s.get("dt_s")
            t_fork = float(s["ts"]) - float(dt) if isinstance(dt, (int, float)) else float(s["ts"])
            kids = []
            for c in fk["children"]:
                cid = c.get("run_id")
                if not cid:
                    continue
                meta[cid] = {"angle": c.get("angle", ""), "adversarial": bool(c.get("adversarial")),
                             "kept": bool(c.get("kept")), "rank": c.get("rank"),
                             "reason": c.get("reason", ""), "n_submitted": c.get("n_submitted"),
                             "n_experiments": c.get("n_experiments")}
                forked_at[cid] = t_fork
                kids.append({"run_id": cid, **meta[cid]})
            fork_records.append({"fork_id": f"f{fork_seq}", "parent": rid, "t": t_fork,
                                 "children": kids, "depth": fk.get("depth"),
                                 "budget_remaining": fk.get("budget_remaining")})

    # --- C. a branch cannot predate its own parent -------------------------------------------------
    # Shift such a run forward, preserving its internal spacing, and record it.
    # The floor is the fork itself when a record names the branch, else the moment its parent began.
    run_first = {rid: min((float(s["ts"]) for s in ss), default=None) for rid, ss in steps_by_run.items()}

    def _shift_run(rid: str, shift: float) -> None:
        for s in steps_by_run[rid]:
            s["ts"] = float(s["ts"]) + shift
        if run_first.get(rid) is not None:
            run_first[rid] += shift
        for fr in fork_records:
            if fr["parent"] == rid:
                fr["t"] += shift
                for c in fr["children"]:
                    if c["run_id"] in forked_at:
                        forked_at[c["run_id"]] += shift

    for rid in sorted(runs, key=LIN.depth):
        if LIN.depth(rid) == 0 or run_first.get(rid) is None:
            continue
        floor = forked_at.get(rid)
        if floor is None:
            floor = run_first.get(LIN.parent(rid) or "")
        if floor is None:
            continue
        if run_first[rid] < floor:
            clock_fixed.append(rid)
            _shift_run(rid, (floor - run_first[rid]) + 0.001)

    # --- D. emit -----------------------------------------------------------------------------------
    events: list[dict] = []
    for rid in runs:
        for s in steps_by_run[rid]:
            t = float(s["ts"])
            events.append({"t": t, "type": "step", "run_id": rid, "step": s.get("step"),
                           "action": s.get("action"), "family": s.get("family"), "phase": s.get("phase"),
                           "reasoning": (s.get("reasoning") or "")[:400],
                           "observation": (s.get("observation") or "")[:240]})
            if s.get("action") == "run_experiments":
                exps = (s.get("args") or {}).get("experiments")
                events.append({"t": t, "type": "experiment", "run_id": rid,
                               "n": len(exps) if isinstance(exps, list) else 1})

    for fr in fork_records:
        events.append({"t": fr["t"], "type": "fork", "run_id": fr["parent"], "fork_id": fr["fork_id"],
                       "children": fr["children"], "depth": fr["depth"],
                       "budget_remaining": fr["budget_remaining"]})
        # The judge runs once the leaves finish, so it belongs just past the last step of any child.
        last = max((float(s["ts"]) for c in fr["children"] for s in steps_by_run.get(c["run_id"], [])),
                   default=fr["t"])
        events.append({"t": max(last, fr["t"]) + 0.001, "type": "judged", "run_id": fr["parent"],
                       "fork_id": fr["fork_id"], "children": fr["children"]})

    db = _db_for_run(run_id)
    events.extend(_verification_events(run_id))
    events.sort(key=lambda e: (e["t"], _EVENT_ORDER.get(e["type"], 5)))

    # --- E. playback clock + lanes -----------------------------------------------------------------
    # `u` is playback time: same order, idle gaps capped. The UI animates on `u` and displays the real `t`.
    u = 0.0
    prev = None
    for e in events:
        if prev is not None:
            u += min(max(0.0, e["t"] - prev), MAX_GAP_S)
        e["u"] = round(u, 3)
        prev = e["t"]

    first_u: dict[str, float] = {}
    last_u: dict[str, float] = {}
    for e in events:
        first_u.setdefault(e["run_id"], e["u"])
        last_u[e["run_id"]] = e["u"]
    lanes = []
    for r in runs:
        # A branch's lane opens at the fork that created it — that is the moment it comes into existence —
        # falling back to its own first event for a branch no visible fork record names.
        f_u = next((e["u"] for e in events if e["type"] == "fork"
                    and any(c["run_id"] == r for c in e["children"])), None)
        if f_u is None:
            f_u = first_u.get(r)
        lanes.append({"run_id": r, "depth": LIN.depth(r), "parent": LIN.parent(r),
                      "u_start": f_u, "u_end": last_u.get(r), **meta.get(r, {})})

    t0 = events[0]["t"] if events else 0
    t1 = events[-1]["t"] if events else 0
    # A couple of standing facts the flowchart shows on nodes that are not themselves events.
    kg_claims = 0
    if db is not None:
        kg_claims = _count_where(db, "claims")
    papers = _count_where(db, "papers") if db is not None else 0

    return {"root": LIN.root(run_id), "lanes": lanes, "events": events,
            "kg_claims": kg_claims, "papers": papers,
            "t0": t0, "t1": t1, "duration": max(0.0, t1 - t0),
            "playback": round(u, 3), "clock_fixed_runs": clock_fixed,
            "max_gap_s": MAX_GAP_S,
            # An investigation is live if any BRANCH still is — same rule as list_runs, so a tree whose
            # every agent has said `done` stops claiming to be running.
            "active": any(_trace_path(r).exists()
                          and (time.time() - _trace_path(r).stat().st_mtime) < ACTIVE_WINDOW_S
                          and ((_read_last_line(_trace_path(r)) or {}).get("action") != "done")
                          for r in runs)}


# Events sharing a timestamp are ordered by what causes what: a step happens, it forks or submits, and the
# verdict lands afterwards. Without this a same-second submit/verdict pair can render out of order.
_EVENT_ORDER = {"step": 0, "experiment": 1, "fork": 2, "submit": 3, "verdict": 4,
                "tested": 5, "novelty": 6, "review": 7, "judged": 8}

_EXP_ID_RX = re.compile(r"#experiment (\d+)")


def _as_dict(v) -> dict:
    """A JSON column as a dict, whether the caller handed us the raw string or an already-parsed dict."""
    if isinstance(v, dict):
        return v
    try:
        d = json.loads(v or "{}")
        return d if isinstance(d, dict) else {}
    except (ValueError, TypeError):
        return {}


def _fans(run_id: str) -> tuple[dict[int, dict], list[dict]]:
    """Which `run_experiments` step produced which entries: the FAN, one of the view's two branchings.
    Read from the step's observation, where the engine writes each id (`#experiment 14 [ran] …`), not
    from entry ordering. Returns (entry_id -> step-info, list of fans)."""
    by_entry: dict[int, dict] = {}
    fans: list[dict] = []
    session, prev = 0, None
    for s in _trace_steps(run_id):
        st = s.get("step")
        if prev is not None and isinstance(st, int) and st <= prev:
            session += 1
        if isinstance(st, int):
            prev = st
        if s.get("action") != "run_experiments":
            continue
        ids = [int(x) for x in _EXP_ID_RX.findall(s.get("observation") or "")]
        asked = len((s.get("args") or {}).get("experiments") or [])
        fan = {"run_id": run_id, "session": session, "step": st, "entry_ids": ids,
               "n_asked": asked, "reasoning": (s.get("reasoning") or "")[:400]}
        fans.append(fan)
        for e in ids:
            by_entry[e] = fan
    return by_entry, fans


def run_tree(run_id: str) -> dict:
    """The investigation as a tree of experiments, as opposed to `run_events`, the same run as a timeline.

    Every experiment is a node carrying its own hypothesis, code, numbers, verdict and provenance. Nodes
    are joined by the two real branchings:
      * FAN   — one `run_experiments` step -> N sibling experiments (divergence inside one agent's step)
      * FORK  — one agent -> N child agents (divergence across agents, from the path-encoded run_id)
    A third relation, the RETRY chain, is derived: same branch + same subject~object, ordered by entry_id,
    where the earlier attempts failed. Unresolvable links are returned as `orphans` rather than dropped."""
    runs = tree_runs(run_id)
    if not runs:
        raise FileNotFoundError(run_id)
    db = _db_for_run(run_id)

    # --- what the agents recorded -------------------------------------------------------------------
    fans_by_entry: dict[int, dict] = {}
    all_fans: list[dict] = []
    for rid in runs:
        be, fs = _fans(rid)
        fans_by_entry.update(be)
        all_fans.extend(fs)

    entries: list[dict] = []
    verdict_by_entry: dict[int, dict] = {}
    sub_by_entry: dict[int, dict] = {}
    unreadable = ""
    if db is not None:
        try:
            con = _connect_ro(db)
        except (FileNotFoundError, duckdb.Error) as exc:
            # A run whose database could not be opened must not render like a run with no experiments.
            con = None
            unreadable = f"{type(exc).__name__}: {exc}"
            print(f"[run_tree] {run_id}: could not open {db} — {unreadable}", flush=True)
        if con is not None:
            try:
                tables = _tables(con)
                frag, params = _tree_pred(run_id)
                if "exploration" in tables:
                    entries = _rows(con, "select entry_id, run_id, kind, title, body, status, score, "
                                         f"provenance, code, result, created_at from exploration "
                                         f"where {frag} order by entry_id", params)
                if "verification_queue" in tables:
                    for r in _rows(con, "select submission_id, run_id, provenance, verdict, reason, "
                                        f"status from verification_queue where {frag}", params):
                        e = _as_dict(r.get("provenance")).get("exploration_entry")
                        if e is not None:
                            sub_by_entry[int(e)] = r
                if "engine_tests" in tables:
                    for r in _rows(con, "select test_id, run_id, status, kill_reason, verdict_note, effect, "
                                        "effect_size, p_null, novelty_verdict, human_review, "
                                        f"explore_entry from engine_tests where {frag}", params):
                        if r.get("explore_entry") is not None:
                            verdict_by_entry[int(r["explore_entry"])] = r
            except duckdb.Error as exc:
                # A swallowed query error is indistinguishable from "this run has no verdicts". Say it.
                unreadable = f"{type(exc).__name__}: {exc}"
                print(f"[run_tree] {run_id}: query failed — {type(exc).__name__}: {exc}", flush=True)
            finally:
                con.close()

    # --- nodes ---------------------------------------------------------------------------------------
    nodes, retry_seen, attempt_of = [], {}, {}
    for e in entries:
        eid = int(e["entry_id"])
        # `data._rows` returns raw columns, unlike `exploration._rows`, which deserializes JSON.
        prov = _as_dict(e.get("provenance"))
        try:
            res = json.loads(e.get("result") or "{}")
        except ValueError:
            res = {}
        if not isinstance(res, dict):
            res = {}
        fan = fans_by_entry.get(eid)
        sub, ver = sub_by_entry.get(eid), verdict_by_entry.get(eid)
        # stage is a property of the experiment, not a place it sits.
        if ver is not None:
            stage = "candidate" if ver.get("status") == "candidate" else "killed"
        elif sub is not None:
            stage = "verifying"
        elif e.get("status") == "submitted":
            stage = "submitted"
        else:
            stage = e.get("status") or "open"
        if ver is not None and (ver.get("human_review") or ""):
            stage = "reviewed"
        node = {
            "entry_id": eid, "run_id": e.get("run_id"), "kind": e.get("kind"),
            "title": e.get("title"),
            "body": e.get("body"), "code": e.get("code"),
            "result": res, "provenance": prov, "output": e.get("result") or "",
            "status": e.get("status"), "stage": stage,
            "subject": prov.get("subject"), "object": prov.get("object"),
            "method": prov.get("method"), "expected_sign": prov.get("expected_sign"),
            "effect": res.get("effect"),
            "p_null": res.get("p_null"), "robust": res.get("robust"),
            "n_units": res.get("n_units"), "created_at": e.get("created_at"),
            # `failed` = produced no measurable RESULT. Whether the code RAISED is a separate question: a
            # RESULT-less experiment may be a probe that ran fine and printed diagnostics.
            "failed": e.get("kind") == "experiment" and not res,
            "raised": (e.get("result") or "").strip().startswith("Traceback"),
            "step": (fan or {}).get("step"), "session": (fan or {}).get("session"),
            "submission_id": (sub or {}).get("submission_id"),
            "test_id": (ver or {}).get("test_id"),
            "verdict": (ver or {}).get("status"), "kill_reason": (ver or {}).get("kill_reason"),
            "verdict_note": (ver or {}).get("verdict_note"),
        }
        if e.get("kind") == "experiment":
            # Key the retry chain on the structured identity (subject~object), not the title, which the
            # agent rewords between attempts.
            key = (e.get("run_id"), str(prov.get("subject") or ""), str(prov.get("object") or ""))
            prior = retry_seen.get(key)
            node["retry_of"] = prior
            node["attempt"] = (attempt_of.get(prior, 1) + 1) if prior is not None else 1
            attempt_of[eid] = node["attempt"]
            # A retry chain runs through failures only: drilling the same pair after a result lands is
            # accumulating evidence, not re-attempting.
            if node["failed"]:
                retry_seen[key] = eid
            else:
                retry_seen.pop(key, None)
        nodes.append(node)

    # --- edges ---------------------------------------------------------------------------------------
    known = {n["entry_id"] for n in nodes}
    orphans = []
    for f in all_fans:
        missing = [e for e in f["entry_ids"] if e not in known]
        if missing:
            orphans.append({"kind": "fan-entry-missing", "run_id": f["run_id"], "step": f["step"],
                            "entry_ids": missing,
                            "why": "the step names these entries but the DB has no such row — "
                                   "the trace and DB have diverged"})
        if f["n_asked"] and not f["entry_ids"]:
            orphans.append({"kind": "fan-unrecorded", "run_id": f["run_id"], "step": f["step"],
                            "n_asked": f["n_asked"],
                            "why": "the step ran experiments but its observation recorded no entry ids"})
    for eid, s in sub_by_entry.items():
        if eid not in known:
            orphans.append({"kind": "submission-orphan", "submission_id": s["submission_id"],
                            "entry_id": eid, "why": "submission points at an entry not in this tree"})
    unverified = [s["submission_id"] for e, s in sub_by_entry.items()
                  if e not in verdict_by_entry]

    lanes = [{"run_id": r, "depth": LIN.depth(r), "parent": LIN.parent(r),
              "n_entries": sum(1 for n in nodes if n["run_id"] == r),
              "n_experiments": sum(1 for n in nodes if n["run_id"] == r and n["kind"] == "experiment")}
             for r in runs]
    return {"root": LIN.root(run_id), "lanes": lanes, "nodes": nodes,
            "fans": [f for f in all_fans if f["entry_ids"]],
            "forks": _fork_index_for(runs),
            "orphans": orphans, "unverified_submissions": unverified,
            # Empty because we could not read it, vs empty because nothing happened.
            "db_unreadable": unreadable,
            "counts": {"experiments": sum(1 for n in nodes if n["kind"] == "experiment"),
                       "submitted": len(sub_by_entry),
                       "candidates": sum(1 for n in nodes if n["stage"] == "candidate"),
                       "killed": sum(1 for n in nodes if n["stage"] == "killed"),
                       "failed": sum(1 for n in nodes if n.get("failed"))}}


def _fork_index_for(runs: list[str]) -> list[dict]:
    """Every fork generation in the tree, with the judge's ranking. Deduped on (parent, children)."""
    out, seen = [], set()
    for rid in runs:
        for s in _trace_steps(rid):
            fk = s.get("fork")
            if not (isinstance(fk, dict) and fk.get("children")):
                continue
            sig = (rid, tuple(sorted(c.get("run_id") or "" for c in fk["children"])))
            if sig in seen:
                continue
            seen.add(sig)
            out.append({"parent": rid, "step": s.get("step"), "depth": fk.get("depth"),
                        "budget_remaining": fk.get("budget_remaining"),
                        "children": [{"run_id": c.get("run_id"), "angle": c.get("angle", ""),
                                      "adversarial": bool(c.get("adversarial")), "kept": bool(c.get("kept")),
                                      "rank": c.get("rank"), "reason": c.get("reason", ""),
                                      "n_submitted": c.get("n_submitted"),
                                      "n_experiments": c.get("n_experiments"),
                                      "top": c.get("top")} for c in fk["children"]]})
    return out


def _verification_events(run_id: str) -> list[dict]:
    """Queue + tested-layer + human-gate events for the whole tree, from the DB where they actually live."""
    db = _db_for_run(run_id)
    if db is None:
        return []
    try:
        con = _connect_ro(db)
    except (FileNotFoundError, duckdb.Error):
        return []
    out: list[dict] = []
    try:
        tables = _tables(con)
        frag, params = _tree_pred(run_id)
        if "verification_queue" in tables:
            for r in _rows(con, "select submission_id, run_id, hypothesis, subject, object, method, "
                                f"verdict, reason, submitted_at, processed_at "
                                f"from verification_queue where {frag}", params):
                ts = _iso_to_unix(r["submitted_at"])
                if ts:
                    out.append({"t": ts, "type": "submit", "run_id": r["run_id"], "id": r["submission_id"],
                                "subject": r["subject"], "object": r["object"],
                                "method": (r["method"] or "")[:120],
                                "hypothesis": (r["hypothesis"] or "")[:240]})
                tp = _iso_to_unix(r["processed_at"])
                if tp:
                    out.append({"t": tp, "type": "verdict", "run_id": r["run_id"], "id": r["submission_id"],
                                "verdict": r["verdict"], "reason": (r["reason"] or "")[:200]})
        if "engine_tests" in tables:
            for r in _rows(con, "select test_id, run_id, subject, object, status, novelty_verdict, "
                                f"human_review, created_at from engine_tests where {frag}", params):
                tc = _iso_to_unix(r["created_at"])
                if not tc:
                    continue
                out.append({"t": tc + 0.002, "type": "tested", "run_id": r["run_id"], "id": r["test_id"],
                            "status": r["status"], "subject": r["subject"], "object": r["object"]})
                if r["novelty_verdict"]:
                    out.append({"t": tc + 0.003, "type": "novelty", "run_id": r["run_id"],
                                "id": r["test_id"], "verdict": r["novelty_verdict"]})
                if r["human_review"]:
                    out.append({"t": tc + 0.004, "type": "review", "run_id": r["run_id"],
                                "id": r["test_id"], "decision": r["human_review"]})
    except duckdb.Error:
        pass
    finally:
        con.close()
    return out


# --- Projects: scoping + the Knowledge-graph lane ---------------------------
# A project owns a graph; a run reasons over a graph; therefore a run belongs to a project.

_run_project_cache: dict[str, str] | None = None


def _run_index_path() -> Path:
    """Derived from the projects directory so a fixture's cache stays inside the fixture."""
    return _projects_dir() / "_run_index.json"


def _load_run_index() -> dict[str, str]:
    global _run_project_cache
    if _run_project_cache is None:
        try:
            _run_project_cache = json.loads(_run_index_path().read_text())
        except (OSError, ValueError):
            _run_project_cache = {}
    return _run_project_cache


def _save_run_index() -> None:
    try:
        _run_index_path().parent.mkdir(parents=True, exist_ok=True)
        tmp = _run_index_path().with_suffix(".json.tmp")
        tmp.write_text(json.dumps(_load_run_index(), indent=0))
        tmp.replace(_run_index_path())
    except OSError:
        pass


_declared_cache: tuple[float, dict[str, str]] = (-1.0, {})


def _declared_project(root: str) -> str | None:
    """The project that says it launched this run, from its own record. Available immediately, unlike
    `_db_for_run`, which cannot attribute a run until it has written rows. Memoized on the projects
    directory's mtime."""
    global _declared_cache
    d = _projects_dir()
    try:
        stamp = d.stat().st_mtime
    except OSError:
        return None
    if _declared_cache[0] != stamp:
        table: dict[str, str] = {}
        for p in sorted(d.glob("*/project.json")):
            try:
                rec = json.loads(p.read_text())
            except (OSError, ValueError):
                continue
            for r in rec.get("runs") or []:
                table[LIN.root(str(r))] = p.parent.name
        _declared_cache = (stamp, table)
    return _declared_cache[1].get(root)


def project_of_run(run_id: str) -> str | None:
    """Which project's corpus this run reasoned over, or None if we cannot tell. Resolved by the
    project's own declaration first, else by evidence: the DuckDB that contains rows for this run's
    tree, whose key in `kg_sources` is the project id. Memoized on disk, per investigation root, since
    forked branches share their parent's database."""
    root = LIN.root(run_id)
    declared = _declared_project(root)
    if declared:
        return declared
    idx = _load_run_index()
    hit = idx.get(root)
    if isinstance(hit, dict):
        # A cached miss expires when the run's trace has been written since we looked, or when the set
        # of graphs has changed.
        if hit.get("p"):
            return hit["p"]
        trace = _trace_path(root)
        stale = (trace.exists() and trace.stat().st_mtime > hit.get("t", 0)) \
            or hit.get("srcs") != len(kg_sources())
        if not stale:
            return None
    db = _db_for_run(root)
    key = _project_for_db(Path(db)) if db else None
    idx[root] = {"p": key or "", "t": time.time(), "srcs": len(kg_sources())}
    _save_run_index()
    return key


def _project_for_db(db: Path) -> str | None:
    """Map a database file back to the project that owns it: an exact path match, or a file inside
    data/projects/<id>/ or data/corpora/<name>/ (a variant beside the canonical graph)."""
    db = db.resolve()
    srcs = {k: Path(v).resolve() for k, v in kg_sources().items()}
    for key, path in srcs.items():
        if path == db:
            return key
    parent = db.parent
    if parent.parent.name in ("projects", "corpora") and parent.name in srcs:
        return parent.name
    return None


def _kg_db_for_project(project: str | None) -> Path | None:
    if not project:
        return None
    return kg_sources().get(project)


def _status_counts(con) -> dict:
    try:
        return {str(s): int(n) for s, n in
                con.execute("select status, count(*) from claim_edges group by 1").fetchall()}
    except duckdb.Error:
        return {}


def kg_stats(project: str | None = None) -> dict:
    """Everything the console needs to describe one project's graph in numbers, in one round trip so
    the KG tab, the projects list and the Workflow lane agree."""
    db = _kg_db_for_project(project)
    out = {
        "project": project, "db": str(db) if db else None, "exists": bool(db and db.exists()),
        "papers": {"n": 0, "full_text": 0},
        "claims": {"n": 0, "entities": 0, "evidence": 0},
        "status_counts": {}, "disputed": 0,
        "vectors": {"n": 0, "coverage": 0.0},
        "predicates": [], "hubs": [],
    }
    if not db or not db.exists():
        return out
    try:
        con = _connect_ro(db)
    except (FileNotFoundError, duckdb.Error) as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"
        return out
    try:
        tabs = _tables(con)
        one = lambda sql: con.execute(sql).fetchone()[0]          # noqa: E731
        if "claims" in tabs and "claim_edges" in _views(con):
            out["claims"]["n"] = int(one("select count(*) from claim_edges"))
            out["claims"]["entities"] = int(one(
                "select count(*) from (select subject_id as e from claim_edges "
                "union select object_id from claim_edges)"))
            out["status_counts"] = _status_counts(con)
            out["disputed"] = int(out["status_counts"].get("disputed", 0))
            out["predicates"] = [
                {"predicate": p, "n": int(n)} for p, n in con.execute(
                    "select predicate, count(*) n from claim_edges group by 1 order by n desc limit 12"
                ).fetchall()]
            out["hubs"] = [
                {"entity": e, "n": int(n)} for e, n in con.execute(
                    "select e, count(*) n from (select subject_label e from claim_edges "
                    "union all select object_label from claim_edges) group by 1 order by n desc limit 12"
                ).fetchall()]
        if "evidence" in tabs:
            out["claims"]["evidence"] = int(one("select count(*) from evidence"))
        if "papers" in tabs:
            out["papers"]["n"] = int(one("select count(*) from papers"))
            try:
                out["papers"]["full_text"] = int(one(
                    "select count(*) from papers where is_full_text"))
            except duckdb.Error:
                pass
        if "claim_vectors" in tabs:
            out["vectors"]["n"] = int(one("select count(*) from claim_vectors"))
            if out["claims"]["n"]:
                out["vectors"]["coverage"] = round(out["vectors"]["n"] / out["claims"]["n"], 3)
    except duckdb.Error as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        con.close()
    return out


# Which build stage feeds which node of the Workflow view's knowledge-graph lane. The lane's boxes
# come from webui/architecture.py; this is the only place that says what lights them up.
_KG_STAGE_NODE = {
    "plan": "find", "discover": "find", "dedup": "find", "filter": "find",
    "known": "find", "triage": "find", "fetch": "find",
    "attach": "extract", "extract": "extract",
    "store": "kg", "status": "kg", "papers": "kg", "card": "kg",
}


def kg_lane(project: str | None = None) -> dict:
    """The Workflow view's Knowledge-graph lane, lit up.

    Two sources, in priority order. If a build is RUNNING, the lane shows where that build is right
    now — the stage it is in becomes `active` and everything before it is `done`. If nothing is
    running, the lane reports the graph that exists on disk. Either way every badge is a real number
    read from a real file; a node with nothing behind it says so rather than showing a zero that
    looks like a measurement."""
    from . import jobs as _jobs

    stats = kg_stats(project)
    node = lambda state, badge="", detail="": {"state": state, "badge": badge, "detail": detail}  # noqa: E731
    lane = {k: node("idle") for k in ("find", "extract", "kg", "semantic")}

    job = None
    events: list[dict] = []
    if project:
        try:
            job = _jobs.active_job(project)
            if job is None:
                recent = _jobs.list_jobs(project)
                job = recent[0] if recent else None
            if job:
                events = _jobs.events(project, job["id"])
        except (ValueError, KeyError, OSError):
            job = None

    live = bool(job and job.get("status") == "running")
    stage_now = ""
    seen_nodes: list[str] = []
    counters: dict[str, dict] = {}
    for ev in events:
        n = _KG_STAGE_NODE.get(ev.get("stage") or "")
        if not n:
            continue
        stage_now = ev.get("stage") or stage_now
        if n not in seen_nodes:
            seen_nodes.append(n)
        c = counters.setdefault(n, {})
        for k in ("done", "total", "n_hits", "n_unique", "n_kept", "n_selected", "n_full",
                  "n_claims", "n_attachments"):
            if ev.get(k) is not None:
                c[k] = ev[k]
        if ev.get("status") == "done":
            c["completed"] = True

    node_now = _KG_STAGE_NODE.get(stage_now, "")
    for n in seen_nodes:
        c = counters.get(n, {})
        bits = []
        if c.get("n_selected"):
            bits.append(f"{c['n_selected']} papers")
        elif c.get("n_unique"):
            bits.append(f"{c['n_unique']} found")
        elif c.get("n_hits"):
            bits.append(f"{c['n_hits']} hits")
        if c.get("n_claims"):
            bits.append(f"{c['n_claims']} claims")
        if c.get("done") and c.get("total"):
            bits.append(f"{c['done']}/{c['total']}")
        badge = " · ".join(bits)
        if live and n == node_now:
            lane[n] = node("active", badge or "working", f"build stage: {stage_now}")
        else:
            lane[n] = node("done" if c.get("completed") else "armed", badge)

    # Fall back to (or fill in from) what is on disk. The test is on the badge, not the state: the
    # write stages report progress, not totals.
    if stats["exists"]:
        p, cl = stats["papers"], stats["claims"]
        def fill(nid: str, badge: str, detail: str) -> None:
            if not lane[nid]["badge"]:
                lane[nid] = node(lane[nid]["state"] if lane[nid]["state"] != "idle" else "armed",
                                 badge, detail)
            elif not lane[nid]["detail"]:
                lane[nid]["detail"] = detail

        if p["n"]:
            fill("find", f"{p['n']:,} papers", f"{p['full_text']:,} with full text")
        if cl["evidence"]:
            fill("extract", f"{cl['evidence']:,} quotes", f"{cl['n']:,} claims extracted")
        if cl["n"]:
            fill("kg", f"{cl['n']:,} claims",
                 f"{cl['entities']:,} entities · {stats['disputed']} disputed")
        v = stats["vectors"]
        lane["semantic"] = node(
            "armed" if v["n"] else "idle",
            f"{v['n']:,} vectors" if v["n"] else "not built",
            f"{int(v['coverage'] * 100)}% of claims embedded" if v["n"]
            else "run scripts/embed_kg.py to enable semantic KG search")

    return {
        "project": project, "nodes": lane, "stats": stats,
        "job": {k: job.get(k) for k in ("id", "kind", "status", "started", "finished", "dry")}
               if job else None,
        "stage": stage_now, "live": live,
        "last_message": (events[-1].get("msg") if events else ""),
    }
