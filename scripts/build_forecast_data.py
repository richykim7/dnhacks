"""Build a reproducible historical packet from two locally cached CIViC releases."""
import argparse
import hashlib
import json
from pathlib import Path

from dnhacksbio.forecasting.snapshots import build_civic_scenario


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--historical", type=Path, default=Path("data/cache/graph-forecasting/civic-01-Jan-2018.tsv"))
    parser.add_argument("--future", type=Path, default=Path("data/cache/graph-forecasting/civic-01-Mar-2022.tsv"))
    parser.add_argument("--output", type=Path, default=Path("demo/forecasting/scenarios/civic-2018-2022"))
    parser.add_argument("--max-variants", type=int, default=24)
    parser.add_argument("--max-therapies", type=int, default=36)
    args = parser.parse_args()
    scenario, outcomes = build_civic_scenario(args.historical, args.future,
        max_variants=args.max_variants, max_therapies=args.max_therapies)
    args.output.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for name, record in [("historical.json", scenario), ("outcomes.json", outcomes)]:
        payload = (json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
        (args.output / name).write_bytes(payload)
        hashes[name] = hashlib.sha256(payload).hexdigest()
    manifest = {"scenario_id": scenario["id"], "files_sha256": hashes,
        "sources": [scenario["manifest"]["source"], outcomes["manifest"]["source"]],
        "license": "CC0-1.0", "license_url": scenario["manifest"]["license_url"],
        "counts": {key: len(scenario[key]) for key in ("nodes", "claims", "evidence", "candidates")},
        "observed_by_horizon": sum(row["observed"] for row in outcomes["outcomes"]),
        "usage": "Scorers read historical.json only. outcomes.json and this audit manifest are evaluation/reveal inputs."}
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), **manifest["counts"],
                      "observed_by_horizon": manifest["observed_by_horizon"]}))


if __name__ == "__main__":
    main()
