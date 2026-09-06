#!/usr/bin/env python3
"""Fit separate malignant and CAF encoders on the frozen untreated donor split."""

import argparse
from dnhacksbio.ecosystem_cna_training import run, train_critics

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--prepared", required=True)
p.add_argument("--output", required=True)
p.add_argument("--critics", action="store_true")
a = p.parse_args()
(train_critics if a.critics else run)(a.prepared, a.output)
