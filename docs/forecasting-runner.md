# Historical graph forecasting runner

The runner builds an inspectable graph, selects more historical evidence, and reranks a fixed pool of variant–therapy associations. It uses graph structure only: no LLM call, no external service, and no future outcome input. The CIViC task concerns later recorded associations, not treatment benefit or first scientific discovery.

```sh
uv run python scripts/run_forecast.py \
  demo/forecasting/scenarios/civic-2018-2022/historical.json \
  --output demo/forecasting/runs/civic-2018-2022-greedy.json
```

Saved paths are exclusive: the command refuses to overwrite an existing run. Use a new output path to preserve another configuration, or omit `--output` for a deterministic content-derived filename. Evaluate the serialized predictions separately with `scripts/evaluate_forecasts.py`; the runner never opens the outcome packet. A presenter may combine historical data, committed run, and outcomes only after forecasting.

## Acquisition and selection

The default seed graph contains the first quarter of historical evidence, ordered by availability date and ID. Four rounds acquire eight more evidence records each. These revisions describe computation within the frozen historical corpus, not the passage of real-world publication years. `--rounds`, `--batch-size`, and `--seed` configure the run; Python callers can provide `initial_evidence_ids`.

Each candidate acquisition is one evidence record, with fixed metadata facets: source entity, target entity, relationship type, and available gene/disease context. Each distinct metadata facet has weight 1; a distinct evidence record contributes 0.25. Already covered facets contribute zero additional value. The engine selects a batch using maximum additional weighted coverage, recomputing marginal gains after every choice. IDs break ties deterministically. This treats each acquisition as one abstract budget unit; it is not measured token cost or equal-duration experiments.

The snapshot selector supports:

| Policy | Behavior |
| --- | --- |
| `greedy` | Recompute marginal coverage after each selection. |
| `exact` | Exhaustively optimize a tiny pool; refuse more than 100,000 combinations. |
| `uniform` | Seeded sampling without replacement. |
| `top_singleton` | Rank individual coverage once, ignoring overlap among selections. |
| `judge_fixture` | Use explicitly supplied `fixture_judge_score` values; label origin `fixture`. No current or live LLM judge was measured. |

For a frozen pool, nonnegative fixed weights, equal costs, and a cardinality budget, coverage is monotone submodular and greedy attains at least `1 − 1/e` of optimal coverage. This is the established [Nemhauser–Wolsey–Fisher result](https://thibaut.horel.org/submodularity/papers/nemhauser1978.pdf), not a new theorem. Each batch also reports a valid instance upper bound from singleton and residual marginal gains, and the achieved value divided by that bound. These certificates concern the specified coverage objective only. They do not establish optimal continuation of an evolving research tree or predict scientific truth.

## Structural forecasts and comparison boundaries

The main score sums degree-normalized paths of length two or three between each candidate's endpoints in the acquired undirected association graph. A two-edge path contributes `1 / degree(middle)`; a three-edge path contributes `1 / sqrt(degree(first) * degree(second))`. Outputs retain path node types, relation signatures, labels, and supporting acquired evidence IDs. Examples include variant → gene → variant → therapy and variant → therapy → variant → therapy. This is a common-neighbor/path heuristic; direction, resistance, and sensitivity remain source context, not causal claims inferred by the scorer.

The graph joins a claim when at least one of its historical evidence records is acquired. It displays only acquired evidence IDs and their source-specific contexts. Forecast candidates remain fixed through the run; later labels do not choose candidate pairs or acquisition facets.

The packet includes three comparison rankings:

- `popularity`: target degree using exactly the same final evidence and candidates; a matched-input baseline.
- `initial_graph`: the seed graph ranking, a progress diagnostic with less evidence. This is **not** a matched-information static-versus-evolving ablation.
- `full_historical_graph`: all historical evidence, an acquisition-budget reference. Its information budget generally exceeds the selected run.

With all evidence acquired, the evolving graph and full historical graph have identical scores by construction. The current implementation does not claim an advantage from graph iteration itself. Different selection policies can be compared at fixed acquisition budgets; measured forecasting gains require the separate outcome evaluator.

## Python and replay contract

```python
from dnhacksbio.forecasting.runner import run_scenario, save_run
from dnhacksbio.forecasting.scoring import score_candidates
from dnhacksbio.forecasting.selection import select_branches

packet = run_scenario(scenario, policy="greedy", batch_size=8, rounds=4)
save_run(packet, "my-new-run.json")
```

`score_candidates(scenario, evidence_ids=None, method="typed_paths")` returns rows containing `candidate_id`, `query_id`, `source`, `target`, `score`, global `rank`, `query_rank`, `reason`, `evidence_ids`, and example `paths`. Scores are heuristic values, not probabilities. An explicit evidence subset must belong to the historical scenario.

`select_branches(branches, k, policy="greedy", weights=None, covered=(), seed=0)` accepts `{id, facets}` rows, with an optional fixture judge score. Its output includes selected IDs, per-choice marginal gains, objective value, upper bound, certificate ratio, and assumptions.

`run_scenario` returns `scenario_id`, `origin`, `model`, `policy`, `events`, `forecasts`, `metrics`, and `costs`, plus deterministic `id`, `scenario_sha256`, `revisions`, `comparisons`, and configuration. `metrics` starts empty because future labels were not read. JSON serialization rejects non-finite values. The scenario itself is unchanged.

Each event has `seq`, `type`, `revision`, `title`, `description`, and `payload`:

- `graph_updated`: acquired `node_ids`/`claim_ids`, acquired and added evidence IDs, and graph counts. Reconstruct nodes/claims from the scenario; filter each claim's evidence IDs and source-specific contexts to the event's acquired evidence IDs.
- `branches_selected`: choices, branch titles/facets, and the snapshot coverage certificate.
- `forecast_recorded`: ranked `candidate_ids`, count, and a revision reference. The corresponding `revisions` entry contains the complete ranking, previous rank, and rank movement.

No timestamps or nondeterministic model outputs enter the run; identical inputs/configuration reproduce the same packet. All data can be replaced by a synthetic historical scenario. Fixture judge runs stay explicitly labeled, and synthetic source packets should identify their dataset accordingly.

## Validation

```sh
uv run pytest tests/test_forecasting_selection.py tests/test_forecasting_runner.py
```

Tests independently enumerate small coverage optima, check the greedy guarantee and certificate, construct a real typed path that changes ranking after acquisition, enforce historical-only inputs and acquired contexts, prove the pure runner opens no files, check matched-input popularity, and verify exclusive prediction serialization. Full repository gates remain those in `AGENTS.md`.

## Recorded CIViC result

The committed `demo/forecasting/runs/civic-2018-2022-{greedy,uniform,top-singleton}.json` packets use 54 seed evidence records plus 32 acquisitions and the same 683 eligible candidates. All three packets were serialized before the evaluator opened the later outcome file. `demo/forecasting/reports/civic-2018-2022.json` includes their hashes, per-query results, all hits/misses, and comparison metadata. There were 24 later recorded associations.

| Ranking | Average precision | AUROC | Precision at 5 |
| --- | ---: | ---: | ---: |
| Greedy acquisition + paths | 0.05169 | 0.60426 | 0.00 |
| Uniform acquisition + paths | 0.08405 | 0.66923 | 0.20 |
| Top-singleton acquisition + paths | 0.05629 | 0.63237 | 0.00 |
| Popularity on final greedy graph | 0.05585 | 0.58204 | 0.00 |
| Initial graph, less evidence | 0.05422 | 0.57910 | 0.00 |
| All historical evidence, larger budget | 0.20108 | 0.81873 | 0.20 |

Greedy coverage does **not** beat the forecasting baselines in this run. Its optimization certificate remains valid for coverage, which is a different objective. This is one scenario and one uniform seed; do not infer statistical superiority. Parameters were not retuned after inspecting the outcomes.

To reproduce the comparison directly from the saved packets:

```python
import json
from pathlib import Path
from dnhacksbio.forecasting.evaluation import compare_forecasts

base = Path("demo/forecasting")
scenario = json.loads((base / "scenarios/civic-2018-2022/historical.json").read_text())
runs = {name: json.loads((base / f"runs/civic-2018-2022-{name}.json").read_text())
        for name in ("greedy", "uniform", "top-singleton")}
models = {name.replace("-", "_") + "_paths": run["forecasts"] for name, run in runs.items()}
models.update(runs["greedy"]["comparisons"])
outcomes = json.loads((base / "scenarios/civic-2018-2022/outcomes.json").read_text())
report = compare_forecasts(scenario["candidates"], models, outcomes["outcomes"])
```
