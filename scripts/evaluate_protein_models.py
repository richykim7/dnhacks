#!/usr/bin/env python3
"""Evaluate one locked development seed and frozen baseline views."""
import argparse
from dnhacksbio.protein_data import write_json
from dnhacksbio.protein_validation import panel_mapping, evaluate

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", required=True)
    p.add_argument("--raw", required=True)
    p.add_argument("--panel", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    write_json(a.output, evaluate(a.data, a.raw, panel_mapping(a.panel)))
