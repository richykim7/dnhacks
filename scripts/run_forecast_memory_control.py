"""No-retrieval memory control: the model scores every sealed candidate with zero evidence.

A modern model may already know post-cutoff biology. If it ranks the later-recorded associations
well while seeing no historical evidence at all, evidence-conditioned model results on this packet
measure recall, not reasoning over the graph. The control is scored on identical rows against the
saved structural and popularity comparators, using the existing evaluator.

uv run python scripts/run_forecast_memory_control.py \
  demo/forecasting/scenarios/civic-2018-2022/historical.json \
  --run demo/forecasting/runs/civic-2018-2022-greedy.json \
  --outcomes demo/forecasting/scenarios/civic-2018-2022/outcomes.json \
  --output-dir demo/forecasting/reasoning/civic-no-retrieval

`--fixture` writes explicitly illustrative scores with no model calls.
"""

import argparse
import asyncio
import json
import math
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from dnhacksbio.forecasting.evaluation import compare_forecasts

SYSTEM = """You are given a historical cutoff date, one cancer variant, and candidate therapy groups.
No evidence, sources, tools or browsing are provided. Using only your own knowledge, estimate for each
candidate the probability that the CIViC database records an association between this variant and this
therapy group by the horizon date. Return one JSON object {"forecasts": [{"candidate_id": "...",
"score": 0.0-1.0}]} that scores every candidate exactly once. Emit JSON only."""


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def save_new(path, value):
    if path.exists():
        raise FileExistsError(f"refusing to overwrite {path}")
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def prepare(scenario, *, model, fixture):
    labels = {n["id"]: n["label"] for n in scenario["nodes"]}
    by_query = {}
    for c in scenario["candidates"]:
        by_query.setdefault(c["query_id"], []).append(c)
    queries = []
    for qid in sorted(by_query):
        rows = sorted(by_query[qid], key=lambda c: c["id"])
        packet = {"cutoff": scenario["cutoff"], "horizon": scenario["horizon"],
                  "query": {"id": qid, "label": labels[qid]},
                  "candidates": [{"candidate_id": c["id"], "therapy": labels[c["target"]]} for c in rows],
                  "evidence": []}
        queries.append({"query_id": qid, "candidate_ids": [c["id"] for c in rows],
                        "prompt": packet, "prompt_sha256": digest(packet)})
    return {"schema_version": "forecast-memory-control/v1", "scenario_id": scenario["id"],
            "historical_packet_sha256": digest(scenario), "created_at": datetime.now(timezone.utc).isoformat(),
            "origin": "illustrative" if fixture else "model", "model": None if fixture else model,
            "budget": {"calls_per_query": 1, "max_attempts_per_call": 1, "effort": "low", "thinking": False,
                       "max_turns_per_call": 1, "tools_disabled": True, "evidence_records": 0},
            "max_concurrent_queries": 3, "candidate_count": len(scenario["candidates"]),
            "attempt_rule": "one attempt per query; no retries, repair or outcome-based tuning",
            "evaluation_rule": "load outcomes only after every query artifact is saved and hash-sealed; "
                               "compare only complete queries, on identical rows for every comparator",
            "queries": queries}


def validate(response, candidate_ids):
    if not isinstance(response, dict) or set(response) != {"forecasts"} or not isinstance(response["forecasts"], list):
        return ["response must be {forecasts: [...]}"]
    errors, seen = [], set()
    for i, row in enumerate(response["forecasts"]):
        if not isinstance(row, dict) or set(row) != {"candidate_id", "score"}:
            errors.append(f"forecasts[{i}]: unexpected/missing fields")
            continue
        cid, score = row["candidate_id"], row["score"]
        if cid not in candidate_ids or cid in seen:
            errors.append(f"forecasts[{i}]: unknown/duplicate candidate_id")
        seen.add(cid)
        if type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 1:
            errors.append(f"forecasts[{i}]: score must be finite within [0,1]")
    if seen != candidate_ids:
        errors.append("forecasts must score exactly the frozen candidate set")
    return errors


async def fixture_completion(prompt, **kwargs):
    """Illustrative provider: deterministic scores from candidate IDs; no knowledge, no inference."""
    packet = json.loads(prompt)
    return {"forecasts": [{"candidate_id": c["candidate_id"],
                           "score": int(sha256(c["candidate_id"].encode()).hexdigest()[:4], 16) / 0xFFFF}
                          for c in packet["candidates"]]}, {}


async def live_completion(prompt, **kwargs):
    from dnhacksbio.llm import acomplete, parse_json
    capture = {}
    with TemporaryDirectory(prefix="forecast-memory-control-") as cwd:
        text = await acomplete(prompt, cwd=cwd, capture=capture, **kwargs)
    usage = next((m.get("usage") or {} for m in reversed(capture.get("messages", []))
                  if isinstance(m, dict) and m.get("type") == "ResultMessage"), {})
    try:
        return parse_json(text), {"usage": usage, "raw_text": text}
    except Exception as exc:  # noqa: BLE001 - the raw text is the diagnostic
        return {"parse_error": repr(exc)}, {"usage": usage, "raw_text": text}


async def run(scenario, output, *, model, fixture, output_tokens, timeout, completion=None):
    output.mkdir(parents=True, exist_ok=False)
    manifest = prepare(scenario, model=model, fixture=fixture)
    save_new(output / "manifest.json", manifest)
    completion = completion or (fixture_completion if fixture else live_completion)
    semaphore = asyncio.Semaphore(manifest["max_concurrent_queries"])

    async def one(index, plan):
        prompt = json.dumps(plan["prompt"], sort_keys=True, separators=(",", ":"))
        record = {"query_id": plan["query_id"], "prompt_sha256": plan["prompt_sha256"], "origin": manifest["origin"]}
        async with semaphore:
            try:
                response, meta = await asyncio.wait_for(completion(
                    prompt, model=model, system=SYSTEM, effort="low", max_turns=1, thinking=False,
                    tools_disabled=True, max_output_tokens=output_tokens, max_attempts=1), timeout)
                errors = validate(response, set(plan["candidate_ids"]))
                record.update(meta, response=response, errors=errors, status="complete" if not errors else "invalid")
            except Exception as exc:  # noqa: BLE001 - timeouts and SDK failures stay visible
                record.update(errors=[repr(exc)], status="failed")
        save_new(output / f"query-{index:02d}.json", record)

    await asyncio.gather(*(one(i, plan) for i, plan in enumerate(manifest["queries"], 1)))
    files = sorted(p.name for p in output.glob("query-*.json"))
    save_new(output / "sealed.json", {"sealed_at": datetime.now(timezone.utc).isoformat(),
                                      "files_sha256": {f: sha256((output / f).read_bytes()).hexdigest() for f in files}})
    return manifest


def evaluate(scenario, output, run_path, outcome_path):
    manifest = json.loads((output / "manifest.json").read_text())
    seal = json.loads((output / "sealed.json").read_text())
    for name, expected in seal["files_sha256"].items():
        if sha256((output / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"{name} changed after sealing")
    if manifest["historical_packet_sha256"] != digest(scenario):
        raise ValueError("historical packet does not match the sealed manifest")
    saved_run = json.loads(Path(run_path).read_text())
    if saved_run["scenario_sha256"] != manifest["historical_packet_sha256"]:
        raise ValueError("saved structural run was computed on a different historical packet")
    records = [json.loads((output / name).read_text()) for name in seal["files_sha256"]]
    complete = {r["query_id"] for r in records if r["status"] == "complete"}
    excluded = {r["query_id"]: r["errors"][:3] for r in records if r["status"] != "complete"}
    cohort = [c for c in scenario["candidates"] if c["query_id"] in complete]
    if not cohort:
        raise ValueError("no query completed; nothing to evaluate")
    ids = {c["id"] for c in cohort}
    forecasts = {"no_retrieval": [row for r in records if r["status"] == "complete" for row in r["response"]["forecasts"]]}
    for name, key in (("structural_full_graph", "full_historical_graph"), ("popularity", "popularity")):
        forecasts[name] = [{"candidate_id": f["candidate_id"], "score": f["score"]}
                           for f in saved_run["comparisons"][key] if f["candidate_id"] in ids]
    outcomes = json.loads(Path(outcome_path).read_text())
    if outcomes["scenario_id"] != scenario["id"] or outcomes["horizon"] != scenario["horizon"]:
        raise ValueError("outcomes do not match the historical scenario")
    rows = [o for o in outcomes["outcomes"] if o["candidate_id"] in ids]
    usage = {}
    for r in records:
        for k, v in (r.get("usage") or {}).items():
            if isinstance(v, (int, float)):
                usage[k] = usage.get(k, 0) + v
    report = compare_forecasts(
        [{"id": c["id"], "source": c["source"], "target": c["target"], "query_id": c["query_id"]} for c in cohort],
        forecasts, rows, ks=(5, 10),
        provenance={"scenario_id": scenario["id"], "origin": manifest["origin"], "control": "no-retrieval memory",
                    "historical_packet_sha256": manifest["historical_packet_sha256"],
                    "outcomes_sha256": sha256(Path(outcome_path).read_bytes()).hexdigest(),
                    "structural_run_id": saved_run["id"]},
        protocol={"cutoff": scenario["cutoff"], "horizon": scenario["horizon"],
                  "comparison": "identical complete-query rows for every comparator",
                  "budget_match": {"status": "different",
                                   "note": "no_retrieval sees zero evidence; comparators use the full historical graph"},
                  "reading": "high no_retrieval scores indicate post-cutoff recall, which caps what any "
                             "evidence-conditioned model result on this packet can show"},
        model_metadata={"no_retrieval": {"model": manifest["model"], "origin": manifest["origin"], "evidence_records": 0},
                        "structural_full_graph": {"origin": "computed", "model": saved_run["model"]},
                        "popularity": {"origin": "computed", "model": "historical target degree"}})
    report["coverage"] = {"planned_queries": len(records), "complete_queries": len(complete),
                          "evaluated_candidates": len(ids), "planned_candidates": manifest["candidate_count"],
                          "evaluated_observed": sum(o["observed"] for o in rows),
                          "planned_observed": sum(o["observed"] for o in outcomes["outcomes"]),
                          "excluded_queries": excluded}
    report["usage"] = usage
    save_new(output / "evaluation.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("historical", type=Path)
    parser.add_argument("--run", type=Path, required=True, help="saved structural run with comparisons")
    parser.add_argument("--outcomes", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--fixture", action="store_true", help="illustrative provider; no model calls")
    parser.add_argument("--model", default=None)
    parser.add_argument("--output-tokens", type=int, default=4000)
    parser.add_argument("--timeout", type=float, default=180)
    args = parser.parse_args()
    if args.model is None and not args.fixture:
        from dnhacksbio.llm import SONNET
        args.model = SONNET
    scenario = json.loads(args.historical.read_text())
    asyncio.run(run(scenario, args.output_dir, model=args.model, fixture=args.fixture,
                    output_tokens=args.output_tokens, timeout=args.timeout))
    report = evaluate(scenario, args.output_dir, args.run, args.outcomes)
    cov = report["coverage"]
    print(f"complete queries {cov['complete_queries']}/{cov['planned_queries']}; "
          f"candidates {cov['evaluated_candidates']}; observed {cov['evaluated_observed']}")
    for name, result in report["models"].items():
        o = result["overall"]
        ap, au = o["average_precision"], o["auroc"]
        print(f"{name:24s} AUROC={au if au is None else round(au, 3)} AP={ap if ap is None else round(ap, 3)} "
              f"P@5={o['at_k']['5']['precision']:.2f} P@10={o['at_k']['10']['precision']:.2f}")


if __name__ == "__main__":
    main()
