#!/usr/bin/env python3
"""Run 10,000 cheap streams per diagnostic case, without touching real observations."""
import argparse
from dnhacksbio.protein_native_diagnostics import run
from dnhacksbio.protein_data import write_json

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    write_json(args.output, run())
