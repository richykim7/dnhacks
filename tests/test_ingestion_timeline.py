"""Observer durability, provenance and read-only snapshot checks."""
import importlib.util
import json
import os
from pathlib import Path

import duckdb

spec = importlib.util.spec_from_file_location(
    "timeline", Path(__file__).parents[1] / "scripts" / "record_ingestion_timeline.py")
timeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(timeline)


def test_observer_recovers_deduplicates_and_preserves_database(tmp_path):
    run = tmp_path / "run"
    paper = run / "001"
    paper.mkdir(parents=True)
    result = paper / "result.json"
    result.write_text(json.dumps({"claims": [{"claim_id": "c1"}]}))
    os.utime(result, (100, 100))
    db = tmp_path / "graph.duckdb"
    con = duckdb.connect(str(db))
    con.execute("CREATE TABLE claims(claim_id VARCHAR, subject_id VARCHAR, object_id VARCHAR)")
    con.execute("INSERT INTO claims VALUES ('c1', 's1', 'o1')")
    con.execute("CREATE VIEW claim_edges AS SELECT * FROM claims")
    con.execute("CREATE TABLE evidence(evidence_id INT, claim_id VARCHAR, quote VARCHAR)")
    con.execute("INSERT INTO evidence VALUES (1, 'c1', 'Actual source quotation')")
    con.close()
    original = db.read_bytes()
    observer = timeline.Observer(run, db)
    observer.poll()
    events = observer.events.read_bytes()
    observer.poll()
    assert observer.events.read_bytes() == events
    records = [json.loads(line) for line in events.splitlines()]
    completion = next(r for r in records if r["type"] == "paper_completed")
    assert completion["timestamp"] == 100
    assert completion["timestamp_basis"] == "result_file_mtime"
    assert completion["recovered"] is True
    graph = next(r for r in records if r["type"] == "graph_published_observed")
    snapshot = json.loads((observer.out / graph["snapshot"]).read_text())
    assert {n["id"] for n in snapshot["nodes"]} == {"s1", "o1"}
    assert snapshot["edges"][0]["claim_id"] == "c1"
    assert snapshot["tables"]["evidence"][0]["replay_evidence_id"]
    assert db.read_bytes() == original
    observer.lock.close()
    # Resume repairs a torn final append but does not duplicate earlier events.
    with (run / "timeline" / "events.jsonl").open("ab") as handle:
        handle.write(b'{"event_id":')
    resumed = timeline.Observer(run, db)
    resumed.poll()
    assert resumed.events.read_bytes() == events
    resumed.lock.close()


def test_observer_skips_wal_and_ignores_unstructured_logs(tmp_path):
    run = tmp_path / "run"
    paper = run / "002"
    paper.mkdir(parents=True)
    (paper / "worker-1.log").write_text("arbitrary SDK content\nCOMPLETE 2 {}\n")
    db = tmp_path / "graph.duckdb"
    db.write_bytes(b"not a closed database")
    Path(str(db) + ".wal").touch()
    observer = timeline.Observer(run, db)
    observer.poll()
    rows = [json.loads(line) for line in observer.events.read_text().splitlines()]
    assert len(rows) == 1
    assert rows[0]["stage"] == "COMPLETE"
    assert rows[0]["historical_time_unknown"]
    assert "arbitrary SDK content" not in observer.events.read_text()
    assert not list(observer.out.glob("graph-*.json"))
    observer.lock.close()


def test_each_completion_creates_cumulative_replay_before_publication(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    db = tmp_path / "absent.duckdb"
    observer = timeline.Observer(run, db)
    for ref in (1, 2):
        paper = run / f"{ref:03d}"
        paper.mkdir()
        claim = {"claim_id": f"c{ref}", "spine": {
            "subject": {"curie": "HGNC:1", "label": "Gene"},
            "object": {"curie": f"GO:{ref}", "label": "Process"},
            "predicate": "increases"}, "evidence": [
                {"claim_id": f"c{ref}", "source_ref": ref, "quote": f"Quote {ref}"}]}
        (paper / "result.json").write_text(json.dumps({"claims": [claim]}))
        observer.poll()
    records = [json.loads(line) for line in observer.events.read_text().splitlines()]
    replays = [r for r in records if r["type"] == "replay_materialized"]
    assert len(replays) == 2
    assert replays[0]["counts"]["edges"] == 1
    assert replays[1]["counts"]["edges"] == 2
    assert all(r["not_a_production_publication"] for r in replays)
    assert not any(r["type"] == "graph_published_observed" for r in records)
    snapshots = [json.loads((observer.out / r["snapshot"]).read_text()) for r in replays]
    assert snapshots[0]["evidence"][0]["replay_evidence_id"] in {
        e["replay_evidence_id"] for e in snapshots[1]["evidence"]}
    observer.close()
