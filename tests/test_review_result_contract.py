import json
from types import SimpleNamespace

import duckdb
import pytest

from dnhacksbio.explorer.explorer import Explorer
from dnhacksbio.explorer.human_review import publish_reviews, record_review
from dnhacksbio.explorer.runtime import Journal
from dnhacksbio.explorer.verifyqueue import VerifyQueue
from dnhacksbio.methods import result_problem


VALID = dict(effect=1.0, p_null=.01, n_units=12, null_model="donor permutation", robust=True)


@pytest.mark.parametrize("patch", [
    {"p_null": 0}, {"p_null": True}, {"p_null": float("nan")},
    {"effect": "1"}, {"effect": 10 ** 1000}, {"n_units": True},
    {"n_units": 12.5}, {"n_units": 0}, {"null_model": " "}, {"robust": "false"},
])
def test_strict_result_types(patch):
    assert result_problem(VALID | patch)


@pytest.mark.parametrize("field", VALID)
def test_missing_result_fields_fail_closed(field):
    result = VALID.copy()
    del result[field]
    assert result_problem(result)


def test_explicit_failed_robustness_is_a_valid_report():
    assert result_problem(VALID | {"robust": False}) is None
    assert result_problem([])


def test_queue_rejects_malformed_result_and_continues(tmp_path):
    queue = VerifyQueue(tmp_path / "kg.duckdb")
    try:
        for i, result in enumerate([{"effect": 1}, VALID]):
            queue.submit(run_id="study", hypothesis="fixture", subject=str(i), object="B",
                         method="test", expected_sign=1, result=result)
        verdicts = queue.drain("study")
        assert verdicts[0]["status"] == "KILL"
        assert verdicts[0]["reason"] == "malformed-result"
        assert verdicts[1]["status"] == "CANDIDATE"
    finally:
        queue.close()


def test_updated_feedback_on_same_entry_is_delivered_once():
    entry = dict(entry_id=1, updated_at="same timestamp", status="promising", title="test", body="Initial verdict")
    ex = object.__new__(Explorer)
    ex._scope = lambda: None
    ex._budget_line = lambda: ""
    ex._seen_fb, ex._seen_corr = set(), set()
    ex.journal = SimpleNamespace(blob=lambda text: {"size": len(text)})
    ex.log = SimpleNamespace(feedback_entries=lambda *a, **kw: [entry],
                             corrections=lambda *a, **kw: [], frontier=lambda *a, **kw: [],
                             open_questions=lambda *a, **kw: [])
    assert "Initial verdict" in ex._turn_message("observation")
    assert "Initial verdict" not in ex._turn_message("observation")
    entry.update(status="validated", body="Later human decision")
    assert "Later human decision" in ex._turn_message("observation")
    assert len(ex._pending_feedback) == 1
    assert "Later human decision" not in ex._turn_message("observation")


def test_human_review_publication_retries_and_preserves_history(tmp_path):
    con = duckdb.connect()
    working = SimpleNamespace(con=con)
    row = dict(test_id=1, run_id="study", explore_entry=7)
    con.execute("CREATE TABLE verification_queue (submission_id INT, run_id VARCHAR, provenance VARCHAR)")
    con.execute("INSERT INTO verification_queue VALUES (1,'study',?)", [json.dumps(
        dict(exploration_entry=7, experiment_id="exp", attempt_id="a"))])
    journal = Journal(tmp_path)
    journal.append("study", "a", "experiment.reviewed", {"verification": "CANDIDATE"}, experiment_id="exp")
    try:
        record_review(working, row | {"explore_entry": None}, "validated", "unlinked")
        assert not con.execute("SELECT 1 FROM information_schema.tables WHERE table_name='human_review_events'").fetchone()
        record_review(working, row, "validated", "Checked control")

        def interrupted(*args, **kwargs):
            journal.append(*args, **kwargs)
            raise OSError("interrupted after journal commit")

        with pytest.raises(OSError):
            publish_reviews(working, SimpleNamespace(append=interrupted))
        record_review(working, row, "validated", "Checked control")
        publish_reviews(working, journal)
        publish_reviews(working, journal)
        assert len(journal.events("study")) == 2
        assert "human_review" not in journal.snapshot("study", through=1)["runs"]["study"]["experiments"]["exp"]
        assert journal.snapshot("study")["runs"]["study"]["experiments"]["exp"]["human_review"] == "validated"
        record_review(working, row, "rejected", "Control was confounded")
        publish_reviews(working, journal)
        record_review(working, row, "validated", "Checked control")
        publish_reviews(working, journal)
        events = journal.events("study")
        assert [e["payload"]["human_review"] for e in events[1:]] == ["validated", "rejected", "validated"]
        assert all(e["attempt_id"] == "a" and e["experiment_id"] == "exp" for e in events)
        assert all("e_value" not in e["payload"] for e in events)
    finally:
        con.close()


def test_api_keeps_saved_decisions_when_publication_fails(tmp_path, monkeypatch):
    from dnhacksbio.webui import data
    from dnhacksbio.explorer import human_review
    from dnhacksbio.litmap.store import KGStore

    monkeypatch.setattr(data, "PROCESSED", tmp_path)
    monkeypatch.setattr(data, "WORKING_KG", tmp_path / "working.duckdb")
    monkeypatch.setattr(data, "MASTER_KG", tmp_path / "master.duckdb")
    monkeypatch.setattr(data, "PROMOTION_DECISIONS_PATH", tmp_path / "decisions.json")
    working = KGStore(data.WORKING_KG)
    working.write_back([dict(status="CANDIDATE", subject="A", object="B", method="test",
                             expected_sign=1, effect=1, p_null=.01)], run_id="study")
    test_id = working.con.execute("SELECT test_id FROM engine_tests").fetchone()[0]
    working.close()
    decisions = {str(test_id): dict(decision="rejected", note="Check independent controls")}
    data._write_json_atomic(data.PROMOTION_DECISIONS_PATH, {"decisions": decisions})
    real_publish = human_review.publish_reviews
    def fail(*args):
        raise OSError("publication unavailable")
    monkeypatch.setattr(human_review, "publish_reviews", fail)
    with pytest.raises(OSError):
        data.apply_promotions()
    assert data.read_promotion_decisions() == decisions
    monkeypatch.setattr(human_review, "publish_reviews", real_publish)
    assert data.apply_promotions()["rejected"] == 1
    assert not data.PROMOTION_DECISIONS_PATH.exists()
