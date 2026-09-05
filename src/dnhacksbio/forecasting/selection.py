"""Snapshot coverage selection; all guarantees concern this objective, never forecast truth."""
from __future__ import annotations

from itertools import combinations
from math import comb, exp, isfinite
import random


POLICIES = ("greedy", "exact", "uniform", "top_singleton", "judge_fixture")


def select_branches(branches: list[dict], k: int, *, policy: str = "greedy",
                    weights: dict[str, float] | None = None, covered=(), seed: int = 0) -> dict:
    """Choose up to k equal-cost items with frozen ``id`` and ``facets`` fields.

    A facet contributes its nonnegative weight once. Greedy breaks ties by ID.
    ``judge_fixture`` consumes explicit fixture_judge_score values, never a live judge.
    The tiny exact oracle refuses more than 100,000 combinations.
    """
    if policy not in POLICIES:
        raise ValueError(f"unknown policy: {policy}")
    if not isinstance(k, int) or k < 0:
        raise ValueError("k must be a nonnegative integer")
    items = sorted(branches, key=lambda item: item["id"])
    if len({item["id"] for item in items}) != len(items):
        raise ValueError("branch IDs must be unique")
    weights = {key: float(value) for key, value in (weights or {}).items()}
    if any(not isfinite(value) or value < 0 for value in weights.values()):
        raise ValueError("facet weights must be finite and nonnegative")
    prior = set(covered)
    facets = {item["id"]: set(item.get("facets", [])) - prior for item in items}
    k = min(k, len(items))

    def value(features):
        return sum(weights.get(facet, 1.0) for facet in sorted(features))

    def coverage(ids):
        return set().union(*(facets[item_id] for item_id in ids))

    selected = []
    if policy == "exact":
        if comb(len(items), k) > 100_000:
            raise ValueError("exact oracle is limited to 100,000 combinations")
        selected = list(max(combinations(facets, k), key=lambda ids: value(coverage(ids))))
    elif policy == "uniform":
        selected = random.Random(seed).sample(list(facets), k)
    elif policy == "judge_fixture":
        if any("fixture_judge_score" not in item for item in items):
            raise ValueError("judge_fixture requires explicit fixture_judge_score for every branch")
        if any(not isfinite(float(item["fixture_judge_score"])) for item in items):
            raise ValueError("fixture judge scores must be finite")
        selected = [item["id"] for item in sorted(
            items, key=lambda item: (-float(item["fixture_judge_score"]), item["id"]))[:k]]
    elif policy == "top_singleton":
        selected = sorted(facets, key=lambda item_id: (-value(facets[item_id]), item_id))[:k]
    else:
        for _ in range(k):
            known = coverage(selected)
            selected.append(min((item_id for item_id in facets if item_id not in selected),
                                key=lambda item_id: (-value(facets[item_id] - known), item_id)))

    gained = coverage(selected)
    total = value(gained)
    # Submodularity bounds every size-k solution by its singleton gains, or by
    # the achieved value plus k residual gains. This is an instance certificate.
    singleton_bound = sum(sorted((value(f) for f in facets.values()), reverse=True)[:k])
    residual_bound = total + sum(sorted((value(f - gained) for f in facets.values()), reverse=True)[:k])
    upper = min(value(coverage(facets)), singleton_bound, residual_bound)
    if policy == "exact":
        upper = total
    cumulative = set()
    choices = []
    for item_id in selected:
        new = facets[item_id] - cumulative
        choices.append({"id": item_id, "marginal_gain": value(new), "new_facets": sorted(new)})
        cumulative |= new
    return {
        "policy": policy, "selected_ids": selected, "choices": choices,
        "value": total, "upper_bound": upper,
        "certificate_ratio": total / upper if upper else 1.0,
        "guarantee": 1 - exp(-1) if policy == "greedy" else (1.0 if policy == "exact" else None),
        "objective": "weighted distinct facet coverage",
        "assumptions": "frozen pool; nonnegative fixed weights; equal cost; cardinality budget",
        "pool_size": len(items), "budget": k,
        "origin": "fixture" if policy == "judge_fixture" else "computed",
    }
