# Forecast the next edge

**Research and demo plan · September 5, 2026 · 16-hour hackathon MVP**

Latest decision: use greedy provisionally. The [parallel session plan](https://github.com/richykim7/dnhacks/blob/main/design/parallel-session-plan.md) records current teammate ownership, the next historical-data slice, and the separate research direction; it supersedes earlier uncoordinated delivery assignments.

Audience: AI engineers and investors. Product beneficiary: scientists. Architecture: domain agnostic. Flagship: biology. All examples and outputs can be stubbed; measured results retain their identity. Production hardening is outside scope.

## The recommendation

Build an evolving scientific graph that turns a research area into ranked, source-linked predictions of relationships that will appear in later evidence. Make the graph itself the research workspace: the model reads a neighborhood, proposes competing explanations, requests additional evidence, revises the graph, and changes its recommendations.

The stage question is: **“Given only what was available then, which connections would you investigate next?”** The reveal opens the later record and scores predictions against established methods. A second view explains why the controller chose these branches and shows a precisely scoped selection certificate.

The American excellence story is increasing the capacity of scientific teams to recognize promising directions early. A measured forecasting advantage would support that ambition; a national productivity multiplier is not an existing result.

Three separate deliverables make this concrete:

1. A polished graph experience with live, recorded, and fixture providers.
2. A historical biological ranking comparison and controlled graph/scheduler ablations.
3. A provisional greedy branch-selection objective with a standard approximation theorem and exact small-instance evaluation.

No new end-to-end predictive advantage has been measured in this research pass.

## The demo, as observable actions

Use a prepared biological investigation and a historical cutoff. Leave the exact subfield open until we inspect the available benchmark cases; cancer biology is a practical visual pilot because readable evidence is already downloaded.

| Moment | What the judge sees | What it demonstrates |
|---|---|---|
| Choose a frontier | A plain-language research question, cutoff year, and “Explore” | One understandable task |
| Build understanding | Papers attach to typed nodes and claims; selected neighborhoods stay spatially stable | The graph changes as evidence is read |
| Explore alternatives | Several proposed branches highlight different parts of the graph | The controller has explicit alternatives |
| Allocate attention | Two branches are selected; overlap and uncovered evidence become visible | A checkable allocation decision |
| Revise | A new source strengthens, qualifies, or redirects a claim; forecast ranks change | The model consumes its updated graph |
| Commit predictions | Three recommended relationships become dashed edges with reasons | A forecast exists before outcomes are opened |
| Open the future | Later evidence attaches to matched predictions; unrecovered predictions remain visible | A falsifiable historical reveal |
| Compare | The same evaluation rows are scored for our system and named baselines | A measurable contribution, if achieved |

This is a proposed presentation sequence, not a claim that an authentic run with this outcome already exists. A fixture can exercise every transition immediately. The measured demonstration later substitutes actual events without changing the UI.

## Assets we can actually use

### Dyport: primary external forecasting comparison

[Dyport's repository](https://github.com/IlyaTyagin/Dyport) supplies yearly biological candidate-pair tables and cached scores for AGATHA, Node2Vec, ComplEx, DistMult, HolE, and TransE. We downloaded its complete 2016 score table: **80,495,323 bytes; 336,710 rows; 30,619 positive and 306,091 negative labels**. Files are cached locally, with hashes and access records.

The benchmark dates curated biological associations using their occurrence in MEDLINE abstracts; its published evaluation uses pre-2016 information and later years. Its negatives are sampled alternatives, rather than experimentally disproved relationships. Future importance and citation-derived fields are outcomes, not forecasting inputs. [Dyport methods](https://arxiv.org/html/2312.03303v1)

The score file does **not** contain the historical training graph. A new Dyport predictor therefore requires a small dated evidence graph for a fixed subset of benchmark subjects, or the compatible historical source package. The immediate implementation task uses the already available CIViC historical graph route below. A score table alone is enough for baseline curves, but not for reproducing graph construction.

Downloaded data: `data/cache/graph-forecasting/dyport-2016.csv`. Access and metrics: `tasks/research/graph-forecasting/dyport-access.json`.

### CIViC: compact graph and readable biological evidence

[CIViC provides historical releases](https://docs.civicdb.org/en/latest/using/data_releases.html). We downloaded January 2018 and March 2022 TSVs: **2,372 and 3,888 evidence rows**, respectively, totaling about 7 MB. They include genes, variants, diseases, therapies, evidence statements, stable IDs, and citations. They are immediately suitable for an evidence-rich cancer graph.

Two tasks must have different names: release-to-release prediction forecasts later additions to CIViC; publication-year prediction forecasts later cited associations within the selected corpus. Neither establishes the first discovery worldwide. Historical curator prose must come from the corresponding release; current summaries cannot simply be backdated. Schema and drug terminology change across releases, so prefer stable IDs and retain variant/disease context.

Use CIViC to deliver the graph narrative while the Dyport predictor is prepared. Their results must have separate dataset labels and scorecards. Downloaded snapshots and hashes are recorded in `tasks/research/graph-forecasting/civic-access.json`.

### PubTator3: annotated papers to grow the graph

The [official NCBI API](https://www.ncbi.nlm.nih.gov/research/pubtator3/api) exports normalized biomedical entities and typed relations. A live export for PMID 29355051 returned HTTP 200, 14,167 bytes, publication-year metadata, and three document relations. Its actual JSON wrapper is `PubTator3`, containing documents. This gives us a tested path to paper-level evidence; select papers by date before building historical inputs. Respect the documented three-requests-per-second limit while preparing the cache.

### Useful references, with clear roles

| Existing work | What to reuse or compare | Why it is not the whole solution |
|---|---|---|
| [AGATHA](https://github.com/JSybrandt/agatha) | A directly relevant graph-based biomedical forecasting baseline; cached predictions are already in Dyport | Its pretrained reproduction package is 38.5 GB and its dependencies are old; rebuilding it is outside the first critical path |
| [BioVerge](https://github.com/Fuyi-Yang/BioVerge/) | Typed-triplet retrieval, paper tools, iterative agent prompts, and flat/text/graph baseline patterns | Its principal test supplies the two endpoints and asks for a relation; that is narrower than recommending previously unknown pairs |
| [BioRED](https://ftp.ncbi.nlm.nih.gov/pub/lu/BioRED/BIORED.zip) | Small normalized entity/relation examples for graph extraction fixtures | Its article-relative novelty annotation is not a temporal discovery label |
| [Science4Cast](https://github.com/iarai/science4cast) | Direct precedent for forecasting edges in an evolving scientific-concept graph | Its domain is AI, not our biological flagship |
| [Mat2vec](https://github.com/materialsintelligence/mat2vec) | Precedent for historical scientific recommendations from literature | It is materials science and not a turnkey dated biology dataset |

BioVerge's 177-triple diabetes evaluation is also useful for a small relation-inference experiment, but its natural-language descriptions are scored with an LLM and its supplied endpoints limit the recommendation claim. [BioVerge paper](https://arxiv.org/html/2511.08866v1)

Do not port a second research engine wholesale. Reuse individual asset formats, benchmark rows, and selected algorithms after checking component reuse terms. Dyport's repository did not expose an explicit license file during inspection; keep raw downloaded data local until redistribution terms are established.

## A backtest that answers the user's objection

**Primary claim to test:** graph iteration improves ranking of later-observed biological relationships under a fixed evidence and inference budget.

1. Fix a subject set, candidate universe, historical cutoff, forecast horizon, and scoring rule before running our predictor. Both endpoints must be eligible at the cutoff; exclude already-observed target relationships. For a released closed-candidate benchmark, describe that conditional task explicitly.
2. Build a physically separate input bundle containing only allowed historical evidence. Source counts, embeddings, summaries, and graph neighborhoods must be computed from that bundle.
3. Run several graph revisions without opening later labels. The controller can read more **historically available** papers during this phase.
4. Save candidate scores and the final graph version. Only then load the outcome table and compute metrics.
5. Report aggregate results and a selected illustrative case. Keep misses and unobserved-by-horizon outcomes visible.

Use precision@10 and average precision for the main ranking scorecard; retain AUROC for compatibility. Precision is conditional on the candidate sampling protocol, not an estimate of success among all conceivable scientific hypotheses. For within-query ranking, preserve candidate groups and define tie handling. Cluster uncertainty by subject/query rather than treating overlapping pairs as independent.

The downloaded table contains 1,451 duplicate subject/object rows. Preserve all released rows when reproducing its unfiltered baseline scores; choose and freeze a common grouping/deduplication policy before our own ranking analysis. Do not compare scores computed on different rows.

### Required comparisons

| Comparison | Held constant | Question answered |
|---|---|---|
| Random, popularity, common-neighbor/Adamic–Adar | Same historical graph and candidate rows | Is the result better than obvious graph heuristics? |
| Cached AGATHA and graph embeddings | Exact matching Dyport rows | How does it compare with established biomedical systems? Training resources differ and must be disclosed |
| Flat evidence log vs static graph plus append log vs evolving graph | Same model, retrieval responses, token budget, and candidates | Does graph representation and updating help? |
| Current judge vs uniform vs top singleton coverage vs coverage selection | Identical candidate branches and evidence facets | Does selection avoid redundant exploration? |
| Full adaptive system | Same permitted corpus and total budget | Does the combined product improve the final forecast? |

The static-graph control still receives newly retrieved evidence in a flat log. Otherwise the comparison confounds graph iteration with access to additional facts. Internal ablations share budgets; historical cached models are external references, not equal-compute replicas.

A modern LLM may remember later biology even when retrieval is frozen. Include a no-retrieval diagnostic and a structural scorer using only the frozen graph. Claim “retrospective performance with historically restricted evidence,” unless stronger evidence establishes absence of model-memory leakage. The graph-only score is a cleaner test of the graph signal; it does not prove the LLM has independently foreseen a discovery.

Do not reward a scheduler with unrevealed future labels during the forecasting loop. A separate simulated active-discovery experiment may reveal a label per paid action, but it answers a different question.

## What we can prove about the harness

The proof should match a real control decision: **which offered branches deserve the next limited batch of compute?** No scheduler can ensure useful biological discovery if every candidate and test is arbitrarily wrong. An unconditional “best research harness” claim has no well-defined comparator.

For one graph revision, define a finite candidate pool B, evidence facets U, nonnegative weights w, and known provenance-backed coverage C(b). Facets can be canonical source clusters or supported graph neighborhoods; freeze their definition before observing later outcomes. Define:

`F(S) = sum of w(u) over the union of C(b), for branches b in S; select at most k branches.`

This measures represented evidence coverage, not how much unknown evidence an unexecuted branch will discover. If facets refer to requested retrieval targets, call it planned coverage; realized coverage is a separate measurement.

### Exact evaluation oracle at the current scale

The current code allows three proposed branches plus an adversarial branch, keeping two survivors. There are only **six two-branch subsets**. Keep greedy as the provisional production choice. Enumerate the alternatives in evaluation to measure its actual gap. The complete scored list supplies an exact comparison certificate. If retaining the adversary becomes mandatory, compare only subsets satisfying that same constraint; the current implementation generates an adversary but does not guarantee it survives the judge.

The oracle finds the exact optimum for this graph snapshot, candidate pool, and objective; the greedy choice is compared with that value. It does not depend on an accurate LLM score. This is an application of straightforward finite optimization, not a new complexity-theory result.

### Scalable theorem and instance certificate

As the provisional policy at both current and larger pool sizes, marginal-gain greedy achieves at least `1 − (1 − 1/k)^k`, hence at least `1 − 1/e`, of the best k-subset for normalized monotone submodular coverage. It requires O(k × |B|) marginal evaluations; the cost of a marginal depends on the facet representation. This is the established [Nemhauser–Wolsey–Fisher theorem](https://thibaut.horel.org/submodularity/papers/nemhauser1978.pdf), adapted to our explicit graph objective.

Proof outline: coverage has diminishing returns. At each step, one of the optimal set's at most k branches closes at least one-kth of the remaining gap. Iterating the gap recurrence gives the bound. Freeze the graph, weights, and candidate incidence during each selection batch. Recomputing between batches does not turn the statement into a guarantee about the globally best evolving investigation.

An additional directly derived certificate upper-bounds the optimum by `U = min(F(B), F(S) + sum of the k largest remaining marginal gains at S)`. Thus `F(S)/U` is a certified achieved fraction when U > 0. The optimum need not include S, so the upper bound uses k, not k minus the size of S. An empty zero-value pool is handled separately.

The classic [maximum-coverage hardness result](https://disco.ethz.ch/alumni/pascalv/refs/ds_1998_feige.pdf) explains the worst-case approximation barrier when the budget is part of the general input. It does not make our four-branch instance difficult. With fixed k, exhaustive enumeration is polynomial in the candidate count.

### What the research probe established

We exhaustively checked all 65,536 binary coverage families with four candidates and four facets, selecting two branches. Across 65,535 nonzero cases, greedy's worst achieved ratio was **0.75**, matching the k=2 bound; no proposed upper-bound certificate fell below the exact optimum. This is a finite algorithm audit, not scientific forecast accuracy or a substitute for the proof.

Reproduce with `python research_spikes/graph_forecasting/probe.py`. The script also recomputes the downloaded baseline metrics. It uses installed analysis packages and makes no model calls.

### Other guarantees worth keeping in reserve

Hedge or EXP3 can compete with a fixed strategy portfolio over appropriately defined independent episodes. Standard external regret does not compare counterfactual graph trajectories when each strategy changes later inputs; [policy-regret impossibility results](https://oferdekel.github.io/pdf/2012AroraDeTe.pdf) explain this distinction. Do not add an online-learning layer until the episode/reward protocol exists.

A simple round-robin schedule across m fixed, independent resumable streams finds an accepted result within m times the best stream's own work, if quanta have equal charged cost and scheduling does not change outputs. That supports a no-starvation demonstration with deliberately misleading heuristic scores. Shared mutable graph contexts and unequal uncharged tool calls invalidate the literal comparison. This is an optional standard scheduling corollary, not the MVP's principal research claim.

The user's MCTS analogy needs qualification: logarithmic regret is not a blanket guarantee for arbitrary scientific tree search. [Orseau and Munos, 2024](https://arxiv.org/abs/2405.04407) establish severe worst-case behavior for UCT variants and correct an issue in earlier lower-bound proofs. Copying a UCB formula would not establish a useful end-to-end theorem here.

## Measured baseline foothold

These are our recomputations on the **entire unfiltered authors' 2016 table**, retaining duplicate rows. They are not our model scores or a reproduction of the paper's stratified tables.

| Cached model column | AUROC | Average precision |
|---|---:|---:|
| AGATHA 2015 | 0.7354 | 0.2582 |
| DistMult without semantic types | 0.7131 | 0.2533 |
| HolE with semantic types | 0.7469 | 0.2443 |
| Node2Vec | 0.7035 | 0.2319 |

The different ordering of AUROC and average precision is a reason to decide the target metric in advance. All ten cached score variants were recomputed; the full results and SHA-256 are in the access record.

## Architecture: the minimum that supports this demo

Reuse the Python service, DuckDB graph, existing events, and injected completion, judge, and execution hooks for fixtures. The teammate now owns a user-authorized React/TypeScript/Vite frontend rewrite; supply its scenario and evidence contracts through the Board. Keep backend changes focused on the demo.

The new product seam is a small scenario record: question, cutoff, historical graph, permitted evidence, candidate set, prediction list, outcome table, and an event trace. A live source, saved run, and deterministic fixture emit the same events. One visible mode indicator distinguishes their origin.

Agree on the small missing graph/forecast/reveal event set with the frontend owner before implementation; the parallel session plan supplies a concrete proposal. Reuse existing branch and experiment events instead of duplicating the trace system.

Track two different notions of progress: the **historical cutoff** remains fixed while **graph revisions** advance as the agent reads. The reveal advances the historical evidence window. Predicted edges stay a distinct typed state when the model consumes the graph; a proposal does not silently become established evidence because it was written back.

Current seams:

- `litmap/graph.py`: canonical claims and evidence; preserve source-backed identity.
- `litmap/store.py`: explorer-facing graph plus tested layer. Its aggregate first-year view is not a historical snapshot of every attached source.
- `explorer/exploration.py`: ideas, evidence, provenance, feedback, and frontier state.
- `explorer/explorer.py::_judge_promise`: branch-selection insertion point. Use full database provenance for facets, not six-item digest truncation.
- Frontend/API presentation: owned by the active React/Vite session; preserve useful graph/replay semantics from the existing implementation.

## Design award direction

One primary canvas, one clear question, and a restrained evidence drawer. Start with an intentional scientific instrument: warm ivory surfaces, deep ink type, one electric accent, and generous space around the active graph. Use the bundled font; tune display scale and spacing before adding another type family.

Render a selected neighborhood of roughly 40–120 nodes. Hold positions stable across revisions; added edges trace into place, source dots attach to their claims, and branch hover highlights exactly what it covers. The background graph becomes quiet while a selected mechanism is explained. Forecast edges use a different stroke pattern; the later-evidence reveal changes their status without rearranging the entire scene.

Use motion to explain events: a source changes a claim, an overlapping branch loses marginal value, a new neighborhood earns attention, or a forecast matches a later paper. Avoid continuous force-layout movement while someone reads. Large-type takeaways should explain what changed and why the next action follows.

The signature interaction is **opening the future**. After committing forecasts, the judge advances the year and watches real later evidence attach to the already-visible predictions. A missed forecast remains on screen as “not observed by this horizon.” A secondary “Why these branches?” action opens the six feasible allocations and their coverage values.

The illustrative animation in this report previews the visual grammar only; it contains no measured forecast result.

## Delivery milestones

The current ownership and launch-ready file boundaries are in the [parallel session plan](https://github.com/richykim7/dnhacks/blob/main/design/parallel-session-plan.md). These relative milestones fit the original 16-hour budget; they do not restart the clock.

Run the existing frontend session plus historical-data, forecast/greedy, evaluation/replay, and policy-research lanes. The session plan assigns concrete files and prevents overlap; the first common artifact is the small scenario/event contract.

| Milestone | Required result |
|---|---|
| First 60–90 minutes | Agreed records, first CIViC historical packet, frontend fixture |
| By hour 2 | Frozen evaluation cohort and scoring protocol; policy-lab objective and exact comparator |
| By hour 6 | Complete fixture demo and one measured graph-to-forecast-to-reveal slice |
| By hour 10 | Matched representation/selection comparisons; supported case selected; stop feature expansion |
| Final hours | Saved replay, frontend polish, projection rehearsal, artifact-backed scorecard |

CIViC is the immediate historical graph route. Dyport model comparisons remain a separate dataset task that requires its compatible historical inputs. A delayed Dyport reconstruction must not block the main visual slice.

Use the AWS GPU only if embeddings or a graph scorer become the measured bottleneck. Baseline replay, greedy selection, graph updates, and the current evidence files do not require a GPU. Plenty of parallel compute helps corpus extraction and independent ablations immediately.

Mockability is part of the architecture from the start: replay any complete scenario, replace any model/tool response, and drive every UI state deterministically. A mocked score may support the design walkthrough but does not enter the measured scoreboard.

## Research status and stopping decision

Completed: primary-source comparison; exact asset downloads; PubTator API probe; baseline recomputation; finite coverage/certificate audit; source inspection and independent proof review. Not completed: a new biological forecast run, an integrated scheduler, a selected final biological case, or an end-to-end model advantage.

Artifact verification: HTML structure, source links, JSON records, and embedded JavaScript syntax were checked. Browser screenshot attempts timed out, so the rendered layout and browser interactions remain visually unverified.

Research stopped once the asset route, baseline route, proof assumptions, and demo architecture were supported. Remaining uncertainty is implementation and measurement: whether graph iteration improves ranking, whether evidence coverage predicts useful exploration, and whether a sufficiently strong historical case can be prepared within the first delivery gates. The next product step is a small actual forecasting slice. In parallel, a bounded research lane will investigate complementary experiments, shared evidence acquisition, and certified search with learned advice; the session plan defines proof/comparator gates and closest prior art. No new publication-level result is claimed.
