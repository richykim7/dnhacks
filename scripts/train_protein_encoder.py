#!/usr/bin/env python3
"""Bounded development training; CUDA serializes on /tmp/dnhacks-gpu.lock."""
import argparse
from dnhacksbio.protein_design import load
from dnhacksbio.protein_encoder import fit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", required=True)
    parser.add_argument("--validation", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--kind", choices=("pca", "denoising"), default="pca")
    parser.add_argument("--latent", type=int, default=32)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-features", type=int, default=8000)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    args = parser.parse_args()
    encoder = fit(load(args.train), load(args.validation), kind=args.kind, latent=args.latent,
                  epochs=args.epochs, seed=args.seed, max_features=args.max_features, device=args.device)
    encoder.save(args.output)


if __name__ == "__main__":
    main()
