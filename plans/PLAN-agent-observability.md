# Agent visibility, instruction compliance, and experiment artifacts

Status: **proposed implementation plan; no runtime changes delivered by this document**.
The user has agreed with the product direction below. This documentation slice records it first;
it is not a claim that events, enforcement, terminal capture, or the corrected viewer are implemented.
The evaluation ideas in [backlog.md](backlog.md) require separate explicit user approval.

## Product contract

Click a research node to inspect that agent's current execution, short stated intent, history,
experiments, results, and errors. When an experiment produces a renderable artifact, show its 3D
viewer **inside that experiment in the node detail**. Do not keep a standalone Structures tab or
substitute an unrelated PDB demo for a missing experiment artifact. Preserve camera/selection while
inspecting that artifact. No artifact means no viewer; pending/failed artifacts have explicit states.

An explicit **Show terminal** button opens a read-only raw tmux view when that agent has a registered
pane. It is closed by default. The ordinary node view uses structured runtime events, not scraped
terminal text or a model's continuous summaries. Do not create a tmux pane per Python branch merely
to pretend an SDK agent has its own terminal.

## What the repository currently does

- `Explorer.step` in `src/dnhacksbio/explorer/explorer.py` awaits `_next_action` and `_dispatch` before
  appending the reasoning trace. Long tool calls therefore have no start/output events in that trace.
  Trace-write exceptions are currently swallowed; the new event channel must expose persistence failure.
- `webui/data.py` derives activity from trace mtime (`ACTIVE_WINDOW_S = 660`). `run_events` truncates
  reasoning/observations and builds a presentation timeline; it is not a complete event-sourced history.
- `webui/jobs.py` records a launched job's question and process state. That is not a durable independent
  run/branch manifest. Explorer branches use SDK sessions; there is no per-agent tmux pane registry.
- `_act_get_skill` returns at most 8,000 characters. Skills are discoverable through
  `explorer/skills.py`; guidance availability is not a verified prerequisite for executing a method.
- `_act_run_experiments` receives sandbox results as a batch and creates experiment entries afterwards.
  `sandbox.py` captures subprocess output on completion and cleans up the temporary job directory.
  Streaming output and durable file artifacts therefore need explicit runner changes.
- Human corrections/verification feedback already enter `_state` and `_turn_message`, with bounded
  excerpts and seen-ID tracking. Preserve that mechanism, add delivery/version provenance, and do not
  confuse putting feedback into context with proving that future performance improved.

## Ownership: code reports execution; the agent reports intent

| Producer | Responsibility | Trust boundary |
| --- | --- | --- |
| Runner/supervisor | lifecycle, model-call start/end, tool dispatch/start/end, output, crash/cancel, heartbeat | Measured execution, never supplied as authoritative state by the model |
| Agent action protocol | short user-facing intent and intended method/skill IDs | Self-reported plan, not evidence of completion or correctness |
| Sandbox/artifact collector | exit status, result validation, artifact availability and provenance | Validate before registering; stdout is untrusted content, not control events |
| Frontend | reduce events, label freshness/source, render artifacts and optional terminal | Never infer success from silence or invent intent/results |

Use a concise `intent` field for the next action (what and why, not private chain-of-thought).
Require it on actionable responses and changes of task. Validate before dispatch, with a bounded repair
opportunity for malformed/missing fields. Failure to repair becomes an explicit protocol error; do not
silently execute an unvalidated action or generate a model-attributed update in the UI. A deterministic
tool label remains available while waiting for a model response. Terminal output cannot spoof intent
or trusted lifecycle events.

## Lifecycle, activity, and liveness are separate

- Lifecycle: `queued`, `running`, `waiting`, `completed`, `failed`, `cancelled`, `budget_exhausted`.
- Activity: structured phase plus active operation ID, e.g. model request, skill loading, tool execution,
  sandbox queue, experiment, child branches, or human input. Waiting always carries a reason.
- Liveness: last supervisor/worker heartbeat and observation freshness. A transport SSE heartbeat
  means the connection is alive, not that the agent is alive or making progress.
- Model/tool timeouts, exhausted step budgets, and pruned branches are not successful completion.
  Record the stopping reason. A resume gets a new attempt identifier; do not overwrite its previous end.
- Supervisor reconciliation uses process/worker ownership and attempt identity, not a reusable PID alone.
  An unexplained crash becomes failed/interrupted with evidence; mere heartbeat delay is stale/unknown.

## Proposed event and persistence contract

Implement a versioned append-only stream per investigation. All branches submit through a serialized
writer so `sequence` is monotonic across that investigation. Assign the sequence and persist before
publishing; flush a complete record before clients can observe it. Define crash recovery for an incomplete
last record and idempotent publication. Do not use timestamp sorting to resolve concurrent branches.

Required envelope:

```text
schema_version, event_id, sequence, investigation_id, run_id, attempt_id,
parent_run_id?, operation_id?, experiment_id?, kind, producer,
occurred_at, recorded_at, payload
```

Record lifecycle transitions, model requests, intent updates, tool starts/output/ends, experiment
starts/results, artifact registration, fork/resume/pruning, instruction delivery, and feedback delivery.
Use bounded output chunks with byte offsets and explicit truncation markers; larger logs/results live
in immutable referenced blobs. Never silently discard an error tail. Redact sensitive arguments/output
before storing or streaming; do not retain credential files or claim regex redaction catches all secrets.

Allocate stable operation/experiment IDs **before execution**, and link any later exploration entry ID
to them. This allows live output, failed experiments, and artifacts to share identity. Avoid a success
record pointing at an unwritten result: use a durable outbox/commit ordering with recovery and idempotency.
If observability storage fails, mark the run degraded through the supervisor and halt further protected
dispatch until resolved; do not report a complete audit trail that was never persisted.

API sketch (proposed, not current routes): scoped snapshot plus cursor, paginated events after a
sequence, and SSE with event IDs/resume cursor. Snapshot and cursor must be consistent. Deduplicate
delivery, identify gaps, and request a new snapshot if retention makes a cursor unavailable. Retention
must not silently break replay. Preserve the old trace endpoints for compatibility while migrating.

## Research question persistence

Persist a run manifest before the first model call for every entry path: UI launch, CLI/harness,
fork, and resume. Store investigation/root/run IDs, original question, branch objective, project ID,
parent, configuration/protocol versions, instruction snapshot references, and timestamps. The original
question is immutable; a user revision becomes an explicit version/event. A branch objective is not a
replacement for the user's research question. Resume preserves both question and lineage.

Do not depend on retaining a launch job or its filename. Keep old runs readable: import a recorded
question only when its provenance is known, otherwise show unavailable—not corpus scope as a question.

## Mandatory instructions and tool-specific skills

Planned main entry: `skills/agent-runtime/SKILL.md`, with pointers to focused guidance for progress,
artifact output, feedback, and the existing scientific method skills. These files are not yet created.
The launcher/runner must resolve and deliver the mandatory entry and required references, rather than
relying on an agent remembering to discover a menu. Coordinate method registries with active e-value
work; this plan does not redefine its statistical contracts.

1. Use an allowlisted skill registry, canonical path containment, and version/content hashes. Reject
   unknown names, traversal, missing required references, and cyclic dependency graphs.
2. Deliver complete required content with an explicit dependency order. Remove silent 8,000-character
   truncation. If context capacity cannot hold requirements, stop or use a defined resumable delivery
   protocol before execution; never claim a partially delivered skill was fully loaded.
3. Pin the instruction snapshot per attempt. Record what the runner actually delivered, when, and to
   which session/branch. A model saying “I read it” is not the audit record. On fork/resume, verify inherited
   snapshot identity or redeliver; document intentional version upgrades.
4. Maintain an action/method-to-required-skills mapping in runner code. Gate dispatch on delivery of
   mandatory and applicable guidance. Experiment requests declare method IDs; arbitrary generated code
   must not bypass checks by omitting a method. Unknown/custom methods require an explicit supported
   exploratory path with common rigor requirements, never automatic audited status.
5. Separate enforceable checks (schema, required fields, limits, provenance, sandbox permissions,
   valid method registration) from semantic scientific judgment. Delivering instructions cannot prove
   comprehension, identify every library in arbitrary code, or guarantee rigorous analysis. Preserve the
   independent verifier; mark unvalidated methods/results exploratory and expose policy failures.
6. Treat papers, outputs, terminal screens, and dataset metadata as untrusted data. They cannot replace
   mandatory instructions or grant new tool authority. Skills themselves cannot override sandbox policy.
7. Add explicit tests for omitted intent, skipped skill delivery, changed/missing references, truncation,
   fork/resume, unknown method, and malicious tool-output instructions. Do not spend model budget merely
   to validate event plumbing; use injected deterministic actions first.

## Experiment artifact contract and inline rendering

```text
schema_version, artifact_id, investigation_id, run_id, attempt_id, experiment_id,
kind, format, media_type, storage_key, byte_length, sha256,
created_at, available_sequence, provenance, status, failure_reason?
```

- Initial kinds: molecular structure plus result/log references. Allowlist PDB/mmCIF renderers; add
  other bio experiment renderers through explicit type contracts, not arbitrary HTML/JavaScript execution.
- Provenance distinguishes experimental reference, prediction, derived geometry, and illustration;
  include source IDs, generating tool/version, input/data hashes, and units/chain/residue numbering when
  applicable. Optional measurements need their own source and units; no placeholder scientific scores.
- The sandbox writes to a designated output directory. The collector validates regular-file type,
  containment (including symlinks), format/parseability and quotas, and copies approved artifacts into
  durable run storage before job cleanup. Never serve arbitrary absolute paths or URLs supplied by a model.
- Register only after successful collection; expose pending/rejected/missing states explicitly. File
  existence is not evidence of scientific validity. Failed experiments may retain diagnostic artifacts
  with their failed status, not a success badge.
- API resolves opaque storage IDs with project/run scope checks. Browser fetches only the selected
  experiment's artifact. Keep bounded file/atom counts and renderer error handling.
- Refactor the existing molecular renderer into node experiment detail and remove the standalone nav
  entry. Future experiment types can use the same registry; no backend predictions are invented now.

## Playback

Use the same deterministic state reducer for live delivery and recorded playback, including lifecycle,
intent, experiment status, feedback, and artifact availability. A replay at sequence N cannot show a
result, review, child node, or artifact first available after N. Current-state detail must not leak into
the replay through an independently polling component. Full immutable result references avoid today's
summary truncation; bounded display previews can still offer full recorded output on demand.

Index/checkpoint long streams with schema versions and snapshot sequence. Handle duplicates, gaps,
reconnects, restarts, pruned branches, and concurrent operations. Label legacy histories as partial;
do not synthesize missing events or confuse execution playback with forecasting's biological time axis.

## Optional tmux view

- At launch, register an exact tmux server/pane identity and ownership scope for the agent that actually
  runs there. Python/SDK branches without their own pane show **Terminal unavailable for this agent**;
  a shared job console can be offered separately and explicitly labeled shared.
- A scoped backend endpoint performs bounded `capture-pane` reads via an argument array (no shell
  interpolation). Clients cannot choose arbitrary pane IDs or capture other sessions. Never send keys,
  create a writable terminal, or execute commands from this view.
- Poll at roughly one second only while the user has opened Show terminal and the page is visible.
  Stop on close/navigation, back off on failure, and indicate capture time and disappearance of the pane.
- Render as inert text, cap history/bytes, handle terminal control sequences, redact known sensitive
  output, and keep access local/authenticated as appropriate. The button is not an authorization boundary.
- This is a screen snapshot, not a complete log. Do not derive lifecycle from it. Unless separately
  recorded with a defined retention policy, it is unavailable in historical replay and labeled accordingly.

## Delivery slices and acceptance

1. Durable manifests/events and lifecycle hooks: injected model/tool tests cover start, completion,
   exception, timeout, cancellation, step-budget exhaustion, fork/resume, and storage failure. Starts are
   visible while a deliberately blocked tool is still running.
2. Intent/instruction prerequisites: complete snapshot delivery, method gates, bounded protocol repair,
   audit records, and feedback-delivery IDs. Test that a skipped prerequisite prevents dispatch.
3. Sandbox streaming/artifact collection: stable experiment IDs, actual incremental output, durable
   validated files, rejected traversal/oversize content, and correct failure propagation.
4. Scoped snapshot/SSE APIs and one live/replay reducer. Test resume/dedup/gaps, question persistence,
   no cross-project reads, and no future-data leakage at every cursor.
5. Node detail integration and opt-in tmux: inline 3D only for a matching artifact; no standalone
   Structures tab. Playwright screenshots and real rendering inspection across dark/light/mobile,
   missing/failed artifacts, live execution, terminal closed/open, and playback.

Coordinate before editing the shared `webui/server.py` and `frontend/src/App.tsx` with the forecasting
session. Use existing record adapters where compatible, without treating forecasting records as this
runtime's already-implemented event contract. Run the repository's full gates before integration.
Evaluation dashboards and model-backed performance studies remain in the explicit-approval backlog.
