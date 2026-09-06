# Binder interface workbench

`binder_bundle.v1` is an exploratory experiment artifact. It contains physical coordinates,
exact atom/residue identity, source bytes and derived exports with SHA-256 hashes. A selected
experiment opens it in the Interface Foundry through the existing scoped runtime blob route.
Nothing creates a statistical verdict, binding-affinity estimate or master-graph promotion.

## Import and inspect

Use `python -m dnhacksbio.binder request.json --output response.json`. Requests contain
`action` and `args`; receipt operations also contain an operator-selected `store` directory.
Supported actions: `binder.prepare_target`, `binder.define_interface`, `binder.import_candidate`,
`binder.evaluate_interface`, `binder.plan_design`, `binder.start_design`,
`binder.collect_candidates`, `binder.cancel`, `binder.recover`, `binder.attach_candidate`,
`binder.compare`, `binder.propose_followup`.
Python functions in `dnhacksbio.binder` expose the same geometry and bundle operations.
The agent must use the existing `exploratory` method and receive the complete agent-runtime
instructions before execution. This does not specify the pending replacement for Docker.

An imported candidate requires `structure_path`, `fmt` (`pdb` or `cif`), `target_chains`,
`binder_chains`, `candidate_id`, `provenance`, `scope` and `source_evidence`.
Scope contains exact `project_id`, `run_id`, `experiment_id`. Evidence rows require `doi`,
`quote`, `context`; only an explicitly illustrative fixture may omit them.
Provenance requires `category`, `source_ids`, `tool`, `tool_version`.

The portable JSON includes base64 content-addressed source PDB/mmCIF, candidate and target mmCIF,
binder FASTA, residue mapping, interface metrics, contacts Parquet and resolved protocol.
`export_bundle` extracts these into a new directory. For runtime collection, write the raw bundle
JSON (the CLI response's `output`, not the response envelope) and declare it in the existing
output manifest with `kind: "binder_bundle"`, `format: "json"`, path and matching provenance.
The collector reconstructs and compares mappings, metrics and exports against source coordinates;
the explorer rejects a bundle whose scope differs from the actual owning experiment before
publishing its artifact event. A digest alone never authorizes access. Replay only reveals a
bundle once the collector event is available.

## Scientific conventions

One explicitly selected structural model; residue-level highest-total-occupancy alternate
conformer, lexicographic tie break. Never combine A/B side chains or reconstruct missing atoms.
Author chain/number/insertion code, label chain/number and atom name remain explicit. Chain
trimming records the identity transform and retains the original identity map. Ambiguous
residue or atom identities, absent chains, nonfinite coordinates and unsupported conformer
policies are rejected. The inspection cap is 6,000 atoms and 20 MiB per portable bundle.

Contacts are interchain heavy-atom pairs at most 4.5 Å, with 4.0/5.0 Å sensitivity counts.
The below-2.0 Å pair count is a simple steric diagnostic, not a comprehensive clash energy.
SASA uses a deterministic 256-point Fibonacci Shrake–Rupley approximation and declared element
radii with a 1.4 Å probe. Total buried area is `SASA(target)+SASA(binder)-SASA(complex)`;
there is no division by two. Unsupported radii produce missing SASA with a reason.
No hydrogen-bond or salt-bridge category is inferred from distance alone.

Assembly expansion, symmetry generation, glycans and membrane placement are not implemented;
context stays unavailable. Import an explicitly prepared full-context structure for review;
assembly labels are supplied provenance, not a verified accessibility assessment. Confidence
is currently missing rather than fabricated from B factors. Comparisons require identical target
coordinates/mapping and metric protocol; Pareto axes (maximize contacts/minimize close pairs)
are explicit engineering criteria, never an affinity ranking.

## Bounded design adapter

BindCraft is pinned to `efb5bfeb8b4b1a5944256f979c34e0c8e6a82d9d`.
`plan_design` pins target/epitope, dependency/environment/settings hashes, lengths, candidate,
trajectory, GPU wall-time and byte budgets. Explicit seeds and insertion-code hotspot notation
are rejected because this pinned upstream interface cannot represent them faithfully.
Start is idempotent within the experiment; a conflicting reuse is rejected. SQLite transactions
serialize receipts and ownership. Cursor collection survives restart and retains canceled,
rejected and partial records. An interrupted job is never automatically rerun.

`binder.adapter.execute` is an operator-side launch requiring a clean pinned BindCraft checkout,
actual installed-environment match to a pip freeze, verified weight inventory, settings hashes,
reviewed deployment eligibility and exact target/epitope hashes. No dependencies or weights are
automatically installed. The GPU-host lease is `/tmp/dnhacks-shared-gpu.lock`, inherited by the
launched process. Wall time, all trajectory-start log events, output bytes and cancellation are
monitored; termination addresses the process group. Poll-based disk/start limits can overshoot
between checks; immutable candidate collection enforces its byte/count cap before publication.
Raw generator output remains separate until explicit target residue mapping and validated import.
A completed generation receipt is not proof of an accepted candidate.

No BindCraft pilot or biological target selection has been performed for this implementation.
A reviewed target/epitope, concrete GPU budget and eligible dependency deployment are required
for the live pilot. Source questions remain those in the plan; the browser fixture is two rigidly
translated copies of RCSB 1CRN and explicitly demonstrates clashes, not a successful design.

## Visual inspection and remaining acceptance

The workbench renders atomic envelopes, optional precomputed atom-union surfaces and a Cα backbone
trace with Three.js r180 / R3F 9.3 / Drei 10.7.
It supports pearl/cyan and bronze/violet studies, physical/exploded/contact-only opposing views,
exact picking, accessible contact tables, camera preservation during inspector selection and
scene/bundle export. Exploded offsets and reduced cutaway sphere radii are presentation only.
Rendering is demand driven, with no autonomous motion in reduced-motion mode.
The workbench element exposes a bounded controller for local browser capture; the development-only
`?sceneReview=1` alias is also available. Readiness waits for fonts, synchronous shader compilation
and settled renders, and stops on scene removal. Runtime capture uses the actual owning experiment.

The browser review fixture is test-only (`frontend/e2e/binder-fixture.json`). Run
`npm --prefix frontend run e2e -- e2e/binder.spec.ts`. The shared runner queues the browser
and owns isolated servers, ports and review artifacts; its output prints the run directory.
The test saves PNGs and camera/visibility metadata for deterministic presets. Development review
records distinguish measured raycast visibility from qualitative image inspection. Secondary-structure
assignment and WebGPU visual comparison remain separate acceptance work. The `candidate-compare`
preset requires a second available candidate with identical target coordinates and metric definitions.
The frame intervals recorded by the demand renderer include idle gaps and are **not** an
interactive p95 performance benchmark. No reference-hardware performance target is claimed.

Inside a runtime-launched experiment, read the assigned scope from
`json.loads(os.environ['DNHACKS_EXPERIMENT_SCOPE'])`; the runner supplies it immediately before
executing the submitted code. It is an identity hint, not authority: publication independently
checks the actual experiment. Standalone imports supply explicit scope themselves.

The model seam's `acomplete(..., images=[png_bytes])` and `Session.ask(..., images=[png_bytes])`
now attach actual SDK image content, bounded to two PNGs, 8 MiB each and 1920×1080 dimensions.
An actual Opus observation of the supplied fixture was verified; its image hash and response
are preserved in [the visual review](binder-review/README.md). This is image transport only;
scoped capture-tool orchestration and replay are described below.


## Recorded scene actions and runtime capture

The trusted local CLI supports `binder.open_scene`, `binder.set_scene_view`,
`binder.capture_scene`, `binder.inspect_scene_capture` and `binder.pick`.
Supply `journal_directory` (the parent of the runtime directory), the exact three-part `scope`,
and `base_url` for capture/pick. The URL must be a local workspace server. Node and the installed
Playwright Chromium are required. The browser opens the real owning experiment, selects the bundle
by its hash, applies the validated recipe and waits for readiness; no fixture responses replace the API.

Recipes are immutable Journal blobs with parent hashes. Each change records an agent action and note.
Historical scene opens return only recipes available at the requested cursor; changing or capturing
a stale revision fails. A scene permits at most 128 actions and an experiment at most 16 captures.
Each capture is bounded to 1920×1080, 8 MiB and at most 60 seconds including browser navigation.
The worker process group is terminated on timeout. Captures retain the source/recipe/image hashes,
actual camera, viewport, physical transform, visible residue IDs and occlusion fractions.
The runtime serves capture PNGs only when the collector artifact is available at the requested cursor.

Image inspection attaches the saved PNG bytes to a tools-disabled vision call and journals its visual
observation. Picking requires the capture and recipe hash, replays the saved camera, checks matching
viewport/transform and returns a source residue identity. Visual observations do not change metrics.

The workbench follows recorded actions by default, with play/pause, a scene-action slider and
0.25–4× playback. Manual rotation, selection and material changes enter local exploration.
Follow latest restores the agent view. Neither local exploration nor replay rewrites the recorded
history; the timeline describes inspection actions, not molecular dynamics or generation progress.


## Optional source-derived surfaces and backbone traces

Pass `surface_options` to candidate import (Python or JSON CLI), for example
`{"spacing":0.8,"probe":1.4,"max_grid_axis":64}`. The portable bundle then includes
`surface-target.json` and `surface-binder.json`; existing eight-member bundles remain valid.
Collection reconstructs both meshes from the immutable source and rejects altered coordinates or
source mappings even if the supplied mesh hash was recomputed.

The mesh is a marching-tetrahedra envelope of heavy-atom spheres with the declared radii plus probe.
It is a visualization approximation, not a solvent-excluded surface or the SASA calculation.
Grid axes are bounded to 64 and each mesh to 120,000 triangles. Spacing can increase to meet the grid
budget and is recorded. No decimation is performed. The mesh records its maximum vertex field
residual and a conservative whole-triangle field-residual bound; these are explicitly **not** a
Hausdorff distance or topology guarantee. Unknown element radii fail instead of being guessed.

A browser worker checks bundle/member hashes, parses meshes, builds spatial buckets for smooth
sphere-normal shading and transfers typed geometry buffers. Source positions and metrics are
unchanged; GPU positions use float32. Surface picks return the source atom associated with the
nearest vertex of the intersected triangle. The exact residue identity then selects the unchanged
contact table. That association does not turn apparent image proximity into a contact measurement.

Scene recipes accept `representation: "atoms" | "surface" | "ribbon"`. Surface is the default when
precomputed meshes are supplied. The UI calls the last mode **Cα backbone trace**: it interpolates
source Cα positions, breaks at missing atoms, author-number gaps, chain boundaries or distances
outside 2.5–4.5 Å, and omits sidechains. It does not assign helices/sheets. Unsupported traces are
unavailable, and interface-close/reverse always use the labeled atomic contact-only cutaway.

The surface review fixture is `frontend/e2e/binder-surface-fixture.json`, the same explicitly
illustrative translated-1CRN pair. `BINDER_SURFACE_REVIEW_DIR` controls its browser capture directory.
The measured/visual review remains separate from reference-hardware performance acceptance.


## Worker recovery and reviewed partial output

`binder.recover` takes `receipt` and `scope`. It marks a running receipt interrupted only when
its recorded boot/PID namespace matches this process and the original PID/start identity is gone.
Live or inaccessible workers, different namespaces and different boot identities fail explicitly.
Recovery never launches inference or reclaims the receipt. Reboots/remote hosts require explicit
operator reconciliation; elapsed time alone is not proof of a dead worker.

After a terminal outcome, `binder.attach_candidate` accepts `bundle_path`, `receipt`, `scope`,
optional `rejection_reason`, and `mapping_review` with `source_sha256`, the protocol's
`target_sha256`, and a concise `policy` describing the reviewed source/target identity mapping.
This is an operator declaration, not automatic validation of a generator's renumbering or alignment.
The complete bundle still passes source reconstruction, scope, protocol and output-budget checks.
Duplicate bundle hashes are idempotent and retain the first immutable review/rejection annotation.
Collection can resume after its cursor; a late import never changes failed/canceled/interrupted
into completed. Partial candidates remain exploratory and may carry explicit rejection reasons.

The default adapter acquires both `/tmp/dnhacks-gpu.lock` and the earlier
`/tmp/dnhacks-shared-gpu.lock` alias nonblockingly during migration. Both descriptors travel to
children and remain held through process-tree cleanup. A custom operator lock path replaces these
names. Setup errors after claim record interruption; every exit terminates descendants, including
when the generator leader has already exited. Fast exits also receive final byte/trajectory checks.
These are polled caps, so a short-lived output overshoot is detected and rejected, not prevented
by a filesystem quota. No dependency deployment or live design run is implied by lifecycle tests.


## Native scientist action

After `get_skill binder-interface` is delivered, the explorer accepts
`{"action":"binder","args":{"operation":"open_scene","experiment_id":"OWNED_EXPERIMENT",
"args":{"bundle_sha256":"AVAILABLE_HASH"}}}`. The runtime supplies project/run scope and the
operator's journal/store/server configuration. It rejects agent host paths, URLs, executables,
store directories and scope overrides. The experiment must already exist in the current researcher.

Native preparation uses a collected `molecular_structure` hash as `source_ref`; it records immutable
`binder_target`, `binder_epitope` and `binder_protocol` artifacts. Subsequent operations use their
`artifact_sha256` as `target_ref`, `epitope_ref` or `protocol_ref`. Native import inherits source
provenance, so a software illustration cannot silently become a prediction. Evaluation reads the
validated bundle's existing metrics. Comparison rebuilds sources and requires identical full target
residue metadata/coordinates and one experiment scope; it saves a `binder_comparison` record.
Follow-up proposals save `binder_followup` records with an explicit human-review status.

Native `start_design` only queues a durable receipt and returns its actual state, including on retry.
It never starts an executable. The operator must configure and invoke the pinned launch adapter.
`collect_candidates` records real `binder.job` events and publishes each validated stored bundle
once; failure/cancellation and rejection notes remain visible in the owning experiment. The UI
shows these records and job events only at their available cursor, without simulated progress.

Native scene operations use the same immutable service as the CLI. `BINDER_SCENE_BASE_URL`
configures the trusted local workspace (default `http://127.0.0.1:8765`). Capture/pick run off the
async event loop; image review passes actual PNG bytes and records model usage in the research
cost ledger, including usage returned before a failure. These provisional actions do not register
an audited structural method, create statistical results, or promote graph edges.

Provider review failures return a bounded, redacted error and preserve the saved capture;
no observation event is appended. `binder-interface` is explicitly rejected as an audited
`run_experiments` method ID; custom analysis must use `exploratory`.
See the [native capture and review status](binder-review/native-review.md) for actual
browser evidence and the provider-quota limitation on the latest image observation.

### Persistent node workspace

Available binder sources are selected in the owning researcher's persistent left scene, alongside
real activity and experiment findings. Only one source viewer is mounted. The selector and native
capture driver resolve the exact experiment and artifact hash at the current cursor. This is source
selection; a second candidate can share the same canvas through the comparison selector.

Camera transitions use a700ms smooth orbit from the displayed pose, including when replacing a
transition in progress. Pointer/orbit takeover cancels motion immediately; reduced motion is static.
Scene readiness waits for settled motion before capture. Recipe export records the actual camera,
including manual navigation. This presentation motion never moves scientific atom coordinates.

### Paired source and capture contract

A scene revision can bind `comparison_bundle_sha256` and `comparison_selected` to a second collected
candidate in the exact same experiment. Target coordinates, complete residue/atom identity and metric
protocol must match; no unrecorded target fitting is performed. Captures require two equal horizontal
viewports with explicit source hashes, one shared camera and physical scale. A saved-pixel pick returns
both candidate hash and residue ID and rejects an identity from the opposite viewport. Native comparison
rows preserve collected byte hashes rather than replacing them with a canonical-JSON hash.

Two scissored views use one actual camera and orbit controller. Both views fit the union
of the displayed candidates, use the same material legend and preserve target alignment. Picking
changes the inspector and contact table to the selected candidate. A separate accessible table shows
contact/clash trade-offs and Pareto status among these two candidates, without an affinity score.
Rewinding before the second artifact removes its view. The projection selector supports perspective
and orthographic cameras. Orthographic recipes save vertical frustum height in Å and zoom, preserving
constant scale through capture and saved-pixel picking. Changing projection remounts the camera;
orthographic explicit-pose updates are immediate. Perspective pose transitions remain animated.
See the [inspected paired comparison](binder-review/comparison-review.md) for source hashes,
native capture/pick evidence, responsive views and remaining performance limits.
