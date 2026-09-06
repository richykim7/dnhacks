# Forecast demo

Open `/#forecast` after starting the app. This prepared route runs entirely from checked-in
historical artifacts. No live model, API key, GPU, or data download is needed for playback.
The default Investigations route is still available for the discovery engine.

```sh
uv sync --extra dev --extra llm
npm --prefix frontend ci
npm --prefix frontend run build
uv run python scripts/serve_ui.py --port 8765
# Open http://127.0.0.1:8765/#forecast
```

On narrow screens, the scientific graph scrolls horizontally to preserve readable entity
labels; the playback controls remain within reach.

The development page also works through Vite on 5174 with
`API_PROXY_TARGET=http://127.0.0.1:8765 npm --prefix frontend run dev`.
The temporary public preview is a read-only proxy to this local build; local build/serve
is the reproducible venue fallback. The public preview reloads when a new build lands.

## A two-minute walkthrough

1. **Read the past.** Show the January 2018 source graph. Select an entity and open a
   citation. The graph is a dated CIViC association map; it does not assert efficacy.
2. **Connect evidence.** Advance the saved acquisition sequence. Positions stay fixed
   while acquired evidence and connections change. Disease nodes summarize source contexts.
3. **Choose branches.** Inspect the greedy allocation and its evidence-coverage certificate.
   The certificate concerns this declared coverage objective, not predictive accuracy.
4. **Commit forecasts.** Open a ranked recommendation and its actual supporting path.
   The artifact already contains saved ranks, sources, and graph revisions. Download the
   full run, including all 683 candidate scores; the presentation shows the top 30.
5. **Open the future.** Rankings stay unchanged. Show the unobserved top recommendations
   before inspecting the first later match at saved rank 22. Its source dates remain visible.
6. **Model memory.** Compare the separately recorded flat-log, static-graph, and evolving-
   graph runs. Advance the two reasoning steps and inspect a citation-linked hypothesis.
   A proposal is unverified model memory, never a new source fact.
7. **The backtest.** Read the measured comparison, including misses. This first structural
   run has lower average precision with greedy acquisition than with uniform acquisition.

Select **Illustrative walkthrough** to exercise the same interaction without measured
claims. The app also falls back to this explicitly labeled provider while historical
artifacts are unavailable. It never invents a scorecard for that provider. Browser test
fixtures remain separate from the application.

## What the evidence actually establishes

- Target: later CIViC **curation additions**, not first scientific discoveries. All 27
  outcome evidence records in this packet cite papers published in 2008–2016; 16 have a
  source URL also present in the historical packet. A 2022 release date is not a 2022
  publication date. Rank 22 is a retrospective curation example, not an early discovery.
- Candidate: a variant–therapy-group association. Resistance, sensitivity, disease
  context, and conflicting findings belong to the underlying source statements. The
  forecast does not predict treatment-effect direction.
- Structural comparison: 683 fixed candidates, 24 observed later associations. Greedy,
  uniform and top-singleton use the same acquisition budget (54 initial sources + 32
  acquisitions). Initial-graph and full-historical-graph rows use different budgets and
  are reference points. Full historical evidence is not a matched-budget win.
- Model pilot: one historically selected query, 20 candidates, 12 sources, two calls per
  condition. A modern model may know post-cutoff science from pretraining. Retrieval
  isolation does not establish historical ignorance, and citation validation checks
  available IDs rather than entailment. See [reasoning](forecasting-reasoning.md).
- Outcome loading occurs only in the separate evaluator and completed-replay presenter.
  The browser receives a completed replay including outcomes; the reveal is a presentation
  control, not a security or pre-registration boundary. The saved runner commitment is
  the auditable boundary.

## Artifact/API boundaries

`GET /api/forecasting/demo` presents `historical.json`, the saved greedy run and the
separate structural comparison. It checks the run's historical-graph commitment before
presenting it. `GET /api/forecasting/run` returns the full unchanged saved run.
`GET /api/forecasting/reasoning` exposes the saved model comparison and separate evaluation
when available. These are read-only endpoints; they do not execute a model.

Optional `DNHACKS_FORECAST_SCENARIO`, `DNHACKS_FORECAST_RUN`, and
`DNHACKS_FORECAST_REPORT` environment variables choose local artifact paths. The outcomes
file is next to the historical scenario. The default paths are under `demo/forecasting/`.
Rebuild a scenario using [the data workflow](forecasting-data.md), then rerun [the structural
runner](forecasting-runner.md); a changed scenario does not silently reuse a mismatched run.

## UX exploration prompt

> Read AGENTS.md, BOARD.md, frontend/DESIGN.md, and the current Forecast route. Review the
> working demo and propose concrete UX, feature, and presentation changes that would most
> improve our odds of winning the frontend award. Prioritize an iteratively created and
> consumed scientific graph, anticipation of research developments, and falsifiable
> comparisons. Biology is the demo domain; keep the system general. We have a 16-hour
> hackathon window, abundant parallel compute, and permission to stub any data or output
> with clear provenance. No production hardening. Rank proposals by audience impact,
> implementation time, and dependency; give a 100-second interaction script and an
> independent prototype if useful. Coordinate on the Board before production edits;
> e-values belong to the teammate, and exploration theory belongs to another session.

## All-query study

The model-memory panel also presents the separately frozen all-query study: all 22
historical query IDs and all 683 eligible candidates, with 12 source records, two calls
per condition and a requested 6,000-output-token limit per call. Saved query progress
is available before the outcome reveal; comparison metrics and observed-label counts
open only after reveal. `DNHACKS_FORECAST_STUDY` can select a local study directory for
preview or fixtures. The default is `demo/forecasting/reasoning/civic-all-queries`.

Only two queries completed every condition's response validation: 64 candidates, five
later-observed associations, and one AP-eligible query. Conditional macro AP is 0.69167
for evolving graph, 0.59639 for static graph, 0.42135 for flat log, and 0.17241 for the
same-evidence popularity baseline. Macro precision@5 over both complete queries is
0.30, 0.30, 0.10 and 0.00 respectively. The other 20 queries and 19 observed associations
are excluded from that comparison and remain in the failure audit. Per-condition
completion is 14/22 for flat log, 17/22 for static graph and 8/22 for evolving graph;
its higher conditional score comes with lower completion in this run.

This is exploratory evidence on a selected-by-completion subset, not a general advantage.
A bootstrap interval from one AP-eligible query is uninformative; the interface suppresses
that interval. Actual reported token use can exceed the requested limit, so the controls
are matched requests rather than enforced compute budgets. All original outputs are saved,
including failed schema/citation validation, without repair or retrospective retries.
