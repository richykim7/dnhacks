"""Durable runner-owned execution journal. SQLite commits serialize every branch.

Events and manifests share a transaction boundary; readers never see partial records.
No model text is interpreted as an event. Blobs are immutable, content addressed, and
written/fsynced before their references are committed. SQLite recovers interrupted writes.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from . import lineage as LIN

VERSION = 1
TERMINAL = {"completed", "failed", "cancelled", "budget_exhausted", "pruned"}
ID = re.compile(r"^[A-Za-z0-9._~-]+$")


def safe_id(value: str) -> str:
    if not ID.fullmatch(value) or value in {".", ".."}:
        raise ValueError("Invalid runtime identifier")
    return value


def redact(value):
    """Best-effort common secret redaction, NOT a general secret detector."""
    if isinstance(value, dict):
        return {k: "[redacted]" if re.search(r"(?i)(password|secret|token|api.?key|authorization)", k)
                else redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        value = re.sub(r"\b(?:21st_sk_|sk-|ghp_|github_pat_)[A-Za-z0-9_-]{12,}", "[redacted]", value)
        return re.sub(r"(?i)((?:api[_-]?key|password|authorization|secret|access_token)\s*[=:]\s*)[^\s,;]+",
                      r"\1[redacted]", value)
    return value


def process_namespace() -> str | None:
    try:
        return os.readlink("/proc/self/ns/pid")
    except OSError:
        return None


def process_identity(pid: int | None = None) -> str | None:
    try:
        pid = pid or os.getpid()
        # Kernel start ticks + boot identity protect against PID reuse and reboot.
        stat = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        namespace = os.readlink(f"/proc/{pid}/ns/pid")
        return f"{Path('/proc/sys/kernel/random/boot_id').read_text().strip()}|{namespace}|{pid}|{stat[19]}"
    except (OSError, IndexError):
        return None


class Journal:
    def __init__(self, directory: str | Path, *, create: bool = True):
        self.directory = Path(directory) / "runtime"
        self.path = self.directory / "journal.sqlite3"
        if create:
            self.directory.mkdir(parents=True, exist_ok=True)
            with self.connect() as con:
                con.executescript('''
                    CREATE TABLE IF NOT EXISTS manifests (
                      run_id TEXT PRIMARY KEY, investigation_id TEXT NOT NULL,
                      project_id TEXT, body TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS events (
                      investigation_id TEXT NOT NULL, sequence INTEGER NOT NULL,
                      event_id TEXT UNIQUE NOT NULL, body TEXT NOT NULL,
                      PRIMARY KEY(investigation_id, sequence));
                ''')

    @contextmanager
    def connect(self):
        con = sqlite3.connect(self.path, timeout=20)
        try:
            con.execute("PRAGMA busy_timeout=20000")
            con.execute("PRAGMA synchronous=FULL")
            with con:
                yield con
        finally:
            con.close()

    def manifests(self) -> list[dict]:
        if not self.path.exists():
            return []
        with self.connect() as con:
            return [json.loads(r[0]) for r in con.execute("SELECT body FROM manifests")]

    def manifest(self, run_id: str, project: str | None = None) -> dict:
        safe_id(run_id)
        if not self.path.exists():
            raise FileNotFoundError("Runtime history unavailable for this legacy run")
        with self.connect() as con:
            row = con.execute("SELECT body FROM manifests WHERE run_id=?", (run_id,)).fetchone()
        if row is None:
            raise FileNotFoundError("Runtime history unavailable for this run")
        m = json.loads(row[0])
        if project and m.get("project_id") != project:
            raise FileNotFoundError("Run not in this project")
        return m

    def register(self, run_id: str, question: str, *, objective: str = "", project: str | None = None,
                 config: dict | None = None) -> dict:
        safe_id(run_id)
        m = dict(schema_version=VERSION, run_id=run_id, investigation_id=LIN.root(run_id),
                 parent_run_id=LIN.parent(run_id), original_question=question,
                 branch_objective=objective or question, project_id=project,
                 created_at=time.time(), config=config or {})
        with self.connect() as con:
            con.execute("INSERT OR IGNORE INTO manifests VALUES (?,?,?,?)",
                        (run_id, m["investigation_id"], project, json.dumps(redact(m))))
        # Existing original question and lineage are immutable on resume.
        return self.manifest(run_id)

    def append(self, run_id: str, attempt_id: str, kind: str, payload: dict | None = None,
               *, operation_id: str | None = None, experiment_id: str | None = None,
               producer: str = "runner", event_id: str | None = None) -> dict:
        root = LIN.root(safe_id(run_id))
        eid = event_id or uuid4().hex
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            old = con.execute("SELECT body FROM events WHERE event_id=?", (eid,)).fetchone()
            if old:
                return json.loads(old[0])
            if kind == "lifecycle" and producer == "supervisor":
                last = con.execute("SELECT body FROM events WHERE investigation_id=? ORDER BY sequence DESC", (root,))
                latest_attempt = next((json.loads(r[0])["attempt_id"] for r in last
                                       if json.loads(r[0])["run_id"] == run_id
                                       and json.loads(r[0])["kind"] == "attempt.started"), None)
                if latest_attempt and latest_attempt != attempt_id:
                    raise ValueError("Supervisor attempt changed; refusing stale terminal event")
            seq = con.execute("SELECT COALESCE(MAX(sequence),0)+1 FROM events WHERE investigation_id=?",
                              (root,)).fetchone()[0]
            event = dict(schema_version=VERSION, event_id=eid, sequence=seq, investigation_id=root,
                         run_id=run_id, parent_run_id=LIN.parent(run_id), attempt_id=attempt_id,
                         operation_id=operation_id, experiment_id=experiment_id, kind=kind,
                         producer=producer, occurred_at=time.time(), recorded_at=time.time(),
                         payload=redact(payload or {}))
            encoded = json.dumps(event, allow_nan=False)
            con.execute("INSERT INTO events VALUES (?,?,?,?)", (root, seq, eid, encoded))
        return event

    def events(self, root: str, after: int = 0, through: int | None = None,
               limit: int = 1000) -> list[dict]:
        safe_id(root)
        if not self.path.exists():
            return []
        with self.connect() as con:
            rows = con.execute("SELECT body FROM events WHERE investigation_id=? AND sequence>? "
                               "AND sequence<=? ORDER BY sequence LIMIT ?",
                               (root, max(0, after), through if through is not None else 2**63-1,
                                max(1, min(limit, 10000)))).fetchall()
        return [json.loads(r[0]) for r in rows]

    def snapshot(self, root: str, through: int | None = None) -> dict:
        # One read transaction pins both history and cursor. No retention deletes events.
        safe_id(root)
        if not self.path.exists():
            raise FileNotFoundError("No runtime history")
        with self.connect() as con:
            rows = con.execute("SELECT body FROM events WHERE investigation_id=? AND sequence<=? "
                               "ORDER BY sequence", (root, through if through is not None else 2**63-1)).fetchall()
        state = {"schema_version": VERSION, "sequence": 0, "runs": {}}
        for row in rows:
            reduce_event(state, json.loads(row[0]))
        return state

    def blob(self, text: str) -> dict:
        raw = redact(text).encode()
        digest = self.store_bytes(raw)
        return {"storage_key": digest, "sha256": digest, "byte_length": len(raw)}

    def store_bytes(self, raw: bytes) -> str:
        digest = hashlib.sha256(raw).hexdigest()
        directory = self.directory / "blobs"
        directory.mkdir(exist_ok=True)
        target = directory / digest
        if not target.exists():
            fd, name = tempfile.mkstemp(dir=directory)
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(raw)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(name, target)
                dfd = os.open(directory, os.O_RDONLY)
                try:
                    os.fsync(dfd)
                finally:
                    os.close(dfd)
            finally:
                if os.path.exists(name):
                    os.unlink(name)
        return digest

    def read_blob(self, key: str) -> bytes:
        if not re.fullmatch(r"[a-f0-9]{64}", key):
            raise FileNotFoundError("Invalid blob")
        p = self.directory / "blobs" / key
        if p.is_symlink():
            raise FileNotFoundError("Invalid blob")
        raw = p.read_bytes()
        if hashlib.sha256(raw).hexdigest() != key:
            raise ValueError("Artifact integrity check failed")
        return raw


def reduce_event(state: dict, e: dict) -> dict:
    """Canonical backend snapshot, mirrored by the frontend reducer and parity fixtures."""
    if e["sequence"] <= state["sequence"]:
        return state
    if e["sequence"] != state["sequence"] + 1:
        raise ValueError("Runtime event gap")
    state["sequence"] = e["sequence"]
    run = state["runs"].setdefault(e["run_id"], {"run_id": e["run_id"], "experiments": {}, "history": []})
    p, kind = e["payload"], e["kind"]
    run["updated_at"] = e["recorded_at"]
    if kind == "attempt.started":
        run.update(p, attempt_id=e["attempt_id"], lifecycle="running", intent="", activity=None, heartbeat_at=None)
    elif kind == "lifecycle":
        run.update(p)
        if p.get("lifecycle") in TERMINAL:
            run["activity"] = None
            for exp in run["experiments"].values():
                if exp.get("status") in {"queued", "running"}:
                    exp.update(status="interrupted", error="Attempt ended before an experiment outcome was recorded")
    elif kind == "worker.registered" and run.get("lifecycle") == "queued":
        run.update(p, attempt_id=e["attempt_id"])
    elif kind == "heartbeat":
        run["heartbeat_at"] = e["recorded_at"]
    elif kind == "intent":
        run["intent"] = p["intent"]
    elif kind.endswith(".started") and kind in {"model.started", "tool.started"}:
        run["activity"] = dict(p, operation_id=e["operation_id"], started_at=e["recorded_at"])
    elif kind in {"model.ended", "tool.ended", "tool.failed"}:
        run["activity"] = None
    elif kind.startswith("experiment."):
        exp = run["experiments"].setdefault(e["experiment_id"], {"experiment_id": e["experiment_id"], "artifacts": []})
        exp.update(p)
    elif kind == "artifact":
        exp = run["experiments"][e["experiment_id"]]
        exp["artifacts"].append(dict(p, available_sequence=e["sequence"]))
    elif kind == "checkpoint.report":
        run["checkpoint"] = p
    elif kind == "branch.decision":
        run["decision"] = p
    if kind != "heartbeat":
        run["history"].append(e)
    return state
