"""Deterministic witness completion; no model calls or future-label access.

Bit i identifies one context-equivalent, reusable action. Witnesses are ANDs,
with additive nonnegative rewards. See the report for the exact scope.
"""
from dataclasses import dataclass
from fractions import Fraction


def bits(mask: int):
    while mask:
        bit = mask & -mask
        yield bit.bit_length() - 1
        mask ^= bit


def subsets(mask: int):
    sub = mask
    while True:
        yield sub
        if sub == 0:
            break
        sub = (sub - 1) & mask


@dataclass(frozen=True)
class Witness:
    actions: int
    weight: int = 1
    label: str = ""


@dataclass(frozen=True)
class Instance:
    costs: tuple[int, ...]
    prerequisites: tuple[int, ...]
    witnesses: tuple[Witness, ...]
    budget: int
    name: str = ""

    def __post_init__(self):
        n = len(self.costs)
        if len(self.prerequisites) != n:
            raise ValueError("one prerequisite mask per action required")
        if type(self.budget) is not int or self.budget < 0:
            raise ValueError("budget must be a nonnegative integer")
        if any(type(c) is not int or c <= 0 for c in self.costs):
            raise ValueError("action costs must be positive integers")
        full = (1 << n) - 1
        for mask in (*self.prerequisites, *(w.actions for w in self.witnesses)):
            if type(mask) is not int or mask < 0 or mask & ~full:
                raise ValueError("action mask outside the universe")
        if any(type(w.weight) is not int or w.weight < 0 for w in self.witnesses):
            raise ValueError("witness weights must be nonnegative integers")
        # Check cycles independently of index order, and compute full closures.
        state, closures = [0] * n, [0] * n

        def visit(i):
            if state[i] == 1:
                raise ValueError("cyclic prerequisites")
            if state[i] == 2:
                return closures[i]
            state[i] = 1
            closure = 1 << i
            for j in bits(self.prerequisites[i]):
                closure |= visit(j)
            state[i], closures[i] = 2, closure
            return closure

        for i in range(n):
            visit(i)
        object.__setattr__(self, "closures", tuple(closures))
        object.__setattr__(self, "requirements", tuple(self.close(w.actions) for w in self.witnesses))

    def close(self, mask):
        out = 0
        for i in bits(mask):
            out |= self.closures[i]
        return out

    def cost(self, mask):
        return sum(self.costs[i] for i in bits(mask))

    def value(self, mask):
        return sum(w.weight for w, req in zip(self.witnesses, self.requirements) if req & mask == req)

    def feasible(self, mask):
        return mask == self.close(mask) and self.cost(mask) <= self.budget

    def shared_core(self):
        frequencies = [sum(bool(req & (1 << i)) for req in self.requirements)
                       for i in range(len(self.costs))]
        return sum(1 << i for i, f in enumerate(frequencies) if f > 1)


def result(problem, mask, *, candidate_evaluations=0, **extra):
    assert problem.feasible(mask)
    return dict(mask=mask, actions=list(bits(mask)), value=problem.value(mask),
                unique_cost=problem.cost(mask), candidate_evaluations=candidate_evaluations,
                experimental_queries=0, **extra)


def exact_actions(problem):
    """Independent 2^n action-set oracle, with prerequisite feasibility checks."""
    best, best_value, evaluated = 0, problem.value(0), 0
    for mask in range(1 << len(problem.costs)):
        if problem.feasible(mask):
            value = problem.value(mask)
            evaluated += 1
            if (value, -problem.cost(mask), -mask) > (best_value, -problem.cost(best), -best):
                best, best_value = mask, value
    return result(problem, best, candidate_evaluations=evaluated)


def greedy(problem, mode="witness", rng=None, coverage_sets=None, initial=0):
    """All modes charge only the residual union of unique action costs.

    witness: strong bundle-density heuristic, including incidental completions.
    singleton: density of completed-reward gain from one action's closure.
    coverage: density of newly covered explicit facets (one per action by default).
    random: uniformly select an affordable remaining action closure.
    """
    selected, evaluations = initial, 0
    assert problem.feasible(selected)
    options = (problem.requirements if mode == "witness" else problem.closures)

    def score(mask):
        if mode == "coverage":
            covered = 0
            for i in bits(mask):
                covered |= coverage_sets[i] if coverage_sets is not None else 1 << i
            return covered.bit_count()
        return problem.value(mask)

    while True:
        candidates = []
        current_score, current_cost = score(selected), problem.cost(selected)
        for option in options:
            expanded = selected | option
            extra_cost = problem.cost(option & ~selected)
            # A union of already closed options stays prerequisite closed.
            if not extra_cost or current_cost + extra_cost > problem.budget:
                continue
            gain = score(expanded) - current_score
            evaluations += 1
            candidates.append((Fraction(gain, extra_cost), gain, -option, expanded))
        if not candidates:
            break
        selected = (rng.choice(candidates) if mode == "random" else max(candidates))[-1]
    return result(problem, selected, candidate_evaluations=evaluations)


def seeded_greedy(problem):
    """Enumerate ≤2 witness seeds and use residual-union gain density.

    A strong empirical control, not a claim to implement a published theorem.
    The separate literature report distinguishes Arulselvan's exact algorithm.
    """
    from itertools import combinations
    seeds = {0, *problem.requirements}
    seeds.update(a | b for a, b in combinations(problem.requirements, 2))
    best = result(problem, 0)
    evaluations = 0
    for seed in sorted(seeds):
        if problem.feasible(seed):
            candidate = greedy(problem, initial=seed)
            evaluations += candidate["candidate_evaluations"]
            if (candidate["value"], -candidate["unique_cost"]) > (best["value"], -best["unique_cost"]):
                best = candidate
    return {**best, "candidate_evaluations": evaluations}


def allocated_seed_greedy(problem):
    """Arulselvan 2014 Algorithms 1–2, then count all actually completed items.

    Static allocated cost is sum(c_a/frequency_a). Enumerate ≤2 item seeds,
    skip infeasible additions and never reconsider them. Counting incidental
    completed items after each run is an explicit, safe zero-cost enhancement.
    Empty items are included upfront so the published positive-cost density is
    well-defined. This baseline is distinct from residual-density seeded_greedy.
    """
    from itertools import combinations
    frequencies = [sum(bool(req & (1 << i)) for req in problem.requirements)
                   for i in range(len(problem.costs))]
    allocated = [sum((Fraction(problem.costs[i], frequencies[i]) for i in bits(req)), Fraction(0))
                 for req in problem.requirements]
    order = sorted((i for i, c in enumerate(allocated) if c > 0),
                   key=lambda i: (-Fraction(problem.witnesses[i].weight, 1) / allocated[i], i))
    indices = list(range(len(problem.witnesses)))
    seeds = [(), *((i,) for i in indices), *combinations(indices, 2)]
    best, evaluations = result(problem, 0), 0
    for seed in seeds:
        mask = 0
        for i in seed:
            mask |= problem.requirements[i]
        if not problem.feasible(mask):
            continue
        for i in order:
            if i in seed:
                continue
            expanded = mask | problem.requirements[i]
            evaluations += 1
            if problem.feasible(expanded):
                mask = expanded
        candidate = result(problem, mask)
        if (candidate["value"], -candidate["unique_cost"]) > (best["value"], -best["unique_cost"]):
            best = candidate
    return {**best, "candidate_evaluations": evaluations}


def _profile(problem, core, chosen):
    """An ordinary private-item knapsack after guessing purchased shared actions."""
    remaining = min(problem.budget, sum(problem.costs)) - problem.cost(chosen)
    items = [(problem.cost(req & ~core), w.weight, req)
             for w, req in zip(problem.witnesses, problem.requirements)
             if req & core & ~chosen == 0]
    return remaining, items


def _fractional_bound(remaining, items):
    value = Fraction(0)
    positive = []
    for cost, weight, req in items:
        if cost == 0:
            value += weight
        else:
            positive.append((Fraction(weight, cost), cost, weight))
    for density, cost, weight in sorted(positive, reverse=True):
        take = min(remaining, cost)
        value += density * take
        remaining -= take
        if not remaining:
            break
    return value


def _knapsack(remaining, items):
    # Values and realizing action unions; two layers also handle zero-cost items.
    dp = [(0, 0)] * (remaining + 1)
    transitions = 0
    for cost, weight, req in items:
        previous = dp
        dp = previous.copy()
        for capacity in range(cost, remaining + 1):
            transitions += 1
            value, mask = previous[capacity - cost]
            if value + weight > dp[capacity][0]:
                dp[capacity] = value + weight, mask | req
    return dp[-1][1], transitions


def shared_core_dp(problem, *, order=None, max_profiles=None):
    """Exact shared-core DP, or an anytime certificate if max_profiles is given.

    Arbitrary advice orders core masks; it never supplies bounds or rewards.
    Fractional private-item relaxations certify every unexplored core profile.
    Returned bounds use rational strings, avoiding floating-point certification.
    """
    core = problem.shared_core()
    profiles = {}
    for chosen in subsets(core):
        remaining, items = _profile(problem, core, chosen)
        if remaining >= 0:
            profiles[chosen] = (_fractional_bound(remaining, items), remaining, items)
    if order is None:
        order = sorted(profiles, key=lambda s: (-profiles[s][0], s))
    else:
        # Omitted/duplicated/invalid advice cannot remove candidates.
        order = list(dict.fromkeys(s for s in order if s in profiles))
        seen = set(order)
        order.extend(s for s in sorted(profiles) if s not in seen)
    best, lower, solved, transitions, pruned = 0, problem.value(0), 0, 0, 0
    pending_upper = Fraction(lower)
    for chosen in order:
        upper, remaining, items = profiles[chosen]
        if upper <= lower:
            pruned += 1
            continue
        if max_profiles is not None and solved >= max_profiles:
            pending_upper = max(pending_upper, upper)
            continue
        mask, count = _knapsack(remaining, items)
        transitions += count
        solved += 1
        value = problem.value(mask)
        if value > lower:
            best, lower = mask, value
    upper = max(Fraction(lower), pending_upper)
    return result(problem, best, candidate_evaluations=solved + 1,
                  lower=lower, upper=str(upper), certified_optimal=upper == lower,
                  core_size=core.bit_count(), core_profiles=len(profiles),
                  profiles_solved=solved, profiles_pruned=pruned,
                  dp_transitions=transitions)
