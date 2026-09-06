# Parallel delivery: current direction

Updated September 6, 2026 after the code audit through main `e04e9ff`.
The [architecture entry point](../docs/architecture/README.md) replaces the earlier
standalone forecasting delivery plan. Recheck the [Board](https://github.com/richykim7/dnhacks/issues/1)
before claiming work; this file is not an assignment or permission to execute backlog items.

## Decisions

- Investigations is the main product surface. Show the scientific graph a selected
  investigation actually consumed, its provisional changes, and the user approval boundary.
- Accepted knowledge changes only through user approval. Working hypotheses and traces
  may persist without being accepted. The intended owner of the accepted graph is still
  unresolved: project-shared versus run-owned. Settle that before storage/API implementation.
- The current engine shares a writable project database across branches; accepted findings
  go to a separate global master that new runs do not automatically read. This is a
  substantive integration gap, not just a naming or tab change.
- Keep greedy provisional, mocks available and the domain contract general. Biology is
  the demo. E-values remain teammate scope. Theory work must state a verifiable objective,
  assumptions and strongest relevant comparator; novelty has not been established.
- The original 16-hour window is not renewed by this plan. Prioritize one complete
  inspect → propose → approve → consume loop and leave time to rehearse.

## Work already delivered

| Lane | Current state | Reuse/coordination implication |
|---|---|---|
| Runtime (`dnhacks/s2--codex`) | Landed in main `e04e9ff`: execution journal, attempt/events, live/playback state, selected experiment and artifacts | Extend the actual Investigations detail; do not build a parallel runtime or researcher tree |
| Evidence (`ian/ux-demo`) | Merged `3a7a227`: directed relationships, stable claim identity, exact sources/context and inspection | Reuse the source inspector; a request to expose claim IDs again is obsolete |
| E-values (`dnhacks/s3--codex`) | Merged `d0b864e`: GPU/cohort evaluation and wealth report | Teammate-owned implementation; do not infer that reports already enforce live KG acceptance |
| Forecast delivery (`ian/graph-plan` and prior workers) | Historical packets, structural scorer/evaluator, saved model study and separate replay UI | Reuse artifacts and graph presentation; the existing global demo endpoint is not investigation-scoped data |
| Policy lab (`ian/policy-lab`) | Exact specialization, proof/counterexample and comparator artifacts delivered | Existing-theory certificates are useful; no novel theorem or empirical advantage over strongest seeded controls |

These are landed facts, not permanent ownership locks. Consult the current Board for active work.

## Proposed next sessions

The [source-linked slice plan](../docs/architecture/surfaces-and-next-work.md) contains
acceptance criteria. Agree on the small owner/revision/context boundary before parallel edits.

| Session | Bounded result | Dependency |
|---|---|---|
| Knowledge boundary | Accepted revision identity, explicitly scoped working proposals, user decision and next-run read path | Resolve owner scope; coordinate current storage and review owners |
| Investigation scientific context | Exact consumed graph plus provisional relationships inside the selected attempt detail | Consume the agreed records and runtime journal; reuse Evidence inspection |
| Demo composition and rehearsal | A deterministic record/replay of one full approval loop, readable animation, source inspection and rejection path | Same records as the intended live flow; provenance visible |
| Evaluation/theory (independent) | Frozen comparable branch-allocation or memory experiment with full failure accounting | Define target and information/cost budget first; leave e-value work to teammate |

The coordinator can handle contracts/integration while independent workers handle one
of these bounded artifacts. Child agents report to their parent and **never post to the
Board**. Independent human-launched sessions use their own stable Board identities.

## Evidence and research already available

- [Forecast demo and measured limits](../docs/forecasting-demo.md): later CIViC curation,
  matched structural controls, flat/static/evolving comparison and substantial attrition.
- [Zero-retrieval control](../docs/forecasting-memory-control.md): a modern model outperforms
  the full-history structural baseline on the same 683 candidates. This benchmark does
  not establish that the graph causes anticipation.
- [Policy proof/comparator audit](../tasks/research/policy-lab/report.md): Set-Union Knapsack
  specialization and certificates; strongest seeded controls match all 95 packet optima.
- [Original asset/research brief](graph-forecasting-plan.html): historical proposal and
  source discovery, not a current architecture specification.

Use the existing freeze/evaluate/reveal records for a recorded experiment. Do not equate
historical cutoff, runtime sequence, graph revision and user acceptance. The previous
standalone milestones and lane assignments are preserved in Git history; they are complete
or superseded, not instructions to rebuild those components.

## Session protocol

Follow [AGENTS.md](../AGENTS.md) and [BOARD.md](../BOARD.md): show/status/branch/worktrees,
claim scoped paths, isolate concurrent work, and post shared-interface changes before edits.
Before each commit fetch/incorporate main and run every current gate. Push, review and
integrate the validated PR under the standing merge authorization. Post done only when
landed; update for unfinished work. Keep handoffs local and ignored under the current protocol.
