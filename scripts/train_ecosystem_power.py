#!/usr/bin/env python3
"""Train CUDA cellular critics with study-held-out native-growth selection."""

import argparse
from dnhacksbio.ecosystem_power_training import run

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--models", required=True)
p.add_argument("--output", required=True)
a = p.parse_args()
run(a.models, a.output)
