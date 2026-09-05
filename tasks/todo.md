# Graph forecasting delivery

## Current brief

Build an iteratively created and consumed scientific graph that recommends promising developments before later evidence is revealed. Keep the engine domain agnostic and the flagship demo biological. The original delivery window is 16 hours, with abundant parallel compute and an AWS GPU if useful. Every data/output path must support fixtures. Production hardening is outside scope.

The presentation should serve scientists, express the ambition of advancing American science, and compete for the frontend design award. Historical comparisons and ablations make the forecasting claim falsifiable. Algorithmic guarantees must state an objective, assumptions, and comparator independent of LLM confidence.

Latest user decision: **greedy coverage is the provisional production policy**. Investigate a more interesting exploration policy in parallel, with publication potential as a research target. Exact selection remains a small-instance oracle.

## Completed planning

- [x] Inspect the graph, exploration, evidence, event, and frontend code.
- [x] Research existing scientific forecasting systems, public biological assets, and applicable algorithmic guarantees.
- [x] Download and inspect Dyport 2016 and two historical CIViC releases; verify PubTator3 export access.
- [x] Recompute cached baseline metrics and exhaustively audit the small coverage objective and residual bound.
- [x] Produce the [research brief and illustrative graph](../design/graph-forecasting-plan.html).
- [x] Pull main, read the mandatory Board/communication rules, and reconcile actual teammate ownership through Board posts.
- [x] Define [parallel session boundaries, first shared contract, and policy research gates](../design/parallel-session-plan.md).

## Next implementation tasks

- [ ] Post and agree on the tiny scenario/evidence/forecast/event contract with the active frontend owner.
- [ ] Build one CIViC historical scenario packet with cutoff-eligible candidates, source metadata, and separately stored outcomes. This is the recommended next task for this session.
- [ ] Feed an illustrative sequence into the teammate's active frontend; retain existing frontend/API ownership.
- [ ] Add structural graph scoring and provisional greedy selection through the current injection seam.
- [ ] Add an evaluator and save predictions before revealing outcomes; keep CIViC and Dyport scorecards separate.
- [ ] Compare flat evidence, static graph plus append log, and evolving graph at matched information and compute budgets.
- [ ] Compare greedy, current judge, uniform, and top-singleton selection; use exact small-instance optimum to measure the gap.
- [x] Run the isolated policy lab: complementary evidence first, shared acquisition as the stronger long-term target; apply two-hour and six-hour gates. See the policy-lab review below.
- [ ] Rehearse a measured replay, inspect misses and citations, and polish the graph transitions and evidence drawer.

## Review — research artifacts

- Dyport: downloaded 80,495,323 bytes, 336,710 rows, 30,619 positive labels, 306,091 sampled negatives, and 1,451 duplicate subject/object rows. All ten score variants were recomputed on the full unfiltered table. These are the authors' cached predictions, not our model scores or a reproduction of the paper's stratified results.
- CIViC: January 2018 and March 2022 snapshots contain 2,372 and 3,888 evidence rows. They provide the immediate historical graph route. Predicting later database additions does not establish first discovery worldwide.
- PubTator3: PMID 29355051 returned HTTP 200, 14,167 bytes, normalized entities, three relations, and publication-year metadata; the response contains a `PubTator3` document list.
- The Dyport score file lacks the historical source graph. A new Dyport predictor therefore needs additional input preparation; it does not block the CIViC visual slice.
- Finite coverage probe: 65,536 four-candidate/four-facet instances; 65,535 nonzero instances; worst greedy/optimum ratio 0.75; no invalid residual upper bounds. This checks an implementation against a scoped theorem, not biological predictive accuracy.
- HTML structure and embedded JavaScript syntax were checked. Earlier browser screenshot attempts timed out, so rendered layout and browser interaction remain visually unverified. The graph storyboard is explicitly illustrative.
- No new model forecasting run, integrated selector, GPU execution, or end-to-end forecasting advantage has been established.

## Review — coordinated session plan

- Pulled the coordination rules at main `587acb2`; read `AGENTS.md`, `BOARD.md`, and `COORDINATION.md`. Posted claims and updates as `ian/graph-plan`, and worked in an isolated task worktree.
- Two read-only research/audit workers also used the Board and posted completion. Future implementation sessions in the plan are proposed, not already launched.
- Confirmed that `dnhacks/s2--codex` owns the user-authorized React/TypeScript/Vite frontend and web API presentation. Removed the stale suggestion to avoid that migration.
- Confirmed that `dnhacks/s3--codex` is publishing a cleaned learned-evalue plan, with no engine implementation claimed. Proposed e-value fields are not assumed capabilities. Runtime history remains unresolved on the Board and is not a prerequisite for the new data/selection/replay slice.
- Updated the research brief and ledger to use greedy provisionally. Exact enumeration remains the evaluation oracle. The probe now computes the same whole-pool coverage cap described in the proof.
- Preserved research files and source metadata for cross-machine access; raw downloads stay local. Removed stale machine-specific planning history from this shared task list. The other session's pre-existing untracked planning file was not included.
- Validation for this planning/probe change: Python compilation, reproducible coverage and Dyport probes, report regeneration, JSON parsing, HTML/JavaScript structural checks, and diff review. No application behavior changed; the repository's full gate section was a placeholder at the audited revision.

Integration status and the resulting main commit are recorded on the [Board](https://github.com/richykim7/dnhacks/issues/1).

## Review — hackathon UX and presentation

- Inspected the rendered local app and the public preview supplied by `ian/graph-plan`; both initially opened in the empty investigation state. Also rendered populated Investigations and Evidence using the existing synthetic browser-test fixtures. The prominent tree represents researchers; the scientific graph is a separate destination.
- Produced the [ranked UX/demo review](../docs/hackathon-ux-review.md): actionable effort estimates, a 100-second script, specific screen interactions, official product references, and fallbacks for model calls, event streams, graph layout, evidence retrieval, metrics, empty data, assets and the presentation network.
- Built an [isolated presentation prototype](../design/ux-demo/index.html) with frozen-history, graph-growth, locked-forecast and evidence-reveal scenes. Candidate selection focuses support paths; rankings remain fixed on reveal; one illustrative candidate remains unresolved. Includes manual stepping, reset, cached content, reduced motion and a narrow layout.
- Kept illustrative source/ranking/outcome labels explicit. The prototype supplies no measured scientific result and its failure control rehearses local continuation rather than implementing a production network adapter.
- Posted production integration proposals before edits; `ian/graph-plan` retains Forecast UI/API ownership. No changes to production frontend, shared forecasting interfaces, e-values or exploration policy. Existing `frontend/DESIGN.md` should be updated by the integration owner if this stronger presentation direction is adopted.
- The initial `uv sync --extra dev` test environment lacked `claude-agent-sdk`, imported by the existing web server. Installed that existing optional dependency in the isolated environment to run the gates; no dependency manifest or lockfile changed. Only tracked tests are present in this worktree; the wider unversioned local vocabulary suite was not copied.
- Validation: frontend production build, 2 unit tests, all 10 browser tests and 46 tracked Python tests passed; `git diff --check` clean. Browser gates used isolated backend 8782/Vite 5188. The existing molecular invalid-file test failed twice on a cold preview while loading 3Dmol, then the unchanged full suite passed after the module was loaded; preload optional 3D assets before any demonstration. The existing 3Dmol build warning remains.
- Prototype validation: all four desktop scenes and the mobile reveal had zero axe violations; checked frozen ranking, outcome lock/reset, unresolved results, record disclosure, fallback scene preservation, offline stepping, reduced motion, no browser errors and a visible main control at 1440 × 900. Final integration status is recorded on the Board with the landed commit.

## Review — policy lab proofs and experiments

- Delivered the [formal model and complete proofs](research/policy-lab/report.md), [primary-paper audit](research/policy-lab/literature.md), [independent adversarial review](research/policy-lab/adversarial-review.md), [executable prototype](../research_spikes/policy_lab/README.md), and [standalone demo/figure](research/policy-lab/demo.html).
- Closed deterministic witness completion is Set-Union Knapsack. The exact small-shared-core DP and fractional certificates survive review, but are derived from established 1994 work; no new theorem is claimed. Arbitrary learned advice may reorder planning work without corrupting the certificate.
- Proved an arbitrarily bad shared-setup family for correctly deduplicated witness greedy, pair-witness exact hardness, and a revealed-action lower bound versus clairvoyance with the same-information optimum stated separately. Both seeded controls solve the shared-setup family.
- Reproduced 5,120 exhaustive reward/budget cases and 2,400 weighted-DAG/advice certificates with no oracle mismatch or invalid bound. The checked-in research regression suite has 64 passing tests; independent reviewers ran additional raw-mask checks.
- All 95 January 2018 CIViC citation-packet/budget cases match action enumeration. On 93 positive cases, residual witness greedy averages 0.969534 of optimum; both seeded controls and exact reach 1.0 throughout. Citation pairs and unit acquisition costs are declared simulation choices, not biological verification or forecasting accuracy. No later labels were read.
- Audited newly landed frozen graph-construction traces: 216 historical evidence records represent 166 source documents; each of three saved policies adds 32 records from 30 new sources. This shows potential document-stage reuse, not measured total compute savings or complementary experiment utility.
- Recommendation: retain delivery coverage greedy for its declared objective; use the existing exact specialization as a small-packet comparator/certificate. Proposed action/context/visibility/prerequisite/cost/verifier records were posted to the Board; production interfaces were not edited.
- Browser artifact checks passed: working theorem slider, no page errors, zero WCAG axe violations, and mobile layout without horizontal overflow. Final repository gate counts and integration commit are recorded on the Board; only tracked Python tests are present here, not the wider unversioned vocabulary suite. The clean dev-only environment initially lacked the already-declared optional LLM SDK; installed repository extras for full validation without changing dependency files.
