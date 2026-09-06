"""Real persisted human review against an isolated collection; no live data/model calls."""
import pytest
from dnhacksbio.explorer import embed
from dnhacksbio.explorer.exploration import ExplorationLog
from dnhacksbio.explorer.runtime import Journal
from dnhacksbio.explorer.verifyqueue import VerifyQueue
from dnhacksbio.litmap.store import KGStore
from dnhacksbio.webui import data, projects, candidate_review as review


@pytest.fixture
def collection(tmp_path, monkeypatch):
    processed = tmp_path / "processed"
    project_dir = tmp_path / "projects" / "fixture"
    project_dir.mkdir(parents=True)
    monkeypatch.setattr(data, "PROCESSED", processed)
    monkeypatch.setattr(data, "CORPORA", tmp_path / "corpora")
    monkeypatch.setattr(data, "MASTER_KG", processed / "master.duckdb")
    monkeypatch.setattr(projects, "PROJECTS", tmp_path / "projects")
    monkeypatch.setattr(embed, "embed_one", lambda _: [0.0] * 384)
    journal = Journal(processed)
    journal.register("fixture-run", "Synthetic review controls", project="fixture")
    journal.append("fixture-run", "attempt", "attempt.started", {"lifecycle": "completed"})
    db = project_dir / "kg.duckdb"
    kg = KGStore(db)
    queue = VerifyQueue(kg=kg)
    log = ExplorationLog(con=kg.con)
    for index in (1, 2):
        entry = log.log("experiment", f"Control {index}", run_id="fixture-run")
        sid = queue.submit(run_id="fixture-run", hypothesis=f"Synthetic claim {index}", subject=f"A{index}", object="B", method="fixture", expected_sign=1,
                           result={"effect": .4, "p_null": .01}, provenance={"experiment_id": f"exp{index}", "attempt_id": "attempt", "exploration_entry": entry})
        queue.con.execute("UPDATE verification_queue SET status='verified',verdict='CANDIDATE' WHERE submission_id=?", [sid])
        kg.record_engine_verdict({"status": "CANDIDATE", "subject": f"A{index}", "object": "B", "method": "fixture", "expected_sign": 1, "hypothesis": f"Synthetic claim {index}", "explore_entry": entry}, "fixture-run")
    kg.close()
    return db, journal


def test_accept_reject_persist_exact_experiment_and_replay(collection):
    db, journal = collection
    initial = review.candidate("fixture-run", "exp1", "fixture")
    assert initial["status"] == "pending_review"
    assert initial["result"] == {"effect": .4, "p_null": .01}
    boundary = journal.snapshot("fixture-run")["sequence"]
    result = review.decide("fixture-run", "exp1", "validated", "Checked the synthetic controls", "fixture")
    assert result["status"] == "validated"
    assert result["pending"] is None
    assert review.decide("fixture-run", "exp1", "validated", "Checked the synthetic controls", "fixture")["status"] == "validated"
    with pytest.raises(RuntimeError, match="already has"):
        review.decide("fixture-run", "exp1", "rejected", "Conflicting click", "fixture")
    result = review.decide("fixture-run", "exp2", "rejected", "Control invalidates this claim", "fixture")
    assert result["status"] == "rejected"
    master = KGStore(data.MASTER_KG)
    assert master.con.execute("SELECT count(*) FROM engine_tests").fetchone()[0] == 1
    master.close()
    published = [e for e in journal.events("fixture-run") if e["kind"] == "experiment.human_reviewed"]
    assert len(published) == 2
    assert {e["experiment_id"] for e in published} == {"exp1", "exp2"}
    assert not any(e["kind"] == "experiment.human_reviewed" for e in journal.events("fixture-run", through=boundary))


def test_scope_notes_and_saved_conflicts(collection, monkeypatch):
    with pytest.raises(FileNotFoundError):
        review.candidate("fixture-run", "exp1", "another")
    with pytest.raises(FileNotFoundError):
        review.candidate("fixture-run", "missing", "fixture")
    for note in ("", "x" * 401):
        with pytest.raises(ValueError):
            review.decide("fixture-run", "exp1", "validated", note, "fixture")
    apply = data._apply_promotions
    monkeypatch.setattr(data, "_apply_promotions", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("Collection busy")))
    saved = review.decide("fixture-run", "exp1", "validated", "Checked", "fixture")
    assert saved["status"] == "pending_application"
    assert saved["pending"]["note"] == "Checked"
    with pytest.raises(RuntimeError, match="different decision"):
        review.decide("fixture-run", "exp1", "rejected", "Changed", "fixture")
    # Saving another card does not allow a scoped apply to consume it.
    data.record_promotion_decision(2, "rejected", "Separate review", "fixture")
    monkeypatch.setattr(data, "_apply_promotions", apply)
    assert review.decide("fixture-run", "exp1", "validated", "Checked", "fixture")["status"] == "validated"
    assert data.read_promotion_decisions("fixture")["2"]["note"] == "Separate review"


def test_publication_failure_retry_preserves_single_correction(collection, monkeypatch):
    from dnhacksbio.explorer import human_review
    publish = human_review.publish_reviews
    monkeypatch.setattr(human_review, "publish_reviews", lambda *a: (_ for _ in ()).throw(RuntimeError("Publication unavailable")))
    result = review.decide("fixture-run", "exp2", "rejected", "Controls failed", "fixture")
    assert result["pending"]
    monkeypatch.setattr(human_review, "publish_reviews", publish)
    result = review.decide("fixture-run", "exp2", "rejected", "Controls failed", "fixture")
    assert result["status"] == "rejected" and result["pending"] is None
    kg = KGStore(collection[0])
    assert kg.con.execute("SELECT count(*) FROM exploration WHERE title LIKE 'CORRECTION:%'").fetchone()[0] == 1
    kg.close()
    assert len([e for e in collection[1].events("fixture-run") if e["kind"] == "experiment.human_reviewed"]) == 1


def test_master_lock_retains_pending_decision(collection, monkeypatch):
    import duckdb
    from dnhacksbio.litmap import store
    original = store.KGStore
    def locked(path):
        if path == data.MASTER_KG:
            raise duckdb.IOException("Synthetic master lock")
        return original(path)
    monkeypatch.setattr(store, "KGStore", locked)
    result = review.decide("fixture-run", "exp1", "validated", "Checked", "fixture")
    assert result["status"] == "pending_application"
    assert "master graph" in result["message"]
    assert not result["test"]["human_review"]
    monkeypatch.setattr(store, "KGStore", original)
    assert review.decide("fixture-run", "exp1", "validated", "Checked", "fixture")["status"] == "validated"


def test_http_candidate_review_is_persisted(collection):
    from http.client import HTTPConnection
    from http.server import ThreadingHTTPServer
    import json
    import threading
    from dnhacksbio.webui.server import Handler
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        conn = HTTPConnection("127.0.0.1", server.server_port)
        conn.request("POST", "/api/review/candidate", json.dumps({"run": "fixture-run", "experiment": "exp1", "project": "fixture", "decision": "validated", "note": "HTTP fixture controls checked"}), {"Content-Type": "application/json"})
        response = conn.getresponse()
        assert response.status == 200
        assert json.loads(response.read())["status"] == "validated"
        conn.request("GET", "/api/review/candidate?run=fixture-run&experiment=exp1&project=fixture")
        response = conn.getresponse()
        assert response.status == 200
        assert json.loads(response.read())["test"]["review_note"] == "HTTP fixture controls checked"
        conn.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_shared_membership_lease_keeps_decision_pending(collection):
    from dnhacksbio.webui.membership import project_lease
    with project_lease("fixture"):
        result = review.decide("fixture-run", "exp1", "validated", "Checked", "fixture")
        assert result["status"] == "pending_application"
        assert "busy" in result["message"]
        assert not result["test"]["human_review"]
    assert review.decide("fixture-run", "exp1", "validated", "Checked", "fixture")["status"] == "validated"
