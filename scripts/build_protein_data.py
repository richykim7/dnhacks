#!/usr/bin/env python3
"""Acquire the frozen development allowlist and emit measured-protein cohorts."""
import argparse
from pathlib import Path
from dnhacksbio.protein_data import build, write_json

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--raw", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    cohorts, audit = build(a.raw)
    out = Path(a.output)
    out.mkdir(parents=True, exist_ok=False)
    for role, cohort in cohorts.items():
        write_json(out / (role.lower() + ".json"), cohort)
    write_json(out / "audit.json", audit)
    print("Development import complete; audited report written")
