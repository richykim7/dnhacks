"""Evaluate complete forecasting runs against a separate outcome file.

uv run python scripts/evaluate_forecasts.py --scenario scenario.json \
  --outcomes outcomes.json --forecasts predictions.json --output report.json
"""

import argparse
import json
from pathlib import Path

from dnhacksbio.forecasting.evaluation import compare_forecasts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", type=Path, required=True)
    parser.add_argument("--outcomes", type=Path, required=True)
    parser.add_argument("--forecasts", type=Path, required=True,
                        help="JSON mapping model IDs to forecasts, or {models, model_metadata}")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--k", type=int, nargs="+", default=[5, 10])
    args = parser.parse_args()
    try:
        scenario = json.loads(args.scenario.read_text())
        outcomes = json.loads(args.outcomes.read_text())
        predictions = json.loads(args.forecasts.read_text())
        if isinstance(outcomes, dict):
            if outcomes.get("scenario_id", scenario["id"]) != scenario["id"]:
                raise ValueError("outcomes scenario_id does not match scenario")
            if "horizon" in outcomes and outcomes["horizon"] != scenario.get("horizon"):
                raise ValueError("outcomes horizon does not match scenario")
        models = predictions.get("models", predictions)
        report = compare_forecasts(
            scenario["candidates"], models,
            outcomes["outcomes"] if isinstance(outcomes, dict) else outcomes,
            ks=args.k,
            provenance={"scenario_id": scenario["id"], "dataset_id": scenario.get("dataset_id", scenario["id"]),
                        "dataset": scenario.get("dataset"),
                        "manifest": scenario.get("manifest", {}),
                        "input_files": {key: str(getattr(args, key))
                                        for key in ("scenario", "forecasts", "outcomes")}},
            protocol={"cutoff": scenario.get("cutoff"), "horizon": scenario.get("horizon")},
            model_metadata=predictions.get("model_metadata", {}) if "models" in predictions else {},
        )
        text = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text)
        else:
            print(text, end="")
    except (ValueError, KeyError, OSError, TypeError) as error:
        parser.exit(2, f"evaluation failed: {error}\n")


if __name__ == "__main__":
    main()
