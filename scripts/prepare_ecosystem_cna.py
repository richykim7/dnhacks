#!/usr/bin/env python3
"""Freeze or acquire the original CUIMC cellular development source."""

import argparse
from dnhacksbio.ecosystem_cna import acquire, freeze, extract_annotations, prepare

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--root", default="data/interim/ecosystems/cna")
p.add_argument("--acquire", action="store_true")
p.add_argument("--annotations", action="store_true")
p.add_argument("--prepare", action="store_true")
p.add_argument("--panel", default="data/interim/ecosystems/expansion/audit/panel.json")
p.add_argument("--allow-missing-author-cells", action="store_true")
a = p.parse_args()
if a.acquire:
    print(acquire(a.root))
elif a.annotations:
    print(extract_annotations(a.root))
elif a.prepare:
    print(
        prepare(
            a.root, a.panel, allow_missing_author_cells=a.allow_missing_author_cells
        )
    )
else:
    print({"donors": len(freeze(a.root)["samples"]), "private_confirmation": False})
