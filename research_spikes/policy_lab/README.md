# Deterministic policy lab

This isolated stdlib prototype optimizes explicit evidence-completion patterns.
It does not change production selection, call an LLM, query live experiments,
or read future outcome labels. Read the [formal report](../../tasks/research/policy-lab/report.md)
before interpreting the results.

From the repository root:

```sh
uv run python -m pytest research_spikes/policy_lab/test_model.py -q
uv run python -m research_spikes.policy_lab.experiments --output /tmp/policy-lab-results
```

The optional historical replay accepts only the January 2018 CIViC file with
the exact SHA-256 already recorded in the repository:

```sh
uv run python -m research_spikes.policy_lab.experiments \
  --output /tmp/policy-lab-results \
  --civic /path/to/civic-01-Jan-2018.tsv
```

Raw data stays outside Git. The download URL and expected hash are embedded in
`experiments.py`.
The script does not auto-download data or accept a 2022 outcome file. The
checked-in result JSON is sufficient to inspect every reported comparison.
Wall-clock timings vary across reruns; objectives, selected policy behavior,
fixed random seeds, and exact checks are reproducible.

To regenerate the standalone chart and HTML (Matplotlib is an already-declared
optional repository dependency):

```sh
uv run --extra litmap python -m research_spikes.policy_lab.present \
  --results tasks/research/policy-lab/results \
  --output tasks/research/policy-lab
```

`model.py` represents each action by a bit, rejects cyclic prerequisites,
closes every requirement transitively, and charges each action once.
`shared_core_dp` returns the actual union plus a rational upper bound. Its
optional advice is a finite sequence of integer masks; omitted masks are filled.
Its `max_profiles` budget limits exact knapsack solves **after** every core
profile's upper bound is built. Bounds and exact solutions use no hidden queries.

`exact_actions` is an exponential evaluation oracle, never a general scalable
policy. The independent tests use raw masks instead of its closure/value code.
Greedy controls include all residual prerequisite costs. `allocated_seed_greedy`
implements the inspected Arulselvan pseudocode plus free incidental completion;
the source audit distinguishes its published approximation claim from our
independently proved exact theorem.

`experiments.py` supplies exhaustive finite checks, the shared-setup family,
coverage/objective mismatch, separate hidden-box and paid-revelation Bellman
oracles, and historical source-sharing panels. Each historical reward requires
one frozen pair of citations, not any two citations and not biological truth.
The biological costs are simulated unit source acquisitions. Small panels are
intentional; their exactness is not a whole-corpus scalability result.

For an existing acquired set, form a residual instance by removing acquired
actions from closed witnesses and remaining prerequisites/costs. The current
prototype deliberately has no live-engine adapter, general plugin framework,
or production cache. Such an adapter needs the action identity, context, cost,
visibility and verifier records specified in the report.
