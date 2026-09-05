"""Independent mathematical oracles; run explicitly with pytest on this path."""
from fractions import Fraction
import random

import pytest

from research_spikes.policy_lab.model import Instance, Witness, shared_core_dp
from research_spikes.policy_lab.experiments import revealing_action_oracle, shared_setup


def raw_oracle(problem):
    # Deliberately avoid model.close/value/feasible/requirements.
    best = 0
    for selected in range(1 << len(problem.costs)):
        if sum(c for i, c in enumerate(problem.costs) if selected & (1 << i)) > problem.budget:
            continue
        if any(selected & (1 << i) and required & selected != required
               for i, required in enumerate(problem.prerequisites)):
            continue
        best = max(best, sum(w.weight for w in problem.witnesses if w.actions & selected == w.actions))
    return best


@pytest.mark.parametrize("seed", range(60))
def test_weighted_dag_and_anytime_advice_against_raw_oracle(seed):
    rng = random.Random(seed)
    n = rng.randrange(0, 9)
    permutation = list(range(n))
    rng.shuffle(permutation)
    prereqs = [0] * n
    for position, action in enumerate(permutation):
        prereqs[action] = sum(1 << earlier for earlier in permutation[:position] if rng.random() < .3)
    costs = tuple(rng.randrange(1, 6) for _ in range(n))
    problem = Instance(costs, tuple(prereqs),
                       tuple(Witness(rng.randrange(1 << n), rng.randrange(11)) for _ in range(12)),
                       rng.randrange(sum(costs) + 1))
    optimum = raw_oracle(problem)
    advice = [rng.randrange(1 << n) for _ in range(6)] + [-1, 1 << (n + 1)]
    for limit in (0, 1, 2, None):
        output = shared_core_dp(problem, order=advice, max_profiles=limit)
        assert output["value"] <= optimum <= Fraction(output["upper"])
        if limit is None:
            assert output["value"] == optimum


def test_shared_core_inherits_prerequisites_and_private_zero_cost():
    problem = Instance((2, 1, 1), (0, 1, 2),
                       (Witness(2, 4), Witness(4, 6), Witness(0, 3), Witness(2, 2)), 4)
    assert problem.shared_core() == 3
    assert shared_core_dp(problem)["value"] == raw_oracle(problem) == 15


def test_large_budget_is_capped_and_empty_problem_is_valid():
    problem = Instance((1,), (0,), (Witness(1, 3),), 10**9)
    output = shared_core_dp(problem)
    assert output["value"] == 3 and output["dp_transitions"] == 1
    assert shared_core_dp(Instance((), (), (Witness(0, 2),), 0))["value"] == 2


def test_cycle_and_invalid_cost_rejected():
    with pytest.raises(ValueError, match="cyclic"):
        Instance((1, 1), (2, 1), (), 2)
    with pytest.raises(ValueError, match="positive"):
        Instance((0,), (0,), (), 2)


def test_strong_greedy_counterexample_and_revealed_action_cost():
    from research_spikes.policy_lab.model import greedy, seeded_greedy, allocated_seed_greedy
    for m in (3, 4, 8):
        problem = shared_setup(m)
        assert greedy(problem)["value"] == 2 * m
        assert shared_core_dp(problem)["value"] == m * m
        assert seeded_greedy(problem)["value"] == m * m
        assert allocated_seed_greedy(problem)["value"] == m * m
    for n in (2, 3, 8):
        assert revealing_action_oracle(n, 1)["adaptive_optimum"] == "0"
        assert Fraction(revealing_action_oracle(n, 2)["adaptive_optimum"]) == Fraction(1, n)
