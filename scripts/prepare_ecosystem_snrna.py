#!/usr/bin/env python3
import argparse
from dnhacksbio.ecosystem_snrna import acquire, prepare

p = argparse.ArgumentParser(
    description="Prepare original snRNA counts with pre-frozen donor roles"
)
p.add_argument("--root", required=True)
p.add_argument("--acquire", action="store_true")
a = p.parse_args()
print(acquire(a.root) if a.acquire else prepare(a.root))
