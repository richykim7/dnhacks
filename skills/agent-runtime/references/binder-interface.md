# Exploratory binder interfaces

Use method_id `exploratory`; binder geometry is not a registered audited statistical method.
Read the source evidence and explicitly identify construct, assembly and unresolved context.
Use `python -m dnhacksbio.binder` with a JSON action request or the package's Python functions.
Prepare the target with exact source hash and residue identities before defining an interface.
An imported candidate carries project/run/experiment scope and reference/prediction/illustration
provenance. Declare portable bundles in the output artifact manifest as kind `binder_bundle`.
Do not print fabricated RESULT statistics or submit structural confidence as `p_null`/`robust`.

Distances use immutable coordinates in Å; surface/camera scaling and exploded views never change
analytical inputs. The default is interchain heavy-atom pairs within 4.5 Å, with 4.0/5.0 sensitivity.
Total buried SASA is SASA(target)+SASA(binder)-SASA(complex), no division by two, 1.4 Å probe.
Confidence, binding affinity, selectivity and PDAC efficacy are distinct and missing unless measured.
An apparent contact in an image must be checked against the coordinate-derived table.

Design starts return durable receipts; collection is cursor-based. A failed or canceled trajectory
is not a negative biological result. Preserve partial output/rejection reasons. Deployment must
pin code, actual environment and weight bytes and use bounded compute under the common GPU lock.
Never order molecules or execute wet-lab follow-up. Assay proposals are for human review.
The runner exposes the assigned identity in `DNHACKS_EXPERIMENT_SCOPE` as JSON; use it as the
bundle scope when generating an artifact inside the owning experiment.


For visual reasoning, use the trusted local scene CLI after the collector publishes the bundle.
Every request carries `journal_directory` and `scope`; capture/pick additionally carry the local
workspace `base_url`. The request shape is:
```json
{"action":"binder.open_scene","journal_directory":"/workspace/data/processed",
 "scope":{"project_id":"PROJECT","run_id":"RUN","experiment_id":"EXPERIMENT"},
 "args":{"bundle_sha256":"COLLECTED_BUNDLE_HASH","preset":"interface-close"}}
```
Use the returned `recipe_sha256` for `binder.capture_scene`; its args may include
`viewport:[1600,1000]` and `render_seconds:60`. Pass the returned `capture_id` and a concrete
visual `question` to `binder.inspect_scene_capture`. This operation sends the actual saved PNG.
If the seam is hidden, call `binder.set_scene_view` with the latest recipe hash,
`view:{"preset":"reverse"}` and a concise `note`, then capture and inspect again.
Use `binder.pick` with capture ID, matching recipe hash and image pixel `x,y` to identify a residue.
Check suspected contacts against the exact coordinate table before reporting a scientific finding.
Supported view fields are preset, pearl/copper style, exact selected residue ID and explicit perspective
camera. Unsupported camera modes fail explicitly. Scene tools do not mutate source coordinates.
The UI records these agent actions with adjustable replay speed; a user's independent exploration
does not replace your saved recipe. Do not interpret replay duration as physical simulation time.
