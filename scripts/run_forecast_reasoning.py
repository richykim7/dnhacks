#!/usr/bin/env python3
"""Save a three-condition reasoning run without opening any outcome packet."""
import argparse
import json
from pathlib import Path

from dnhacksbio.forecasting.reasoning import run_reasoning_comparison
from dnhacksbio.forecasting.snapshots import load_scenario


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("historical", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--fixture", action="store_true", help="explicit illustrative provider; no model calls")
    parser.add_argument("--model", default=None)
    parser.add_argument("--steps", type=int, default=2, choices=(2, 3))
    parser.add_argument("--candidate-limit", type=int, default=20)
    parser.add_argument("--evidence-limit", type=int, default=12)
    parser.add_argument("--query-id")
    parser.add_argument("--output-tokens", type=int, default=4000)
    parser.add_argument("--timeout", type=float, default=90)
    args = parser.parse_args()
    scenario = load_scenario(args.historical)
    result = run_reasoning_comparison(scenario, fixture=args.fixture, model=args.model,
        steps=args.steps, candidate_limit=args.candidate_limit, evidence_limit=args.evidence_limit,
        query_id=args.query_id, output_tokens=args.output_tokens, timeout=args.timeout)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    def save(name, value):
        (args.output_dir / name).write_text(json.dumps(value, separators=(",", ":"), sort_keys=True, allow_nan=False) + "\n")
    save("comparison.json", result)
    save("cohort.json", {key: scenario[key] for key in ("id", "dataset", "cutoff", "horizon")} |
         {"candidates": result["candidates"], "provenance": result["provenance"]})
    # An incomplete run must never leave a stale, apparently comparable score file.
    forecasts_path = args.output_dir / "forecasts.json"
    if result["comparison_ready"]:
        save("forecasts.json", {"models": {name: run["forecasts"] for name, run in result["conditions"].items()},
            "model_metadata": {name: {"dataset_id": scenario["dataset"], "origin": result["origin"],
                "model": result["provenance"]["model"], "budget_tag": result["protocol"]["budget_tag"]}
                for name in result["conditions"]}, "protocol": result["protocol"]})
    else:
        forecasts_path.unlink(missing_ok=True)
    print(json.dumps({"output_dir": str(args.output_dir), "origin": result["origin"],
        "comparison_ready": result["comparison_ready"], "candidates": len(result["candidates"]),
        "conditions": {name: {"status": run["status"], "diagnostics": run["diagnostics"]}
                       for name, run in result["conditions"].items()}}, indent=2))
    return 0 if result["comparison_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
