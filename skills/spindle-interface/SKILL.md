---
name: spindle-interface
description: Run provisional 3D centrosome/filament experiments and inspect their saved geometry through scoped spindle scenes.
---

**One line:** Bounded native spindle mechanics, saved-geometry inspection and image-bearing scene review.
**Category:** exploratory simulation

Use action `spindle` with `{operation, experiment_id, args}`. Project and run scope come from the current researcher; never supply host paths. Read source papers before choosing biological parameters. The current `cytosim-3d-aster-v1` model is uncalibrated and is not the published planar model or a validated PDAC mechanism.

Call `describe_model` with empty args to retrieve all required protocol fields, parameter names, engineering bounds and supported condition fields. It does not supply biological defaults.

Numerical workflow:

1. `prepare_spindle_experiment`: args `{protocol}`. Supply complete source-linked parameters, controls, explicit seeds and prespecified clustering threshold/dwell/sensitivity. Returned `spec_ref` identifies the frozen protocol.
2. `run_spindle_experiment`: fresh experiment_id, args `{protocol,idempotency_key,budget:{wall_seconds,artifact_bytes},title}`. Optional top-level `parent_experiment_id` links a scientific follow-up. Reusing an experiment ID cannot change its numerical specification. Submission returns a durable receipt; it does not imply completion.
3. `status` or `cancel`: args `{receipt}`. Completed native outputs are collected into the owning experiment. Do not silently relaunch interrupted or failed jobs.
4. `analyze_spindle_ensemble`: args `{receipt,analysis_plan_ref}`. The latter is SHA-256 of canonical sorted compact JSON for the frozen analysis plan. Read all conditions and seeds, censoring and threshold sensitivity, including failures. A simulation seed is not a biological sample; never invent p-values or a RESULT to bypass the verification contract.

Visual workflow:

1. State a visible question, then `open_scene` with args `{bundle_sha256,preset:"oblique"}` using a collected filament artifact. It returns `recipe_sha256`.
2. `set_scene_view`: args `{recipe_sha256,view,note}`. Bounded view fields are shot (front/oblique/detail), treatment (luminous/fine), saved run/frame indices, persistent selected pole ID or null, trails boolean, optional comparison run index, and finite camera position/target/lens. A scene change never reruns mechanics. Physical time uses saved samples without interpolation.
3. `capture_scene`: args `{recipe_sha256,viewport:[1600,1000],render_seconds:30}`. Capture uses the actual owning experiment and shader-ready rendered state, yielding immutable PNG and camera/frame metadata.
4. `inspect_scene_capture`: args `{capture_id,question}`. This explicitly delivers the exact PNG bytes to a vision worker and returns its image-linked observation. A pathname, hash or camera description does not mean you saw an image.
5. `record_visual_review`: args `{review_sha256,observed_defects:[...],changes:[...],disposition:"revise"|"accepted"|"incomplete"}`. Requires an image-bearing observation. For defects, revise a recipe, recapture and inspect again before accepting. Keep visible findings separate from measured distances, motor forces and biological outcomes.

Operator setup must provide a pinned native build and reachable local scene server. An unavailable build or capture is an explicit operational failure, never evidence against clustering. Existing rigor and human promotion gates remain in force.
