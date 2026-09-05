# Parallel delivery: iterative graph forecasting

Status: implementation split proposed from main `587acb2` and the live [team Board](https://github.com/richykim7/dnhacks/issues/1), September 5, 2026. This plan records actual ownership separately from sessions to start. Recheck the Board before claiming any work. The earlier [research brief](graph-forecasting-plan.html) contains asset evidence and the full backtest rationale.

## Decisions now

- Keep the architecture domain agnostic; use biology for the demo. Start with the downloaded CIViC historical releases because they already contain readable evidence and stable identifiers. Keep the biological question open until a small candidate audit establishes a usable case.
- Use **marginal-gain greedy coverage** as the provisional branch policy. Exact enumeration is an evaluation oracle and optional displayed certificate. It does not replace the chosen production policy.
- Build one complete sequence: historical evidence → graph revision → branch allocation → committed forecasts → later evidence → scorecard. Every transition supports a fixture immediately, recorded results next, and live execution where useful.
- Preserve a separate policy research lane with a concrete theoretical objective, executable counterexamples, strong baselines, and time gates. It does not block the demo.
- The 16-hour budget is the original delivery window, not a new allowance. Compress the milestones below to the actual remaining time. Stop adding demo features early enough to rehearse.

## What the teammate is actually doing

| Owner | Board-confirmed work | Coordination implication |
|---|---|---|
| `dnhacks/s2--codex` | User-authorized React/TypeScript/Vite frontend rewrite on `dnhacks/s2--codex-frontend`; owns `frontend/`, `src/dnhacksbio/webui/`, `scripts/serve_ui.py`, its frontend server test/doc, `.gitignore`, and `.env` | This is the frontend and API presentation session. Do not launch a second rewrite or edit its API handlers from another lane. No credential-file access is needed for this plan. |
| `dnhacks/s3--codex` | Cleaning and publishing the previously ignored learned-evalue plan under `plans/PLAN-learned-evalue.md`; no engine implementation claimed | Read the tracked plan when it lands. Optional `ToolResult.e_value/e_method` fields and wealth traces are proposals, not installed capabilities or agreed graph contracts. |
| `ian/graph-plan` | This session map, graph research brief, asset metadata, and reproducible probes | Deliver these artifacts, then take the historical scenario/data slice described below under a fresh Board claim. |

The statistical review raised unresolved claim/measurement alignment, dependence, selective-submission, and fallback issues. Keep that work outside the forecasting delivery dependency chain until its actual implementation and interface are agreed. Tracked main contains Docker calls, while a Board discussion says the runtime changed; source inspection alone does not settle the team's running environment. None of the proposed data, selection, or replay work requires resolving that runtime question first.

The frontend owner has been asked on the Board for its minimum scenario/event contract. The contract below is a concrete proposal for that exchange, not a claim that the frontend already accepts it.

## Sessions to run

Run the existing frontend session plus four narrowly owned lanes. Use separate branches and worktrees; directory names below define proposed boundaries, not permission to overwrite another active claim.

| Session | Owns | First reviewable result | Done for the demo when |
|---|---|---|---|
| **Frontend — already active** | Existing frontend/API paths owned by `dnhacks/s2--codex` | One polished scene consuming a fixture, with stable graph positions and an evidence drawer | A judge can start a run, understand a changed recommendation, inspect evidence, and reveal outcomes; recorded playback uses the same experience |
| **Historical scenario + shared records — our next slice** | New `src/dnhacksbio/forecasting/records.py`, `sources/civic.py`, `snapshots.py`, package initializers; `scripts/build_forecast_data.py`; `demo/forecasting/scenarios/` | One small historical graph, eligible candidate list, separately stored later outcomes, and a manifest with source URLs/dates/hashes | The scorer can run using only the historical input file; IDs match the UI and evaluator; future records are unavailable to its normal input path |
| **Forecast runner + greedy policy** | New `forecasting/scoring.py`, `runner.py`, `selection.py`; `scripts/run_forecast.py`; the one small agreed hook in `explorer/explorer.py` | Structural baseline scores and greedy decisions on the common scenario, written before reveal | Same-scenario flat/static/evolving graph runs and selector comparisons produce inspectable records; default selection is greedy |
| **Evaluation + replay assembly** | New `forecasting/evaluation.py`; `scripts/evaluate_forecasts.py`; `demo/forecasting/runs/`, `demo/forecasting/reports/` | Evaluator against a fixed example plus a fixture trace for the frontend | Scores come from committed predictions and matching outcome rows; real, replayed, imported-baseline, and illustrative results remain identifiable |
| **Policy lab — research only** | New `research_spikes/policy_lab/`; `tasks/research/policy-lab/` | Formal objective/comparator, tiny exact oracle, one greedy failure case, closest-prior-art map | A scoped lemma and measured advantage survive the gates below, or a useful negative result is documented; production remains shippable either way |

The forecasting owner is the only new lane editing the explorer. The frontend owner adapts web endpoints. The records owner merges the tiny schema first; other lanes add only the fields they jointly agree on through the Board. Do not create a second graph database or general plugin framework.

With four local agent slots, keep the coordinator/data owner plus forecast, evaluation, and policy workers locally; the teammate's existing frontend session runs separately. Assign each worker a stable Board identity. A session is started only after it posts its own claim; this table does not claim that these implementation workers have already launched.

## First shared contract

Reuse `ClaimGraph` identities, existing evidence citations, and current event envelopes where possible. Keep the scientific claim graph separate from the agent/experiment search forest. They can cross-highlight through identifiers; their edges mean different things.

| Record | Minimum information and interpretation |
|---|---|
| Scenario manifest | `scenario_id`, dataset/release identity, cutoff, horizon, eligible candidate policy, graph snapshot ID, input/output hashes, origin. Explain whether dates represent publication or database availability. |
| Source | Stable evidence ID; URL/PMID when present; publication date when known; release/availability date; content hash. Missing publication dates stay missing. |
| Claim | Existing canonical `claim_id`, endpoints, relation, biological context, supporting evidence IDs, and observed-by date. A forecast has a separate status from an observed claim. |
| Forecast | Candidate ID, scenario/snapshot ID, model and policy identity, numeric score plus its meaning, supporting evidence IDs, creation order/time, and cost counters. A rank score or source-count heuristic is not automatically a probability. |
| Event | Existing envelope plus run ID, monotonic sequence number, graph revision, referenced branch/candidate/claim IDs, and provenance. Add events only for missing semantics. |
| Outcome | Candidate ID, matching later evidence, availability date, and observed-by-horizon status. Unobserved does not mean experimentally disproved. Outcomes are read by reveal/evaluation after forecasts are saved. |

Agree on one set of event names before code generation. Suggested additions: `graph_updated`, `forecast_recorded`, `outcome_revealed`, `evaluation_completed`; use existing branch/experiment events for branch motion. Preserve both fixed historical cutoff and advancing graph revision.

Two provenance dimensions are useful: a computed run can later be replayed. Retain its computed origin and record playback mode separately. Fixtures stay illustrative; cached external scores retain their named model/dataset. All providers can emit the same small record shapes without implementing an abstraction framework.

The current `/api/kg` projection omits claim IDs and evidence references despite backend support. Post a narrow request for the frontend/API owner to expose those fields. Branch digests summarize only a handful of results; compute coverage from actual canonical evidence, not the truncated display summary. Keep existing sibling information boundaries intact when reusing computation.

## What to take on next

The highest-value next task is **one historical scenario packet that the frontend, predictor, and evaluator can all consume**. Another broad literature review or a second UI session would not unblock these lanes.

1. Post the proposed records/events and exact ownership on the Board, reconcile the frontend's response, and merge the small record definitions plus a minimal fixture.
2. Normalize the January 2018 and March 2022 CIViC TSVs using stable evidence/gene/variant identifiers. Preserve disease, treatment, direction, and variant context. Check the real schema differences (`pubmed_id` versus typed citation IDs, missing drug IDs) before claiming an automatic cross-release join.
3. Define the candidate universe from information available in the earlier release, with eligibility and exclusion rules fixed before scoring. Use the later release only for outcomes. Freeze at least one general evaluation cohort; an attractive featured case can be selected afterward and labeled as selected.
4. Produce `historical.json`, `candidates.json`, and a separate `outcomes.json` plus manifest. A valid first task is **predicting later CIViC additions**. These releases alone do not establish the first worldwide discovery date.
5. Give the frontend an illustrative trace immediately. Replace it with a saved measured run after the structural scorer and evaluator connect. Forecast creation must precede future-evidence reveal in both the records and animation.

Downloaded CIViC metadata and retrieval URLs are in `tasks/research/graph-forecasting/civic-access.json`. The Dyport 2016 file supplies 336,710 labeled candidate rows and cached model scores, but not its original historical graph. Keep its baseline scoreboard separate from CIViC results; a new Dyport model comparison requires the same candidate rows and a compatible input graph. Do not stall the first visual slice on that reconstruction.

## Greedy delivery contract

For a fixed batch, each branch covers a known set of canonical evidence facets. With nonnegative weights, choose up to `k` branches by repeatedly taking the largest additional coverage. Fix tie-breaking and return selected IDs, marginal gains, covered facet IDs, and the objective/candidate snapshot identity.

For this cardinality-constrained coverage objective, the standard guarantee is at least `1 − (1 − 1/k)^k` of the best offered `k`-branch subset. For `k = 2`, that is 75%. It is independent of LLM score calibration because it concerns explicitly represented coverage. It does not certify undiscovered evidence, future graph trajectories, or biological truth. [Original theorem](https://thibaut.horel.org/submodularity/papers/nemhauser1978.pdf)

Use exact enumeration on the current four-branch pool to report the actual gap and validate greedy; all six pairs are cheap. Add current LLM judge, uniform selection, and top-singleton coverage as controls. Do not assign arbitrary unequal costs and keep citing the cardinality theorem; measured cost-aware selection needs a separately specified objective and comparator.

Success on the demo is visible and checkable: two individually attractive branches may overlap, so the second greedy choice covers a new neighborhood. Show that decision with real facet IDs. The existing finite probe audits the theorem and residual bound; it does not demonstrate forecasting lift.

## Research with a plausible publication target

The promising gap is that research actions can **unlock later actions, combine with other evidence, and benefit several hypotheses at once**. A frozen set-coverage score omits those effects. The research claim should concern that explicit structure and the cost of acquiring evidence, with an objective and verifier that do not depend on believing an LLM's confidence.

### First tractable direction: complementary evidence

Study an explicit objective consisting of ordinary evidence coverage plus rewards for completing predefined evidence patterns. For example, an independent measurement and a mechanistic link may jointly satisfy a pattern; either alone earns little. Pattern completion certifies that the evidence conditions were met, not scientific truth. Freeze patterns and weights without future labels.

Start with deterministic outcomes, a finite action universe, equal action costs, and an explicitly represented dependency graph. The theoretical question is whether restricted scientific patterns permit an efficiently maintained bound or better dependence on structure than generic complementary-set optimization.

Bounded supermodular degree already has an established algorithm and cardinality guarantee `1 − exp(−1/(d+1))`, with dependency-oracle assumptions and exponential dependence on `d`. Neither that result nor pair lookahead is novel, and that guarantee does not apply to arbitrary pair-greedy code. [Feldman–Izsak, Theorem 15](https://drops.dagstuhl.de/opus/volltexte/2014/4695/pdf/12.pdf)

Compare singleton greedy, pair lookahead, the applicable dependency-aware method, and exact optimum on small instances. Sweep dependency density and complementarity strength, then check whether the effect occurs in frozen biological traces. A reward invented to favor our algorithm is not empirical evidence of scientific value.

### Stronger long-term direction: shared evidence acquisition

Represent a reusable extraction or experiment as one action in a dependency DAG. It incurs cost once and can advance several eligible hypotheses. Ask which bounded patterns of shared prerequisites allow a useful approximation, parameterized algorithm, or valid instance bound against the best policy with the same information and budget.

Combinatorial Markov Search already treats costly multistage DAG search and proves a `1/2 − ε` prophet inequality under matroid constraints for mutually independent search processes. Shared observations across hypotheses violate that independence, so extending the model requires new analysis. [Bowers–Lindgren–Waggoner](https://arxiv.org/html/2502.08976v1)

Restrict the first attempt to bounded sharing, finite outcomes, and known action costs. Compare independent-tree search, **deduplicated greedy**, and the proposed policy on diamond-shaped dependency graphs with an exact adaptive oracle. Charge unique expensive actions and total compute separately. An improvement over duplicated work alone demonstrates caching, not a better exploration policy. A clairvoyant policy is an upper bound, not the same-information competitor.

Existing graph claim identities help identify shared artifacts, but equal names do not establish interchangeable execution states. Include input hashes, relevant context, and allowed visibility when declaring two actions reusable. Do not silently expose sibling-only findings through a cache.

### Useful alternative: certified search guided by learned advice

If the team can define a checkable goal and action costs, allow LLM heuristics to suggest search order while a conservative anchor maintains a bound. Multi-Heuristic A* already combines arbitrary inadmissible heuristics with a consistent anchor to retain completeness and bounded suboptimality. [Original paper](https://ai.dmi.unibas.ch/research/reading_group/aine-et-al-rss2014.pdf)

LazySP separates expensive edge evaluation from optimistic path selection. Reusing it can produce an intentional harness, but shortest-path optimality is not an expected query-complexity result; evaluation policies need their own analysis. [LazySP](https://cdn.aaai.org/ojs/13788/13788-40-17306-1-2-20201228.pdf), [query-policy analysis](https://www.ijcai.org/Proceedings/2019/0855.pdf)

Treat a shared-evidence query bound or a robust improvement from learned advice as a research question. Do not rename A* or UCB and claim novelty. If the goal is only an LLM declaring an idea promising, this direction has not obtained the required independent verifier.

Relevant nearby methods also include [adaptive seeding](https://arxiv.org/abs/1507.02351), [adaptive sequence optimization](https://arxiv.org/abs/1902.05981) with [author code](https://github.com/ehsankazemi/adaptiveSubseq), and [hypergraph sequence optimization](https://proceedings.mlr.press/v84/mitrovic18a.html). Start by mapping the proposed problem against these assumptions.

### Gates for the policy lab

- **Two hours:** one-page problem/assumptions/comparator, closest-prior-art reduction, executable tiny-instance oracle, and one counterexample showing what coverage greedy misses. Choose one main direction; do not pursue all three equally.
- **Six hours:** a proof lemma survives exhaustive counterexample search and the method beats the strongest applicable baseline at matched cost on frozen traces. Otherwise retain greedy and record the negative result. A surviving finite check supports a proof attempt; it does not replace a proof.
- **For a publication claim later:** a novel theorem or complexity separation with correct assumptions, reproducible experiments on meaningful scientific tasks, and comparison with the closest existing algorithm. No such new result has been established yet.

## Integration milestones and cut lines

| Relative milestone | Required artifact |
|---|---|
| First 60–90 minutes | Agreed small records contract, first CIViC packet, fixture in the active frontend |
| By hour 2 | Frozen evaluation cohort and scoring protocol; policy lab formalization; each lane independently runnable |
| By hour 6 | Complete fixture demo plus one real graph → forecast → reveal → score run; greedy and baseline comparison |
| By hour 10 | Measured flat/static/evolving ablation, replay of the strongest supported case, truthful scorecard; stop feature expansion |
| Final hours | Frontend polish, browser/projection rehearsal, replay reliability, and checking every displayed claim against its artifact |

The design award effort belongs in the existing frontend lane: clear question, stable graph layout, purposeful edge animation, branch-to-evidence highlighting, readable evidence drawer, and a satisfying future reveal. Use motion to explain a changed decision. Keep misses inspectable. Frame the mission as helping American scientists identify promising directions earlier; any numerical advantage must come from the evaluation.

Use parallel compute for extraction, fixed-budget ablations, exhaustive small-instance policy checks, and frontend iteration. Use the available GPU only for a measured bottleneck such as batched embeddings; AWS infrastructure expansion is not a prerequisite for this demo.

## Operating protocol for every session

Follow [AGENTS.md](../AGENTS.md) and [BOARD.md](../BOARD.md): read Board/status/branch/worktrees, post a file-scoped claim before edits, use an isolated task worktree when occupancy is uncertain, post shared-interface changes before implementing them, and communicate with `@agent-name` on the Board. Do not use private session messages for cross-machine decisions.

Before each commit: Board show/check, fetch and incorporate `origin/main`, run current repository gates and relevant task checks, then commit and push. Review the PR and merge with the validated head using the prescribed rebase merge; post `done` only after main contains the work. Rebase unpublished work only; do not rewrite published history. Use `update` for pending work. No new handoff file is needed.

At the audited revision, `docs/` and `tests/` are ignored and the gate list is a placeholder. Put shared plans in tracked `design/` or `plans/`; confirm tests are tracked when implementation adds them, coordinating ignore changes with the frontend owner. Read the current instructions again after pulling changes.
