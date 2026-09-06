"""Promotion gate: the human seat at the back of the loop.

The engine writes freely to the working graph; nothing reaches the master graph without a human verdict.
This module writes a graded discovery card per surviving, unreviewed candidate, the API records decisions,
and `apply_decisions` copies only validated cards into the master store with provenance.

Every decision requires a written `note`, validated and rejected alike; an unexplained verdict is skipped.
  validated -> copied into the master graph; the note is its promotion provenance.
  rejected  -> stays field-local negative space, and the note is pushed to the explorer as a correction.
"""
from __future__ import annotations

from dnhacksbio.litmap.store import KGStore

ACTIONS = ("validated", "rejected")   # both require a written note


def _recommend(novelty_verdict: str) -> str:
    """A suggestion only; the human decides. Keyed on the external novelty verdict."""
    v = (novelty_verdict or "").lower()
    return {
        "known": "reject: already established in the literature (confirmatory / control)",
        "contradicts": "REVIEW (high value): result contradicts the in-field consensus",
        "distant-field": "REVIEW (Swanson-bridge lead): known only in a distant field, unconnected here",
        "open": "REVIEW: specific claim unattested in the literature searched; send to a post-cutoff "
                "holdout before any discovery claim",
    }.get(v, "REVIEW")


def apply_decisions(working: KGStore, master: KGStore, decisions: dict) -> dict:
    """Apply human verdicts. A decision without a note is skipped. `validated` stamps the working-graph
    edge and copies it with its literature provenance into master; `rejected` stays field-local and pushes
    the note to the explorer as a correction. Idempotent. Returns a summary including the rejections."""
    promoted = rejected = skipped = 0
    rejections = []
    elog = None
    for tid, d in (decisions or {}).items():
        if not isinstance(d, dict) or d.get("decision") not in ACTIONS:
            skipped += 1
            continue
        decision, note = d["decision"], (d.get("note") or "").strip()
        if not note:
            skipped += 1
            continue
        try:
            test_id = int(tid)
        except (TypeError, ValueError):
            skipped += 1
            continue
        row = working.get_engine_test(test_id)
        if not row:
            skipped += 1
            continue
        working.set_human_review(test_id, decision, note)
        from dnhacksbio.explorer.human_review import record_review
        record_review(working, row, decision, note)
        # route the verdict back to the explorer's exploration entry, outranking the verifier's
        ee = row.get("explore_entry")
        if ee:
            if elog is None:
                from dnhacksbio.explorer.exploration import ExplorationLog
                elog = ExplorationLog(con=working.con)
            new_status = {"validated": "validated", "rejected": "dead"}[decision]
            elog.record_feedback(int(ee), source="human", verdict=decision, note=note, new_status=new_status)
            if decision == "rejected":
                elog.log("note", f"CORRECTION: {row.get('subject')}~{row.get('object')}",
                         f"A human REJECTED this candidate: {note}. Do not repeat this framing; update the "
                         f"mental model accordingly.",
                         run_id=row.get("run_id", ""))
        if decision == "validated":
            claim_row = working.get_claim(row["kg_claim_id"]) if row.get("kg_claim_id") else None
            ev = working.evidence_for(row["kg_claim_id"]) if row.get("kg_claim_id") else []
            if master.insert_promoted(row, claim_row, ev, note) is not None:
                promoted += 1
        else:  # rejected
            rejected += 1
            rejections.append({"test_id": test_id,
                               "edge": f"{row.get('subject')}~{row.get('object')}", "note": note})
    return {"promoted": promoted, "rejected": rejected, "skipped": skipped,
            "rejections": rejections, "master_counts": master.counts()}
