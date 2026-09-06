"""Fixed-data, one-sided blocked label-permutation evidence; no verdict integration."""
from __future__ import annotations

from itertools import combinations, product
import math
import random

from .evalues import p_to_e

NULL = "Uniform event-label exchangeability within frozen blocks, conditional on scores and group counts"


def blocked_permutation(rows, *, min_group=8, exact_limit=100_000, permutations=9999, seed=0):
    """Positive effect = stronger dependency in deleted units. Pure numerical kernel.

    The private adapter enforces registration, design justification and the operational floor.
    Smaller floors are useful only for exhaustive numerical validation of small null orbits.
    """
    for value, minimum, maximum in ((min_group, 1, 10**9), (exact_limit, 1, 100_000),
                                     (permutations, 1, 9999), (seed, 0, 2**32 - 1)):
        if type(value) is not int or not minimum <= value <= maximum:
            raise ValueError("Invalid permutation configuration")
    groups = {}
    units, models = set(), set()
    exclusions = {"unknown_event": 0, "missing_effect": 0, "uninformative_block": 0}
    for row in rows:
        if set(row) != {"unit_id", "model_id", "disease", "event_status", "block_id", "target_effect"}:
            raise ValueError("Invalid table columns")
        for field in ("unit_id", "model_id", "disease", "block_id"):
            if not isinstance(row[field], str) or not row[field].strip():
                raise ValueError("Missing identity or block")
        if row["unit_id"] in units or row["model_id"] in models:
            raise ValueError("Repeated biological unit or model")
        units.add(row["unit_id"])
        models.add(row["model_id"])
        event, effect = row["event_status"], row["target_effect"]
        if event not in ("deleted", "intact", "unknown"):
            raise ValueError("Invalid curated event call")
        if effect is not None and (type(effect) not in (int, float) or not math.isfinite(effect)):
            raise ValueError("Nonfinite or invalid effect")
        if event == "unknown":
            exclusions["unknown_event"] += 1
            continue
        if effect is None:
            exclusions["missing_effect"] += 1
            continue
        groups.setdefault(row["block_id"], []).append(row)
    blocks = []
    counts = []
    for name, members in sorted(groups.items()):
        members.sort(key=lambda r: r["unit_id"])
        deleted = tuple(i for i, r in enumerate(members) if r["event_status"] == "deleted")
        n = len(members)
        counts.append({"block_id": name, "deleted": len(deleted), "intact": n - len(deleted)})
        if not deleted or len(deleted) == n:
            exclusions["uninformative_block"] += n
            continue
        blocks.append(([float(r["target_effect"]) for r in members], deleted))
    nd = sum(len(d) for _, d in blocks)
    ni = sum(len(x) - len(d) for x, d in blocks)
    base = {"null": NULL, "counts": {"deleted": nd, "intact": ni, "blocks": counts},
            "exclusions": exclusions, "seed": seed, "configured_permutations": permutations,
            "exact_limit": exact_limit, "statistic": "size-weighted mean_intact minus mean_deleted",
            "uninformative_blocks": "exclude", "evidence_type": "fixed-data"}
    if min(nd, ni) < min_group:
        return {**base, "status": "unavailable", "reason": "insufficient_independent_units",
                "effect": None, "p_value": None, "e_value": None}
    total = nd + ni

    def statistic(labels):
        terms = []
        for (scores, _), selected in zip(blocks, labels):
            selected = set(selected)
            # fsum and fixed unit ordering avoid permutation-order rounding differences.
            a = math.fsum(x for i, x in enumerate(scores) if i in selected) / len(selected)
            b = math.fsum(x for i, x in enumerate(scores) if i not in selected) / (len(scores) - len(selected))
            terms.append(len(scores) / total * (b - a))
        value = math.fsum(terms)
        if not math.isfinite(value):
            raise ValueError("Statistic overflow")
        return value

    observed = statistic([d for _, d in blocks])
    orbit = math.prod(math.comb(len(x), len(d)) for x, d in blocks)
    exact = orbit <= exact_limit
    if exact:
        labels = product(*(combinations(range(len(x)), len(d)) for x, d in blocks))
        draws = orbit
    else:
        rng = random.Random(seed)
        labels = ([rng.sample(range(len(x)), len(d)) for x, d in blocks] for _ in range(permutations))
        draws = permutations
    # Conservative near-tie inclusion prevents numerical anti-conservatism.
    tolerance = 1e-12 * max(1.0, abs(observed))
    exceed = sum(statistic(label) >= observed - tolerance for label in labels)
    p = exceed / draws if exact else (1 + exceed) / (draws + 1)
    return {**base, "status": "ok", "reason": None, "effect": observed, "p_value": p,
            "e_value": p_to_e(p), "orbit_size": orbit, "exact": exact, "draws": draws,
            "exceedances": exceed, "minimum_attainable_p": 1 / (draws if exact else draws + 1)}
