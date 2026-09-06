# Research execution visibility

New Explorer attempts publish runtime-owned events before model/tool work starts. Select a researcher
in Investigations to see actual execution, its brief stated intent, liveness, experiment output, and
recorded artifacts. Terminal capture is opt-in and is not the source of lifecycle state.

## Persistence and scope

`<trace_dir>/runtime/journal.sqlite3` stores immutable original-question/branch manifests and version-1
events. SQLite `BEGIN IMMEDIATE` serializes concurrent branches; sequence numbers are contiguous within
each investigation. Transactions recover interrupted writes without publishing incomplete records.
Events have unique IDs, investigation/run/attempt/operation/experiment identity, producer and timestamps.
Resume creates a new attempt and retains earlier outcomes and the original question. New forks receive
new child IDs rather than overwriting prior branches.

The journal commits before publication. Content-addressed blobs are written, flushed and fsynced before
references commit. A crash between blob storage and event commit may leave an unreferenced blob, never
a success event pointing at an unwritten blob. There is currently no automatic retention/deletion.
SQLite indexes the ordered stream; snapshots are rebuilt from history rather than persisted checkpoints.
Large histories therefore cost more to load/reduce; pagination bounds each event response, not the total
client history. Do not prune the journal to save space without introducing explicit cursor-expiry rules.

Observability write failures stop protected dispatch, cancel sandbox work, and emit an explicit process
stderr warning. A heartbeat delay is shown as stale/unknown, not failure. The API reconciles a missing
worker only with kernel boot/PID/start identity evidence and an attempt guard. Reconciliation requires
Linux `/proc` in the worker's PID namespace; unsupported hosts or other namespaces retain unknown liveness. UI cancellation records cancellation and
SIGTERM cancels the CLI task so its sandbox can stop and final output can be collected.

Launch jobs register the question and queued state before spawning. CLI/harness construction registers
its manifest before model calls. Legacy histories remain readable but are explicitly partial; their
missing lifecycle, intent and artifact history is not fabricated or imported from collection scope.

## API

All routes live under `/api/runtime/<run_id>/`. Optional `project=<id>` must match the persisted manifest.
This is a local single-operator workspace: omitting project deliberately permits All projects. These
scope checks are not multi-tenant authentication; do not expose the unauthenticated server publicly.

- `snapshot?through=N`: state and consistent cursor at N (omit for latest).
- `events?after=N&through=M`: next ordered page, maximum 1,000 events.
- `stream?after=N`: SSE `runtime` events, IDs equal sequence, with `Last-Event-ID` reconnect support.
  SSE comments indicate transport health only. Connections periodically reopen to bound request lifetime.
- `blob/<opaque-sha256>?through=N`: only runner-owned references actually available to that exact run
  at that cursor. Arbitrary digests nested in model results do not grant access. Integrity is rechecked.
- `terminal`: bounded read-only capture of an explicitly registered dedicated pane, otherwise unavailable.

Live and playback use the same frontend reducer. Children, results, feedback and artifacts cannot appear
before their events. The backend reducer produces matching snapshots. Legacy endpoints are retained for
compatibility. Full observations are immutable referenced text, not truncated presentation summaries.
The visible event list is a bounded preview; the event API retains the complete stream.
Verifier assessments are published from the durable verification queue with stable event IDs, so an
interrupted publication can recover on the next drain without duplicates. The node shows pending,
rejected or passed-verifier checks separately from execution status; passing is not human confirmation.

## Agent protocol and skills

`skills/agent-runtime/SKILL.md` is mandatory. It points to rigor, progress/feedback and artifact guidance.
Every action requires a concise `intent`, action name and object args. One malformed-response repair is
allowed; a second failure ends the attempt without dispatch. Model requests have a 600-second timeout.

The skill registry enforces containment, explicit reference allowlists, dependency order, complete
content hashes, cycle/missing-reference checks, and a 200 KB instruction delivery cap. An unavailable
method fails closed; unrelated unavailable methods do not prevent other registered methods. Each attempt
pins complete snapshots. Required/previously selected guidance is re-sent on each model request so SDK
context compaction does not silently invalidate the delivery ledger. Audit events record supplied context,
not proof that a provider accepted it, that the model understood it, or that arbitrary code implements it.

Experiments declare an exact `method_id`. `get_skill` schedules that method's complete pinned guidance
for the next model request; the dispatch gate checks recorded delivery, not model claims. A custom method
uses `exploratory`, receives common rigor, and cannot be submitted as an audited experiment. Registered
method use still requires independent scientific verification. Tool outputs cannot emit trusted events or
override the sandbox. Existing feedback excerpts continue to enter context with version references; this
is delivery provenance, not evidence that feedback improved future performance.

## Sandbox and artifacts

The sandbox retains its network/resource/user/mount boundaries. Python output is unbuffered; both pipes
are drained while the process runs. Events carry stream byte offsets and bounded chunks. At 1 MB per
stream live publication stops with an explicit marker; a bounded final tail retains traceback endings.
Known token patterns and sensitive field names are redacted before journaling/streaming. This is
best-effort, not comprehensive secret detection; never print secrets or put them in scientific artifacts.

Before execution the runner allocates experiment IDs. The sandbox writes an output manifest under
`/work/output` (`DN_ARTIFACT_DIR`); see the mandatory artifact skill for the precise schema. The collector
accepts only contained regular PDB/mmCIF files, validates actual coordinates with Gemmi, enforces
8 files / 20 MB each / 40 MB total / 100,000 atoms, checks provenance, and stores approved bytes before
temporary job cleanup. Rejections are recorded explicitly. A failed process cannot publish its printed
statistics as a promising result. Failed experiments may retain collected diagnostic structures.

Artifact records include version, stable identity, experiment/attempt lineage, format/media type, hash,
length, creation/availability, status and provenance. Types are allowlisted; no model-supplied arbitrary
HTML, script, absolute path or remote URL is rendered. The engine does not invent structure predictions.
No renderable artifact means no viewer. Colours are decorative unless backed by separately recorded data.

The 3Dmol public API provides high-quality cartoons, ambient occlusion, orthographic framing, ligands,
atomic/surface modes, chain/residue selection, reduced-motion-aware optional rotation and camera reset.
Camera and selection are cached for recently inspected artifacts. There is no dependency fork or
standalone Structures tab. The RCSB 1CRN coordinates in browser fixtures are a reference-only test asset,
not a real experiment produced by this application.

## Optional terminal integration

Trusted launchers can call `webui.runtime.register_terminal(journal, run_id, attempt_id, socket=..., pane=...)`
for a dedicated pane they own. The registry pins pane PID/start identity. The browser cannot supply pane
or server identifiers. Capture uses argument arrays, never sends keys, and is rendered as inert text.
Polling runs about once per second only while opened and visible, with failure backoff and cleanup.
SDK research branches do not own tmux panes, so the default is honestly unavailable. Terminal snapshots
are not persisted and are unavailable in playback. No per-branch panes are created to simulate execution.

## Checks

`pytest tests/test_runtime.py tests/test_runtime_api.py`, frontend `test`, and `e2e/runtime.spec.ts` use
deterministic injected actions and isolated browser fixtures, without model budget. Full repository gates
remain required. Set `PLAYWRIGHT_BASE_URL` when checking an isolated Vite server; set `API_PROXY_TARGET`
on that server for its isolated Python backend. Inspect actual dark/light/mobile and surface screenshots.
Evaluation studies and KG-build animation/demo playback remain deferred in `plans/backlog.md`.
