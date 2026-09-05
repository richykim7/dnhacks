"""Reproducible finite audits and matched-budget mechanisms (stdlib only).

Run: python -m research_spikes.policy_lab.experiments --output <directory>
Optional: --civic /path/to/civic-01-Jan-2018.tsv (hash-checked historical input).
No 2022 snapshot or later label file is accepted or read.
"""
import argparse
import csv
import hashlib
import json
import random
import statistics
import time
from collections import Counter, defaultdict
from fractions import Fraction
from itertools import combinations
from pathlib import Path

from .model import Instance, Witness, allocated_seed_greedy, exact_actions, greedy, seeded_greedy, shared_core_dp


def matched(problem, *, seed=0, coverage_sets=None, oracle=True):
    outputs = {}
    policies = {
        "deduplicated_coverage": lambda: greedy(problem, "coverage", coverage_sets=coverage_sets),
        "completion_singleton": lambda: greedy(problem, "singleton"),
        "deduplicated_witness": lambda: greedy(problem),
        "two_seed_witness": lambda: seeded_greedy(problem),
        "allocated_two_seed": lambda: allocated_seed_greedy(problem),
        "shared_core_exact": lambda: shared_core_dp(problem),
    }
    if oracle:
        policies["action_oracle"] = lambda: exact_actions(problem)
    for name, run in policies.items():
        start = time.perf_counter()
        outputs[name] = {**run(), "wall_seconds": time.perf_counter() - start}
    random_values = [greedy(problem, "random", random.Random(seed + i)) for i in range(32)]
    outputs["uniform_32_seeds"] = {
        "mean_value": statistics.mean(r["value"] for r in random_values),
        "mean_unique_cost": statistics.mean(r["unique_cost"] for r in random_values),
        "min_value": min(r["value"] for r in random_values),
        "max_value": max(r["value"] for r in random_values), "experimental_queries": 0,
    }
    return dict(name=problem.name, actions=len(problem.costs), patterns=len(problem.witnesses),
                core_size=problem.shared_core().bit_count(), budget=problem.budget,
                policies=outputs)


def shared_setup(m):
    costs = (m,) + (1,) * (3 * m)
    prereqs = (0,) + (1,) * m + (0,) * (2 * m)
    witnesses = tuple(Witness(1 | (1 << i), m) for i in range(1, m + 1))
    witnesses += tuple(Witness(1 << i) for i in range(m + 1, 3 * m + 1))
    return Instance(costs, prereqs, witnesses, 2 * m, f"shared-setup-m{m}")


def finite_audit():
    counts = Counter()
    worst = None
    # ALL unweighted singleton/pair reward families on 4 actions and all budgets.
    masks = [1 << i for i in range(4)] + [(1 << i) | (1 << j) for i, j in combinations(range(4), 2)]
    for family in range(1 << len(masks)):
        witnesses = tuple(Witness(mask) for i, mask in enumerate(masks) if family & (1 << i))
        for budget in range(5):
            problem = Instance((1,) * 4, (0,) * 4, witnesses, budget)
            oracle, dp = exact_actions(problem), shared_core_dp(problem)
            assert oracle["value"] == dp["value"] == Fraction(dp["upper"])
            counts["exhaustive_reward_family_budget_pairs"] += 1
            singleton = greedy(problem, "singleton")
            if oracle["value"] and (worst is None or singleton["value"] / oracle["value"] < worst["ratio"]):
                worst = dict(ratio=singleton["value"] / oracle["value"], budget=budget,
                             witness_masks=[w.actions for w in witnesses],
                             singleton=singleton, optimum=oracle)
    # Random weighted DAGs, empty/duplicate witnesses, and adversarial advice.
    rng = random.Random(20260905)
    for _ in range(600):
        n = rng.randrange(1, 10)
        costs = tuple(rng.randrange(1, 5) for _ in range(n))
        prereqs = tuple(sum(1 << j for j in range(i) if rng.random() < 0.18) for i in range(n))
        witnesses = tuple(Witness(rng.randrange(1 << n), rng.randrange(0, 11))
                          for _ in range(rng.randrange(0, 12)))
        problem = Instance(costs, prereqs, witnesses, rng.randrange(sum(costs) + 1))
        optimum = exact_actions(problem)["value"]
        # Advice deliberately includes invalid, missing and duplicate profiles.
        advice = [rng.randrange(1 << n) for _ in range(5)] + [-1, 1 << (n + 1)]
        for limit in (0, 1, 2, None):
            solution = shared_core_dp(problem, order=advice, max_profiles=limit)
            assert solution["value"] <= optimum <= Fraction(solution["upper"])
            if limit is None:
                assert solution["value"] == optimum and solution["certified_optimal"]
            counts["weighted_dag_advice_certificates"] += 1
    return {**counts, "invalid_certificates": 0, "oracle_mismatches": 0,
            "singleton_counterexample_found": worst,
            "meaning": "Finite implementation audit; general results require the report proofs."}


def hidden_box_oracle(n, probes):
    """Exact same-information Bellman oracle under a uniform one-prize prior.

    A query opens a box. All failures
    are indistinguishable and the unique winning box is uniform. Stop on success.
    No clairvoyant label is available to the policy's choice.
    """
    from functools import cache

    @cache
    def value(remaining, left):
        if left == 0 or remaining == 0:
            return Fraction(0)
        # Every available action has the same conditional transition distribution.
        return Fraction(1, remaining) + Fraction(remaining - 1, remaining) * value(remaining - 1, left - 1)

    answer = value(n, probes)
    assert answer == Fraction(min(n, probes), n)
    return dict(boxes=n, probes=probes, adaptive_optimum=str(answer),
                clairvoyant_optimum=1 if probes else 0, bellman_states=value.cache_info().currsize)


def revealing_action_oracle(n, budget=2):
    """Exact adaptive Bellman oracle: pay to reveal, then pay to execute child.

    The unique successful root is uniform; root identities are known, its child
    is unavailable until revealed. The value function has controller information
    only, never the hidden winning root. Symmetry makes every root choice equal.
    """
    from functools import cache

    @cache
    def value(unopened, child_available, left):
        if left == 0:
            return Fraction(0)
        if child_available:
            return Fraction(1)  # Spend one action to complete the revealed child.
        if not unopened:
            return Fraction(0)
        return (Fraction(1, unopened) * value(unopened - 1, True, left - 1)
                + Fraction(unopened - 1, unopened) * value(unopened - 1, False, left - 1))

    answer = value(n, False, budget)
    assert answer == Fraction(min(n, max(0, budget - 1)), n)
    return dict(roots=n, budget=budget, adaptive_optimum=str(answer),
                clairvoyant_optimum=1 if budget >= 2 else 0,
                bellman_states=value.cache_info().currsize,
                meaning="Root acquisition and revealed-child execution each cost one.")


def synthetic():
    setup = [matched(shared_setup(m), oracle=m <= 4) for m in (3, 4, 6, 8)]
    for row, m in zip(setup, (3, 4, 6, 8)):
        assert row["policies"]["deduplicated_witness"]["value"] == 2 * m
        assert row["policies"]["shared_core_exact"]["value"] == m * m
    # Coverage decoys have 3 disjoint represented facets each; complementary
    # experiment actions have one each. Both objectives are shown explicitly.
    problem = Instance((1,) * 4, (0,) * 4,
                       (Witness(1, 1), Witness(2, 1), Witness(12, 100)), 2, "coverage-completion-mismatch")
    facets = (0b111, 0b111000, 1 << 6, 1 << 7)
    counterexample = matched(problem, coverage_sets=facets)
    counterexample["coverage_facet_masks"] = facets
    counterexample["interpretation"] = "Greedy is optimal for its declared coverage here; that objective omits pair completion."
    # Price of disallowing reuse: same target packet count has m*(m+1) cost
    # instead of 2m. This isolated arithmetic control is ONLY a caching gain.
    caching = [dict(m=m, completed_patterns=m, shared_cost=2*m, duplicated_cost=m*(m+1))
               for m in (3, 4, 8, 16, 32)]
    advice = []
    for m in (4, 16, 32):
        problem = shared_setup(m)
        advice.append(dict(m=m, helpful_core_order=shared_core_dp(problem, order=[1, 0], max_profiles=1),
                           misleading_core_order=shared_core_dp(problem, order=[0, 1], max_profiles=1),
                           misleading_completed=shared_core_dp(problem, order=[0, 1]),
                           caveat="Advice orders optimization work only; experimental-query cost stays zero."))
    return dict(shared_setup=setup, coverage_counterexample=counterexample, caching_only_control=caching,
                advice_certificates=advice,
                hidden_box_oracles=[hidden_box_oracle(n, min(3, n)) for n in (4, 8, 16, 64)],
                revealed_action_oracles=[revealing_action_oracle(n) for n in (4, 8, 16, 64)])


CIVIC_SHA = "8895ce10b7c119856c3cbd38d8cf08fb597dbd294b06e22eaf50c35ba0db05d3"
CIVIC_URL = "https://civicdb.org/downloads/01-Jan-2018/01-Jan-2018-ClinicalEvidenceSummaries.tsv"


def biological(path):
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != CIVIC_SHA:
        raise ValueError("only the manifest-pinned January 2018 snapshot is allowed")
    rows = list(csv.DictReader(raw.decode("utf-8-sig").splitlines(), delimiter="\t"))
    groups, paper_rows = defaultdict(set), Counter()
    fields = ("gene_id", "variant_id", "disease", "drugs", "evidence_type", "evidence_direction", "clinical_significance")
    for row in rows:
        pmid = row["pubmed_id"].strip()
        if not pmid.isdigit():
            continue
        context = tuple(row[field].strip() for field in fields)
        groups[context].add(pmid)
        paper_rows[pmid] += 1
    # Freeze one SPECIFIC pair per context, not an OR-over-all-pairs reward.
    # No claim of independence: distinct publications may reuse an experiment.
    eligible = [(context, tuple(sorted(papers, key=int)[:2]))
                for context, papers in sorted(groups.items()) if len(papers) >= 2]
    outputs, packet_manifest = [], []
    for start in range(0, len(eligible), 6):
        chunk = eligible[start:start + 6]
        papers = sorted({paper for _, pair in chunk for paper in pair}, key=int)
        indices = {paper: i for i, paper in enumerate(papers)}
        witnesses = tuple(Witness(sum(1 << indices[p] for p in pair), 1, " | ".join(context))
                          for context, pair in chunk)
        # Facets are contexts associated with the source in the January snapshot,
        # providing a real deduplicated coverage baseline on the same sources.
        contexts = sorted({context for context, sources in groups.items() if sources.intersection(papers)})
        facets = tuple(sum(1 << j for j, context in enumerate(contexts) if paper in groups[context])
                       for paper in papers)
        for budget in sorted({max(1, len(papers) // 3), max(1, len(papers) // 2), max(1, 2 * len(papers) // 3)}):
            problem = Instance((1,) * len(papers), (0,) * len(papers), witnesses, budget,
                               f"civic-packet-{start//6:03d}-budget-{budget}")
            outputs.append(matched(problem, seed=start, coverage_sets=facets))
        packet_manifest.append(dict(packet=start//6, papers=papers,
                                    contexts=[dict(key=context, required_pmids=pair) for context, pair in chunk]))
    ratios = defaultdict(list)
    for row in outputs:
        optimum = row["policies"]["action_oracle"]["value"]
        for name, outcome in row["policies"].items():
            if "value" in outcome and optimum:
                ratios[name].append(outcome["value"] / optimum)
    return dict(source=CIVIC_URL, sha256=digest, rows=len(rows), publications=len(paper_rows),
                context_fields=fields, eligible_contexts=len(eligible), packets=len(packet_manifest),
                budgeted_instances=len(outputs),
                mechanism=dict(publications_in_multiple_contexts=sum(sum(p in s for s in groups.values()) > 1 for p in paper_rows),
                               contexts_with_multiple_publications=len(eligible)),
                aggregate={name: dict(mean_ratio=statistics.mean(values), min_ratio=min(values),
                                      nonzero_optimum_instances=len(values)) for name, values in ratios.items()},
                interpretation="Structural replay of a declared two-citation audit packet objective, with simulated unit source-acquisition costs. Not an actual exploration trace, an independent-evidence verifier, or forecasting performance.",
                future_labels_read=False, selection_rule="All eligible contexts, lexicographic groups of six; first two numeric PMIDs per context. No outcome-based selection or tuning.",
                packet_manifest=packet_manifest, comparisons=outputs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--civic", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    runs = [("finite-audit", finite_audit), ("synthetic", synthetic)]
    if args.civic:
        runs.append(("biological", lambda: biological(args.civic)))
    for name, run in runs:
        output = run()
        (args.output / f"{name}.json").write_text(json.dumps(output, indent=2) + "\n")
        print(name, "saved", flush=True)


if __name__ == "__main__":
    main()
