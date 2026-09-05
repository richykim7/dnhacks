"""Read only frozen historical inputs and saved forecast runs, never outcomes.

Audits source sharing and graph revisions. Does not score forecasts, select
hypotheses, tune packet objectives, or assume source reuse eliminates extraction.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def audit(historical_path, run_paths):
    raw = historical_path.read_bytes()
    historical = json.loads(raw)
    if "outcomes" in historical:
        raise ValueError("historical input cannot contain outcomes")
    canonical = json.dumps(historical, sort_keys=True, separators=(",", ":"), allow_nan=False)
    snapshot_hash = hashlib.sha256(canonical.encode()).hexdigest()
    by_id = {row["id"]: row for row in historical["evidence"]}

    def source(evidence_id):
        row = by_id[evidence_id]
        return (row.get("source_type", ""), row.get("citation_id") or evidence_id)

    frequency = Counter(source(eid) for eid in by_id)
    outputs = []
    for path in run_paths:
        run_raw = path.read_bytes()
        run = json.loads(run_raw)
        if "outcomes" in run or run["scenario_sha256"] != snapshot_hash:
            raise ValueError("run must match the historical-only snapshot")
        revisions = run["revisions"]
        initial = set(revisions[0]["evidence_ids"])
        initial_sources = {source(eid) for eid in initial}
        previous, seen, counts = set(), set(), []
        for revision in revisions:
            current = set(revision["evidence_ids"])
            assert previous <= current <= by_id.keys()
            assert len(revision["forecasts"]) == len(historical["candidates"])
            current_sources = {source(eid) for eid in current}
            added = current - previous
            counts.append(dict(revision=revision["revision"], evidence_records=len(current),
                               source_documents=len(current_sources), claim_count=revision["claim_count"],
                               added_records=len(added), newly_encountered_sources=len(current_sources - seen)))
            previous, seen = current, current_sources
        new = previous - initial
        new_sources = {source(eid) for eid in new} - initial_sources
        assert len(new) == run["costs"]["evidence_acquisitions"]
        outputs.append(dict(file=path.name, sha256=hashlib.sha256(run_raw).hexdigest(),
                            origin=run["origin"], policy=run["policy"],
                            recorded_cost_unit=run["costs"]["unit"],
                            initial_records=len(initial), initial_sources=len(initial_sources),
                            additional_records=len(new), additional_source_documents=len(new_sources),
                            acquired_records_with_already_acquired_source=len(new)-len(new_sources),
                            fixed_candidates=len(historical["candidates"]), revisions=counts))
    return dict(historical_file=historical_path.name, historical_sha256=hashlib.sha256(raw).hexdigest(),
                scenario_canonical_sha256=snapshot_hash, cutoff=historical["cutoff"],
                historical_records=len(by_id), source_documents=len(frequency),
                sources_with_multiple_records=sum(n > 1 for n in frequency.values()),
                future_labels_read=False, forecast_scores_evaluated=False, runs=outputs,
                interpretation="Actual saved graph-construction replays, with recorded abstract per-evidence costs. Shared source identity demonstrates a possible reusable document stage; it does not establish reusable extraction, measured compute savings, complementarity, or future-action discovery. Candidate pool is fixed.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--historical", type=Path, required=True)
    parser.add_argument("--runs", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = audit(args.historical, args.runs)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps({k: v for k, v in output.items() if k != "runs"}))
    for run in output["runs"]:
        print(run["policy"], "records", run["additional_records"], "new source documents", run["additional_source_documents"])


if __name__ == "__main__":
    main()
