# Research execution visibility

New Explorer attempts publish runtime-owned events before model/tool work starts. Select a researcher
in Investigations to see actual execution, its brief stated intent, liveness, experiment output, and
recorded artifacts. Terminal capture is opt-in and is not the source of lifecycle state.
The inline researcher workspace keeps recorded scene actions and image observations under
**Advanced diagnostics**, including `scene.recipe` notes and `scene.review` observations.
These entries follow the activity playback cursor alongside the other runtime events.

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

Observability write failures stop protected dispatch, cancel experiment work, and emit an explicit process
stderr warning. A heartbeat delay is shown as stale/unknown, not failure. The API reconciles a missing
worker only with kernel boot/PID/start identity evidence and an attempt guard. Reconciliation requires
Linux `/proc` in the worker's PID namespace; unsupported hosts or other namespaces retain unknown liveness. UI cancellation records cancellation and
SIGTERM cancels the CLI task so its experiment process group can stop and final output can be collected.

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

Human decisions remain supported by the backend, but review controls are hidden in the frontend.
Applying a decision records a durable outbox row in the working database, linked to the exact experiment
and attempt. Publication emits `experiment.human_reviewed` without private statistical scores. Repeating
the same decision/note is idempotent; changing a decision produces a new historical event. A publication
failure retains the saved decisions so applying again retries delivery. Legacy tests without an exact
runtime association do not invent one. Playback shows a human decision only after its event cursor.
Agent feedback deduplication tracks entry versions (timestamp, status and body), not just entry IDs, so
a later decision on an already-seen experiment is delivered on the next turn.

Parsed and queued results require finite numeric effect, p in (0,1], positive integer independent-unit
count, a nonempty null description and an explicit boolean robustness check. Invalid queued results
receive a retryable `malformed-result` verdict. Missing robustness never silently passes.

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
override the runtime policy. Existing feedback excerpts continue to enter context with version references; this
is delivery provenance, not evidence that feedback improved future performance.

## Sandbox and artifacts

Experiment code runs directly in the app's host Python environment, with no container runtime.
Install the `experiments` extra; deployment does this automatically. Each subprocess has an owned
process group for cancellation, temporary cwd/output, persistent cache and per-branch scratch.
The child receives a selected environment plus declared runtime paths and scope. Host execution is
not an OS filesystem/network security boundary: read-only-data and network settings are instructions.
Legacy `/data`, `/cache`, `/scratch` and `/work` Python path literals resolve to actual host paths;
`experiment.started` records those aliases, interpreter and the resolved code blob. The submitted code
remains in `experiment.queued`; replay can access each version only after its corresponding event.
Both output pipes stream with offsets and explicit truncation notices. Cancellation stops the owned
process group and retains available diagnostics. Temporary files are removed after artifact collection.

Before execution the runner allocates experiment IDs. The process writes an output manifest under
`DN_ARTIFACT_DIR`; see the mandatory artifact skill for the precise schema. The collector
accepts only contained regular PDB/mmCIF files, validates actual coordinates with Gemmi, enforces
8 files / 20 MB each / 40 MB total / 100,000 atoms, checks provenance, and stores approved bytes before
temporary job cleanup. Rejections are recorded explicitly. A failed process cannot publish its printed
statistics as a promising result. Failed experiments may retain collected diagnostic structures.

Artifact records include version, stable identity, experiment/attempt lineage, format/media type, hash,
length, creation/availability, status and provenance. Types are allowlisted; no model-supplied arbitrary
HTML, script, absolute path or remote URL is rendered. The engine does not invent structure predictions.
No renderable artifact means no viewer. Colours are decorative unless backed by separately recorded data.

An explicitly recorded `illustrative_scene` artifact can select a local cinematic illustration in the
expanded researcher's left scene pane. Its immutable JSON blob uses `schema: "illustrative_scene.v1"`,
`scene` (`binder`, `tissue`, or `spindle`), nonempty `title` and `purpose`, and
`provenance: {"category": "illustrative", "description": "..."}`. This is read-only presentation support,
not a scientific trajectory or an additional experiment collector format. The frontend fetches the
descriptor through the normal run/cursor-scoped blob route and rejects unknown scenes or missing
illustrative provenance. Availability follows the recorded artifact event; nodes without a visual
artifact remain full-width. A persistent label distinguishes the animation from measured output.
Its local 18-second play/pause/reset/scrub controls are independent of investigation playback, and
reduced motion holds a static pose. No arbitrary HTML, remote asset URLs or executable code is accepted.
Experiment details render optional `summary`, `plan` and `result.summary` strings as readable text
alongside the existing result disclosure, preserving the event projection's historical visibility.

Operator-installed project records may declare `presentation_only: true`. These namespaces use their
own regular `projects/<id>/kg.duckdb` and normal runtime run identities. The API blocks project changes,
uploads, corpus builds and researcher launches. Individual and bulk candidate decisions update only
their private review rows and durable runtime review outbox; they never open the master graph, promote
claims, or send feedback into exploration. A failed runtime publication retains the pending decision
for an idempotent retry. The review database must be inside its own project directory and may not be
a symlink or hard link. This operator-only flag cannot be enabled or cleared by a browser project patch.

An operator may also set `presentation_source_project` to an existing non-presentation collection
with a graph. Its attached private project is omitted from the collection switcher, and its runtime
investigations appear in that source collection's investigation list. Manifests keep their original
private owner. Only snapshots, ordered events/streams, immutable blobs and exact candidate lookup
accept the configured source scope. Candidate decisions resolve back to the private owner's database
and decision file; corpus and bulk-promotion APIs never treat this association as a writable alias.
Terminal and specialized instrument routes retain exact-owner scope. Unrelated, missing, self-referential
or chained presentation associations grant no additional access. Browser project patches cannot set
this operator-only association.

Use `scripts/import_presentation.py --source <staged-data> --destination <app-data>
--project <id> --root <run-root>` to validate a staged presentation without writing destination state.
After the deployed app supports presentation-only review isolation, add `--apply
--deployment-home <installation-home>` to register it under the shared deployment lease. The importer
requires a private graph and terminal, internally consistent runtime history. It adds only the new
project, referenced hash-verified blobs, and manifests/events in one SQLite transaction; it never
replaces a shared journal or graph. A private `.presentation-import.json` receipt permits recovery
and repeat import without resetting subsequent review decisions. Preserve the unchanged staging
bundle for retries. Identifier collisions, altered imports and active source records are refused.

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

### Exploratory binder bundles

The collector accepts bounded `binder_bundle` JSON artifacts with schema `binder_bundle.v1`.
It validates embedded member hashes, reconstructs mappings/metrics from the immutable source,
and requires matching provenance. The explorer verifies project/run/experiment scope before
publishing; a mismatch yields a rejected artifact event with no available blob reference.
The existing exact-run and replay-cursor blob access rules apply. This capability does not add
an audited structural result or bypass the human promotion gate. See [binder design](binder-design.md).

Binder scene actions use `scene.recipe` and `scene.review` events plus collector-owned
`scene_capture` PNG artifacts. Recipes, images and review blobs remain subject to run/cursor
reference checks; the scene service additionally enforces the exact experiment and bundle scope.
Capture/pick are bounded local browser operations; see the binder guide for CLI request fields.

Binder imports optionally embed two source-derived surface members and their bounded grid options.
The collector rebuilds these members before accepting the bundle. Scene recipe representation
changes are cosmetic; source coordinates, contacts and buried-area measurements remain immutable.


The native `binder` explorer action requires delivered `binder-interface` guidance and an existing
owned experiment. Target/epitope/protocol, comparison and follow-up records are immutable collected
JSON artifacts; `binder.job` records receipt milestones without changing the experiment's scientific
verdict. Receipt queuing does not launch inference. Candidate collection retains partial/rejected
outputs, and scene image reviews contribute actual model usage to the research cost ledger.
Agent arguments cannot override host paths, stores, workspace URLs or project/run identity.

### Scoped Investigation human review

The Investigation review card uses `GET /api/review/candidate` with exact `run`, `experiment`, and
optional `project` parameters. Runtime manifest scope and verification-queue provenance must resolve
one surviving engine test; ambiguous or missing associations are not guessed. Only ordinary submitted
results, verification, source evidence and human decision records are returned.

`POST /api/review/candidate` saves a required note (1–400 characters) with a `validated` or `rejected`
decision, then applies only that test through the existing promotion gate. Saved decisions survive
working/master writer locks and runtime-publication failure; the response distinguishes pending
application from applied review. Identical retries finish missing publication without duplicate
correction notes, and conflicting decisions are rejected. Old bulk promotion endpoints share the
per-collection decision lock. Graph application additionally holds the shared Library/build/run
collection lease; saving the decision does not wait on that lease. Accepted records retain their supported source provenance; review events
remain in the existing durable publication outbox and appear only after their historical cursor.
