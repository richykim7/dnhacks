# Controlled graph reasoning

This optional experiment asks a model to rank one fixed historical query while maintaining
up to six citation-linked hypotheses. It compares three representations over exactly the
same candidate rows and evidence retrieval schedule:

| Condition | Source information | Model memory consumed on the next step |
| --- | --- | --- |
| `flat_log` | Evidence and source claims serialized in a text log | Hypotheses serialized in the log |
| `static_graph` | Initial source graph; all evidence and later source claims remain in the log | Hypotheses in the log |
| `evolving_graph` | Source graph grows with acquired evidence; source texts remain in the log | Hypotheses in a separate graph overlay |

The model can replace, revise or remove hypotheses, but cannot write source facts. Each
accepted hypothesis is forced to `unverified_model_hypothesis`. Citation checks establish
that a source was available, not that it entails a prediction. Association direction and
disease context remain in the source packet; resistance is not treatment benefit.

## Run and replay

```bash
# No model dependency or credentials needed for an explicitly illustrative replay.
.venv/bin/python scripts/run_forecast_reasoning.py \
  demo/forecasting/scenarios/civic-2018-2022/historical.json \
  --fixture --candidate-limit 8 --evidence-limit 6 \
  --output-dir demo/forecasting/reasoning/fixture

# Existing Claude Agent SDK/CLI login; six bounded calls (three concurrent conditions).
# The SDK is in the project's existing optional llm dependency group.
.venv/bin/python scripts/run_forecast_reasoning.py \
  demo/forecasting/scenarios/civic-2018-2022/historical.json \
  --candidate-limit 20 --evidence-limit 12 --steps 2 --output-tokens 4000 \
  --output-dir demo/forecasting/reasoning/civic-model
```

`--model` overrides the existing `llm.SONNET` default. `--query-id` chooses a historical
query explicitly. Otherwise selection takes the query with the greatest historical source
claim degree, then orders its candidates by historical target degree and stable ID. Relevant
evidence is ordered by its count of claims touching selected endpoints, availability date,
and ID, then divided into balanced batches. Neither selection nor retrieval reads outcomes.

The checked-in `civic-model` packet is a real `claude-sonnet-5` run: 20 candidates for
historically selected query `civic:variant:306`, 12 sources, two steps and six successful
single-attempt calls. Final rankings differ. Output tokens totaled 5,199 for flat, 5,111
for static and 5,098 for evolving. This artifact records predictions only; it does not
claim a forecasting improvement. The separate `fixture` packet is illustrative throughout.

The synchronous API is `run_reasoning_comparison(scenario, **options)`; async callers use
`arun_reasoning_comparison`. An injected async `completion(prompt, **kwargs)` can return a
JSON string or a dictionary and accepts the same keywords as `llm.acomplete`. Injection and
fixtures are labeled `illustrative`; the built-in live provider is labeled `model`.

Every run writes `comparison.json` with full prompt packets, source/prompt hashes, returned
structured responses, per-step usage, graph revision deltas and diagnostics. `cohort.json`
identifies the exact eligible candidate rows. Only a wholly valid three-condition run writes
`forecasts.json` in the existing evaluator's `{models, model_metadata}` format. A failed run
removes any stale score file at that output path. Distinct output directories preserve prior
experiments. The CLI exits 2 when comparison is incomplete.

Invalid rows, unknown citations, incomplete rankings, extra fields that attempt to promote a
hypothesis to fact, parse failures and timeouts remain visible. Invalid attempts cannot alter
hypothesis memory. There are no automatic substitute rankings or retries. Raw invalid
responses are stored as diagnostic strings so even a nonfinite score remains JSON-safe.

## Experimental boundary

All three conditions receive the same evidence at the same step and the same model, effort,
call count, turn ceiling, timeout and output-token ceiling. Actual token use can differ because
representations differ; this is matched allocation, not identical tokens consumed. The
source-packet hash at each step permits an independent parity check. The graph experiment
holds retrieval and the branch scheduler fixed; it does not measure scheduler advantage.

The live adapter reuses `llm.acomplete` with `tools=[]`, strict MCP configuration, empty
settings sources and a fresh empty working directory. The SDK's `allowed_tools=[]` alone
does **not** disable its default tools. New seam options are opt-in; existing callers retain
their defaults. Injected providers are controlled by their caller, so they do not inherit
these isolation guarantees.

Outcomes must be supplied only to the separate evaluator after these files are saved.
Filter the outcome packet to `cohort.json`'s candidate IDs and compare every model on that
same set. Preserve the dataset and budget tags. A cohort with no later-observed associations
has no eligible AP/AUROC comparison; unobserved means absent under the release protocol,
not experimentally disproved. These CIViC scores must remain separate from published Dyport
scores on a different cohort.

A modern model may already know post-cutoff biology from pretraining. Restricting retrieved
evidence does not establish historical ignorance. This small query is a functional
representation experiment; superiority needs repeated queries, seeds/model samples,
uncertainty estimates and transparent null results. The checked-in fixture demonstrates
replay and validation only.
