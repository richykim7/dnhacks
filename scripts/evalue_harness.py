#!/usr/bin/env python3
"""Reproducible synthetic DAVT diagnostics. Simulation is not a validity proof."""
from __future__ import annotations

import argparse
from dataclasses import replace
import json
import math
from pathlib import Path
import time

import numpy as np
import torch

from dnhacksbio.evalues import from_log, p_to_e
from dnhacksbio.expr_encoder import fit_autoencoder, fit_pca
from dnhacksbio.learned_evalue import LearnedEConfig, SamplingContract, learned_two_sample_e


def interval(k, n):
    """Wilson 95% binomial interval; uncertainty for simulation rejection rates."""
    z = 1.959963984540054
    p = k / n
    den = 1 + z * z / n
    center = (p + z * z / (2 * n)) / den
    radius = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [max(0, center - radius), min(1, center + radius)]


def permutation_p(a, b, rng, permutations):
    """Fixed, multivariate mean-distance statistic and plus-one randomization p."""
    n = len(a)
    pooled = np.concatenate([a, b])
    observed = float(np.square(a.mean(0) - b.mean(0)).sum())
    count = 0
    for _ in range(permutations):
        order = rng.permutation(len(pooled))
        statistic = np.square(pooled[order[:n]].mean(0) - pooled[order[n:]].mean(0)).sum()
        count += int(statistic >= observed)
    return (count + 1) / (permutations + 1)


def leaked_wealth(a, b):
    """INVALID negative control: fit a lookup judge to the same labels it scores.

    On continuous synthetic data each vector is unique. Memorization assigns
    +2 to A and -2 to B, then scores those same rows. Under the null it should
    produce conspicuous false rejections. Never return this as valid evidence.
    """
    judge = {tuple(x): 2.0 for x in a}
    judge.update({tuple(x): -2.0 for x in b})
    return sum(math.log1p(math.tanh(judge[tuple(x)] - judge[tuple(y)])) for x, y in zip(a, b))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repetitions", type=int, default=100)
    parser.add_argument("--pairs", type=int, default=96)
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--permutations", type=int, default=999)
    parser.add_argument("--seed", type=int, default=104729)
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--scenarios", nargs="+", choices=["null", "mean_shift", "variance_shift", "discarded_signal"],
                        default=["null", "mean_shift", "variance_shift", "discarded_signal"])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--artifacts", type=Path, default=Path("data/processed/evalue-synthetic"))
    args = parser.parse_args()
    if args.repetitions < 1 or args.pairs < 48 or args.epochs < 1 or args.permutations < 1 or not 0 < args.alpha < 1:
        parser.error("positive budgets, at least 48 pairs, and alpha in (0,1) are required")
    torch.set_num_threads(1)  # CLI-owned process; library does not modify caller thread settings.
    args.artifacts.mkdir(parents=True, exist_ok=True)
    genes = [f"synthetic-{i}" for i in range(8)]
    # Separate fixed training seed, independent of all evaluation streams.
    training = np.exp(np.random.default_rng(271828).normal(size=(256, 8)))
    kw = dict(genes=genes, units=[f"train-{i}" for i in range(len(training))],
              source="synthetic lognormal, training seed 271828", sampling="iid synthetic units",
              unit_namespace="synthetic-training", components=4)
    fit_pca(training, **kw).save(args.artifacts / "pca.npz")
    fit_autoencoder(training, **kw, hidden=32, epochs=30, seed=314159).save(args.artifacts / "autoencoder.npz")
    config = LearnedEConfig(hidden=(16, 16), max_epochs=args.epochs, patience=5, lr=0.005)
    feature_contract = SamplingContract("synthetic", "generated normal features", "independent iid units")
    expression_contract = SamplingContract("synthetic", "generated lognormal TPM", "independent iid units",
                                           "synthetic-evaluation", "TPM")
    report = dict(schema=1, diagnostic_only=True, data="synthetic; no real-cohort power claim",
                  configuration=vars(args) | {"output": str(args.output), "artifacts": str(args.artifacts)},
                  training_seeds=[271828, 314159], scenarios={}, runs=[])
    start = time.perf_counter()
    for scenario_index, scenario in enumerate(args.scenarios):
        samples = {}
        for repetition in range(args.repetitions):
            seed = args.seed + 1000003 * scenario_index + repetition
            rng = np.random.default_rng(seed)
            a, b = rng.normal(size=(args.pairs, 8)), rng.normal(size=(args.pairs, 8))
            if scenario == "mean_shift":
                b[:, :2] += 0.8
            elif scenario == "variance_shift":
                b[:, :2] *= 2
            elif scenario == "discarded_signal":
                b[:, -1] += 1.5
            variants = {
                "identity": (a, b, genes, feature_contract, None),
                "pca": (np.exp(a), np.exp(b), genes, expression_contract, str(args.artifacts / "pca.npz")),
                "autoencoder": (np.exp(a), np.exp(b), genes, expression_contract, str(args.artifacts / "autoencoder.npz")),
                "scalar": (a[:, :1], b[:, :1], genes[:1], feature_contract, None),
                "fixed_projection": (a[:, :4], b[:, :4], genes[:4], feature_contract, None),
            }
            for method, (x, y, names, contract, encoder) in variants.items():
                tick = time.perf_counter()
                result = learned_two_sample_e(x, y, genes=names, sampling=contract,
                                             config=replace(config, seed=seed, encoder=encoder))
                record = dict(scenario=scenario, repetition=repetition, method=method, seed=seed,
                              seconds=time.perf_counter() - tick, result=result.to_dict())
                report["runs"].append(record)
                samples.setdefault(method, []).append((result.e_value, max(result.log_wealth_path) >= math.log(1 / args.alpha)))
            p = permutation_p(a, b, rng, args.permutations)
            samples.setdefault("permutation_p", []).append((p, p <= args.alpha))
            e = p_to_e(p)
            samples.setdefault("permutation_calibrated_e", []).append((e, e >= 1 / args.alpha))
            # Match the scored data budget of the valid test for the invalid control.
            leak = leaked_wealth(a[16:], b[16:])
            samples.setdefault("INVALID_label_memorization", []).append((from_log(leak), leak >= math.log(1 / args.alpha)))
            report["runs"].append(dict(scenario=scenario, repetition=repetition, seed=seed,
                                       permutation_p=p, calibrated_e=e, invalid_log_wealth=leak))
            if (repetition + 1) % 25 == 0:
                print(f"{scenario}: {repetition + 1}/{args.repetitions}", flush=True)
        summary = {}
        for method, values in samples.items():
            numeric = np.array([v for v, _ in values])
            crossing = int(sum(c for _, c in values))
            final = int(sum(v <= args.alpha if method == "permutation_p" else v >= 1 / args.alpha for v in numeric))
            summary[method] = dict(final_rejections=final, final_rate=final / args.repetitions,
                                   final_ci95=interval(final, args.repetitions),
                                   crossing_rejections=crossing, crossing_rate=crossing / args.repetitions,
                                   crossing_ci95=interval(crossing, args.repetitions),
                                   quantiles=dict(zip(["q00", "q50", "q90", "q99", "q100"],
                                                      map(float, np.quantile(numeric, [0, .5, .9, .99, 1])))))
        report["scenarios"][scenario] = summary
        print(json.dumps({"scenario": scenario, "repetitions": args.repetitions,
                          "final_rates": {m: s["final_rate"] for m, s in summary.items()}}), flush=True)
    report["seconds"] = time.perf_counter() - start
    report["limitations"] = ["Null simulation does not prove validity.",
                              "Fixed mean-distance permutation statistic is not an omnibus characteristic-kernel test.",
                              "All methods receive the same total pairs; DAVT reserves two burn-in batches.",
                              "Fixed projection omits the shifted coordinate in discarded_signal.",
                              "Wealth has heavy tails; rejection intervals and quantiles do not certify its expectation.",
                              "These are synthetic benchmarks, not evidence of biological utility."]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(f"Saved {args.output}; elapsed {report['seconds']:.1f}s", flush=True)


if __name__ == "__main__":
    main()
