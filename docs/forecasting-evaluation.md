# Forecasting evaluation

The evaluator joins a complete set of candidate scores to separately supplied
later-observed outcomes. It makes no model calls, selects no historical evidence,
and cannot validate a model's training-data cutoff. A scorecard measures ranking
of later-recorded associations; an unobserved association is not disproved.

```python
from dnhacksbio.forecasting.evaluation import compare_forecasts

report = compare_forecasts(
    candidates,                     # [{id, source, target, query_id}, ...]
    {"graph": graph, "flat": flat},  # each [{candidate_id, score}, ...]
    outcomes,                       # [{candidate_id, observed: bool, evidence_ids}, ...]
    ks=(5, 10),
    provenance={"dataset_id": "civic-snapshot-pair", "origin": "computed"},
    protocol={"cutoff": "2024-01-01", "horizon": "2025-01-01"},
    model_metadata={
        "graph": {"budget_tag": "same-20-lookups"},
        "flat": {"budget_tag": "same-20-lookups"},
    },
)
```

`evaluate_forecasts(candidates, forecasts, outcomes, *, ks, provenance, protocol)`
evaluates a single model and returns the same report metadata, with model result
fields at the top level instead of beneath `models[model_id]`.

All IDs must be nonempty strings and unique within each input. Every model and
the outcome file must cover exactly the complete candidate ID set. Missing,
extra, duplicate, nonnumeric and nonfinite predictions reject the comparison;
there is no silent per-model row filtering. Outcomes require actual JSON
booleans and an evidence-ID list. An empty candidate cohort is an error.
Candidates and forecasts must not carry `observed` or `outcomes` fields.

Metrics:

- **Average precision:** non-interpolated area under the precision-recall step
  curve, grouping equal scores into a single threshold. Undefined (`null`) when
  the cohort contains no observed outcomes.
- **AUROC:** probability an observed candidate outranks an unobserved candidate;
  equal scores receive half credit. Undefined without both outcome classes.
- **P@k:** observed hits divided by `min(k, eligible candidates)`. Every result
  includes the requested k, actual selected count and precision denominator.
  Top-k lists break score ties by ascending candidate ID. This ID tie rule does
  not affect the tie-grouped AP or AUROC calculation.
- **Recall@k:** observed hits divided by all observed outcomes; `null` without
  observed outcomes.

`models[name].overall` pools the whole candidate set. `queries[query_id]`
contains metrics within each query. `macro` weights queries equally, excludes
undefined values, and reports eligible query counts separately for each metric.
Queries without positives contribute zero to macro precision and are excluded
from macro AP, recall and AUROC. Query cohorts of different sizes therefore
receive equal macro weight even when their effective top-k denominators differ.

`ranking` supplies candidate IDs, scores, query IDs, outcome flags and outcome
evidence IDs. Each top-k record also provides `hit_ids`, `missed_ids` (observed
outside top-k), `selected_ids`, and `unobserved_ids` (selected but unobserved).
These fields support the demo reveal. They contain future information and must
never be passed back to a historical forecasting run before it finishes.

Provenance and caller protocol metadata are retained. SHA-256 fingerprints cover
the normalized candidate cohort and outcome records, independent of row order.
Matching budget tags yield `declared_matched`, never a verified budget claim;
missing tags yield `unspecified`, differing tags yield `different`. Declared
per-model dataset IDs must agree with each other and the report dataset ID.

## Command line

```sh
uv run python scripts/evaluate_forecasts.py \
  --scenario demo/forecasting/scenarios/example.json \
  --outcomes /path/to/sealed-outcomes.json \
  --forecasts /path/to/predictions.json \
  --k 5 10 --output demo/forecasting/reports/example.json
```

The scenario file contains `id`, `candidates`, and optional `dataset`, `manifest`,
`cutoff`, and `horizon`. Outcomes can be a JSON list or an `{"outcomes": [...]}`
wrapper. Forecasts can be a mapping of model IDs to prediction lists, or an
`{"models": {...}, "model_metadata": {...}}` wrapper. Without `--output`, the
report is printed to stdout. Invalid inputs exit with status 2 without printing
a partial report. Outcome wrappers' scenario ID and horizon must match when
provided. File paths are recorded in provenance; no credentials or model
configuration files are read.

## Historical protocol and comparators

Freeze source availability, candidate universe and run budgets before prediction.
Use only evidence available at the cutoff for graph construction and iteration.
Keep outcome files sealed until the last forecast is committed. Replaying the
same retrieved historical evidence into flat-log, static-graph and evolving-graph
variants isolates the representation change. Evaluate adaptive retrieval as a
separate comparison. Model pretraining can contain later knowledge even when
retrieval is historically filtered; this evaluator does not rule that out.

Dyport is a separate external benchmark, not a CIViC comparator cohort. The
cached access audit at `tasks/research/graph-forecasting/dyport-access.json`
contains published-model results on the authors' unfiltered 2016 table, including
duplicate rows and model-specific nonfinite filtering. Do not compare those
aggregate numbers directly to a CIViC demo or to a deduplicated Dyport cohort.
Recompute every comparison on explicitly matched rows, recording any changed
sampling protocol. The generic evaluator intentionally does not import Dyport
scores or choose a deduplication policy. Its future importance fields must remain
evaluation metadata, never historical features.

Validation: `uv run pytest tests/test_forecasting_evaluation.py` checks known
rankings, score ties, undefined metrics, cohort mismatches, metadata, outcome
separation and the CLI. Synthetic fixtures are arithmetic tests, not performance
claims about the demo or biomedical discovery.
