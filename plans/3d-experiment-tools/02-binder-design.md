# Binder and interface design: the Interface Foundry

Status: proposed implementation plan; no design pipeline, renderer migration, or compute run is implemented by this document.
Priority: make binder discovery a beautiful, spatial, futuristic experience whose images the developing agent actually inspects and improves.
The scientific deliverable is a reproducible candidate complex and an explicit interface assessment, with enough uncertainty and provenance to decide the next experiment.
The visual deliverable is an art-directed molecular workbench that feels like examining an extraordinary physical specimen.
Use the shared [scene/vision contract](README.md) for immutable experiment, scene-recipe and visual-review records; details below specialize it for binders.

## 1. Fit to the PDAC investigation

The frozen local corpus contains 100 papers, with a publication cutoff of 2026-01-25; it is a curated historical demonstration corpus.
Its manifest describes PDAC survival across division machinery, metabolism, stress and tumor–stromal signaling; cross-model mechanistic transfer needs checking.
A useful opening hypothesis is whether an accessible integrin interface implicated in tumor–matrix signaling can support a designed competitive binder.
Manifest paper 24 concerns β1-integrin-associated resistance to MEK inhibition; paper 26 concerns collagen I homotrimers and α3β1 integrin; paper 27 concerns purinergic GPCR–integrin interactions.
These are literature anchors for target review, not proof of a tractable epitope, available target structure, therapeutic selectivity, or successful inhibition.
Record their exact DOI, source quote and biological context when the experiment is created; manifest titles alone are insufficient mechanistic evidence.
Begin with one reviewed extracellular target construct and a small, defensible epitope; choose the actual structure only after assembly, residue and accessibility checks.
An intracellular KRAS binder is an alternative investigation with distinct delivery and allele-specificity questions, not a silent substitute for the extracellular scenario.
Deliver design candidates and assay hypotheses; never present an attractive predicted complex as demonstrated PDAC efficacy.

Existing behavior comes from [ARCHITECTURE.md](../../ARCHITECTURE.md) and [docs/frontend.md](../../docs/frontend.md): experiment-scoped validated PDB/mmCIF artifacts rendered by 3Dmol, immutable runtime blobs, ordered replay and human promotion.
This plan proposes new experiment tools and a custom rendering surface inside the owning experiment, retaining project/run scope and evidence lineage.
No independent Structures route is required. Existing artifacts remain readable while the new scene renderer is introduced behind an explicit artifact capability.
The experiment runtime replacement is still unspecified; this plan does not convert the old Docker implementation into a new architectural requirement.

## 2. Art direction: a luminous interface under inspection

The opening composition is a large suspended target in smoked pearl, with a compact electric-cyan binder emerging along one edge and a restrained coral seam marking the contact patch.
Use a deep ink environment, soft architectural light bars, a thin cool rim and a dark reflective plinth suggested beneath the specimen; the plinth is illustrative scenery.
Surfaces should feel sculptural and slightly translucent at the silhouette, while the interface remains sharp enough to read. Avoid uniform glass that hides depth and chains.
Keep one dominant object, generous negative space and a small number of precise labels; motion and lighting should guide attention toward the binding surface.
Allow dramatic materials, saturated alternate palettes, exploded compositions, cutaways, ribbons, molecular sculptures and abstract transitions when they improve the design.
The initial palette is an art direction to test, not a permanent restriction: compare at least two substantially different material/lighting treatments before settling.
Use sparse bloom on highlights, soft contact shadowing and a clear silhouette; avoid screen-wide fog, excessive transparency and glowing atoms that erase interface topology.
A quiet sequence rail anchors residue selections below the scene; the right inspector changes from target context to exact selected contact without turning the whole screen into a dashboard.
Candidate comparison becomes two specimens on the same virtual stage with synchronized cameras, not a grid of tiny unrelated molecular thumbnails.
Uncertainty can appear as stippled peripheral surface coverage or optional soft envelope geometry; a legend must connect the encoding to a supplied field, and missing confidence gets no fabricated texture.

### Storyboard and spatial transitions

| Beat | User sees and does | Scientific state represented |
| --- | --- | --- |
| Establish | Slow optional three-quarter reveal; target silhouette, epitope glow, one sentence of rationale | Actual imported target; target provenance and unresolved regions available |
| Choose patch | Brush residues on a cutaway surface; sequence rail follows; rotate behind the target | Exact chain/residue IDs and explicit permitted/excluded regions |
| Launch design | Epitope remains on stage; candidate tiles arrive with real job events | Queued/running/failed/completed events, never simulated compute progress |
| Inspect candidate | Binder appears at its predicted pose; one click flies into interface close-up | Saved candidate coordinates and supplied confidence fields |
| Understand contacts | Surface peels away; contact arcs and residue labels resolve locally | Computed contacts with distances and declared definitions |
| Compare | Two candidates rotate together; differences illuminate without changing geometry | Same target alignment and metric definitions, missing scores explicit |
| Decide next step | Stable hero composition with concise strengths, weaknesses and export controls | Candidate shortlist, controls and proposed follow-up, not accepted biological truth |

A presentation-only arrival or exploded-view animation may interpolate between poses; label its timeline as illustrative and offer a direct jump to scientific coordinates.
Optimization snapshots, if actually saved, receive their own iteration scrubber. They are search history, not physical time or a binding trajectory.

## 3. Choose the stack for the image we want

Use a custom Three.js scene composed with React Three Fiber and Drei for interaction, cameras and React integration. R3F is a React renderer for Three.js, so bespoke scene composition is a natural fit. [R3F documentation](https://r3f.docs.pmnd.rs/getting-started/introduction), [Drei documentation](https://drei.docs.pmnd.rs/)
Build atom/bond instancing, ribbon meshes, surface meshes and residue picking around an explicit parsed molecular representation; do not let a decorative GLB become the source of residue identity.
Prototype Three.js WebGPURenderer/TSL lighting and materials against a WebGL2 composition before choosing the production path; WebGPU has its own material/postprocessing constraints and fallback behavior. [Three.js renderer guide](https://threejs.org/manual/en/webgpurenderer)
Choose the winner through inspected screenshots and interaction measurements on target hardware; the first milestone should demonstrate the interface close-up and the hero view, not merely a spinning protein.
Use conventional WebGL2 rendering if it reaches the intended quality more reliably; this is an implementation fallback, not permission to dilute the art direction.
Precompute expensive molecular surfaces on the analysis worker and simplify with a measured deviation bound; browser workers parse and prepare chunks while the main thread handles interaction.
Use Blender/Cycles optionally for art-direction studies and high-resolution export when offline lighting meaningfully improves the image; it is not a runtime browser dependency. [Blender rendering](https://www.blender.org/features/rendering/)

For design, implement an adapter around BindCraft first: it combines structure-based design, sequence optimization and evaluation in one documented pipeline. Pin its commit, weights, settings and dependency environment. [BindCraft repository](https://github.com/martinpacesa/BindCraft)
Use RFdiffusion followed by ProteinMPNN and separately recorded complex reprediction as the alternative when backbone conditioning or design-stage control is more useful. [RFdiffusion repository](https://github.com/RosettaCommons/RFdiffusion), [ProteinMPNN repository](https://github.com/dauparas/ProteinMPNN)
Do not benchmark every available generator before producing the visual workbench; start with a small imported candidate bundle, then attach real job execution.
The design engine and renderer are deliberately independent: any engine emitting the candidate artifact contract can use the same high-quality stage.
BindCraft recommends substantial GPU memory and warns that difficult targets may require many trajectories; size and budget are measured by a small authorized pilot, not guessed from a target name. [BindCraft requirements](https://github.com/martinpacesa/BindCraft)

## 4. Scientist-agent experiment tools, all proposed

Tools return validated structured data plus durable artifact references; long jobs return a receipt and publish immutable milestones rather than keeping a tool call open.
A method guide and version-pinned instruction delivery must be registered before a new method can submit audited results under the existing engine contract.

| Proposed tool | Required input | Output and boundary |
| --- | --- | --- |
| `binder.prepare_target` | Structure artifact hash, assembly/chains, sequence mapping, source evidence, construct policy | Validated target bundle; missing residues, alternate conformers and assumptions; no guessed atoms |
| `binder.define_interface` | Target hash, selected residue IDs, excluded regions, intended competition context | Versioned epitope specification, accessible-area calculation if supported, target-context warnings |
| `binder.plan_design` | Target/epitope hashes, engine preset, lengths, seeds, candidate cap, resource budget | Resolved immutable protocol and resource estimate; unsupported settings rejected |
| `binder.start_design` | Protocol hash, idempotency key, run/experiment scope | Durable receipt and job state; cancellation and restart recovery are explicit |
| `binder.collect_candidates` | Receipt, event cursor | Newly completed candidate bundles; partial and rejected designs retain reasons |
| `binder.evaluate_interface` | Candidate hashes, metric protocol, context structures | Contact table, buried-area convention, steric checks, supplied prediction confidence and failure notes |
| `binder.compare` | Candidate set, same evaluation protocol, target alignment policy | Pareto table and scene comparison spec; no unsupported composite affinity score |
| `binder.propose_followup` | Candidate set, evidence and declared question | Human-reviewable assay/design-of-controls document; does not order molecules or run wet-lab work |

Cap target size, design trajectories, GPU wall time, simultaneous jobs and artifact bytes in the protocol; record resource exhaustion separately from scientific failure.
Reject invalid residue selections before launch; preserve author numbering, insertion codes, label numbering and chain aliases through target trimming.
Evaluate proposed complexes in their biological assembly where available: a patch exposed in a cropped fragment may face another chain, membrane or unresolved glycan in context.
If the context is absent, return “context unavailable” and show that scope in the inspector; a membrane plane added for orientation is illustrative unless its placement has a source.

## 5. Artifact and scientific output contract

Proposed `binder_bundle.v1` contains `manifest.json`, target and candidate mmCIF, binder FASTA, `residue_map.json`, `interface_metrics.json`, `contacts.parquet`, `protocol.json`, source/weight hashes and optional surface meshes.
Every blob is content-addressed, belongs to project/run/node/experiment, and declares reference/prediction/derived/illustration provenance; collection reuses current immutable artifact validation boundaries.
`manifest.json` includes producer/version, parent artifacts, original structure source, assembly, crop transform, seed, method version, timestamps and validation status.
Confidence fields state their producer, definition and units; predicted aligned error and model confidence remain distinct from affinity, specificity and experimental success.
Contact rows identify both exact residues and participating atoms, distance in Å, contact rule/version and candidate ID; interaction categories require their own geometry rule.
Define a simple contact fixture as any interchain heavy-atom pair within 4.5 Å, with sensitivity views at 4.0 and 5.0 Å; these are proposed analysis settings, not universal binding criteria.
Report buried solvent-accessible area with the probe radius and formula: `SASA(target) + SASA(binder) - SASA(complex)` is total buried area; state explicitly if dividing by two.
Compute on immutable physical coordinates in Å. Camera matrices, scene scaling, exploded offsets, glow and artist-authored geometry live in `scene_recipe.json` and do not change analytical inputs.
Residue picking through a simplified surface resolves via an explicit atom/residue map; surface approximation error and clipping settings travel with exports.
Provide raw metrics, missingness and rejection reasons; aggregate rankings require a predeclared scoring recipe and must retain the component values.
Design seeds are engineering repeats, not independent patient or biological units. Do not manufacture `p_null` or `robust=true` to force these outputs through the existing statistical result schema.
Until a compatible registered structural method and verification contract are approved and implemented, keep these as exploratory artifacts with no statistical verdict or master-graph promotion.
For a later benchmark, predeclare target-family holdouts, positive and matched negative complexes, success criteria and independent units before tuning thresholds; account for correlated candidate sequences.
Wet-lab binding/competition/selectivity and PDAC functional results would be separate experiments linked back to the design, with their own controls and independent-unit analysis.

## 6. The developing agent must render, look, critique and revise

The implementation task is incomplete if the agent writes scene code and reports success without seeing screenshots of the actual browser result.
Start with a small reproducible structural fixture carrying correct metadata; mark any purely illustrative demo binder in the fixture and UI as such.
Use a licensed or internally generated fixture appropriate for redistribution; the corpus's local copyrighted figures are reference evidence, not public scene textures.
Create deterministic presets: `hero`, `epitope`, `interface-close`, `exploded`, `candidate-compare`, and `small-screen`.
Each preset stores position, target, quaternion/up, perspective or orthographic projection, FOV/zoom, near/far planes, viewport, DPR, clipping planes, selected residues and fixed animation time.
The shared proposed test-only `window.sceneReview` bridge exposes `apply` and `ready`; the binder adapter supplies fixture loading, camera presets, selection and state inspection.
`ready` waits for meshes, fonts, lighting/environment assets, shader compilation and postprocessing settling; it must not resolve merely because the page is idle.
Use Playwright to set a known viewport, apply the preset, freeze motion, await scene readiness and capture both the scene element and full page. [Playwright screenshots](https://playwright.dev/docs/screenshots)
For example: `await page.locator('[data-testid="binder-stage"]').screenshot({ path: '/tmp/binder-interface-r01.png' })` after the readiness promise resolves.
Then invoke the available image-view tool on that exact saved PNG (`view_image` in this environment); log the viewed artifact hash and concrete observations.
Inspect full-page composition and a native-resolution crop; a thumbnail alone cannot reveal residue-label collisions, transparency errors or a muddy seam.
Evaluate: focal hierarchy, silhouette, depth, chain separation, interface legibility, material quality, typography, annotation occlusion and visual consistency between views.
Record a concise revision row: screenshot hash, camera preset, observed defect, chosen design change, replacement screenshot hash and outcome.
Example intended record: “Interface disappears behind the target rim; move key light 25°, lower target transmission, shift camera 15°; inspected r02 restores seam visibility.” This is an example, not a claimed completed review.
Run at least two screenshot–inspection–revision cycles on the hero and close-up views, and one comparative review of two art directions, before selecting a baseline.
Repeat after changes to camera fitting, material, picking, overlays or responsive layout; do not accept a passing pixel test as proof that a new composition looks good.
Preserve representative before/after images and short public design critiques as review artifacts, without storing private reasoning.
If browser rendering or image inspection is unavailable, report visual acceptance as blocked rather than guessing from code; continue independent scientific-contract work.

### Visual acceptance criteria and proposed performance targets

- Hero at shared desktop 1600×1000 and presentation 1920×1080 sizes has a readable target silhouette, a distinct binder, visible contact region and no clipped specimen or critical label.
- Interface close-up exposes at least 90% of the selected contact residues across its primary view and one opposite-side view, using residue visibility metadata plus image inspection.
- Candidate comparisons share physical scale, target alignment and legend ranges; an explicit independent-camera option may depart from these for exploration.
- Labels remain readable at 100% zoom; no critical label collisions in recorded presets; text/controls meet WCAG contrast and keyboard criteria.
- At 390×844, the scene and selected-contact inspector remain usable without horizontal page scrolling; inspector expansion may reduce scene height deliberately.
- Reduced-motion mode freezes presentation motion and camera transitions; a static scene preserves meaning and all numeric data remains available in accessible DOM tables.
- Proposed measured budget on declared reference hardware: p95 interactive frame time ≤33 ms for the agreed candidate fixture and ≤100 ms picking response after load.
- Report fixture atom count, mesh triangles, GPU/browser/renderer, DPR and peak memory with measurements; reduce decoration/mesh LOD before degrading contact visibility.
- Screenshot regressions run with pinned browser/renderer/font assets and modest GPU-aware tolerances; human/agent image critique remains mandatory for aesthetic acceptance.

## 7. Runtime scientist-agent vision

The research agent should be able to see the specimen it is reasoning about, not receive only a sentence saying a structure rendered successfully.
Use shared `open_scene`, `set_scene_view`, `capture_scene` and `inspect_scene_capture` operations with the binder adapter; capture requests include bundle hash, preset, camera, selected residues, style and frame. Scientific inputs remain read-only; scene changes create immutable recipe revisions and capture creates scoped image/review artifacts. Capture returns a PNG artifact and matching structured scene state.
Implement actual image transport through the model/session adapter, then verify a real image-grounded task; current screenshot paths do not imply runtime vision support. `inspect_scene_capture` attaches image content to a supported vision observation, or invokes an explicit vision worker and returns grounded findings.
Include image hash, artifact hashes, projection/camera/clipping, physical-to-scene transform, annotations, visible residue IDs and occlusion fractions; declare illustrative overlays.
The binder specialization of shared `set_scene_view` supports orbit, fit-selection, focus-contact, orthographic comparison and explicit pose; clamp invalid clipping planes and report corrected values.
Proposed `binder.pick` maps image pixel coordinates plus snapshot hash to exact scene entities, preventing picks against an obsolete camera frame.
An agent investigating a questionable interface first requests the close view, sees the PNG, then requests the reverse view or cutaway if the contact is occluded.
It checks any visual concern against `evaluate_interface` outputs or exact coordinates before making a scientific claim; image color or apparent proximity is not a measured contact.
If a supplied confidence overlay seems discontinuous, the agent requests the field/table and verifies residue mapping rather than inventing uncertainty from the aesthetic material.
Bound image resolution, view count and render time per action; reuse image hashes and saved camera presets while keeping the latest candidate/version explicit.
Log visual observations as concise evidence-linked notes with image hash and camera state; replay shows the exact image available at that action's event cursor.
Scientific acceptance remains separate from visual quality: a striking scene can display a failed candidate, and a convincing-looking interface can still require rejection.

## 8. Milestones, verification and delivery

1. **Target and contract review:** choose a structure-backed PDAC question, inspect original evidence/context, freeze identity mapping and example artifact schemas; no large compute.
2. **Art-direction spike:** implement a standalone fixture within the experiment surface, compare WebGPU/WebGL lighting and two material treatments; deliver inspected images and revision history.
3. **Scientific geometry core:** add validated coordinate ingestion, target trimming maps, surfaces, contacts, buried-area calculation and exact residue picking.
4. **Design adapter:** register the proposed method guide, implement receipt/job lifecycle and bounded BindCraft pilot once compute availability and dependencies are verified.
5. **Comparison and agent vision:** connect real candidate events, synchronized stage views, render/inspect/pick tools and immutable screenshot observations with correct replay.
6. **Acceptance and documentation:** inspect all required desktop/mobile/reduced-motion presets, benchmark the declared fixture, document supported metrics and finish repository gates before integration.

Scientific tests use small known-coordinate complexes: exact contacts, insertion-code mapping, symmetry/assembly context, cropped-to-full alignment, alternate-conformer policy and missing fields.
Adversarial fixtures include swapped chain aliases, residue renumbering, absent target residues, stale artifact hashes, wrong project scope, NaN metrics and a fully occluded binder.
Job tests cover duplicate start, worker interruption, canceled partial output, failed generation and resumed collection without duplicate candidates.
Replay tests establish that a candidate, screenshot or confidence overlay never appears before its recorded event; unavailable resources remain unavailable in historical playback.
Browser tests check picks after rotation and scene resizing, preserved camera on inspector changes, synchronized comparison, errors and accessible fallback tables.
Run the repository-required build, frontend tests, e2e suite with isolated empty-data server, full Python suite and `git diff --check` at implementation commits; report local-data failures explicitly.
Update `docs/frontend.md`, runtime/artifact documentation, method registry documentation and architecture description in the same implementation milestone that changes their behavior.

## 9. Risks and explicit choices

Custom rendering costs more than adopting a molecular viewer, especially surfaces, picking and transparency; choose it because the requested visual freedom is central, and contain risk with fixtures and independent geometry checks.
3Dmol remains a useful compatibility fallback for legacy artifacts; Mol* is an alternative if large-assembly handling dominates, but neither should dictate the new workbench's composition.
BindCraft can demand substantial resources, and its PyRosetta dependency has licensing requirements; resolve actual deployment eligibility and GPU capacity before the pilot. [BindCraft installation](https://github.com/martinpacesa/BindCraft)
Model confidence is not binding affinity; generator/evaluator overlap can make confidence optimistic, so retain provenance and seek orthogonal assessment without claiming independence merely from a second run.
Cropping integrins or omitting glycans/membranes can create attractive but inaccessible epitopes; preserve the full-context review and explicit missing-context state.
A camera that flatters a candidate may hide clashes; pair authored hero views with deterministic opposing analytical views and coordinate-derived checks.
The parent checked an L40S with 46,068 MiB reported memory and no use at that instant; this is transient availability, not a reserved design budget. No compute was launched.
Unresolved decisions are target construct/epitope, concrete GPU budget, final renderer after the art spike, and the structural-verification contract; this planning task does not authorize implementation or wet-lab execution.
