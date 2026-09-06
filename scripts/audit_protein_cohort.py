#!/usr/bin/env python3
"""Operator-only audit: creates a private report, never prints cohort counts."""
import argparse
import json
import os
from dnhacksbio.protein_design import audit, load


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", required=True)
    parser.add_argument("--panel", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--min-coverage", type=float, default=0.8)
    args = parser.parse_args()
    result = audit(load(args.cohort), load(args.panel), min_coverage=args.min_coverage)
    with open(args.output, "x", opener=lambda p, flags: os.open(p, flags, 0o600)) as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
