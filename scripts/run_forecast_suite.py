"""Run a frozen all-query graph-representation comparison, then evaluate sealed runs."""
import argparse
import asyncio
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import random
import time

from dnhacksbio.forecasting.evaluation import compare_forecasts
from dnhacksbio.forecasting.reasoning import CONDITIONS, arun_reasoning_comparison, prepare_reasoning
from dnhacksbio.forecasting.scoring import score_candidates
from dnhacksbio.forecasting.snapshots import load_scenario


BUDGET = dict(steps=2, candidate_limit=36, evidence_limit=12, output_tokens=6000, timeout=90)
BOOTSTRAP = dict(samples=2000, seed=20260905, confidence=0.95)


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def save_new(path, value):
    """Never overwrite a protocol, run, or evaluation from an earlier attempt."""
    with Path(path).open("x") as stream:
        stream.write(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")


def prepare_suite(scenario, *, model, fixture=False):
    queries = []
    for index, query_id in enumerate(sorted({c["query_id"] for c in scenario["candidates"]})):
        plan = prepare_reasoning(scenario, query_id=query_id, **{key: BUDGET[key]
            for key in ("steps", "candidate_limit", "evidence_limit")})
        expected = {c["id"] for c in scenario["candidates"] if c["query_id"] == query_id}
        if {c["id"] for c in plan["candidates"]} != expected:
            raise ValueError("fixed candidate limit would omit historical candidates")
        queries.append({"query_id": query_id, "file": f"query-{index + 1:02d}.json", **plan})
    return {"schema_version": "forecast-suite/v1", "scenario_id": scenario["id"],
        "historical_packet_sha256": digest(scenario), "origin": "illustrative" if fixture else "model",
        "model": model, "conditions": list(CONDITIONS), "budget": dict(BUDGET),
        "max_concurrent_queries": 3, "planned_model_calls": len(queries) * 3 * BUDGET["steps"],
        "created_at": datetime.now(timezone.utc).isoformat(), "queries": queries,
        "candidate_count": sum(len(q["candidates"]) for q in queries),
        "cohort_rule": "all distinct historical query IDs in sorted order; all eligible candidates per query",
        "attempt_rule": "one attempt per condition/step; no retries or outcome-based tuning",
        "evaluation_rule": "load outcomes only after every query artifact is saved and hash-sealed; compare only queries complete in every condition",
        "primary_metrics": ["macro average precision over eligible queries", "macro precision@5 over all complete queries"],
        "bootstrap": dict(BOOTSTRAP),
        "limitations": ["Predicts later CIViC curation, not later scientific publications or first discovery.",
            "Modern pretrained models can know post-cutoff facts despite historical-only supplied evidence.",
            "Citation identity validation is not an entailment check.",
            "Independent query scores are not calibrated across queries; pooled metrics are secondary.",
            "Query bootstrap is exploratory; queries share biological entities and source papers."]}


async def run_suite(scenario, output, *, model, fixture=False, completion=None):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError("suite output directory must be empty; existing attempts are immutable")
    manifest = prepare_suite(scenario, model=model, fixture=fixture or completion is not None)
    save_new(output / "manifest.json", manifest)
    semaphore = asyncio.Semaphore(manifest["max_concurrent_queries"])

    async def run_query(plan):
        async with semaphore:
            start = time.monotonic()
            try:
                result = await arun_reasoning_comparison(scenario, model=model, fixture=fixture,
                    completion=completion, query_id=plan["query_id"], **BUDGET)
            except Exception as error:
                result = {"comparison_ready": False, "conditions": {},
                          "diagnostics": [f"{type(error).__name__}: {error}"]}
            record = {"query_id": plan["query_id"], "elapsed_seconds": time.monotonic() - start,
                      "finished_at": datetime.now(timezone.utc).isoformat(), "result": result}
            save_new(output / plan["file"], record)
            print(json.dumps({"query_id": plan["query_id"], "comparison_ready": result["comparison_ready"],
                              "elapsed_seconds": round(record["elapsed_seconds"], 2)}), flush=True)
            return record

    records = await asyncio.gather(*(run_query(plan) for plan in manifest["queries"]))
    seal = {"sealed_at": datetime.now(timezone.utc).isoformat(),
        "manifest_sha256": sha256((output / "manifest.json").read_bytes()).hexdigest(),
        "query_files_sha256": {plan["file"]: sha256((output / plan["file"]).read_bytes()).hexdigest()
                               for plan in manifest["queries"]},
        "completed_queries": sum(r["result"]["comparison_ready"] for r in records),
        "attempted_queries": len(records)}
    save_new(output / "sealed.json", seal)
    return manifest, records


def paired_bootstrap(models, *, samples=2000, seed=20260905, confidence=0.95):
    result = {}
    for baseline in ("flat_log", "static_graph", "popularity"):
        for metric in ("average_precision", "precision_at_5"):
            def value(model, query):
                row = models[model]["queries"][query]
                return row["average_precision"] if metric == "average_precision" else row["at_k"]["5"]["precision"]
            query_ids = [q for q in sorted(models["evolving_graph"]["queries"])
                         if value("evolving_graph", q) is not None and value(baseline, q) is not None]
            differences = [value("evolving_graph", q) - value(baseline, q) for q in query_ids]
            if not differences:
                result[f"evolving_graph-minus-{baseline}/{metric}"] = {"eligible_queries": 0,
                    "estimate": None, "interval": None}
                continue
            rng = random.Random(seed)
            means = sorted(sum(rng.choices(differences, k=len(differences))) / len(differences)
                           for _ in range(samples))
            tail = (1 - confidence) / 2
            result[f"evolving_graph-minus-{baseline}/{metric}"] = {
                "eligible_queries": len(query_ids), "query_ids": query_ids,
                "estimate": sum(differences) / len(differences),
                "interval": [means[int(tail * (samples - 1))], means[int((1 - tail) * (samples - 1))]]}
    return {"method": "paired query bootstrap of mean differences, percentile interval; exploratory with shared sources",
            "samples": samples, "seed": seed, "confidence": confidence, "comparisons": result}


def evaluate_suite(scenario, output, outcome_path):
    """Verify every saved run before the first outcome-file read."""
    output = Path(output)
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    seal = json.loads((output / "sealed.json").read_text())
    if sha256(manifest_path.read_bytes()).hexdigest() != seal["manifest_sha256"]:
        raise ValueError("suite manifest changed after sealing")
    if manifest["historical_packet_sha256"] != digest(scenario):
        raise ValueError("historical packet does not match sealed suite")
    records = []
    for plan in manifest["queries"]:
        raw = (output / plan["file"]).read_bytes()
        if sha256(raw).hexdigest() != seal["query_files_sha256"][plan["file"]]:
            raise ValueError("query artifact changed after sealing")
        records.append(json.loads(raw))
    # This is deliberately the first use of the outcome path.
    outcomes = json.loads(Path(outcome_path).read_text())
    if outcomes["scenario_id"] != scenario["id"] or outcomes["horizon"] != scenario["horizon"]:
        raise ValueError("outcome packet does not match scenario/horizon")
    if {row["candidate_id"] for row in outcomes["outcomes"]} != {c["id"] for c in scenario["candidates"]}:
        raise ValueError("outcome cohort does not match historical cohort")
    observed = {row["candidate_id"] for row in outcomes["outcomes"] if row["observed"]}
    complete = {r["query_id"] for r in records if r["result"].get("comparison_ready")
                and all(r["result"].get("conditions", {}).get(name, {}).get("status") == "complete"
                        for name in CONDITIONS)}
    selected = [c for c in scenario["candidates"] if c["query_id"] in complete]
    selected_ids = {c["id"] for c in selected}
    failures, usage = [], {}
    forecasts = {name: [] for name in (*CONDITIONS, "popularity")}
    for plan, record in zip(manifest["queries"], records):
        result = record["result"]
        if record["query_id"] not in complete:
            failures.append({"query_id": record["query_id"],
                "diagnostics": result.get("diagnostics", []),
                "conditions": {name: {"status": run.get("status"), "diagnostics": run.get("diagnostics", [])}
                               for name, run in result.get("conditions", {}).items()}})
        for name, run in result.get("conditions", {}).items():
            totals = usage.setdefault(name, {"attempted_calls": 0, "reported_calls": 0,
                "input_tokens": 0, "output_tokens": 0, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0})
            for event in run.get("events", []):
                totals["attempted_calls"] += event.get("attempts", 1)
                for entry in event.get("usage", []):
                    totals["reported_calls"] += 1
                    for key in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"):
                        totals[key] += entry.get(key, 0) or 0
            if record["query_id"] in complete:
                forecasts[name].extend(run["forecasts"])
        if record["query_id"] in complete:
            scoped = {**scenario, "candidates": plan["candidates"]}
            evidence_ids = {eid for batch in plan["evidence_batches"] for eid in batch}
            forecasts["popularity"].extend(score_candidates(scoped, evidence_ids=evidence_ids, method="popularity"))
    report = compare_forecasts(selected, forecasts,
        [row for row in outcomes["outcomes"] if row["candidate_id"] in selected_ids],
        provenance={"scenario_id": scenario["id"], "dataset_id": scenario["dataset"],
            "origin": manifest["origin"], "suite_manifest_sha256": seal["manifest_sha256"]},
        protocol={"budget": manifest["budget"], "primary": "query-macro metrics; pooled scores are not calibrated across queries"},
        model_metadata={name: {"model": manifest["model"] if name != "popularity" else "historical target degree",
            "origin": manifest["origin"] if name != "popularity" else "computed",
            "evidence_budget": "same frozen 12-record schedule per query", "inference_budget": "two calls" if name != "popularity" else "no model calls"}
            for name in forecasts}) if selected else None
    historical_urls = {e.get("url") for e in scenario["evidence"] if e.get("url")}
    future_evidence = outcomes.get("evidence", [])
    evaluation = {"schema_version": "forecast-suite-evaluation/v1", "origin": manifest["origin"],
        "coverage": {"planned_queries": len(manifest["queries"]), "complete_queries": len(complete),
            "complete_query_ids": sorted(complete), "planned_candidates": len(scenario["candidates"]),
            "evaluated_candidates": len(selected), "planned_observed": len(observed),
            "evaluated_observed": len(observed & selected_ids), "excluded_observed": len(observed - selected_ids)},
        "failures": failures, "usage": usage, "comparison": report,
        "bootstrap": paired_bootstrap(report["models"], **manifest["bootstrap"]) if report else None,
        "source_audit": {"later_evidence_records": len(future_evidence),
            "publication_years": sorted({e["publication_year"] for e in future_evidence if e.get("publication_year")}),
            "shared_historical_source_urls": sum(e.get("url") in historical_urls for e in future_evidence),
            "interpretation": "Later database curation can cite older papers already represented in historical inputs; not a future-publication benchmark."},
        "outcomes_sha256": sha256(Path(outcome_path).read_bytes()).hexdigest()}
    save_new(output / "evaluation.json", evaluation)
    return evaluation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("historical", type=Path)
    parser.add_argument("--outcomes", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--fixture", action="store_true")
    args = parser.parse_args()
    from dnhacksbio.llm import SONNET
    scenario = load_scenario(args.historical)
    asyncio.run(run_suite(scenario, args.output_dir, model=SONNET, fixture=args.fixture))
    evaluation = evaluate_suite(scenario, args.output_dir, args.outcomes)
    print(json.dumps(evaluation["coverage"], sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
