"""Durable human-decision publication; no private statistical scoring data."""
import json
import time
from uuid import uuid4


def record_review(working, row, decision, note):
    con = working.con
    if not row.get("explore_entry"):
        return  # Never guess an association for an older/unlinked test.
    if not con.execute("SELECT 1 FROM information_schema.tables WHERE table_name='verification_queue'").fetchone():
        return  # Legacy result without a runtime experiment association.
    rows = con.execute("SELECT provenance FROM verification_queue WHERE run_id=? ORDER BY submission_id DESC",
                       [row.get("run_id")]).fetchall()
    association = None
    for (raw,) in rows:
        p = json.loads(raw or "{}")
        if p.get("exploration_entry") == row.get("explore_entry") and p.get("experiment_id") and p.get("attempt_id"):
            association = p
            break
    if not association:
        return
    con.execute("""CREATE TABLE IF NOT EXISTS human_review_events (
        event_id VARCHAR PRIMARY KEY, test_id BIGINT, run_id VARCHAR, attempt_id VARCHAR,
        experiment_id VARCHAR, payload VARCHAR, applied_at DOUBLE, published BOOLEAN)""")
    payload = json.dumps({"human_review": decision, "human_review_note": note, "test_id": row["test_id"]}, sort_keys=True)
    last = con.execute("SELECT payload FROM human_review_events WHERE test_id=? ORDER BY applied_at DESC LIMIT 1",
                       [row["test_id"]]).fetchone()
    if last and last[0] == payload:
        return
    con.execute("INSERT INTO human_review_events VALUES (?,?,?,?,?,?,?,false)",
                [uuid4().hex, row["test_id"], row["run_id"], association["attempt_id"],
                 association["experiment_id"], payload, time.time()])


def publish_reviews(working, journal):
    con = working.con
    if not con.execute("SELECT 1 FROM information_schema.tables WHERE table_name='human_review_events'").fetchone():
        return
    for eid, run, attempt, experiment, raw, applied in con.execute(
            "SELECT event_id,run_id,attempt_id,experiment_id,payload,applied_at FROM human_review_events "
            "WHERE NOT published ORDER BY applied_at,event_id").fetchall():
        journal.append(run, attempt, "experiment.human_reviewed", dict(json.loads(raw), human_review_at=applied),
                       experiment_id=experiment, producer="human-review", event_id="human-review-" + eid)
        con.execute("UPDATE human_review_events SET published=true WHERE event_id=?", [eid])
