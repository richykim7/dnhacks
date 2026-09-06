"""Exact finite-null calibration and deliberately invalid global-shuffle controls."""
from itertools import combinations, product
import math
import random

import pytest

from dnhacksbio.dependency_evalue import blocked_permutation


def rows(blocks):
    return [{"unit_id": f"u{s}-{i}", "model_id": f"m{s}-{i}", "disease": "PDAC",
             "block_id": str(s), "event_status": "deleted" if deleted else "intact", "target_effect": x}
            for s, block in enumerate(blocks) for i, (x, deleted) in enumerate(block)]


@pytest.mark.parametrize("scores,counts", [([[0, 1, 2, 3]], [2]), ([[0, 0, 1], [5, 7, 8, 10]], [1, 2]),
                                            ([[0, 0, 0], [4, 4]], [2, 1])])
def test_full_null_orbits_are_superuniform_and_calibrated(scores, counts):
    results = []
    for labels in product(*(combinations(range(len(x)), k) for x, k in zip(scores, counts))):
        data = rows([[(x, i in chosen) for i, x in enumerate(block)] for block, chosen in zip(scores, labels)])
        results.append(blocked_permutation(data, min_group=1))
    assert sum(r["e_value"] for r in results) / len(results) <= 1 + 1e-12
    for alpha in (0.01, 0.05, 0.1, 0.25, 0.5, 1):
        assert sum(r["p_value"] <= alpha for r in results) / len(results) <= alpha + 1e-12
        assert sum(r["e_value"] >= 1 / alpha for r in results) / len(results) <= alpha + 1e-12
    assert all(r["exact"] and r["draws"] == len(results) for r in results)


def test_exact_tail_ties_small_attainable_evidence_and_direction():
    result = blocked_permutation(rows([[(-1, True), (0, False)]]), min_group=1)
    assert result["effect"] == 1 and result["p_value"] == 0.5
    assert result["e_value"] == pytest.approx(math.sqrt(2) - 1)
    tied = blocked_permutation(rows([[(0, True), (0, False)]]), min_group=1)
    assert tied["p_value"] == 1 and tied["e_value"] == 0


def test_block_confounding_is_not_repaired_by_global_shuffling():
    data = rows([[(-10, i < 7) for i in range(8)], [(10, i < 1) for i in range(8)]])
    valid = blocked_permutation(data)
    assert valid["p_value"] == 1 and valid["effect"] == 0
    global_rows = [dict(r, block_id="global") for r in data]
    assert blocked_permutation(global_rows)["p_value"] < 0.05


def test_monte_carlo_replay_and_plus_one():
    data = rows([[(-1 if i < 8 else 0, i < 8) for i in range(16)]])
    first = blocked_permutation(data, exact_limit=1, seed=37)
    assert first == blocked_permutation(list(reversed(data)), exact_limit=1, seed=37)
    assert not first["exact"] and first["draws"] == 9999
    assert first["p_value"] == (1 + first["exceedances"]) / 10000
    assert first["p_value"] > 0


def test_units_unknowns_and_uninformative_blocks():
    data = rows([[(0, True), (1, False)], [(3, True)]])
    data[0]["event_status"] = "unknown"
    result = blocked_permutation(data)
    assert result["status"] == "unavailable" and result["e_value"] is None
    assert result["exclusions"] == {"unknown_event": 1, "missing_effect": 0, "uninformative_block": 2}
    with pytest.raises(ValueError, match="Repeated"):
        blocked_permutation(data + data[:1])
    data[0]["target_effect"] = float("nan")
    with pytest.raises(ValueError, match="Nonfinite"):
        blocked_permutation(data)


def test_selective_dependency_power_curve():
    # Fixed synthetic designs, paired noise across effect sizes; no biological pilot.
    powers = []
    for shift in (0, 1, 3):
        rejections = 0
        for seed in range(16):
            rng = random.Random(seed)
            data = rows([[(rng.gauss(0, 1) - (shift if i < 8 else 0), i < 8) for i in range(16)]])
            result = blocked_permutation(data, exact_limit=1, permutations=999, seed=100 + seed)
            rejections += result["p_value"] <= 0.05
        powers.append(rejections)
    assert powers[0] <= 3 and powers[0] < powers[1] < powers[2] == 16
