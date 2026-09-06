# No-retrieval memory control

`scripts/run_forecast_memory_control.py` asks the model to score every sealed candidate with
**zero evidence**: only the cutoff, the horizon, the query variant label, and each candidate
therapy-group label. It answers one question that every model-scored result on this packet
depends on: does the model already know the later-recorded associations from pretraining?

If the no-retrieval ranking is strong, evidence-conditioned model runs on this packet measure
recall, not reasoning over the graph, and their advantage over baselines is capped by this
control. If it is near random, historical retrieval isolation is doing real work.

```sh
uv run python scripts/run_forecast_memory_control.py \
  demo/forecasting/scenarios/civic-2018-2022/historical.json \
  --run demo/forecasting/runs/civic-2018-2022-greedy.json \
  --outcomes demo/forecasting/scenarios/civic-2018-2022/outcomes.json \
  --output-dir demo/forecasting/reasoning/civic-no-retrieval
```

Protocol, fixed before the first call: sorted query IDs, every candidate per query, one call per
query, one attempt, low effort, thinking off, one turn, all tools and MCP servers disabled, an
empty temporary working directory, and a 4,000-output-token request. Three queries run at once.
`manifest.json` is written before any call and includes every prompt hash. Each `query-NN.json`
keeps the prompt hash, raw text, parsed response or errors, and reported usage. `sealed.json`
hashes the query records; evaluation verifies the seal and the historical packet hash before it
opens the outcome file. Existing files are never overwritten; use a fresh output directory.

Evaluation uses the existing `compare_forecasts` on identical rows: only queries whose response
scored the complete candidate set are included, and the saved structural run's
`full_historical_graph` and `popularity` comparators are filtered to the same rows. The saved run
must carry the same historical packet hash. `--fixture` writes explicitly illustrative scores
derived from candidate IDs with no model calls; it demonstrates the plumbing only.

Reading the result: the comparators see the whole 2018 graph and the control sees nothing, so
budgets are deliberately different. The control is not a competitor; it is a ceiling on what
evidence-conditioned model results on this packet can claim. Labels mean later CIViC release
inclusion, not first discovery, and all later evidence in this packet cites papers from 2008–2016.

## Recorded run

`demo/forecasting/reasoning/civic-no-retrieval/` holds a real `claude-sonnet-5` run: 22 of 22
queries returned a complete, valid scoring on the first attempt, so all 683 candidates and all
24 later-recorded associations are in the comparison. Reported usage: 42,797 input tokens and
25,674 output tokens across 22 calls.

| Model | Evidence seen | AUROC | AP | P@5 | P@10 |
|---|---|---:|---:|---:|---:|
| No-retrieval memory control | none | 0.854 | 0.233 | 0.20 | 0.30 |
| Structural path scorer | full 2018 graph, 216 rows | 0.819 | 0.201 | 0.20 | 0.20 |
| Popularity | full 2018 graph | 0.582 | 0.056 | 0.00 | 0.00 |

Query-macro AUROC: 0.853 for the control, 0.805 structural, 0.610 popularity.

**Reading.** With no evidence at all, the model ranks the later-recorded associations at least
as well as the structural scorer does with the entire historical graph. On this packet, a model
that sees evidence cannot be credited with reasoning over it: its pretraining already contains
the answers, which is consistent with every later evidence record citing papers from 2008–2016.
Evidence-conditioned model results on `civic-2018-2022` are therefore diagnostics of plumbing
and representation, not measurements of forecasting skill. The structural scorer, which uses
no model, remains the only uncontaminated forecasting number on this packet. A clean model
forecast needs a cohort whose outcomes postdate the model's training data, or a prospective run.
