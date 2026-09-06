#!/usr/bin/env python3
"""Evaluate an existing frozen native critic on new author-defined compartments."""

import argparse
from dnhacksbio.ecosystem_cna import evaluate_existing_critic

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--training-views", required=True)
p.add_argument("--new-views", required=True)
p.add_argument("--weights", required=True)
p.add_argument("--output", required=True)
a = p.parse_args()
evaluate_existing_critic(a.training_views, a.new_views, a.weights, a.output)
