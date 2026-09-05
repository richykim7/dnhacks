import itertools
import random

import pytest

from dnhacksbio.forecasting.selection import select_branches


def test_greedy_accounts_for_overlap_instead_of_individual_scores():
    branches = [{"id": "a", "facets": ["1", "2", "3"]},
                {"id": "b", "facets": ["1", "2"]},
                {"id": "c", "facets": ["4"]}]
    greedy = select_branches(branches, 2)
    assert greedy["selected_ids"] == ["a", "c"]
    assert greedy["value"] == 4
    assert select_branches(branches, 2, policy="top_singleton")["value"] == 3
    assert greedy["certificate_ratio"] == 1


def test_weighted_residual_selection_and_ties_are_deterministic():
    branches = [{"id": "b", "facets": ["seen", "b"]},
                {"id": "a", "facets": ["seen", "a"]}]
    result = select_branches(branches, 1, covered={"seen"}, weights={"seen": 100, "b": 2})
    assert result["selected_ids"] == ["b"]
    assert result["value"] == 2
    assert select_branches(branches, 1)["selected_ids"] == ["a"]
    assert select_branches(branches[::-1], 1)["selected_ids"] == ["a"]


def test_certificate_and_greedy_bound_against_independent_small_optima():
    rng = random.Random(19)
    for _ in range(120):
        branches = [{"id": str(i), "facets": [str(j) for j in range(7) if rng.random() < 0.4]}
                    for i in range(6)]
        weights = {str(j): rng.randint(0, 4) for j in range(7)}
        k = rng.randint(0, 4)
        values = []
        for subset in itertools.combinations(branches, k):
            union = set().union(*(set(item["facets"]) for item in subset))
            values.append(sum(weights[facet] for facet in union))
        optimum = max(values)
        result = select_branches(branches, k, weights=weights)
        assert result["value"] <= optimum <= result["upper_bound"] + 1e-9
        assert result["value"] + 1e-9 >= result["guarantee"] * optimum
        assert select_branches(branches, k, weights=weights, policy="exact")["value"] == optimum


def test_fixture_judge_is_explicit_and_uniform_is_reproducible():
    branches = [{"id": str(i), "facets": [str(i)], "fixture_judge_score": i} for i in range(6)]
    assert select_branches(branches, 2, policy="uniform", seed=12) == select_branches(
        branches[::-1], 2, policy="uniform", seed=12)
    result = select_branches(branches, 2, policy="judge_fixture")
    assert result["selected_ids"] == ["5", "4"]
    assert result["origin"] == "fixture"
    with pytest.raises(ValueError, match="explicit"):
        select_branches([{"id": "a"}], 1, policy="judge_fixture")


def test_invalid_inputs_and_exact_oracle_limit():
    for bad in (-1, float("nan"), float("inf")):
        with pytest.raises(ValueError, match="weights"):
            select_branches([{"id": "a"}], 1, weights={"x": bad})
    with pytest.raises(ValueError, match="unique"):
        select_branches([{"id": "a"}, {"id": "a"}], 1)
    with pytest.raises(ValueError, match="100,000"):
        select_branches([{"id": str(i)} for i in range(30)], 15, policy="exact")
    assert select_branches([], 3)["value"] == 0
