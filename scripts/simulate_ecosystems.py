#!/usr/bin/env python3
"""Write reproducible CPU synthetic diagnostics to a local operator-selected file."""
import argparse
import json
from pathlib import Path
from dnhacksbio.ecosystem_simulations import run

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--output',required=True)
p.add_argument('--streams',type=int,default=10000)
p.add_argument('--seed',type=int,default=1701)
a=p.parse_args()
Path(a.output).write_text(json.dumps(run(streams=a.streams,seed=a.seed),indent=2,allow_nan=False)+'\n')
