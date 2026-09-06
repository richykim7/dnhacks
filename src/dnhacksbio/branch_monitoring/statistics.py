"""E-valuator-style history ratios and Algorithm 1 calibration; no enforcement."""
from __future__ import annotations

import hashlib
import json
import math
import numpy as np


def fingerprint(model):
    return hashlib.sha256(json.dumps(model, sort_keys=True, allow_nan=False).encode()).hexdigest()


def _score(x):
    if type(x) not in (float, int) or not math.isfinite(x) or not 0 <= x <= 1:
        raise ValueError("Verifier scores must be finite probabilities in [0,1]")
    return float(x)


def split_group(group, seed="branch-monitor-v1"):
    n = int(hashlib.sha256(f"{seed}:{group}".encode()).hexdigest()[:8], 16) % 10
    return "fit" if n < 6 else ("calibration" if n < 8 else "test")


def counts(episodes):
    return {"roots": len({e["root_id"] for e in episodes}),
            "groups": len({e["group_id"] for e in episodes}), "episodes": len(episodes),
            "checkpoints": sum(len(e["scores"]) for e in episodes),
            "censored": sum(e.get("outcome") not in {"success", "unsuccessful"} for e in episodes)}


def _eligible(episodes):
    return [e for e in episodes if e.get("outcome") in {"success", "unsuccessful"}
            and e["scores"] and all(s is not None for s in e["scores"])]


def fit(episodes, protocol_hash, *, iterations=1200, ridge=.02):
    """One logistic classifier per observed prefix length, as in paper Eq.3.

    Each root has equal total weight; each episode within a root has equal weight.
    Prefixes of unsupported lengths or with missing observations yield unavailable.
    """
    if any(e["protocol_hash"] != protocol_hash for e in episodes):
        raise ValueError("Mixed protocol versions")
    data = _eligible(episodes)
    if not data or len({e["outcome"] for e in data}) < 2:
        raise ValueError("Fitting needs completed successful and unsuccessful episodes")
    model = {"schema_version": 1, "kind": "history_logistic_ratio", "protocol_hash": protocol_hash,
             "fit_roots": sorted({e["root_id"] for e in episodes}),
             "fit_groups": sorted({e["group_id"] for e in episodes}), "counts": counts(episodes), "lengths": {}}
    for t in range(1, max(map(lambda e: len(e["scores"]), data)) + 1):
        rows = [e for e in data if len(e["scores"]) >= t]
        if len({e["outcome"] for e in rows}) < 2:
            continue
        X = np.array([[1.] + [_score(s) for s in e["scores"][:t]] for e in rows])
        y = np.array([float(e["outcome"] == "success") for e in rows])
        w = np.array([1 / sum(r["root_id"] == e["root_id"] for r in rows) for e in rows])
        w /= w.sum()
        prior = float(w @ y)
        beta = np.zeros(t + 1)
        for _ in range(iterations):
            pred = 1 / (1 + np.exp(-np.clip(X @ beta, -30, 30)))
            grad = X.T @ (w * (pred - y)) + ridge * np.r_[0., beta[1:]]
            beta -= .5 * grad
        model["lengths"][str(t)] = {"coefficients": beta.tolist(), "success_prior": prior}
    return model


def history_values(model, scores):
    out = []
    for t in range(1, len(scores) + 1):
        spec = model["lengths"].get(str(t))
        if spec is None or any(s is None for s in scores[:t]):
            out.append(None)
            continue
        x = np.array([1.] + [_score(s) for s in scores[:t]])
        logit = float(x @ spec["coefficients"])
        prior = spec["success_prior"]
        out.append(math.exp(max(-60., min(60., -logit + math.log(prior / (1 - prior))))))
    return out


def pac_threshold(maxima, alpha=.045, delta=.005):
    """Algorithm 1: ascending kth order statistic with Binomial(n,1-alpha) tail <= delta.

    Return None (infinite/no threshold) for insufficient independent successful episodes.
    Strict > comparison handles ties conservatively. No learned ratio is claimed exact.
    """
    if not 0 < alpha < 1 or not 0 < delta < 1:
        raise ValueError("alpha and delta must lie in (0,1)")
    values = sorted(float(x) for x in maxima)
    if any(not math.isfinite(x) or x < 0 for x in values):
        raise ValueError("Finite nonnegative maxima required")
    n = len(values)
    if n == 0 or n * math.log1p(-alpha) > math.log(delta):
        return None
    # Sum upper tail from n down in log space to avoid under/overflow at large n.
    logs = [math.lgamma(n + 1) - math.lgamma(j + 1) - math.lgamma(n - j + 1)
            + j * math.log1p(-alpha) + (n - j) * math.log(alpha) for j in range(n + 1)]
    tail = -math.inf
    k = n
    for j in range(n, 0, -1):
        tail = float(np.logaddexp(tail, logs[j]))
        if tail <= math.log(delta):
            k = j
        else:
            break
    return values[k - 1]


def _selected(episodes):
    # Enrollment selects this unit BEFORE any outcomes. Never pick the best successful sibling.
    selected = [e for e in episodes if e.get("calibration_unit")]
    roots = [e["root_id"] for e in selected]
    groups = [e["group_id"] for e in selected]
    if len(roots) != len(set(roots)) or len(groups) != len(set(groups)):
        raise ValueError("Calibration/evaluation needs one preselected episode per independent root/group")
    return selected


def calibrate(model, episodes, alpha=.045, delta=.005):
    if any(e["root_id"] in model["fit_roots"] or e["group_id"] in model["fit_groups"] for e in episodes):
        raise ValueError("Fitting/calibration leakage")
    if any(e["protocol_hash"] != model["protocol_hash"] for e in episodes):
        raise ValueError("Protocol mismatch")
    selected = _selected(episodes)
    good = [e for e in selected if e.get("outcome") == "success"]
    maxima, raw_maxima = [], []
    for e in good:
        values = history_values(model, e["scores"])
        # Missing verifier/model coverage precludes claiming complete-path calibration.
        if not values or any(v is None for v in values):
            raise ValueError("Incomplete successful calibration history")
        maxima.append(max(values))
        raw_maxima.append(max(1 - _score(s) for s in e["scores"]))
    return {"schema_version": 1, "protocol_hash": model["protocol_hash"], "model_hash": fingerprint(model),
            "alpha": alpha, "delta": delta, "threshold": pac_threshold(maxima, alpha, delta),
            "raw_threshold": pac_threshold(raw_maxima, alpha, delta),
            "successful_units": len(good), "required_minimum": math.ceil(math.log(delta) / math.log1p(-alpha)),
            "calibration_roots": sorted({e["root_id"] for e in episodes}),
            "calibration_groups": sorted({e["group_id"] for e in episodes}),
            "counts": counts(episodes), "mode": "observation_only"}


def wilson(successes, n, z=1.96):
    if not n:
        return None
    p = successes / n
    center = (p + z*z/(2*n)) / (1 + z*z/n)
    radius = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / (1 + z*z/n)
    return [max(0., center-radius), min(1., center+radius)]


def evaluate(model, calibration, episodes, raw_threshold=.5):
    if calibration.get("model_hash") != fingerprint(model):
        raise ValueError("Calibration belongs to a different fitted model")
    forbidden_roots = set(model["fit_roots"]) | set(calibration["calibration_roots"])
    forbidden_groups = set(model["fit_groups"]) | set(calibration["calibration_groups"])
    if any(e["root_id"] in forbidden_roots or e["group_id"] in forbidden_groups for e in episodes):
        raise ValueError("Held-out evaluation leakage")
    if any(e["protocol_hash"] != model["protocol_hash"] for e in episodes):
        raise ValueError("Protocol mismatch")
    selected = _selected(episodes)
    result = {"counts": counts(episodes), "selected_counts": counts(selected), "methods": {},
              "interpretation": "Observation-only replay; savings are potential, not realized discovery gains"}
    for name, threshold in [("direct_verifier", raw_threshold), ("pac_verifier", calibration["raw_threshold"]),
                            ("history_ratio", calibration["threshold"])]:
        rows = []
        for e in selected:
            vals = history_values(model, e["scores"]) if name == "history_ratio" else [None if s is None else 1 - _score(s) for s in e["scores"]]
            stop = next((i for i, v in enumerate(vals) if v is not None and threshold is not None and v > threshold), None)
            total = (e.get("label_provenance") or {}).get("total_cost")
            costs = e.get("costs", [])
            potential_saved = max(0., total - costs[stop]) if stop is not None and total is not None and len(costs) > stop else None
            rows.append({"potential_saved_cost": potential_saved, "episode_id": e["episode_id"], "outcome": e.get("outcome"), "stop_checkpoint": None if stop is None else stop + 1,
                         "subgroup": e.get("subgroup", "unspecified"), "values": vals,
                         "missing_values": sum(v is None for v in vals)})
        good = [r for r in rows if r["outcome"] == "success"]
        bad = [r for r in rows if r["outcome"] == "unsuccessful"]
        result["methods"][name] = {"threshold": threshold, "rows": rows,
            "successful_units": len(good), "unsuccessful_units": len(bad),
            "false_stops": sum(r["stop_checkpoint"] is not None for r in good),
            "detected_unsuccessful": sum(r["stop_checkpoint"] is not None for r in bad),
            "false_stop_rate": sum(r["stop_checkpoint"] is not None for r in good) / len(good) if good else None,
            "false_stop_wilson95": wilson(sum(r["stop_checkpoint"] is not None for r in good), len(good)),
            "potential_saved_cost": sum(r["potential_saved_cost"] or 0 for r in rows),
            "cost_observed_units": sum(r["potential_saved_cost"] is not None for r in rows),
            "subgroups": {g: {"units": sum(r["subgroup"] == g for r in rows),
                "successful_units": sum(r["subgroup"] == g for r in good),
                "false_stops": sum(r["subgroup"] == g and r["stop_checkpoint"] is not None for r in good)}
                for g in {r["subgroup"] for r in rows}},
            "detection_rate": sum(r["stop_checkpoint"] is not None for r in bad) / len(bad) if bad else None}
    return result
