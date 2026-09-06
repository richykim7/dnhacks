#!/usr/bin/env python3
"""Train the fixed CUDA malignant-versus-normal-ductal diagnostic."""

import argparse
from dnhacksbio.ecosystem_cna import train_malignancy

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--prepared", required=True)
p.add_argument("--output", required=True)
a = p.parse_args()
train_malignancy(a.prepared, a.output)
