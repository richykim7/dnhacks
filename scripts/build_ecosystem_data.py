#!/usr/bin/env python3
"""Prepare independently frozen Peng development count panels from original files."""
import argparse
import json
from dnhacksbio.ecosystem_data import prepare_peng, prepare_lin, acquire
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--root',required=True)
p.add_argument('--source',choices=['peng','lin','acquire'],default='peng')
a=p.parse_args()
print(json.dumps({'peng':prepare_peng,'lin':prepare_lin,'acquire':acquire}[a.source](a.root),indent=2))
