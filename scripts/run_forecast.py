"""Build a computed replay from a historical scenario; never opens outcome files."""
import argparse
import json
from pathlib import Path

from dnhacksbio.forecasting.runner import run_scenario, save_run
from dnhacksbio.forecasting.selection import POLICIES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--policy", choices=POLICIES, default="greedy")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--rounds", type=int, default=4)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    scenario = json.loads(args.scenario.read_text())
    packet = run_scenario(scenario, policy=args.policy, batch_size=args.batch_size,
                          rounds=args.rounds, seed=args.seed)
    path = args.output or Path("demo/forecasting/runs") / f"{packet['id']}.json"
    save_run(packet, path)
    print(json.dumps({"path": str(path), "run_id": packet["id"],
                      "forecasts": len(packet["forecasts"]), "origin": packet["origin"]}))


if __name__ == "__main__":
    main()
