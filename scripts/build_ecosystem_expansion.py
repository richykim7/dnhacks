#!/usr/bin/env python3
"""Build sparse original-study packs for GPU cellular development."""

import argparse, json
from dnhacksbio.ecosystem_expansion import prepare, acquire

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--root", required=True)
p.add_argument("--action", choices=["acquire", "prepare"], default="prepare")
a = p.parse_args()
print(json.dumps((acquire if a.action == "acquire" else prepare)(a.root), indent=2))
