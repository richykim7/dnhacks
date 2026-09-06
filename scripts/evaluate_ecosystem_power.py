#!/usr/bin/env python3
"""Measure real frozen cellular critics through the native donor betting kernel."""

import argparse
from dnhacksbio.ecosystem_power import diagnose

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--models", required=True)
p.add_argument("--output", required=True)
p.add_argument("--streams", type=int, default=10000)
a = p.parse_args()
diagnose(a.models, a.output, streams=a.streams)
