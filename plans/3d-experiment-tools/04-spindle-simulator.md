# Centrosome clustering: the spindle observatory

Status: implementation in progress, 2026-09-06. The trajectory viewer and clustering analysis
landed in PR68; the pinned Cytosim CPU worker and archive adapter are implemented.
See [implemented scope and remaining work](../../docs/spindle-simulator.md). Scoped runtime capture/vision review is implemented. Calibration and final broad
visual/performance acceptance are not complete. Native cortical fields and scoped
WebM export are implemented, including an explicit placement correction and measured
render/update timings in the implementation docs.
Follow the [shared studio contract](README.md) for ownership, artifacts, capture and review.
The visual ambition is a luminous kinetic sculpture: a complete spindle suspended in a glasslike
cell, with microtubule fans sweeping through depth and centrosomes moving like small pearl stars.
Artistic liberties are encouraged. Establish a beautiful interactive prototype before scientific integration.

## Research question and corpus grounding

Compare how centrosome number, cortical dynein localization, HSET-like activity and cell geometry
change clustering trajectories and the persistence of bipolar versus multipolar arrangements.
The output is a mechanistic simulation experiment, with numerical trajectories and controls.
A cinematic movie is its explorable presentation; visual beauty is an independent delivery criterion.

The frozen corpus supplies specific starting points, to be read fully before parameter selection:

| Corpus paper | Anchor | Intended role |
|---|---|---|
| 34 | [Amplified centrosomes in PDAC](https://doi.org/10.1080/15384101.2015.1068478) | Disease context; no patient-specific calibration implied |
| 36 | [CEP215–HSET complex](https://doi.org/10.1038/ncomms11005) | Mechanistic hypothesis for centrosome/pole coupling |
| 54 | [KIF24 depletion in PDAC](https://doi.org/10.26508/lsa.202201470) | Perturbation direction to investigate, not a direct force constant |
| 57 | [Cortical dynein and clustering](https://pmc.ncbi.nlm.nih.gov/articles/PMC10208098/) | Explicit simulation and experimental reference |
| 62 | [Kinesins after whole-genome duplication](https://doi.org/10.26508/lsa.202402670) | Heterogeneity and alternative motor hypotheses |

Paper 57's methods describe a **two-dimensional** model with dynamic microtubules and stochastic
motor forces, implemented in MATLAB with GPUs; code is described as available upon request.
Its planar trajectories may appear inside an artistic 3D stage, but remain planar simulation data.
A true 3D implementation requires a new model specification, calibration and independent validation.
Do not imply that compiling a simulator for 3D reproduces or validates that published model.
These details are verified in the local frozen paper text and its linked primary article.

## Art direction and storyboard

Use the shared indigo stage, but make this scene's identity exceptionally fine luminous filaments,
pearl centrosome cores, an iridescent cortex rim and amber motor-enrichment crescents.
The central silhouette should feel sculpted and organic, with disciplined negative space.
Microtubules have bright narrow cores, soft edge light and depth attenuation rather than uniform neon.
Foreground arcs may be thicker than life; a selective cutaway reveals deep spindle bundles.
Chromatin can be a quiet opalescent ribbon sculpture when explicitly illustrative, not simulated DNA.
Give the background almost no decoration. One restrained time rail and a floating outcome card suffice.

| Beat | Composition and motion | Interaction and evidence |
|---|---|---|
| Arrival, 0–3 s | Three-quarter cell silhouette fills about two-thirds of the stage; rim resolves into a cutaway | Show simulation/illustration badge; no automatic scientific conclusion |
| Reveal, 3–7 s | Several centrosome stars emerge; broad filament fans establish foreground and background | Pick a centrosome to isolate its aster and persistent ID |
| Intervention, 7–11 s | An amber cortical crescent illuminates; camera eases toward the engaged aster | Show the actual dynein distribution and intervention time |
| Motion, 11–18 s | Pole paths draw thin fading arcs as clustering succeeds, stalls or reverses | Time remapping is disclosed; nearest-pole distances track physical coordinates |
| Comparison, 18–24 s | Two equally sized cells share camera and physical clock | Control and perturbation use matched initial conditions and visible seed IDs |
| Explanation, on demand | Freeze and open one bundle into a spacious detail composition | Show measured forces only when exported; otherwise use labeled mechanism illustration |
| Outcome, user-held | Maintain an elegant still showing the observed final pole arrangement | Ensemble distribution sits beside the chosen trajectory, including failures |

These seconds are a presentation script, not experimental timing or a promise of bipolarity.
Preserve a dramatic, equally finished multipolar ending; never steer motion to fit the storyboard.
A reduced-motion version uses the arrival still, manual timeline stepping and instantaneous view changes.
Mobile uses one tall cell stage with a control/perturbation toggle that preserves camera and time.

## Simulation and rendering choices

Recommend **Cytosim for the new 3D filament/motor model**, with a Python job and export adapter.
Its authors describe flexible filaments, molecular motors and crosslinkers plus other geometric objects;
this is a natural basis for exportable aster mechanics, not a ready-made calibrated PDAC spindle.
Use the [authors' workflow](https://arxiv.org/abs/2205.13852) and
[upstream repository](https://gitlab.com/f-nedelec/cytosim) to pin a build and inspect supported objects.
Specify asters/centrosome bodies, dynamic instability, motor binding/unbinding, confinement and drag.
Validate the chosen release's 3D build and required interaction semantics in a tiny CPU pilot.
Add a custom interaction only after a minimal test shows the stock model cannot express it.

Maintain a separate paper-57 reproduction adapter if source code becomes available or methods permit
an independently documented reimplementation. Label a reimplementation as such and compare its outputs.
Do not delay visual prototyping on code acquisition; deterministic illustrative fixtures are sufficient.
A reduced-order centrosome force model can support cheap exploratory sweeps, with its approximation
explicit and its outputs distinct from filament-resolved Cytosim results. It cannot silently replace them.

| Choice | Why / tradeoff |
|---|---|
| Cytosim + exported filament frames | Mechanics supplies curved geometry and persistent biological entities; calibration remains substantial work |
| Custom reduced-order Python model | Fast hypothesis screening; lacks resolved filament mechanics and needs separate validation |
| Published planar model | Best route to a faithful paper-57 reproduction; does not establish true 3D behavior |
| Browser particle/physics engine | Useful for labeled visual fixtures; arbitrary spring dynamics are not accepted spindle science |
| React Three Fiber + Three.js | Custom filament materials, picking, choreography and React integration without a molecular viewer's constraints |
| 3Dmol | Retain for existing atomic structures; do not make its molecular primitives the spindle design ceiling |
| Blender export | Optional cinematic lighting/film output from the same trajectory; interactive browser quality still must pass |

Use instanced filament segments or GPU-buffered ribbons with stable IDs and smooth joins; high quality
may use short tubular sections. Batch geometry and update typed buffers rather than thousands of React nodes.
[Three.js instancing](https://threejs.org/docs/pages/InstancedMesh.html) reduces repeated-geometry draw calls.
Aster cores and cortical markers use separate pickable layers; pick handles remain usable at mobile scale.
Start the art spike with the shared renderer; evaluate WebGPU/TSL for dense filament shading and post effects.
[Three.js documents](https://threejs.org/manual/en/webgpurenderer) separate WebGPU node materials and
postprocessing from WebGL ShaderMaterial/EffectComposer. Choose and pin a coherent tested pipeline.
Depth of field belongs to cinematic mode; scientific comparison keeps both cells and pole labels sharp.

## Scientific experiment and artifact contract

All operations below are proposed additions, not claims about today's registered tools.
Keep the scene inside the selected experiment in Investigations, following
[architecture](../../ARCHITECTURE.md) and the [frontend contract](../../docs/frontend.md).
Extend collection beyond PDB/mmCIF intentionally; immutable filament bundles are a new artifact family.

1. `prepare_spindle_experiment(model_id, parameters, controls, seeds, analysis_plan)` validates units,
   source-linked parameter provenance, model dimensionality and a bounded resource estimate.
2. `run_spindle_experiment(spec_ref, budget)` starts a cancellable job and returns a receipt; progress
   records accepted timesteps/frames and failures. No front-end animation timer drives the solver.
3. `analyze_spindle_ensemble(job_ref, analysis_plan_ref)` produces prespecified clustering metrics,
   time-to-cluster with censoring, dwell time, pole count, pairwise distances and uncertainty summaries.
4. `open_scene(experiment_id, preset='spindle-observatory')` binds the collected trajectory and recipe.
5. `set_scene_view`, `capture_scene`, `inspect_scene_capture` and `record_visual_review` use the shared
   studio schema, with camera/time/selection and bounded visual parameters rather than arbitrary code.
6. A numerical hypothesis change creates a linked experiment revision through steps 1–3; a visual edit
   changes only the scene recipe. Submission to verification uses the existing rigor and human gate.

Store a versioned manifest with project/run/experiment IDs, source references, solver commit/build,
configuration hash, dimensionality, units (µm, s, pN where applicable), seed, timestep and sampling interval.
Export chunked binary position buffers plus filament offsets, birth/death times, stable entity IDs,
centrosome transforms, cortex geometry and motor/force fields actually computed by the model.
Keep raw solver outputs and a lossless scientific trajectory; downsample only a separate display stream.
Include checksums and chunk bounds, metrics JSON/CSV, calibration report, analysis code and failed-run receipts.
The scene recipe stores coordinate transform, filament radius exaggeration, illustrative context, trails,
color semantics, clipping, exposure, camera keyframes, selected seed and physical-to-presentation time mapping.
Captures and image-grounded reviews reference exact experiment, adapter and recipe hashes.
Replay exposes a bundle only after its owning artifact event; missing chunks yield explicit loading/errors.

## Calibration and limits that preserve styling freedom

Start with geometry and units tests, isolated motor/filament behavior and timestep convergence.
Define cluster membership, distance threshold and required dwell time before inspecting perturbation results;
report threshold sensitivity and distinguish two poles from all centrosomes collapsing into one cluster.
Paper 57's proximity definition is a reference choice, not a universal 3D clustering classifier.
Calibrate identifiable parameters against designated training observations, then assess held-out conditions.
Keep two-centrosome controls, no-cortical-dynein controls and altered-localization controls where meaningful.
Use matched seeds/initial states for comparisons and enough independent simulation replicates for the
prespecified analysis; frames and individual filaments are not independent experimental replicates.
Simulation seeds are not independent biological samples. Keep outputs exploratory unless a compatible
audited simulation method is registered; never invent p-values or biological n_units to enter the current gate.
Report numerical uncertainty separately from biological uncertainty and investigate model sensitivity.
A mechanistic motor-activity reduction is not automatically a drug concentration, gene knockdown or efficacy.
PDAC transfer, chromosome segregation accuracy and cell viability remain unvalidated unless modeled and tested.
None of these limits restrict color, light, expressive filament width, illustrative cortex or camera drama.
A quiet provenance badge and optional detail panel distinguish geometry from presentation without dominating it.

## Developer render → inspect → revise loop

First build deterministic visual fixtures for bipolar, crowded multipolar and transient clustering scenes.
Use them to compare at least two compositions and filament treatments in the actual application.
Playwright opens the selected fixture/experiment and waits on an explicit scene-ready promise covering
loaded buffers, shader compilation and a rendered frame. Freeze simulation playback, shader clocks,
trail evolution, camera easing and all seeded decorative effects; CSS animation disabling is insufficient.
Save full UI and canvas PNGs at front, oblique and aster-detail views, plus start/middle/end contact sheets.
Open every review set through `view_image`; deliver its returned image content to the coding agent.
A pathname, artifact hash, browser console log or screenshot dimensions do not count as seeing the image.
Review a short movie for disappearing filaments, camera jumps, pole-ID swaps and strobing bloom.
Record concrete defects, for example “the amber crescent clips through the foreground rim” or
“the rear centrosome vanishes behind bloom”; revise shaders, layering, camera or labels accordingly.
Recapture the same views and times, open the new images and compare with the previous captures.
Require an inspected draft, an inspected revision and an inspected final pass; unresolved major defects
keep the visual milestone incomplete even if browser tests pass. Save the accepted visual decision log.

## Runtime research agent render → inspect → revise loop

The agent states the visual question, such as whether a third pole is visibly distinct in both conditions.
It opens the actual computed experiment, sets a deterministic comparison recipe, then captures images.
`inspect_scene_capture(image_refs)` must resolve scoped immutable PNG bytes and attach image-bearing
content to a vision-capable model session through the tested SDK transport. Text containing paths is insufficient.
If the active reasoning session cannot consume pixels, an explicit vision worker receives the images and
returns image-grounded findings linked to capture hashes; the main agent must not invent its own viewing receipt.
The reviewer reports visible occlusion, ambiguous pole identities, color/label failures and comparison imbalance.
The agent may revise clip planes, cameras, trail length, filament opacity, exposure and label placement;
it recaptures, receives the new pixels and records whether each visible defect was resolved.
Separately, the agent reads ensemble metrics, proposes a scientific follow-up and starts a linked run.
A pleasing screenshot never supplies a missing measurement or establishes a mechanistic effect.

## Determinism, visual acceptance and delivery

Persist camera position/quaternion, target, projection, FOV/orthographic span, clipping and viewport/DPR.
Persist physical time, exact sampled frame indices, interpolation rule, trail history and presentation clock.
Use fixed asset/renderer/browser versions and stable effect seeds; prevent camera reframing as poles move.
Compare runs on a common physical timeline; any event-aligned comparison explicitly records its offset.
Interpolate only surviving entities and never smooth across births/deaths or invent a completed trajectory.

Accept only after inspected 1600×1000, 1920×1080 and 390×844 captures plus reduced-motion and comparison views.
The complete cell silhouette and every pole must remain discoverable; selected pole identity survives rotation.
Near/far filaments show depth without turning the center into a white knot; the cortex reads as a curved shell.
Control and perturbation have equal scale/exposure; intervention is encoded by shape/label as well as color.
Labels do not cover pole cores; timeline, picking and numerical readouts match the underlying saved coordinates.
Target 60 fps desktop and 30 fps reference mobile/laptop after warmup; record hardware and p95 frame times.
Tune filament LOD, display sampling and glow while preserving pole count, selection and comparison composition.

Milestones: (1) inspected art spike and stack choice; (2) immutable adapters and pixel-delivery proof;
(3) small validated mechanics cases and an explicitly provisional 3D ensemble; (4) calibrated/held-out
assessment plus agent science and visual loops; (5) performance/accessibility pass and cinematic export.
Tests cover dimensionality/units, deterministic solver configuration, chunk corruption/ownership, entity
birth/death interpolation, convergence, cluster edge cases and correct metrics on known trajectories.
Browser tests cover real pixel delivery, readiness/freeze, camera replay, picking, comparison time sync,
mobile controls, context-loss recovery and missing artifacts. Vision critique supplies aesthetic acceptance.
Run all repository commit gates during implementation; this plan makes no claim those future tests exist.
