"""Presentation decisions stay in their own namespace, including durable retry."""
import hashlib
import json

import pytest

from dnhacksbio.explorer.runtime import Journal
from dnhacksbio.litmap.store import KGStore
from dnhacksbio.webui import candidate_review, data, jobs, membership, projects


@pytest.fixture
def presentation(tmp_path, monkeypatch):
    monkeypatch.setattr(projects, "PROJECTS", tmp_path / "projects")
    monkeypatch.setattr(projects, "CORPORA", tmp_path / "corpora")
    monkeypatch.setattr(data, "PROCESSED", tmp_path / "processed")
    monkeypatch.setattr(data, "CORPORA", tmp_path / "corpora")
    monkeypatch.setattr(data, "_projects_dir", lambda: projects.PROJECTS)
    monkeypatch.setattr(data, "WORKING_KG", tmp_path / "source.duckdb")
    monkeypatch.setattr(data, "MASTER_KG", tmp_path / "master.duckdb")
    for path in (data.WORKING_KG, data.MASTER_KG):
        store = KGStore(path)
        store.close()
    rec = projects.create("Presentation fixture")
    pid = rec["id"]
    raw = projects._record_path(pid)
    value = json.loads(raw.read_text())
    value["presentation_only"] = True
    raw.write_text(json.dumps(value))
    journal = Journal(data.PROCESSED)
    journal.register("example-run", "Generic fixture", project=pid)
    journal.append("example-run", "attempt", "attempt.started", {})
    store = KGStore(projects.kg_path(pid))
    store.con.execute("CREATE TABLE verification_queue (submission_id BIGINT, run_id VARCHAR, provenance VARCHAR, hypothesis VARCHAR, result_json VARCHAR, code VARCHAR, verdict VARCHAR, reason VARCHAR)")
    for n in (1, 2):
        store.record_engine_verdict({"status": "CANDIDATE", "subject": str(n), "object": "fixture",
                                    "method": "illustrative", "explore_entry": n}, "example-run")
        provenance = json.dumps({"experiment_id": f"exp-{n}", "attempt_id": "attempt", "exploration_entry": n})
        store.con.execute("INSERT INTO verification_queue VALUES (?, ?, ?, '', '{}', '', 'CANDIDATE', '')",
                          [n, "example-run", provenance])
    store.close()
    hashes = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in (data.WORKING_KG, data.MASTER_KG)}
    yield pid, journal
    assert {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in hashes} == hashes


def test_scoped_and_bulk_reviews_never_promote(presentation):
    pid, journal = presentation
    accepted = candidate_review.decide("example-run", "exp-1", "validated", "Illustrative acceptance", pid)
    assert accepted["status"] == "validated"
    data.record_promotion_decision(2, "rejected", "Illustrative rejection", pid)
    result = data.apply_promotions(pid)
    assert result["promoted"] == 0 and result["reviewed"] == 1 and result["presentation_only"]
    assert candidate_review.candidate("example-run", "exp-2", pid)["status"] == "rejected"
    reviews = [e for e in journal.snapshot("example-run")["runs"]["example-run"]["history"] if e["kind"] == "experiment.human_reviewed"]
    assert len(reviews) == 2
    assert data.read_promotion_decisions(pid) == {}
    # Scope-free lookup resolves the manifest's presentation project, not default KG.
    assert candidate_review.candidate("example-run", "exp-1")["project"] == pid


def test_publication_failure_retries_without_duplicate_review(presentation, monkeypatch):
    from dnhacksbio.explorer import human_review
    pid, journal = presentation
    publish = human_review.publish_reviews
    def fail(*args):
        raise OSError("fixture publication outage")
    monkeypatch.setattr(human_review, "publish_reviews", fail)
    card = candidate_review.decide("example-run", "exp-1", "validated", "Keep isolated", pid)
    assert card["status"] == "pending_application"
    assert "publication is pending" in card["message"]
    monkeypatch.setattr(human_review, "publish_reviews", publish)
    assert candidate_review.decide("example-run", "exp-1", "validated", "Keep isolated", pid)["status"] == "validated"
    candidate_review.decide("example-run", "exp-1", "validated", "Keep isolated", pid)
    events = journal.snapshot("example-run")["runs"]["example-run"]["history"]
    assert len([e for e in events if e["kind"] == "experiment.human_reviewed"]) == 1


def test_presentation_mutations_and_shared_review_database_rejected(presentation):
    pid, _ = presentation
    for operation in (
        lambda: jobs.start_run(pid, goal="A valid exploratory question"),
        lambda: jobs.start_build(pid),
        lambda: membership.ensure_editable(pid),
        lambda: membership.write_connection(pid),
        lambda: projects.update(pid, {"presentation_only": False}),
        lambda: projects.delete(pid, purge=True),
    ):
        with pytest.raises(ValueError, match="presentation-only"):
            operation()
    data.record_promotion_decision(1, "validated", "Retain only locally", pid)
    db = projects.kg_path(pid)
    owned = db.with_name("private.duckdb")
    db.rename(owned)
    db.symlink_to(owned)
    with pytest.raises(RuntimeError, match="private database"):
        data.apply_promotions(pid)
