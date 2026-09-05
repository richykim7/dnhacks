# Hackathon UX and demo review

Recommendation: make **the next scientific connection** the product's opening experience. Use one evolving graph, an inspectable forecast, and a later-evidence reveal. Rehearse a complete recorded run; treat live execution as an optional demonstration through the same interface. Spend polish on the graph's transformations and the evidence card.

Reviewed 2026-09-05. This is a presentation and implementation proposal, coordinated with `ian/graph-plan`; it does not change the production frontend, forecasting schema, e-values, or exploration policy. The [interactive prototype](../design/ux-demo/index.html) is isolated and explicitly illustrative. Run instructions are in its [README](../design/ux-demo/README.md).

## Ranked changes

Effort estimates are engineering hours after the scenario/run packet is available, not commitments from other owners. Ship in order; stop when the main story works.

| Rank | Concrete change | What judges understand | Fast implementation and fallback | Effort |
|---|---|---|---|---|
| 1 | Open directly into a prepared **Forecast** scene: question, 2018 cutoff, graph, one primary action. | The product anticipates scientific connections. No setup explanation is necessary. | Make Forecast the demo default/deep link. A bundled packet fills the same screen if the project/API is empty. | 0.5–1 |
| 2 | **Lock forecasts → reveal later evidence in place.** Keep the selected endpoints, rank and historical rationale visible. | A prediction existed before the outcome was inspected; the later result is traceable. | Two distinct states in one scene. Dashed violet forecast becomes solid lime only for an observed outcome; unresolved stays dashed and labeled. Cached excerpt replaces a network fetch. | 1–2 |
| 3 | Provide a complete **recorded run, reset and manual step controls**. Preserve selection when live execution fails. | The demo has a clear beginning, development and conclusion even under stage conditions. | One deterministic event reducer and a local scenario/run/outcomes bundle. Origin badge: Live run / Recorded run / Illustrative replay. Bounded live wait, explicit continuation from recording. | 1–2 |
| 4 | Show a **curated 12–20-node neighborhood**, typed nodes and three synchronized forecast cards. | The graph explains a specific recommendation rather than decorative activity. | Stable positions; click a card to dim unrelated nodes and highlight a 3–5-node support path. Show the actual full-graph count separately if available. Existing React Flow is sufficient. | 1–2 |
| 5 | Add three purposeful visual beats: **source enters → path connects → candidate rises**. Freeze geometry for the reveal. | The system is building and consuming the graph iteratively. | Replay actual event batches with 300–600 ms transitions and presenter-controlled pauses. Precomputed positions are sufficient; no new layout engine. | 1–2 |
| 6 | Add a **presentation shell**: large title, graphite/sage graph, warm paper evidence panel, compact temporal controls. | The interface looks intentional and the eye moves from question to graph to proof. | Scoped `forecasting.css` and a presentation flag; keep existing local fonts, Motion and controls. Stage viewport first, usable narrow layout second. | 1–2 |
| 7 | End with **one measured comparison**, denominator and one unresolved example. | There is technical substance beyond the chosen success story. | Read evaluator output; e.g. `hits / k at horizon` versus the same-candidate popularity baseline. Hide the comparison when unavailable; offer “Inspect evaluation” without an invented number. | 0.5–1 |
| 8 | Keep **How it reasoned** and research tools one click away. | The system can explain its computation, while the presentation remains comprehensible. | Put recorded actions, graph revisions and evidence IDs in an expandable drawer. Keep Investigations, Library and Structures reachable through secondary navigation. | 0.5–1 |

If there are only two hours, prioritize the prepared opening, frozen ranking, cached evidence reveal, reset, and a clean selected path. Do not spend that window adding a new renderer or a global navigation rewrite.

## Proposed 100-second demonstration

| Time | Presenter says | Screen and action |
|---|---|---|
| 0–12 s | “Can a system build a map of science that tells us where to look next?” | Start already loaded. Show a plain-language biological question, the earlier cutoff, and the historical graph. Header says Recorded run when using an actual recording. |
| 12–30 s | “We start with the earlier evidence. Reading it adds context and changes which connections are worth investigating.” | Click **Evolve graph**. Three meaningful updates add context, join a short path, and surface a candidate. Persistent cutoff remains 2018: processing time is not publication time. |
| 30–45 s | “These are the connections it prioritizes before we open the later evidence.” | Click **Lock forecasts**. Three readable cards appear. Select the top candidate; the supporting path lights up. Show rank, not an uncalibrated confidence percentage. |
| 45–60 s | “Here is why this one is plausible from what was available then.” | The right panel shows one concise rationale and cached historical evidence. Agent trace is available but closed. Pause before reveal. |
| 60–80 s | “Now open the later snapshot. Did that association get recorded?” | Click **Reveal later evidence**. Update the time marker, retain the ranking, change only observed edges, and open the selected outcome's source card beside its historical rationale. |
| 80–92 s | “We can inspect the record—and the candidates that were not recorded.” | Open the cached passage/record. Show actual disease, therapy-group semantics, direction and dates. Briefly select an unresolved candidate. External citation link is optional. |
| 92–100 s | “The ambition is an evolving map that recommends the next place to investigate.” | If verified, show one aggregate comparison from the evaluator and its sample size. End with **Explore another forecast** or the graph's next open question. |

Use a preselected case as an explicitly selected illustration; compute aggregate results on the declared complete candidate set. Do not turn later appearance in CIViC into a claim of first scientific discovery, treatment efficacy, or prospective clinical validation. The prepared dataset targets later-recorded variant–therapy-group associations; its context is part of the evidence.

## Specific screens and interactions

**Opening / frozen frontier.** Question and value proposition at the top, approximately 70% graph and a 320–380 px right panel. Put “Knowledge available at cutoff” beside the year. The next step is visually dominant; data import and project selection are secondary. Use actual scenario dates, not hardcoded years in integration.

**Graph growth.** Existing nodes stay fixed. Add a small number of meaningful context nodes; animate their edges once. The bottom strip explains the consequence in a short sentence, such as “Shared context opens a new candidate path.” Do not animate random births, simulated agent messages or invented counters. A compact “Showing X of Y nodes” communicates scale without making the canvas unreadable.

**Forecast selection.** Three cards lead with variant → therapy group and disease context. Click pins selection and reveals rationale; keyboard selection has the same result. Highlight a short supporting path and dim the surrounding neighborhood. Keep edges labeled by relationship where space allows; use a fixed legend to distinguish historical, forecast and later-recorded states. Rank and model score are separate from confidence.

**Evidence reveal.** The action is explicit and reversible for rehearsal. Keep the historical support and frozen rank anchored while adding a dated later record. Source card hierarchy: outcome status → association/context → highlighted cached passage → publication date and snapshot availability → source link. Do not imply a database-entry date is a publication date. Unrecorded candidates use “Not recorded by horizon,” not “False.” The prototype shows the visual transition and record-detail disclosure; the integrated view should add actual excerpts and keep historical rationale visible beside them.

**Presentation navigation.** During the pitch, replace the left project/run roster with a four-step rail on the same scene. In normal use, put Forecast first and retain the existing tools. **Evidence** belongs to the selected forecast's drawer in this flow. **Investigations** explains computation; it should not replace the scientific graph. **Structures** is an optional contextual detour only when the chosen evidence actually benefits from it.

**Visual direction.** Keep IBM Plex and the existing botanical palette. Increase title and evidence-card hierarchy, pair the dark canvas with warm paper, and reserve a bright accent for the selected path/outcome. Shape plus text carries status; color is supplemental. Keep the graph legible on the presentation screen. The isolated prototype intentionally explores a stronger visual direction than `frontend/DESIGN.md`'s quiet instrument brief. If adopted in production, update that brief in the same implementation commit.

## Failure plan

| Failure point | Prepared fallback | Presenter-visible behavior |
|---|---|---|
| No project, empty database or scenario request fails | Bundled complete historical scenario, saved run and separate outcomes | Open the prepared case. Never begin with a blank collection builder. |
| Model/provider error, timeout, GPU unavailable | Recorded real run using the same render contract | Offer **Continue recorded run** after a short bounded wait (suggest 3 seconds). Retain candidate and stage where mappings are valid; otherwise reset explicitly to the saved run. |
| No verified recorded output yet | Independently authored illustrative packet | Display **Illustrative replay** and omit measured claims. Plausible scientific context is acceptable; invented provenance is not. |
| SSE disconnect, duplicate or out-of-order events | Last accepted revision plus saved remaining events | Resume from deterministic sequence/revision; no double additions or rewound ranks. |
| Layout slow or unstable | Saved node positions and bounded neighborhood | Keep the same shape throughout. Offer Reset; skip force simulation. |
| Source website/PDF unavailable | Cached permitted excerpt and source metadata | Open the evidence card locally; source link is a secondary action. |
| Evaluation output unavailable or unfavorable | Omit headline metric; show inspectable case and unresolved candidates | Say what was demonstrated. Do not replace it with a synthetic performance number. |
| Public tunnel or venue network fails | Local built app and packet on the presentation machine; local screen recording | Switch to the already-open local tab, then video if needed. Test with networking disabled. |
| Remote fonts/assets or molecular viewer fail | Bundled fonts/assets; omit optional structure detour | Main graph and evidence remain fully usable. No WebGL dependency is needed for the core scene. |
| Presenter loses the scene | Deterministic Reset; Back/Next; bookmarked demo route | Restore cutoff, selected candidate, graph coordinates and locked outcome state together. |

Ship one complete local bundle before attempting live polish. A mock switch alone does not cover source loading, metric parsing, graph layout, fonts, navigation state or replay reset. Cache the entire judged path. Keep fallback metadata accessible in a quiet provenance disclosure rather than filling the main screen with engineering controls.

## Actual inspection and reusable implementation

Chromium rendered the current app at `http://127.0.0.1:8765/` and the public preview supplied by `ian/graph-plan`, `https://weighted-belong-donna-understand.trycloudflare.com/`, during the initial review. Both opened into the empty investigation experience at inspection time; the parallel Forecast view was still being implemented. This report does not claim to have validated that later implementation.

Also rendered the existing application's populated Investigations and Evidence routes using its browser-test API fixtures. Those are synthetic test states, not live scientific results. The populated investigation has a well-spaced researcher tree and usable detail interactions; two left columns consume roughly 460 px at a 1600 px viewport. The scientific graph lives on a different route, with large uniform node cards and no visible edge semantics in the captured three-node example. The live empty state requires collection setup before any graph is visible.

- `frontend/src/App.tsx`: current default is Investigations; four top-level destinations separate the core story.
- `frontend/src/components/Investigation.tsx`: reuse event cursor, camera selection and reduced-motion handling. Its playback is execution history, not a biological cutoff axis.
- `frontend/src/components/Evidence.tsx`: degree-sorted spiral and uniform nodes are acceptable exploration defaults; replace with saved positions for the prepared forecasting scene.
- `frontend/src/lib/api.ts`: current resource fetching has no complete recorded fallback. Put the adapter in the new forecasting module owned by `ian/graph-plan`.
- `frontend/src/components/common.tsx`, `ui/animated-tabs.tsx`, `styles.css`: reuse accessible controls, detail/disclosure patterns and tokens.
- React Flow, Dagre, Motion, Radix, Lucide and local fonts are already installed. No dependency is needed for this proposal. The prototype uses native SVG/CSS/JavaScript to stay isolated.
- `frontend/e2e/fixtures.ts` explicitly prohibits production imports. Demo packets should have their own origin/provenance contract.

Coordination proposals were posted before implementation, including the presentation entry point, persistent graph, temporal lock, candidate/evidence interaction and recorded adapter. Production `App.tsx`, `Forecasting.tsx`, `forecasting.css`, APIs and shared schemas remain with `ian/graph-plan` and the data/runner/evaluation owners. `tasks/todo.md` receives only an appended review from this task.

## Existing products to draw from

These observations come from official public product documentation, not authenticated workspace testing.

| Product | Existing pattern worth borrowing | Adaptation to this demo |
|---|---|---|
| [Elicit](https://elicit.com/) and its [report evaluation](https://elicit.com/blog/elicit-reports-eval) | Claim-to-source transparency and sentence-level citation inspection | One click from forecast rationale to historical source, then a contrasting later-evidence card. |
| [ResearchRabbit interaction guide](https://www.researchrabbit.ai/articles/guide-to-using-researchrabbit) and [map-size controls](https://www.researchrabbit.ai/releases/major-release-2026-07-09-2) | Exploration perspectives within a visual map; bounded article neighborhoods | Temporal perspectives on one canvas; a deliberately small selected scientific neighborhood. |
| [Connected Papers](https://www.connectedpapers.com/about) | A few dozen strong connections selected from a larger search space; path highlighting | Link the selected forecast card to a short readable support path, with actual total scale in a caption. |
| [Linkurious layouts](https://doc.linkurious.com/user-manual/latest/layout/), [selective expansion](https://doc.linkurious.com/user-manual/latest/expand/) and [publishing](https://doc.linkurious.com/user-manual/latest/page.html) | Stable exploration through pinning/expansion and shareable interactive snapshots | Saved demo geometry and a self-contained presentation route with deterministic controls. |

Use these patterns with the already installed stack. Forking a full product or adding another graph engine would consume integration time without improving the short presentation. The distinctive claim is not “papers on a graph”: it is a graph used to rank what to investigate, with a frozen historical input and later inspectable evidence.

## Scope cuts

Skip a new 3D graph, a new chat home screen, another domain, a molecular animation unconnected to the forecast, onboarding redesign, fabricated live telemetry, and an elaborate theorem panel. The e-value teammate and exploration-policy session retain those technical areas. If there is spare time, add a second **real** inspected candidate and rehearse the failure path before adding another visual feature.

## Validation

The isolated prototype was visually inspected in Chromium. Its four desktop scenes and mobile reveal returned no axe violations after fixing rank-label contrast. Checked locked outcomes, stable ranking on reveal, unresolved outcome copy, record details, reset, fallback state preservation, offline stepping, reduced motion, no browser errors, and a visible primary control at 1440 × 900. The [saved screenshot](../design/ux-demo/reveal.png) shows the 1600 × 1000 reveal.

Repository gates passed: production build, 2 frontend unit tests, 10 browser tests, 46 tracked Python tests and diff whitespace validation. Browser tests used an isolated empty-data backend on 8782 and Vite on 5188. The existing molecular invalid-file check twice exceeded its five-second assertion on a cold preview while loading 3Dmol; after loading the module, the unchanged full suite passed. This is a concrete reason to preload optional visual assets. The existing 3Dmol build warning remains. The documented dev-only Python setup lacked the server's optional `claude-agent-sdk` import; it was installed only in this worktree's environment. The wider unversioned local vocabulary test/data suite was not copied or validated.
