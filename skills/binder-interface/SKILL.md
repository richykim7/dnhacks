---
name: binder-interface
description: Prepare scoped binder targets and epitopes, queue bounded design receipts, compare saved interfaces and inspect actual scene images.
---

**One line:** Source-backed exploratory binder geometry, durable design receipts and image-bearing interface inspection.
**Category:** exploratory structural design

Use action `binder` with `{operation,experiment_id,args}` after this guide is delivered. Project and
run identity come from the current researcher; the experiment must already exist in that run.
Create the owning experiment using the existing `exploratory` experiment method and collect its
source PDB/mmCIF as a `molecular_structure` artifact. Never supply host paths, executables, URLs,
store directories or run/project overrides to the native action. Missing artifacts stay unavailable.

1. `prepare_target`: args `{source_ref,chains,source_evidence,construct_policy}`. `source_ref` is the
   collected molecular artifact SHA. Evidence rows contain exact DOI, short quote and biological
   context. Review assembly, extracellular construct, missing residues, glycans and membrane context
   before selecting a patch. The current helper trims chains with an identity transform; it does not
   expand assemblies or prove accessibility. Return includes target `artifact_sha256` and data.
2. `define_interface`: args `{target_ref,selected,excluded,competition}`. Use exact residue IDs from
   target data, including author/label identities and insertion code. Return is an immutable epitope ref.
3. `plan_design`: args `{target_ref,epitope_ref,lengths,seeds:[],candidate_cap,gpu_seconds,trajectory_cap,
   artifact_bytes,environment_sha256,weights_sha256,filters_sha256,advanced_sha256}`. Obtain actual
   operator dependency hashes; do not invent them. Pinned BindCraft chooses seeds internally.
   Unsupported residue notation or budgets fail. Planning reports an unmeasured resource estimate.
4. `start_design`: args `{protocol_ref,idempotency_key}` returns the actual receipt state. It queues
   work but **does not launch inference**. A separately configured operator adapter must verify
   deployment eligibility, dependency bytes and GPU leases before execution. Do not claim a running
   job from a queued receipt. Repeated starts reuse the receipt without changing terminal outcomes.
5. `collect_candidates`: args `{receipt,after:0}`. Preserve the returned cursor. Native collection
   records real job events and publishes validated candidate blobs once, including rejected/partial
   candidates. `cancel` and `recover` take `{receipt}`; recovery requires a dead local process identity.
   An operator attaches reviewed terminal output through the documented CLI; no silent renumbering.
6. `import_candidate`: for a saved complete complex, args `{source_ref,target_chains,binder_chains,
   candidate_id,source_evidence}` plus optional `surface_options` and `protocol_ref`. Source provenance
   is inherited, so an illustration stays illustrative. Return includes collected `bundle_sha256`.
7. `evaluate_interface`: args `{bundle_sha256}` returns immutable coordinate metrics and missingness.
   `compare`: args `{bundle_sha256s:[...]}` requires 2–8 distinct bundles from this exact experiment,
   identical target coordinates/residue metadata and metric protocol. It saves an exploratory Pareto
   table with contacts/clashes as separate axes; it is not an affinity ranking.
8. `propose_followup`: args `{bundle_sha256s,question,evidence}` saves a human-reviewable assay/control
   proposal. No molecules are ordered and no wet-lab action is performed.

Use `open_scene`, `set_scene_view`, `capture_scene`, `inspect_scene_capture` and `pick` with the
argument shapes in the [full interface reference](../agent-runtime/references/binder-interface.md).
For native actions, omit the CLI's journal directory, scope and base URL: the runtime supplies them.
Capture saves actual PNG bytes and camera metadata. Image inspection sends that PNG to a vision
worker; a hash or file path is not image perception. If the seam is hidden, capture and inspect the
reverse or contact cutaway, then verify any concern against the exact coordinate table. The default
scene server is operator-configured by `BINDER_SCENE_BASE_URL`; an unavailable server is an
operational failure. Bounded image review never changes scientific metrics or source coordinates.

This is a provisional action guide, not a registered audited structural method. Use `exploratory`
for the parent experiment. Never fabricate RESULT statistics, binding affinity, confidence fields,
PDAC efficacy, `p_null` or `robust=true`. Search repeats are not independent biological replicates.
