# Improvements grounded in the research application

This review supersedes the standalone backtesting prototype as a product direction. The user rejected that prototype's design and its substitution of backtesting for actual research use. This pass reads the current application and engine, preserves the existing frontend, and implements a useful interaction directly in Evidence.

## What the code actually does

1. `webui/jobs.py:launch_run` takes a research question and the selected project's existing graph. It launches Explorer with the goal and database.
2. `explorer/explorer.py` shares the graph, full-text store, exploration log and verification queue across branches. The run ID carries lineage.
3. `run_experiments` saves the hypothesis, analysis code, structured result, branch, and subject/object/method provenance in the exploration log. Submission and verification preserve the experiment-entry link.
4. The UI's investigation tree shows researchers. Its experiment cards draw on exploration entries joined to submission and verification results. These records are useful research outputs already available to the frontend.
5. The literature graph is a separate layer: `/api/kg` reads `claim_edges`. `fetch_papers` explicitly stores text without running claim extraction. Experiments write tested results; they do not automatically become literature claims.

The important product gap is **connecting what a researcher did to what was learned and what should happen next**. Merely animating the literature graph cannot establish that connection.

## Ranked next improvements

| Priority | Concrete interaction | Available data / missing work | Ownership and status |
|---|---|---|---|
| 1 | An investigation's **Findings** view answers “What have we learned?” with the researcher's synthesis, tested findings and unresolved attempts. Each result opens the exact experiment/code/artifact and originating branch. | `/api/tree/:root` already includes notes and experiments. `reflect` persists a note titled `reflection`; the current frontend filters the experiment view to `kind === "experiment"`. Label reflection as researcher interpretation. A structured final answer/next-work object is not yet supplied: `done` returns `DONE`. | Proposed to runtime owner; no new synthesis/model call or invented conclusions in this change. |
| 2 | Select a research branch and see **the scientific relationships it tested**, with a path back to the recorded attempt. | Branch → entry → submission → test is reliable. Exact literature attribution is missing: experiment provenance lacks claim/evidence IDs and `_act_submit` does not pass the supported `kg_claim_id`. Persist explicit IDs before drawing audited links. Subject/object labels can be displayed, but should not be guessed into canonical entities. | Runtime/shared-interface proposal only. No changes to inference, branch selection or graph-write policy here. |
| 3 | Click a literature relationship and read **what supports it, in what context**. Search and follow connected entities within the existing graph. | Quotes, source reference, attribution, `evidence_context` and `papers` were stored already. The graph API selected `claim_id` but discarded it; the frontend stopped at source counts. | **Implemented in this change.** Read-only API plus existing Evidence screen; no new visual shell. |
| 4 | Preserve the selected investigation when moving to Evidence/Library; an experiment click should open **that experiment**, not the agent's default Activity tab. | Project, run ID and experiment entry ID are already available; sidebar links discard the run, and experiment clicks previously selected only the agent. | Runtime owner confirmed both fixes are in their active slice. This task does not duplicate those edits. |
| 5 | Make Library's ready state lead to **Explore evidence / Ask a research question**. After Build, show the returned job's live progress and a clear Open investigation action. | Ready/built/stale status, collection counts, job ID and run ID are present. Today ready/imported collections foreground settings, and a build request can leave the user on that form. | Small follow-up in `Library.tsx` with App callback wiring. No new setup framework needed. |

For a judge-facing demonstration, lead with a real research objective, then show the recorded branching work, one substantive finding, its experiment and evidence, and the next question. The existing workspace contains more useful material than the rejected standalone storyboard exposed.

## Implemented evidence interaction

- Kept the existing navigation, typography, palette, graph library and review flow.
- Replaced the degree-sorted spiral with a left-to-right relationship layout using the already installed Dagre. Limited initial zoom prevents tiny graphs from becoming oversized cards.
- Added readable directions and relationship labels. Corpus-disputed edges use a dashed amber stroke; selecting a relationship highlights its endpoints and keeps its meaning on the graph.
- Added a searchable list of loaded relationships. Select a list result or edge to open the same source inspector; endpoint buttons continue exploration. Search explicitly describes its loaded-subset scope.
- The inspector shows stored source statements, paper title/year/link where recorded, neutral attribution (this source, prior work, unclear), stored assertion certainty, and biological context with stated/inherited provenance. It does not turn source counts or the existing corpus status into scientific confidence.
- Details load only on selection. Missing metadata, missing quotations, older graph responses and source-query errors have visible states. A mobile sheet retains the same controls and source content.
- Preserved the measured property per relationship, including it in titles and search so otherwise identical entity/predicate pairs remain distinguishable.
- Retained claim identity in the graph API and added `?source=...&claim=...` inspection. Registry lookup and parameterized queries keep the request in the explicitly named collection. No paper text is fetched remotely.
- Fixed an existing snapshot-key collision: two projects' `kg.duckdb` files with matching timestamps could share the fallback copy when read-only opening failed. Cache names and cleanup now include a resolved-path hash. A forced-lock regression verifies the two projects remain separate.

This is a normal research interaction and works with a built collection. It is not a benchmark, an evidence-grounding evaluation, a model-generated demo, or a replacement product design. Deferred evaluations, naming, e-values and exploration-policy work remain outside scope.

## Code locations

- Frontend: `frontend/src/components/Evidence.tsx`, `frontend/src/evidence.css`, `frontend/src/lib/evidence.ts`.
- Read API: `src/dnhacksbio/webui/evidence.py`; narrow dispatch and edge-ID additions in `server.py` and `data.py`.
- Stored evidence: `src/dnhacksbio/litmap/graph.py`, `store.py`; source metadata: `src/dnhacksbio/explorer/fulltext.py` and `litmap/corpus_build.py`.
- Research-output linkage: `_act_run_experiments`, `_act_submit`, `_act_fetch_papers`, `reflect`/`done` dispatch in `explorer.py`; `verifyqueue.py`; `webui/data.py:run_tree`.
- Follow-up UI targets: `Investigation.tsx`, `Library.tsx`, `App.tsx`, coordinated with their active owner.

## Validation scope

The API tests construct two real DuckDB graph stores with deliberately colliding claim/source IDs, then verify quotations, context and metadata stay in the correct collection, including forced lock-snapshot fallback. They cover missing collections/claims, optional paper metadata, empty evidence and explicit-source dispatch.

Browser tests exercise the actual React application using clearly synthetic API fixtures: relationship selection, paper links, context, search, empty evidence, retry, dark/light contrast and mobile navigation. Rendered screenshots were visually inspected. The shared preview has no populated normal research collection, so these screenshots demonstrate the implemented UI against test data, not a live scientific result. No model calls or new scientific claims were made.

Final repository gate counts and integration commit are recorded in `tasks/todo.md` and on the Board.
