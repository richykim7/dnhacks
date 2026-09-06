"""Exact public experiment review; uses the existing human promotion gate."""
from contextlib import contextmanager
import fcntl
import json

from dnhacksbio.explorer.runtime import Journal
from . import data


@contextmanager
def decision_lock(project):
    """Serialize both old and scoped review endpoints across server processes."""
    if project and project not in data.kg_sources():
        raise FileNotFoundError("Review collection not found")
    path = data.promotion_decisions_path(project).with_suffix(".lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def candidate(run, experiment, project=None):
    manifest = Journal(data.PROCESSED, create=False).manifest(run, project)
    scope = manifest.get("project_id") or manifest.get("project") or None
    if scope and scope not in data.kg_sources():
        raise FileNotFoundError("Review collection not found")
    db = data.working_kg(scope)
    con = data._connect_ro(db)
    try:
        if not {"verification_queue", "engine_tests"}.issubset(data._tables(con)):
            raise FileNotFoundError("No linked candidate record is available")
        matches = []
        for row in data._rows(con, "SELECT submission_id, provenance, hypothesis, result_json, code, verdict, reason "
                              "FROM verification_queue WHERE run_id=? ORDER BY submission_id DESC", [run]):
            provenance = json.loads(row.pop("provenance") or "{}")
            if provenance.get("experiment_id") != experiment:
                continue
            entry = provenance.get("exploration_entry")
            if entry is None:
                continue
            tests = data._rows(con, "SELECT test_id, run_id, kg_claim_id, hypothesis, subject, object, method, source, "
                               "effect, effect_size, p_null, expected_sign, observed_sign, status, verdict_note, "
                               "novelty_verdict, novelty_detail, human_review, review_note "
                               "FROM engine_tests WHERE run_id=? AND explore_entry=?", [run, entry])
            for test in tests:
                if str(test.get("status")).lower() != "candidate" and not test.get("human_review"):
                    continue
                matches.append((test, row))
        # Never guess if provenance maps to more than one surviving test.
        unique = {test["test_id"] for test, _ in matches}
        if len(unique) != 1:
            raise FileNotFoundError("A unique linked candidate record is not available for this experiment")
        test, submission = matches[0]
        claim_id = test.get("kg_claim_id")
        claim = data._rows(con, "SELECT subject_label, predicate, object_label, polarity, status FROM claim_edges WHERE claim_id=?", [claim_id]) if claim_id else []
        evidence = data._rows(con, "SELECT source_ref, source_label, quote FROM evidence WHERE claim_id=? LIMIT 20", [claim_id]) if claim_id else []
        pending = data.read_promotion_decisions(scope).get(str(test["test_id"]))
        return {"project": scope, "run": run, "experiment": experiment, "test": test,
                "submission_id": submission["submission_id"], "verification": submission["verdict"],
                "verification_reason": submission["reason"], "result": json.loads(submission["result_json"] or "{}"),
                "code": submission["code"], "claim": claim[0] if claim else None,
                "evidence": evidence, "pending": pending,
                "status": "pending_application" if pending else (test.get("human_review") or "pending_review")}
    finally:
        con.close()


def decide(run, experiment, decision, note, project=None):
    card = candidate(run, experiment, project)
    scope = card["project"]
    with decision_lock(scope):
        # Re-read after obtaining the lock; concurrent clicks cannot overwrite a verdict.
        card = candidate(run, experiment, scope)
        saved = data._record_promotion_decision(card["test"]["test_id"], decision, note, scope)
        if saved.get("applied"):
            return card
        try:
            data._apply_promotions(scope, test_id=card["test"]["test_id"])
        except RuntimeError as exc:
            return {**candidate(run, experiment, scope), "message": str(exc)}
        return candidate(run, experiment, scope)
