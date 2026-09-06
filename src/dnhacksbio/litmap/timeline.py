"""Read-only ingestion observer; append replay events and complete published KG snapshots.

Run with --run RUN_DIR --db CORPUS_DB --watch (or --once). Earlier activity is
recovered from file mtimes, never presented as an observed real-time event.
Only timeline/ is written. Published databases must be closed atomic snapshots;
a locked or changing database is retried on the next poll, never copied mid-write.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import time


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=lambda v: v.model_dump(mode="json") if hasattr(v, "model_dump") else str(v), separators=(",", ":"))


def identity(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


def file_key(path):
    st = path.stat()
    return (st.st_ino, st.st_size, st.st_mtime_ns)


class TimelineRecorder:
    def __init__(self, run: Path, db: Path | None = None):
        self.run, self.db = run, db
        self.out = run / "timeline"
        self.out.mkdir(parents=True, exist_ok=True)
        self.lock = (self.out / ".observer.lock").open("a")
        fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.events = self.out / "events.jsonl"
        self.seen = set()
        self.results = {}
        if self.events.exists():
            with self.events.open("rb+") as stream:
                while raw := stream.readline():
                    try:
                        record = json.loads(raw)
                        self.seen.add(record["event_id"])
                        if record.get("type") == "paper_completed":
                            self.results[int(record["paper_ref"])] = record["result"]
                    except (ValueError, KeyError):
                        # Only discard an incomplete final append after a crash.
                        if stream.read(1):
                            raise ValueError("Corrupt non-final timeline event")
                        stream.truncate(stream.tell() - len(raw))
                        break
        if self.events.exists() and not any(self.out.glob("replay-*.json")):
            self.results = {}
        self.started = time.time()
        self.db_key = None
        self.paths = {}

    def emit(self, kind, key, payload, *, timestamp=None, basis="observer_wall_clock"):
        event_id = identity([kind, key])
        if event_id in self.seen:
            return
        now = time.time()
        event = dict(schema_version=1, event_id=event_id, type=kind,
                     timestamp=now if timestamp is None else timestamp,
                     timestamp_basis=basis, observed_at=now,
                     recovered=timestamp is not None and timestamp < self.started,
                     **payload)
        with self.events.open("a") as handle:
            handle.write(encoded(event) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        self.seen.add(event_id)

    def close(self):
        self.lock.close()

    def event(self, kind, key, payload, *, timestamp=None,
              timestamp_basis="observer_wall_clock"):
        self.emit(kind, key, payload, timestamp=timestamp, basis=timestamp_basis)

    def paper_completed(self, ref, result, *, timestamp=None,
                        timestamp_basis="observer_wall_clock"):
        result = json.loads(encoded(result))
        self.results[int(ref)] = result
        self.emit("paper_completed", [f"{int(ref):03d}", identity(result)],
                  {"paper_ref": int(ref), "result": result},
                  timestamp=timestamp, basis=timestamp_basis)
        graph = materialize_results(self.results)
        graph_id = identity(graph)
        snapshot = self.out / f"replay-{graph_id}.json"
        if not snapshot.exists():
            tmp = snapshot.with_suffix(".tmp")
            tmp.write_text(encoded({"schema_version": 1, "snapshot_id": graph_id, **graph}))
            tmp.replace(snapshot)
        self.emit("replay_materialized", graph_id,
                  {"snapshot": snapshot.name, "snapshot_id": graph_id,
                   "paper_ref": int(ref), "completed_papers": sorted(self.results),
                   "not_a_production_publication": True,
                   "counts": {k: len(graph[k]) for k in ("nodes", "edges", "evidence")}},
                  timestamp=timestamp, basis=timestamp_basis)

    def poll_files(self):
        for path in sorted(self.run.glob("[0-9][0-9][0-9]/result.json"), key=lambda p: (p.stat().st_mtime_ns, str(p))):
            key = file_key(path)
            if self.paths.get(path) == key:
                continue
            try:
                result = json.loads(path.read_text())
            except (OSError, ValueError):
                continue
            self.paper_completed(int(path.parent.name), result,
                                 timestamp=path.stat().st_mtime,
                                 timestamp_basis="result_file_mtime")
            self.paths[path] = key
        for path in sorted(self.run.glob("[0-9][0-9][0-9]/worker-*.log")):
            key = file_key(path)
            if self.paths.get(path) == key:
                continue
            # Retain only explicit stage tokens, never arbitrary SDK log content.
            lines = path.read_text(errors="replace").splitlines()
            for number, line in enumerate(lines):
                match = re.match(r"^(BATCH_START|COMPLETE|PAPER_EXIT|READ_START|REPAIR_START|DIRECTION_START)\b", line)
                if match:
                    self.emit("worker_stage_observed", [str(path.relative_to(self.run)), number, match[1]],
                              {"paper_ref": int(path.parent.name), "stage": match[1],
                               "log_file": str(path.relative_to(self.run)), "line": number + 1,
                               "historical_time_unknown": True},
                              basis="observer_wall_clock_not_stage_start")
            self.paths[path] = key

    def published(self, db: Path):
        """Record a closed production DB snapshot after successful publication."""
        self.db = Path(db)
        self.poll_graph()

    def poll_graph(self):
        import duckdb
        if self.db is None or not self.db.exists() or Path(str(self.db) + ".wal").exists():
            return
        before = file_key(self.db)
        if before == self.db_key:
            return
        try:
            con = duckdb.connect(str(self.db), read_only=True)
            try:
                available = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
                tables = {}
                for name in ("claims", "claim_edges", "evidence", "evidence_context", "evidence_cites", "experiments", "papers", "deferrals", "claim_status"):
                    if name not in available:
                        continue
                    cur = con.execute(f'SELECT * FROM "{name}"')
                    columns = [d[0] for d in cur.description]
                    rows = [dict(zip(columns, row)) for row in cur.fetchall()]
                    if name == "evidence":
                        for row in rows:
                            row["replay_evidence_id"] = identity({k: v for k, v in row.items() if k != "evidence_id"})
                    tables[name] = sorted(rows, key=encoded)
            finally:
                con.close()
        except duckdb.Error:
            return
        if not self.db.exists() or file_key(self.db) != before or Path(str(self.db) + ".wal").exists():
            return
        graph_id = identity(tables)
        snapshot = self.out / f"graph-{graph_id}.json"
        if not snapshot.exists():
            tmp = snapshot.with_suffix(".tmp")
            edges = tables.get("claim_edges", tables.get("claims", []))
            nodes = {}
            for edge in edges:
                for side in ("subject", "object"):
                    node_id = edge.get(f"{side}_id")
                    if node_id:
                        nodes[node_id] = {"id": node_id, **{
                            field: edge.get(f"{side}_{field}")
                            for field in ("label", "curie", "kind")}}
            tmp.write_text(encoded({"schema_version": 1, "snapshot_id": graph_id,
                                    "nodes": sorted(nodes.values(), key=encoded),
                                    "edges": edges, "tables": tables}))
            tmp.replace(snapshot)
        self.emit("graph_published_observed", graph_id,
                  {"snapshot": snapshot.name, "snapshot_id": graph_id,
                   "counts": {k: len(v) for k, v in tables.items()},
                   "db_path": str(self.db), "publication_time_unknown": True},
                  timestamp=before[2] / 1e9, basis="database_file_mtime_not_publication_time")
        self.db_key = before

    def poll(self):
        self.poll_files()
        self.poll_graph()


def materialize_results(results):
    """Cumulative replay state; preserve source assertions and corrected result versions.

    Claim IDs are extractor IDs; node IDs match the production claim_edges view.
    Evidence IDs derive from full content, independent of database sequence numbers.
    This is extracted state, not inferred production corroboration/status.
    """
    nodes, edges, evidence = {}, {}, {}
    for ref, result in sorted(results.items()):
        for claim in result.get("claims", []):
            source_evidence = claim.get("evidence", [])
            claim_id = claim.get("claim_id") or next(
                (e["claim_id"] for e in source_evidence if e.get("claim_id")), None)
            if not claim_id:
                from .schema import Claim
                claim_id = Claim.model_validate(claim).claim_id
            spine = claim.get("spine", {})
            edge = edges.setdefault(claim_id, {"claim_id": claim_id, "spine": spine,
                                              "paper_refs": [], "assertions": []})
            edge["paper_refs"].append(ref)
            edge["assertions"].append({"paper_ref": ref, "claim": claim})
            for side in ("subject", "object"):
                entity = spine.get(side, {})
                node_id = entity.get("curie") or entity.get("label")
                if node_id:
                    nodes[node_id] = {"id": node_id, **entity}
                    edge["source" if side == "subject" else "target"] = node_id
            edge["predicate"] = spine.get("predicate")
            for record in source_evidence:
                replay_id = identity({k: v for k, v in record.items() if k != "evidence_id"})
                evidence[replay_id] = {**record, "replay_evidence_id": replay_id}
    return {"nodes": sorted(nodes.values(), key=encoded),
            "edges": sorted(edges.values(), key=encoded),
            "evidence": sorted(evidence.values(), key=encoded),
            "results": {str(k): v for k, v in sorted(results.items())}}


class Observer(TimelineRecorder):
    """File-polling compatibility observer for already running ingestion jobs."""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--db", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true")
    mode.add_argument("--watch", action="store_true")
    parser.add_argument("--interval", type=float, default=1.5)
    args = parser.parse_args()
    observer = Observer(args.run.resolve(), args.db.resolve())
    while True:
        observer.poll()
        if args.once:
            break
        time.sleep(max(0.2, args.interval))


if __name__ == "__main__":
    main()
