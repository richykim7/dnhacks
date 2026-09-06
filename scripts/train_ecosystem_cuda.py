#!/usr/bin/env python3
"""Train expanded cellular development models on CUDA under the shared lease."""

import argparse
from dnhacksbio.ecosystem_cuda import run, refresh_exact_pca

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--prepared", required=True)
p.add_argument("--output", required=True)
p.add_argument("--refresh-pca", action="store_true")
p.add_argument("--epochs", type=int, default=200)
p.add_argument("--seeds", default="2701")
p.add_argument("--lease", default="/tmp/dnhacks-gpu.lock")
a = p.parse_args()
if a.refresh_pca:
    refresh_exact_pca(a.prepared, a.output, a.lease)
else:
    run(
        a.prepared,
        a.output,
        epochs=a.epochs,
        seeds=tuple(map(int, a.seeds.split(","))),
        lease=a.lease,
    )
