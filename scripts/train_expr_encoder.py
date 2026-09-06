#!/usr/bin/env python3
"""Train a frozen encoder from a separate, one-row-per-unit TPM NPZ cohort."""
import argparse
import hashlib
from pathlib import Path

import numpy as np

from dnhacksbio.expr_encoder import fit_autoencoder, fit_pca


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("input", type=Path, help="NPZ containing X, genes, and units (no object arrays)")
    p.add_argument("output", type=Path)
    p.add_argument("--kind", choices=["pca", "autoencoder"], default="pca")
    p.add_argument("--source", required=True, help="dataset release/accession and exclusions")
    p.add_argument("--sampling", required=True, help="independent-unit sampling assumptions")
    p.add_argument("--unit-namespace", required=True, help="stable donor identifier system")
    p.add_argument("--components", type=int, default=64)
    p.add_argument("--hidden", type=int, default=512)
    p.add_argument("--epochs", type=int, default=100)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--device", default="cpu", help="autoencoder device: cpu or cuda[:index]")
    p.add_argument("--dtype", choices=["float32", "float64"], default="float64")
    args = p.parse_args()
    with np.load(args.input, allow_pickle=False) as data:
        kw = dict(genes=data["genes"], units=data["units"], source=args.source,
                  sampling=args.sampling, unit_namespace=args.unit_namespace, components=args.components)
        if args.kind == "pca":
            artifact = fit_pca(data["X"], **kw)
        else:
            artifact = fit_autoencoder(data["X"], **kw, hidden=args.hidden, epochs=args.epochs, seed=args.seed,
                                       device=args.device, dtype=args.dtype)
    artifact.manifest["input_sha256"] = hashlib.sha256(args.input.read_bytes()).hexdigest()
    artifact.save(args.output)
    print(f"Saved {args.kind} encoder: {args.output}")


if __name__ == "__main__":
    main()
