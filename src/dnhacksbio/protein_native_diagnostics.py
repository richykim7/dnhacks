"""Cheap generated fresh-donor diagnostics of the actual odd-contrast kernel.

The vectorized critic is a predictable linear witness, selected on the last past
batch; this is not a 10,000-stream benchmark of neural Adam optimization. The kernel
is imported from learned_evalue and the same two-burn-in schedule is preserved.
"""
from __future__ import annotations

import math
import time
import numpy as np
import torch
from .learned_evalue import _log_payoffs


def interval(successes, n):
    """Wilson 95% binomial interval, including zero events."""
    z = 1.959963984540054
    p = successes/n
    center = (p + z*z/(2*n)) / (1+z*z/n)
    half = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/(1+z*z/n)
    return [max(0., center-half), min(1., center+half)]


def factors(a, b, weights):
    class Witness:
        def __call__(self, x):
            return (x * weights[:, None, :]).sum(-1)
    with torch.no_grad():
        result = _log_payoffs(Witness(), a, b, 4.).reshape(a.shape[:2])
    return result


def streams(case, *, n=10000, pairs=48, seed=0, effect=.4):
    if n < 1 or pairs < 24:
        raise ValueError("Invalid diagnostic budget")
    rng = np.random.default_rng(seed)
    shape = (n, pairs, 6)
    if case == "heavy_tail_null":
        x, y = rng.standard_t(3, shape), rng.standard_t(3, shape)
    else:
        x, y = rng.normal(size=shape), rng.normal(size=shape)
    if case in {"shift", "batch_shift"}:
        x[:, :, 0] += effect
    elif case == "nonlinear":
        x[:, :, 0] *= 1.5
        x, y = x*x, y*y
    elif case in {"missingness_null", "missingness_alternative"}:
        mx = rng.random(shape) > .1
        my = rng.random(shape) > (.4 if case == "missingness_alternative" else .1)
        x = np.concatenate((x*mx, mx), axis=2)
        y = np.concatenate((y*my, my), axis=2)
    elif case not in {"normal_null", "heavy_tail_null", "current_batch_leak"}:
        raise ValueError("Unknown case")
    a, b = torch.tensor(x), torch.tensor(y)
    wealth = np.zeros(n)
    maximum = wealth.copy()
    crossing = np.full(n, -1, dtype=int)
    bound = math.log(20.)
    scored = 0
    for start in range(16, pairs, 8):
        end = min(start+8, pairs)
        if case == "current_batch_leak":
            difference = (a[:, start:end]-b[:, start:end]).mean(1)
        else:
            difference = (a[:, :start-8]-b[:, :start-8]).mean(1)
        direction = difference / torch.clamp(torch.linalg.vector_norm(difference, dim=1, keepdim=True), min=1e-12)
        # No bet is an explicit permissible baseline. Select stakes on the previous batch only.
        best = torch.zeros(n)
        weight = torch.zeros_like(direction)
        for scale in (.1, .25, .5):
            w = direction*scale
            va, vb = (a[:,start:end], b[:,start:end]) if case == "current_batch_leak" else (a[:,start-8:start], b[:,start-8:start])
            score = factors(va, vb, w).mean(1)
            improved = score > best
            weight[improved] = w[improved]
            best = torch.maximum(best, score)
        logs = factors(a[:,start:end], b[:,start:end], weight).numpy()
        # Track each pair, not just batch endpoints, for genuine anytime diagnostics.
        for j in range(end-start):
            wealth += logs[:,j]
            maximum = np.maximum(maximum, wealth)
            crossing[(crossing<0)&(wealth>=bound)] = start+j+1
        scored += end-start
    final, anytime = int((wealth>=bound).sum()), int((maximum>=bound).sum())
    caught = crossing[crossing>=0]
    return {"streams": n, "pairs": pairs, "scored_pairs": scored, "case": case,
            "invalid_control": case == "current_batch_leak", "effect": effect,
            "final_rejections": final, "final_rate": final/n, "final_ci95": interval(final,n),
            "anytime_rejections": anytime, "anytime_rate": anytime/n, "anytime_ci95": interval(anytime,n),
            "median_detection_pair_if_detected": float(np.median(caught)) if len(caught) else None,
            "final_log_wealth_quantiles": np.quantile(wealth,[0,.5,.9,.99,.999,1]).tolist(),
            "maximum_log_wealth": float(maximum.max())}


def run(n=10000):
    started = time.monotonic()
    cases = ["normal_null", "heavy_tail_null", "missingness_null", "shift", "nonlinear",
             "missingness_alternative", "batch_shift", "current_batch_leak"]
    results = {case: streams(case,n=n,seed=120+idx) for idx,case in enumerate(cases)}
    # Budget sensitivity, without treating the undersized audit as an eligible process.
    results["shift_at_26_pair_audit_ceiling"] = streams("shift",n=n,pairs=26,seed=200)
    results["shift_at_96_pairs"] = streams("shift",n=n,pairs=96,seed=201)
    return {"schema": "ProteinNativeDiagnostics-v1", "alpha": .05,
            "kernel": "learned_evalue._log_payoffs", "schedule": "two burn-in batches, 8 pairs/batch",
            "critic": "predictable past-mean direction, previous-batch stake selection; not neural Adam power",
            "minimum_effect": .4, "minimum_effect_basis": "rounded down from fixed development mitotic difference 0.4791",
            "results": results, "seconds": time.monotonic()-started,
            "biological_release": "unavailable: not an audited independent confirmation cohort or model-specific power certificate",
            "sampling_argument": "Conditional exchangeability and a past-measurable witness make the clipped tanh contrast odd with conditional mean zero. Factors are positive with conditional mean one. Distinct IDs, simulations and batch correction cannot establish these assumptions for actual samples."}
