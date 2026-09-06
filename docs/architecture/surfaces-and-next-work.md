# Product surfaces and proposed next work

This audit began at `37dabe4` and was refreshed against main **`e04e9ff8bbe6a1abce23ba022518dbdde3ebb370`**. All code links below pin that final snapshot. Evidence source inspection landed at `3a7a227`, learned e-value diagnostics at `d0b864e`, and runtime visibility at `e04e9ff` through PR #28. The earlier runtime head `16e76c1` is superseded; PR #25 closed without a recorded merge commit. Its runtime features are now main behavior, not pending work.

The intended product destination is **Investigations**: a question leads to researchers consuming scientific context, proposing changes, testing findings, and requesting review. The durable, approval-controlled knowledge graph should supply subsequent investigations; active branch context is temporary, while provenance and execution history remain inspectable. That is the intended contract. The current implementation only partially closes this loop; [knowledge-contract.md](knowledge-contract.md) details its storage and approval boundaries.

## What each surface owns today

| Surface | Current responsibility and implementation | Boundary to preserve |
| --- | --- | --- |
| Investigations | Project-scoped investigation selection, researcher lineage, activity, experiments, and execution playback. `Investigation` consumes `useRuntime`, reduces history at the cursor, and opens `RuntimeDetail` for the selected researcher. [Investigation.tsx:154][investigation] | The search tree represents **researchers and execution ancestry**, not biological entities or claims. Its playback cursor is execution sequence, not publication year. |
| Researcher detail | Actual intent, lifecycle, model/tool activity, experiment results, verifier assessments, and registered artifacts. `RuntimeDetail` places structure artifacts inside their experiment. [RuntimeDetail.tsx:111][detail] | “Passed verifier checks” remains distinct from human review. Missing results or structures are not synthesized. |
| Library | Collection settings, document intake, assistant-assisted collection edits, and build/run jobs. `LaunchInvestigation` submits a question and step budget against a project. [Library.tsx:188][library], [LaunchInvestigation:865][launch-ui] | This is source preparation and launch, not the accepted-knowledge review surface. |
| Evidence | `Relationships` browses extracted claims; `ClaimSources` opens exact quotations, papers, certainty, and context. `Review` saves written decisions and separately applies them. [Evidence.tsx:104][claim-sources], [Review:548][review] | Saving an “Accept” decision is not yet applying a promotion. Extracted literature assertions, verifier results, and accepted findings have different meanings. |
| Forecast | A saved CIViC historical replay, model-memory comparison, and cohort scorecard fetched through global forecast endpoints. [Forecasting.tsx:81][forecast-ui], [forecasting.py:26][forecast-api] | These artifacts have scenario/candidate identities, not project/run identities. The standalone screen does not execute an Explorer investigation or modify its graph. |

`App.readRoute` already defaults to Investigations, although Forecast is first in navigation. `App` renders Forecast without project/run props. Structures is no longer a standalone navigation destination; registered structures belong to the selected experiment. [App.tsx:24][app], [App.tsx:208][app-render], [RuntimeDetail.tsx:356][artifacts]

## Main behavior and remaining integration gaps

- **Runtime is available to reuse.** The durable journal, ordered events, scoped blobs, live stream, reconnect handling, and shared live/playback reducer are implemented. `reduceRuntime` handles execution, experiments, artifacts, and branch decisions; it has no dedicated scientific graph-context, proposal-overlay, or accepted-revision state yet. Add the missing domain records through that system. [runtime.md:9][runtime-doc], [runtime.ts:28][reducer]
- **Exact source inspection is available to reuse.** `webui.evidence.claim_detail` resolves a stable claim ID within a named source and returns evidence, paper metadata, and contexts. The UI's `ClaimSources` is currently private to `Evidence.tsx`; reuse requires a small extraction or explicit export, not another source viewer. [evidence.py:5][claim-api], [Evidence.tsx:104][claim-sources]
- **The accepted-graph loop is incomplete.** `apply_promotions` writes into `MASTER_KG`, but `kg_sources` enumerates project/corpus graphs, and `jobs.start_run` launches against the project or adopted graph. A promoted record is not thereby exposed as a browsable accepted source or selected as the next run's input. Canonical scope/revision must be decided before representing that loop as complete. [data.py:602][kg-sources], [data.py:827][promotion], [jobs.py:130][launch-api]
- **Branches are not currently disposable graph copies.** `Explorer.__init__` gives branches separate scratch directories but shares the graph, papers, exploration log, and verification queue; cross-run memory defaults on. Pruning stops continuation and retains submissions. Temporary proposal overlays must be distinguished from this durable audit/memory behavior. [explorer.py:320][explorer], [explorer.py:1402][pruning]
- **Learned diagnostics are a separate completed asset.** The e-value work includes real-expression training/evaluation and a standalone wealth report. Its documentation explicitly leaves native verification, investigation-wide allocation, and UI integration for later work; it does not supply an automatic approval rule. [learned-evalue-process.md:256][evalue]

These findings replace the earlier “runtime branch pending” assessment. No unmerged implementation is required to obtain the runtime or Evidence capabilities described above. Deferred ideas in [plans/backlog.md][backlog] remain proposals, not permission to implement them.

## Forecast assets worth carrying into Investigations

1. **The visual vocabulary.** `MemoryMap` uses a bounded, stable source neighborhood and distinguishes model hypotheses with dashed edges. Revision lists, citation counts, selected-rationale details, and measured usage make graph iteration understandable. Extract presentation primitives from `ForecastReasoning`; its current self-fetch of `/api/forecasting/reasoning` must not survive inside a project-scoped researcher panel. [ForecastReasoning.tsx:103][memory-map], [ForecastReasoning.tsx:228][reasoning-ui]
2. **The proposal contract.** `prepare_reasoning` accepts historical inputs only; validated model outputs preserve `unverified_model_hypothesis` status and explicit `graph_revision` changes. These records demonstrate a useful overlay shape. They need an adapter to source-qualified claim/evidence IDs and runtime run/attempt/sequence identity before being used in live Investigations. Forecast candidate IDs must not be silently treated as literature claim IDs or engine test IDs. [reasoning.py:46][reasoning-input], [reasoning.py:218][reasoning-revisions], [records.py:24][forecast-records]
3. **The measurement discipline.** The frozen forecasts, separate outcomes, matched-condition metadata, actual usage, and coverage-aware scorecards are reusable as recorded experiment artifacts. The comparison holds retrieval and branch scheduling fixed, so its results concern representation/self-generated memory, not scheduler optimality. Preserve model origin and modern-training limitations. [reasoning.py:245][reasoning-protocol], [ForecastStudy.tsx:128][study]

The conceptual mismatch is the global, parallel product flow: a selected investigator cannot currently explain a Forecast graph because that graph comes from a fixed demo packet. The backend also returns later outcomes for presentation; the UI's reveal control is a presentation gate, not a time-filtered research API. Keep the benchmark replay identifiable as a benchmark while making the working graph visible through the investigation's own records. [forecasting.py:26][forecast-api]

## Proposed vertical slices

These are bounded proposals with role owners and dependencies, not autonomous assignments. The first two establish the graph experience; the third closes the product's knowledge loop. The fourth brings comparative evidence into the same workspace.

### 1. Show the scientific context consumed by a researcher

**Proposed owner:** Investigations/runtime presentation, with the runtime producer and Evidence source adapter owners.

Add a compact graph-context panel inside the selected researcher. Record the exact consumed claim/evidence packet with project/source identity, base graph snapshot or revision, run/attempt, and availability sequence. Reuse the Evidence quotation/paper view and the bounded graph presentation. A historical cursor must resolve the recorded packet, not fetch today's graph and imply it was previously consumed.

**Acceptance:** two researchers can show different consumed contexts; selecting an edge opens its exact recorded quote and source; scrubbing before the context event hides it; switching projects never displays the global CIViC packet. Missing historical source content is explicitly unavailable.

**Dependency:** a small graph-context record and producer seam in the existing runtime, plus extraction of the shared source presentation. No second journal, stream, or investigator navigator.

### 2. Animate one citation-backed proposal overlay

**Proposed owner:** Investigations graph presentation and Explorer producer, with the knowledge-contract owner.

Represent a model suggestion as an unverified dashed relationship attached to its consumed context. Ordered revision events show additions, replacements, and removals, with concise rationale and source IDs. Reuse Forecast's revision/validation concepts without conflating a valid output shape with scientific truth.

**Acceptance:** one real or explicitly labeled fixture proposal changes only the branch overlay; invalid citations remain diagnostic attempts; removing a proposal removes its active edge; pruning ends the active overlay while preserving replay and any already submitted review records. The accepted graph remains unchanged.

**Dependency:** slice 1's identities and cursor scope, plus an explicit overlay lifetime. The current shared working database is not a branch snapshot mechanism.

### 3. Connect a tested finding to approval and the next investigation

**Proposed owner:** knowledge persistence and Evidence review, with the investigation launcher owner.

Link an eligible finding's `test_id` to the existing review flow: written decision, saved pending state, explicit apply, and resulting accepted provenance/revision. Expose which accepted source the next investigation actually reads. Resolve global-master versus project-scoped accepted knowledge in the knowledge contract first.

**Acceptance:** saving a decision alone does not change accepted knowledge; rejection retains written feedback; applying one acceptance makes its source-linked record inspectable; a subsequent investigation demonstrably consumes that accepted record under the chosen scope. Literature qualifiers survive the transition.

**Dependency:** the canonical source/read contract and existing promotion rules. For the minimal demonstration, finish the active run before applying: `apply_promotions` already returns a conflict when its working graph is locked. This is not a generic arbitrary graph-edit approval API. [data.py:827][promotion]

### 4. Attach comparative evaluation to an investigation artifact

**Proposed owner:** evaluation artifact adapter and runtime experiment presentation, with the forecasting evaluator owner.

Make the memory-comparison and study views accept a recorded artifact associated with a run/experiment. Preserve candidate cohort, source packet hash, condition budgets, actual usage, model origin, failures, and outcome availability. Treat publication cutoff and runtime replay sequence as separate axes. The existing forecast screen can remain a benchmark entry point until this scoped view exists.

**Acceptance:** selecting a researcher causes no global forecast fetch; its downloaded comparison identifies the parent run and source packet; later labels/metrics appear only after explicit reveal and artifact availability; incomplete-query counts and eligible metric denominators remain visible. A one-query AP comparison is not presented as established lift, and unobserved candidates are not labeled disproved.

**Dependency:** a runtime artifact adapter for the saved JSON reports. Reuse numerical evaluation and UI presentation; do not rerun models merely to navigate or replay the artifact.

## Audit boundary

This document records source inspection and proposes integration work. It adds no application behavior, changes no approval policy, and claims no newly run tests or experiments. Deployment ownership and the durable knowledge model are documented separately in [hosting.md](hosting.md) and [knowledge-contract.md](knowledge-contract.md).

[app]: https://github.com/richykim7/dnhacks/blob/e04e9ff8bbe6a1abce23ba022518dbdde3ebb370/frontend/src/App.tsx#L24
[app-render]: https://github.com/richykim7/dnhacks/blob/e04e9ff8bbe6a1abce23ba022518dbdde3ebb370/frontend/src/App.tsx#L208
[investigation]: https://github.com/richykim7/dnhacks/blob/e04e9ff8bbe6a1abce23ba022518dbdde3ebb370/frontend/src/components/Investigation.tsx#L154
[detail]: https://github.com/richykim7/dnhacks/blob/e04e9ff8bbe6a1abce23ba022518dbdde3ebb370/frontend/src/components/RuntimeDetail.tsx#L111
[artifacts]: https://github.com/richykim7/dnhacks/blob/e04e9ff8bbe6a1abce23ba022518dbdde3ebb370/frontend/src/components/RuntimeDetail.tsx#L356
[library]: https://github.com/richykim7/dnhacks/blob/e04e9ff8bbe6a1abce23ba022518dbdde3ebb370/frontend/src/components/Library.tsx#L188
[launch-ui]: https://github.com/richykim7/dnhacks/blob/e04e9ff8bbe6a1abce23ba022518dbdde3ebb370/frontend/src/components/Library.tsx#L865
[claim-sources]: https://github.com/richykim7/dnhacks/blob/e04e9ff8bbe6a1abce23ba022518dbdde3ebb370/frontend/src/components/Evidence.tsx#L104
[review]: https://github.com/richykim7/dnhacks/blob/e04e9ff8bbe6a1abce23ba022518dbdde3ebb370/frontend/src/components/Evidence.tsx#L548
[forecast-ui]: https://github.com/richykim7/dnhacks/blob/e04e9ff8bbe6a1abce23ba022518dbdde3ebb370/frontend/src/components/Forecasting.tsx#L81
[forecast-api]: https://github.com/richykim7/dnhacks/blob/e04e9ff8bbe6a1abce23ba022518dbdde3ebb370/src/dnhacksbio/webui/forecasting.py#L26
[runtime-doc]: https://github.com/richykim7/dnhacks/blob/e04e9ff8bbe6a1abce23ba022518dbdde3ebb370/docs/runtime.md#L9
[reducer]: https://github.com/richykim7/dnhacks/blob/e04e9ff8bbe6a1abce23ba022518dbdde3ebb370/frontend/src/lib/runtime.ts#L28
[claim-api]: https://github.com/richykim7/dnhacks/blob/e04e9ff8bbe6a1abce23ba022518dbdde3ebb370/src/dnhacksbio/webui/evidence.py#L5
[kg-sources]: https://github.com/richykim7/dnhacks/blob/e04e9ff8bbe6a1abce23ba022518dbdde3ebb370/src/dnhacksbio/webui/data.py#L602
[promotion]: https://github.com/richykim7/dnhacks/blob/e04e9ff8bbe6a1abce23ba022518dbdde3ebb370/src/dnhacksbio/webui/data.py#L827
[launch-api]: https://github.com/richykim7/dnhacks/blob/e04e9ff8bbe6a1abce23ba022518dbdde3ebb370/src/dnhacksbio/webui/jobs.py#L130
[explorer]: https://github.com/richykim7/dnhacks/blob/e04e9ff8bbe6a1abce23ba022518dbdde3ebb370/src/dnhacksbio/explorer/explorer.py#L320
[pruning]: https://github.com/richykim7/dnhacks/blob/e04e9ff8bbe6a1abce23ba022518dbdde3ebb370/src/dnhacksbio/explorer/explorer.py#L1402
[evalue]: https://github.com/richykim7/dnhacks/blob/e04e9ff8bbe6a1abce23ba022518dbdde3ebb370/docs/learned-evalue-process.md#L256
[backlog]: https://github.com/richykim7/dnhacks/blob/e04e9ff8bbe6a1abce23ba022518dbdde3ebb370/plans/backlog.md
[memory-map]: https://github.com/richykim7/dnhacks/blob/e04e9ff8bbe6a1abce23ba022518dbdde3ebb370/frontend/src/components/ForecastReasoning.tsx#L103
[reasoning-ui]: https://github.com/richykim7/dnhacks/blob/e04e9ff8bbe6a1abce23ba022518dbdde3ebb370/frontend/src/components/ForecastReasoning.tsx#L228
[reasoning-input]: https://github.com/richykim7/dnhacks/blob/e04e9ff8bbe6a1abce23ba022518dbdde3ebb370/src/dnhacksbio/forecasting/reasoning.py#L46
[reasoning-revisions]: https://github.com/richykim7/dnhacks/blob/e04e9ff8bbe6a1abce23ba022518dbdde3ebb370/src/dnhacksbio/forecasting/reasoning.py#L218
[reasoning-protocol]: https://github.com/richykim7/dnhacks/blob/e04e9ff8bbe6a1abce23ba022518dbdde3ebb370/src/dnhacksbio/forecasting/reasoning.py#L245
[forecast-records]: https://github.com/richykim7/dnhacks/blob/e04e9ff8bbe6a1abce23ba022518dbdde3ebb370/src/dnhacksbio/forecasting/records.py#L24
[study]: https://github.com/richykim7/dnhacks/blob/e04e9ff8bbe6a1abce23ba022518dbdde3ebb370/frontend/src/components/ForecastStudy.tsx#L128
