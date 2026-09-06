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
`binder.collect_candidates`, `binder.cancel`, `binder.compare`, `binder.propose_followup`.
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

The workbench renders instanced atomic envelopes with Three.js r180 / R3F 9.3 / Drei 10.7.
It supports pearl/cyan and bronze/violet studies, physical/exploded/contact-only opposing views,
exact picking, accessible contact tables, camera preservation during inspector selection and
scene/bundle export. Exploded offsets and reduced cutaway sphere radii are presentation only.
Rendering is demand driven, with no autonomous motion in reduced-motion mode.
The development-only `?sceneReview=1` bridge exposes apply, ready, inspect, pick and capture.
Readiness waits for fonts, shader compilation and settled scene renders. The bridge is excluded
from production and is not by itself a runtime vision transport.

The browser review fixture is test-only (`frontend/e2e/binder-fixture.json`). Run
`BINDER_REVIEW_DIR=/tmp/binder-review PLAYWRIGHT_BASE_URL=http://127.0.0.1:5192 npm --prefix frontend run e2e -- binder.spec.ts`.
The test saves PNGs and camera/visibility metadata for deterministic presets. Development review
records distinguish measured raycast visibility from qualitative image inspection. Full surfaces,
ribbon meshes, actual second-candidate synchronized rendering and WebGPU visual comparison remain
separate acceptance work; the `candidate-compare` preset reports the missing second candidate.
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
scoped capture-tool orchestration and replay still need their separate integration.
