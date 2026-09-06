# 03 — Living tumor: a cinematic tumor–stroma experiment instrument

Status: implementation authorized and active. Native simulation, artifact collection, scoped agent
tools, tissue theater, action replay and actual image transport are implemented; the165-run source-
grounded sensitivity study and numerical checks completed. Final visual/performance acceptance and
integration are recorded in [the implementation report](../../docs/tumor-stroma.md).
The [shared studio contract](README.md) governs scene recipes, captures and image-bearing review.

## Experience and scientific purpose

Build a beautiful, explorable tissue volume where a scientist can see a metabolic rescue emerge,
remove its proposed cause, and compare what survives. The first scene is a pancreatic tumor spheroid
with surrounding fibroblasts, a nutrient field, and a paired perturbation. It must feel like a polished
scientific instrument from a future laboratory, with a clear focal subject and deliberate composition.
Artistic liberties in lighting, surface detail, camera, palette and transitions are explicitly allowed.
Cell positions, radii, identities, concentrations and outcomes remain tied to their numerical artifacts.
Procedural membranes and decorative fibers are illustrative; they cannot silently become measurements.

The first scientific question is: under which modeled spatial conditions does fibroblast-derived
alanine rescue pancreatic tumor growth, and does suppressing tumor alanine uptake abolish that rescue?
This is a conditional model experiment, not a patient response forecast or reconstructed biopsy.
Hold treatment delivery and other stromal mechanisms outside the first model to keep it identifiable.
Later extensions can test drug penetration, redox rescue and heterogeneous CAF populations separately.

Corpus anchors from `data/corpora/pdac-frozen/MANIFEST.json`:

- Ref 9: pancreatic stellate-cell autophagic alanine secretion motivates the exchange mechanism.
- Ref 18: measured microenvironmental metabolites constrain plausible nutrient regimes.
- Ref 21: selective alanine transporter utilization motivates the perturbation and rescue controls.
- Refs 97–99: CAF heterogeneity and metabolism motivate later model stratification.
- Ref 100: heterotypic 3D culture and stromal redox-associated resistance provide a later validation track.

Read full papers and extracted experimental context before assigning numerical parameter values.
Distinguish measured, fitted, transferred-from-another-model and assumed values in the parameter table.
The frozen literature cutoff is 2026-01-25; later software sources do not extend the scientific corpus.

## Art direction and storyboard

Use a near-black indigo stage, pearlescent tumor membranes, warm amber CAFs, and a luminous cyan
alanine field. Keep one saturated scientific accent at a time. Avoid a rainbow cloud of identical balls.
Cells should have soft rim lighting, subtle uneven membranes and readable internal silhouettes.
Shape cues distinguish CAFs from tumor cells; color is a redundant cue, with a visible legend.
Atmospheric haze and restrained bloom establish depth without obscuring field values or cell boundaries.
Use a narrow editorial type scale, generous negative space and a small floating instrument rail.
The cutaway edge and selected cell receive crisp highlights; the rest recedes through depth and contrast.

1. **Establish:** show the whole spheroid at a three-quarter angle, with the CAF shell offset visibly.
   A scale bar, simulated-time label and quiet `Simulation` badge anchor the otherwise cinematic scene.
2. **Reveal:** a deliberate cross-section motion exposes the core; the alanine field fades into view.
   A short annotation ties the nutrient-rich perimeter to the modeled secretion mechanism.
3. **Intervene:** split the same camera into baseline and uptake-suppressed conditions.
   A synchronized playhead reveals cell-state changes; identical field ranges prevent deceptive contrast.
4. **Investigate:** click a surviving cell and inspect local alanine, lineage, condition and model inputs.
   A neighborhood halo shows the radius used by the actual analysis, in micrometers.
5. **Explain:** save a still or a short looping sequence with the selected measurement and source links.
   The frame should work as an attractive standalone scientific figure with its legend intact.

Default interactions: orbit, zoom, section plane, field opacity, time scrub and paired comparison.
Keep uncommon render controls in a scene inspector. Provide named views: Exterior, Core, Neighborhood.
Disable auto-orbit by default; user-started presentation playback can use a slow authored camera move.
Reduced-motion mode uses cuts and still states. Keyboard controls expose the same selection and timeline.
Mobile opens one condition at a time with a clear switch; desktop supports synchronized side-by-side.
Light mode uses a deliberately composed pale stage and adjusted materials, not an inverted dark render.

## Stack decision

Choose **PhysiCell + BioFVM** for simulation and **custom Three.js through React Three Fiber** for viewing.
PhysiCell supplies cell-based 3D simulation; BioFVM supplies diffusing substrate fields and source/sink terms.
The browser renderer is custom because composition, membrane materials, volume treatment, cutaways and
camera choreography are essential product features. It is not constrained to the existing 3Dmol viewer.
Use instanced geometry, custom shader materials, Data3DTexture fields and a bounded ray-marching pass.
Use Drei selectively for camera controls; keep scene state serializable and independent of JSX instances.
Use a restrained postprocessing chain; bloom must not alter quantitative field interpretation.

Alternatives and decisions:

| Option | Decision |
| --- | --- |
| Existing 3Dmol | Keep for molecular artifacts; tissue cells and scalar volumes need different semantics. |
| vtk.js | Strong volume/data alternative; retain as fallback if custom quantitative slicing fails its spike. |
| Blender/Cycles | Optional later hero export; browser interaction and identical agent/user views come first. |
| Unity/Unreal | Reject for this plan: separate deployment/runtime would complicate the existing web product. |
| CompuCell3D | Revisit if deformable cell geometry becomes the hypothesis; unnecessary for initial exchange model. |
| Handwritten simulation in Three.js | Reject: animation timing must not determine the scientific model. |

Pin reviewed dependency versions during implementation and record them in each reproducibility manifest.
No GPU training or compute-heavy benchmark is part of this plan. Check the local GPU handoff only if
later implementation proposes GPU compute; the initial simulator can use a bounded CPU worker.

## Scientific agent workflow and proposed tool calls

Names below are proposed contracts, not claims about currently available tools.
All tools return immutable IDs, progress/error states and structured results rather than unbounded stdout.

1. `tissue.build_model({question, paper_refs, parameters, geometry, units, controls})`
   validates a versioned model specification and returns `model_id`, provenance and unresolved assumptions.
2. `tissue.simulate({model_id, conditions, seeds, duration_minutes, resource_limits})`
   launches bounded simulation jobs and returns `job_id`; cancellation leaves an explicit incomplete record.
3. `tissue.analyze({artifact_id, endpoints, grouping, contrasts, sensitivity_spec})`
   reports survival/growth, spatial rescue distance, field summaries and parameter sensitivity.
4. `open_scene(experiment_id, preset)` then `capture_scene(scene_id, recipe_revision, views, viewport)`
   invoke the same browser renderer used by people and return PNG image references plus scene metadata.
5. `inspect_scene_capture(image_refs)`
   delivers the actual images to a vision-capable runtime model and records its visible observations.
6. `set_scene_view(scene_id, camera, time, clip, selection, style_patch)` creates a new scene version.
   A scientific model revision uses `tissue.build_model` and reruns simulation; it cannot edit past outcomes.
Use `record_visual_review` for image-grounded findings. Implement image transport at the model/session seam;
verify actual pixel delivery with a real image task, using an explicit vision worker if necessary.

Initial experiment: paired geometries with CAF secretion on/off, tumor uptake normal/suppressed, and
an extracellular-alanine rescue condition. Keep initial cell placement paired across relevant contrasts.
Prespecify endpoints and sweep plausible uncertainty in secretion, uptake and nutrient boundary values.
Use convergence checks and analytical diffusion cases before interpreting patterned survival.
Simulation seeds are computational replicates; individual cells are nested within simulations.
Neither count is a substitute for independent biological samples in the existing verification contract.
Return `analysis_class: simulation_sensitivity`; require a compatible audited method before verifier submission.
Do not fabricate p-values or an `n_units` that makes a mechanistic simulation appear experimentally validated.

## Proposed artifact and API contract

Extend the existing experiment-owned, immutable artifact collection path; retain project/run/experiment scope.
Use `kind: tissue_simulation`, `schema_version: 1`, and a manifest with these required fields:

| Field | Meaning |
| --- | --- |
| `model` | Model-spec hash, engine/version, executable hash, parameter provenance, boundary conditions. |
| `simulation` | Condition, seed, numerical tolerances, time units, completion status, diagnostics. |
| `domain` | Origin, bounds, axis order, right-handed coordinates, length units, field-grid spacing. |
| `frames` | Ordered time index and immutable cell/field chunk references; explicit absent frames. |
| `cells` | Stable IDs, positions, physical radii, type/state codes, optional parent IDs and scalar attributes. |
| `fields` | Name, concentration units, dimensions, dtype, axis layout and finite-value range. |
| `analysis` | Endpoint table references, contrast definitions, grouping and sensitivity report. |
| `provenance` | Paper refs, source hashes, assumed geometry, measured/fitted/assumed parameter labels. |
| `visual_schema` | Supported adapter/schema versions; scene recipes and reviews are separate immutable records referencing this experiment hash. |

Store simulation arrays in chunked binary files with JSON descriptors; cap decoded sizes before allocation.
The browser must not execute serialized model code. Validate shapes, finite values, units and bounds server-side.
Represent cell birth/death explicitly; never interpolate a disappearing cell into an invented survivor.
Browser frame interpolation is labeled visual smoothing; exact-frame mode is the analytical default.
Decorative fibers and surface displacement live in `illustration_layers`; sampling never reads them.
GLB is optional presentation export, not the authoritative representation of fields or cell identities.

Reuse scoped runtime blob delivery for immutable binary payloads, with streaming/range support if required.
Propose `POST /api/runtime/<run>/scene-renders` for bounded render requests and a returned render-job ID.
Expose render completion through existing ordered runtime events, with blob hashes and owning experiment.
Replay reveals simulation/render artifacts only after their recorded collection event, as existing artifacts do.
Separate readable snapshots from mutable scene requests; resolve permissions and containment before serving files.
Store image inspection and revisions as runtime observations tied to the exact image and scene hashes.
Do not add a disconnected demo route; expand the selected experiment into a focused theater view.

## Mandatory visual inspection loops

**Developer loop:** first build one attractive authored fixture before integrating a live simulator.
Capture Exterior, Core and Comparison at 1600×1000 and 1920×1080; also light mode and 390×844 mobile.
Use Playwright screenshots of the rendered browser page, wait for explicit asset/render readiness, and
open every capture with an actual image-viewing tool. Merely writing screenshots does not complete review.
Inspect focal hierarchy, membrane depth, clipping, field legibility, annotation collisions and empty space.
Revise materials/camera/layout, capture again, and compare actual before/after images in at least two passes.
Keep a visual-review note linking capture hashes to concrete observed defects and the final accepted views.
Perform another complete capture-and-view pass after real simulation data replaces the fixture.
If a graphics context is unavailable, record the block; do not accept a black screenshot as a passing render.

**Runtime science-agent loop:** render Exterior, Core and synchronized Comparison for each shortlisted result.
Deliver the PNGs as image input to the science agent; a text URL or numerical render report is insufficient.
Ask whether the proposed spatial effect is visible, whether occlusion hides contradictory regions, and whether
camera, scales or transfer functions exaggerate the difference. Cross-check all apparent effects numerically.
Budget two view revisions initially; remaining critical defects require further work or an incomplete review.
Store the final still with the quantitative summary and visual critique only when review is complete.
If the effect remains invisible, say so and show a diagnostic slice; never tune the simulation for a prettier claim.
If vision input fails, mark `visual_review: unavailable` and keep the result outside the visually reviewed set.
Viewing a beautiful image is quality control and explanation, not independent evidence for the hypothesis.

## Delivery milestones and acceptance gates

1. **Visual vertical slice:** fixture, cinematic materials, cutaway, comparison, accessible controls and screenshots.
   Accept only after the developer has inspected actual images and corrected visible flaws in two passes.
2. **Model adapter:** reproducible small CPU simulation, validated arrays, controls and analytical diffusion tests.
   Accept deterministic replay within documented tolerances and mass-balance/convergence diagnostics.
3. **Artifact integration:** immutable collection, scoped delivery, lazy chunk loading and event-correct replay.
   Test cross-project denial, hash mismatch, oversize arrays, missing chunks and canceled runs.
4. **Agent visual loop:** tools render images, deliver image inputs, record critique and replay exact scene revisions.
   Test that a black/empty frame and failed vision call cannot acquire a visually reviewed status.
5. **Scientific demonstration:** one sourced alanine experiment with uncertainty sweeps and paired visual comparison.
   Accept only with explicit assumptions, numerical endpoints and consistent legends across compared views.

Performance targets to measure on recorded browser/hardware configurations, not promises already achieved:

- Desktop: target 60 fps with 10,000 cells and one 128³ field at 1600×1000; measure p95 ≤16.7 ms.
- Mobile: target 30 fps with ≤2,000 aggregate glyphs and a 64³ field, p95 ≤33 ms. Aggregate by spatial bin and cell type/state; retain counts and encode occupied volume/population explicitly. Label aggregation and show full population totals. Drill-down restores individual IDs; quantitative analysis always uses full arrays. Never silently drop cells to meet a rendering budget.
- First meaningful scene ≤3 s on local delivery for a ≤10 MB initial payload; defer later frames and high detail.
- Keep GPU residency bounded through a three-frame cache; release resources when changing experiments.
- Use instancing, capped pixel ratio, dynamic volume steps and demand rendering when paused.
- Automated screenshot mode freezes time, seed, camera, pixel ratio and quality; disable temporal randomness.

Test field sampling against known voxels, ID picking against source cells and world/axis transforms exactly.
Use behavioral browser tests plus visual snapshots; numeric tests alone cannot accept the artistic result.
Run all repository pre-commit gates, including build, frontend tests/e2e, full Python tests and diff checks.
Use the isolated empty-data server procedure in `docs/frontend.md`; report local missing-data failures explicitly.
Update `ARCHITECTURE.md` and `docs/frontend.md` with the implemented artifact/view behavior in its commit.

## Primary sources and implementation references

- [PhysiCell paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC5841829/): 3D cell-based modeling framework.
- [BioFVM paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC4824128/): substrate transport and cell source/sink terms.
- [PhysiCell official repository](https://github.com/MathCancer/PhysiCell): engine, examples and reproducible version pin.
- [R3F scaling performance](https://r3f.docs.pmnd.rs/advanced/scaling-performance): instancing and demand rendering.
- [Three.js Data3DTexture](https://threejs.org/docs/pages/Data3DTexture.html): browser volume texture primitive.
- [Three.js VolumeShader](https://threejs.org/docs/pages/module-VolumeShader.html): volume rendering starting point.
