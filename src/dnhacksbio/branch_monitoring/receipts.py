"""Read existing private scoring results into private human review; never rescore."""
import json
import sqlite3
from pathlib import Path

from .store import digest


def import_receipt(store, queue_directory, receipt, *, run_id, experiment_id, finding_id,
                   method_id, null, validity_policy, disclosure_boundary):
    path = Path(queue_directory).resolve() / "scoring.sqlite3"
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as c:
        exists = c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='aliases'").fetchone()
        alias = c.execute("SELECT canonical FROM aliases WHERE receipt=?", (receipt,)).fetchone() if exists else None
        canonical = alias[0] if alias else receipt
        row = c.execute("SELECT digest,payload,status,result FROM jobs WHERE receipt=?", (canonical,)).fetchone()
    if not row or row[2] != "completed" or row[3] is None:
        raise ValueError("Private evidence is unavailable; no scientific decision inferred")
    payload, evidence = json.loads(row[1]), json.loads(row[3])
    # Numerical method results can themselves report invalid sampling or unavailable inputs.
    # They remain evidence for human inspection, never an automatic pass/fail threshold.
    declared = payload.get("spec", {})
    if declared.get("experiment_id") and declared["experiment_id"] != experiment_id:
        raise ValueError("Declared experiment identity mismatch")
    if declared.get("method_id") and declared["method_id"] != method_id:
        raise ValueError("Declared method identity mismatch")
    return store.associate_review(receipt=canonical, run_id=run_id, experiment_id=experiment_id,
        finding_id=finding_id, method_id=method_id, null=null, validity_policy=validity_policy,
        evidence=evidence, provenance={"input_digest": row[0], "result_digest": digest(evidence),
                                      "association": "operator_declared", "declared_spec": declared},
        disclosure_boundary=disclosure_boundary)
