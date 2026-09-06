#!/usr/bin/env python3
import argparse
from dnhacksbio.ecosystem_snrna import evaluate

p = argparse.ArgumentParser(
    description="Evaluate frozen cellular models on snRNA using CUDA"
)
p.add_argument("--prepared", required=True)
p.add_argument("--models", required=True)
p.add_argument("--output", required=True)
a = p.parse_args()
evaluate(a.prepared, a.models, a.output)
