#!/usr/bin/env python3
"""Acquire and audit public Fudan protein data for a declared external benchmark."""
import argparse
from dnhacksbio.protein_external import prepare

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("raw", "cptac", "curated", "output"):
        p.add_argument("--"+name, required=True)
    a = p.parse_args()
    prepare(a.raw, a.cptac, a.curated, a.output)
