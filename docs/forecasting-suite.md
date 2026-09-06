# Frozen all-query graph-representation comparison

`scripts/run_forecast_suite.py` extends the initial single-query pilot to every historical query and every eligible pair. The original pilot remains unchanged. The CIViC packet has 22 queries and 683 pairs; no query is selected using later labels.

The protocol is fixed before model execution: sorted historical query IDs, at most 36 candidates per query (the script rejects any truncation), 12 historical evidence records, two steps, flat-log/static-graph/evolving-graph conditions, the repository's pinned SONNET model, 6,000 output tokens per call, one attempt, and a 90-second call timeout. A semaphore limits execution to three queries, hence at most nine simultaneous calls. This is 132 planned calls. Actual usage and failures remain in the saved query records.

```sh
.venv/bin/python scripts/run_forecast_suite.py \
  demo/forecasting/scenarios/civic-2018-2022/historical.json \
  --outcomes demo/forecasting/scenarios/civic-2018-2022/outcomes.json \
  --output-dir demo/forecasting/reasoning/civic-all-queries
```

The script uses the existing Claude SDK login through the repository LLM helper. It does not read credential files. `--fixture` runs the same workflow with explicitly illustrative outputs and no model calls. Use a fresh output directory: saved attempts cannot be overwritten or silently retried.

`manifest.json` freezes query IDs, candidate IDs, evidence schedules and budgets before the first call. Each `query-NN.json` retains accepted or invalid responses, usage and diagnostics. `sealed.json` hashes every query artifact. Only after all artifacts are sealed does evaluation first open the outcome file; it verifies the seal before doing so.

The main comparison includes only queries for which all three model conditions completed. `evaluation.json` reports excluded queries, failure diagnostics, candidate coverage and excluded positives. The popularity comparator uses exactly the same frozen evidence schedule for each included query. Its inference cost differs from the models and is labeled accordingly.

Primary metrics are query-macro average precision and precision@5. Average precision excludes no-positive queries with explicit eligibility counts; precision@5 includes all complete queries. Pooled scores are secondary because independently prompted query scores are not calibrated across queries. Paired 95% query bootstrap intervals use 2,000 resamples with seed 20260905 for evolving-minus-flat/static/popularity differences. These are exploratory intervals: biological queries share sources and entities, and only one model realization is observed per condition.

This forecasts later CIViC curation, not later scientific publications. All 27 later evidence records in the current packet cite papers from 2008–2016; 16 share URLs with historical evidence. Modern pretrained models may already know the associations. The representation comparison holds candidate and retrieval schedules fixed; it does not test adaptive retrieval or a superior branch scheduler.

## Review

Fixture tests verify complete historical candidate coverage, pre-call manifest persistence, bounded concurrency, unchanged budgets, no retries, seal-before-outcome ordering, tamper detection, common-query failure handling, same-evidence popularity, deterministic paired bootstrap, and no-positive metric handling. Live results and full repository gates are recorded in the PR and suite artifacts.

The recorded run attempted all 132 calls. Only **2 of 22 queries** passed every condition, leaving **64 of 683 pairs and 5 of 24 observed additions** in the main comparison. Nineteen positives were excluded along with failed queries. The flat, static and evolving conditions independently completed 14, 17 and 8 queries, respectively. `audit.json` summarizes validation failures, reported usage and budget deviations without altering any frozen run or the original evaluation.

| Condition | Conditional macro AP | AP-eligible queries | Conditional macro precision@5 |
|---|---:|---:|---:|
| Flat log | 0.4213 | 1 | 0.10 |
| Static graph | 0.5964 | 1 | 0.30 |
| Evolving graph | 0.6917 | 1 | 0.30 |
| Same-evidence popularity | 0.1724 | 1 | 0.00 |

All five evaluated positives belong to one query. These conditional numbers are inadequate to establish a general ranking advantage. The original evaluation's one-query AP bootstrap interval is degenerate and cannot support a credible confidence or significance claim; precision@5 has only two query clusters. Failed-response selection can be systematic. Do not present these figures as results across all 683 pairs or as a statistically established improvement.

Reported usage totals 1,951,317 input tokens including cache creation/reads and 459,721 output tokens across 130 usage-bearing calls; two attempted calls lack usage records. Three evolving-condition calls reported 6,128–6,777 output tokens despite the requested 6,000-token setting. Those queries are outside the main comparison, but the setting must be described as a request, not a verified hard execution limit. `audit.json` preserves the exact affected calls and implementation hashes. No retry, response repair, candidate tuning or model rerun was performed.
