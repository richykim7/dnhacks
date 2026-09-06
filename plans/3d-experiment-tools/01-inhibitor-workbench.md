# 01 — Inhibitor workbench: the pocket observatory

Status: proposed design and implementation plan, 2026-09-06. No implementation or compute run is authorized by this document.

## Outcome and architectural fit

Build an experiment-owned, cinematic 3D workbench where a scientist and research agent can prepare a target, compare candidate inhibitor poses, inspect contacts, and produce an auditable computational prioritization report.
The signature experience is a luminous molecular pocket suspended above a quiet instrument deck: beautiful enough to invite exploration, precise enough to answer which atoms support a claim.
The workbench expands from the selected investigator's experiment; its full-screen scene retains the experiment breadcrumb, source evidence, and return path.
It does not introduce a separate structure library or change human promotion, private scoring, or project/corpus semantics.

Today the frontend displays collected PDB/mmCIF artifacts with 3Dmol.js; no docking, preparation, or dynamics tool described here exists.
All interfaces below are proposals. Shared job lifecycle, immutable artifact storage, scope enforcement, and visual-tool transport follow the [shared platform plan](README.md).
The current runner still uses Docker even though its removal is a product decision; this plan defines tool requirements without selecting the replacement execution permission model.

## First scientific slice

Use the frozen 100-paper PDAC corpus as hypothesis context, not as a source of invented coordinates or measured inhibition.
The local manifest contains TTK inhibition in pancreatic cancer (ref 38, DOI `10.1371/journal.pone.0174863`), Aurora A inhibition and centrosome clustering (ref 41, `10.18632/oncotarget.26714`), and selective KIF18A inhibition (ref 63, `10.1038/s41467-024-55300-z`).
These are candidate starting points from titles and metadata; read complete relevant papers and verify model/compound context before selecting the actual demonstration.
Prefer a target with an experimentally solved ligand complex and a chemically appropriate reproducible preparation path; target suitability wins over name recognition.
If none qualifies, deliver the verified structure-and-contact slice and record the precise preparation blocker rather than making a docking demonstration look successful.
Record the corpus selection hash, source refs, exact target state/construct, and separately acquired structure accession, revision, retrieval date, and hash.
Do not imply that a non-PDAC mechanistic study or docking result demonstrates PDAC efficacy.

The first question: under a frozen preparation and docking protocol, can the method recover the known ligand geometry and distinguish credible candidate poses from obvious clashes?
Secondary questions: which contacts survive alternative receptor conformations, and which proposed analog changes require explicit testing?
Outputs are geometry quality, contact tables, within-protocol docking scores, seed sensitivity, and a prioritized follow-up list; affinity and cellular inhibition remain unmeasured unless separate evidence exists.

## Art direction: a precision instrument with cinematic scale

- Start with an ink-blue void, porcelain molecular ribbons, a restrained cyan rim, and one warm amber ligand; select a distinct violet accent for a compared candidate.
- Make the protein a sculptural object: crisp ribbons inside a softly translucent pocket shell, subtle depth separation, controlled specular reflections, and generous negative space.
- Let the ligand be the visual anchor. Pocket geometry frames it like architecture; scientific labels form a few quiet callouts rather than a cloud of text.
- Keep the interface tactile and sparse: a thin pose rail, a compact experiment card, and one contextual inspector. Typography, pacing, material richness, and composition carry the futuristic character.
- Use an optional theatrical arrival: a slow orbit resolves into the active site, surface layers separate, then controls settle. Reduced-motion enters directly at the final camera.
- Permit bold palettes, exploded views, stylized ribbons, illustrative particles, atmospheric backgrounds, and dramatic camera choreography. They are adjustable design choices, not scientific measurements.
- Provide a measurement view with the same visual care: true relative coordinates, restrained lighting, clear atom identity, distance units, and no foreground haze.
- Never encode scientific confidence using an unlabeled glow. Any score-dependent color uses an explicit scale; aesthetic highlights remain selections or decoration.

Initial composition targets are guides, revised after seeing renders: the molecule occupies roughly 55–70% of the desktop scene; the ligand has a readable silhouette; at most six priority callouts appear initially.
Make every state look intentionally designed, including preparation failure, an empty candidate set, absent structures, and unavailable dynamics.

## Storyboard and interaction

| Shot/state | What the person sees and does | Scientific purpose |
|---|---|---|
| 1. Arrival | Full protein appears as an ivory sculpture; a thin halo locates the pocket; source card names construct and provenance. | Establish identity and structure limitations before interpretation. |
| 2. Pocket descent | Click the halo; camera follows a reproducible arc while a local cutaway opens around the ligand. | Reveal occluded geometry without silently deleting scientific atoms. |
| 3. Preparation audit | Side-by-side original/prepared structure; changed hydrogens, waters, alternate locations, and repairs illuminate on demand. | Explain exactly what the docking input differs from. |
| 4. Pose gallery | A horizontal rail of candidate miniatures; selecting one gently replaces the ligand in a fixed receptor camera. | Compare actual poses without camera-induced apparent differences. |
| 5. Contact lens | Select a residue; surrounding atoms sharpen, distances appear, and the inspector links each measurement to atom IDs. | Inspect clashes and interactions numerically. |
| 6. Paired comparison | Split scene uses synchronized cameras; optional aligned overlay has independently controlled opacity. | Compare candidates and receptor states under a declared alignment. |
| 7. Dynamics ribbon | Optional trajectory scrubber shows a sampled recorded frame, time, and contact occupancy plot. | Inspect a real trajectory, with temporal correlation disclosed. |
| 8. Evidence plate | Freeze a composed view beside score distribution, contact table, limitations, and source evidence. | Export a reviewable experiment artifact and next-test rationale. |

Orbit, pan, zoom, reset, clipping, residue search, keyboard selection, and camera bookmarks are first-class controls.
Atom and residue picking must remain accurate under instancing, cutaways, alignment, and display transformations.
An exploded arrangement carries a visible mode indicator; requesting a distance switches to canonical coordinates or explicitly reports canonical distance.
The source structure stays immutable; all camera, material, alignment, and illustrative transforms live in a separate scene recipe.

## Stack selected for visual quality

Choose custom Three.js rendering through React Three Fiber (R3F), with reusable molecular geometry builders and React DOM inspectors.
This gives direct control over shaders, instanced atoms/bonds, clipping, selective bloom, lighting, callout placement, and camera paths while fitting the existing React app.
Use WebGL2 as the first verified interactive path; evaluate WebGPU only after the same scenes pass the visual and browser matrix.
R3F documents instancing and demand rendering for performance; use these to support dense molecules and static inspection without permanent animation. [R3F performance guidance](https://r3f.docs.pmnd.rs/advanced/scaling-performance)
Three.js physical materials support transmission, giving a starting point for the pocket shell; benchmark it because transparent layers can be expensive and obscure geometry. [Three.js material reference](https://threejs.org/docs/pages/MeshPhysicalMaterial.html)
Start with ambient occlusion, restrained emissive accents, and antialiasing; add effects individually only after inspecting the actual browser result.
Generate solvent-accessible/excluded surface meshes with a scientifically identified algorithm and recorded parameters; decorative shells are separate meshes with explicit illustrative provenance.
Use backend Gemmi for PDB/mmCIF parsing and residue/chain identity, not a handwritten browser parser as the scientific source of truth. [Gemmi documentation](https://gemmi.readthedocs.io/en/latest/)
Use RDKit for ligand sanitization and seeded conformer generation, retaining stereochemistry and atom mapping. [RDKit conformer documentation](https://www.rdkit.org/docs/GettingStartedInPython.html)
Use AutoDock Vina for an initial reproducible noncovalent docking adapter with pinned receptor/ligand preparation; its Python API supports controlled docking workflows. [Vina Python API](https://autodock-vina.readthedocs.io/en/latest/docking_python.html)
OpenMM is an optional later dynamics engine; require supported ligand parameters, force-field provenance, system validation, and an explicit run budget. [OpenMM application guide](https://docs.openmm.org/latest/userguide/application.html)
Do not launch GPU work while implementing the visual spike; before planning actual heavy simulations, follow the repository GPU handoff and verify availability.

| Alternative | Strength | Reason to keep or reject for this slice |
|---|---|---|
| Existing 3Dmol view | Already integrated; preserves a useful reference rendering. | Keep as a geometry comparison/fallback, but do not constrain art direction to its viewer API. |
| Mol* | Worth evaluating for molecular scale and established representation machinery. | A useful comparator if custom geometry costs dominate; require the same cinematic scene trial before selecting it. |
| Blender offline rendering | Candidate for exceptional export lighting and composition. | Optional evidence-plate pipeline after a prototype; interactive browser control remains necessary. |
| Unreal/Unity streaming | Candidate for elaborate real-time presentation. | Additional deployment and interaction transport are disproportionate for the first local research slice. |
| Browser rigid-body physics | Convenient animated motion. | May animate illustrative props; cannot supply molecular dynamics or docking evidence. |

These are architecture judgments, not claims that comparative prototypes have been run. Select the final rendering stack after the observed visual spike below.

## Proposed scientific tools and contracts

Each tool takes scoped immutable artifact references and a versioned specification, returns a durable job/receipt, and publishes typed artifacts through the common runtime.
Requests include `project_id`, `run_id`, `experiment_id`, `spec_version`, `idempotency_key`, input hashes, method version, and declared resource limits.
Every completed artifact includes producer/version, parameters, seed where applicable, units, scientific/illustrative provenance, warnings, and source hashes.
Errors such as unsupported chemistry, missing parameterization, residue mismatch, interrupted job, or absent structure are typed outcomes; partial results cannot masquerade as completed results.

| Proposed tool | Principal arguments | Durable output |
|---|---|---|
| `structure.resolve` | verified target identifier/state, accession, assembly, source refs | original mmCIF, identity map, sequence/construct comparison, retrieval provenance |
| `inhibitor.prepare` | structure hash, ligand SDF, protonation policy, retained waters/cofactors, alternate-location policy | prepared structures, atom map, complete preparation delta, suitability report |
| `inhibitor.define_pocket` | residue IDs or reference ligand, explicit margin in Å | grid box, selected residues, rationale, camera bookmark |
| `inhibitor.dock` | prepared inputs, box hash, scoring mode, exhaustiveness, seeds, pose count | pose SDFs, score table with native units, logs, execution manifest |
| `inhibitor.audit_pose` | pose/receptor hashes, contact-rule version, alignment reference | clashes, distances/angles, contact identities, symmetry-aware ligand RMSD where defined |
| `inhibitor.compare` | compatible protocol/run IDs, predefined ranking and grouping rules | pose clusters, seed sensitivity, contact differences, comparison exclusions |
| `inhibitor.relax` | optional validated system, force fields, integration settings, budget | actual trajectory, sampled frames/times, diagnostics, contact occupancy |
| `inhibitor.report` | selected results, question, evidence refs, limitations | report JSON/Markdown, evidence plate, proposed follow-up tests |

Preparation never silently removes functionally relevant cofactors or changes stereochemistry; ambiguous choices are explicit protocol branches.
A structure's asymmetric unit need not equal its biological assembly; retain the chosen assembly and transformation records. [RCSB assembly guide](https://pdb101.rcsb.org/learn/guide-to-understanding-pdb-data/biological-assemblies)
Contact rules distinguish measured proximity from an assigned hydrogen bond, whose geometry and donor/acceptor assumptions are recorded.
Scores are compared only under a declared compatible scoring/preparation protocol; a score is not a dissociation constant or demonstrated binding.

Proposed bundle layout: `structure.cif`, `ligands.sdf`, `poses/*.sdf`, `atom-map.json`, `preparation.json`, `contacts.parquet`, `scores.parquet`, `protocol.json`, `scene.json`, `report.json`.
`scene.json` references hashes and stores camera position/target/up, projection, clipping planes, viewport, selected atoms/residues, style recipe/version, seed, trajectory frame/time, and canonical-to-display transforms.
A trajectory bundle also specifies topology hash, frame indexing, physical time units, periodic-boundary handling, and alignment policy; an interpolated display frame is labeled interpolated.
Mesh exports include coordinate frame, units, atom/residue selection map where applicable, generation algorithm, and explicit indication of illustrative geometry.

## Scientific experiment design and interpretation

1. Freeze target identity, ligand stereochemistry, preparation, receptor selection, box definition, metric, and candidate list before examining docking outcomes.
2. Redock a known ligand from a withheld pose initialization; report symmetry-aware heavy-atom RMSD and the fraction of seeds meeting a predeclared recovery target, initially 2 Å.
3. Include a deliberately displaced/clashing pose as a geometry test, and documented inactive compounds or justified matched decoys where available; describe their limitations.
4. Vary receptor conformer and plausible preparation choices as sensitivity analyses; report failures and rank changes, not only the best seed.
5. Summarize contacts, protocol-specific score distributions, pose diversity, and unsupported assumptions; do not equate repeated seeds or trajectory frames with independent biological replicates.
6. If measured activity data later support a separate registered test, split by an appropriate independent unit such as scaffold or experimental source and predeclare analysis/controls.
7. Keep docking and visual inspection exploratory unless a suitable audited method is independently registered. Never fabricate `p_null`, `n_units`, or `robust` to satisfy the existing `ToolResult` gate.
8. Preserve the existing candidate/human-review boundary. A striking figure, successful redocking, or stable short trajectory cannot promote a claim by itself.

Acceptance of the first scientific slice means reproducible inputs, an honest benchmark report, correct coordinate measurements, and understandable negative results; it does not require a favorable candidate ranking.

## Developer must see and revise actual renders

A screenshot file existing on disk is insufficient. The implementing agent must open the resulting images with an image-capable inspection tool and describe observed defects before revising the design.
Build an isolated fixture experiment with a legitimate small structure, a prepared comparison, a known ligand, a failure case, and explicitly labeled illustrative poses if needed before real docking exists.
Expose a test-only `window.sceneReview` controller supporting `loadFixture`, `setCamera`, `setStyle`, `setFrame`, `select`, and `ready`; do not expose unrestricted script execution to runtime scientist agents.
`ready` resolves only after required geometry/materials/fonts are loaded, shader compilation and a completed render are acknowledged, and pending scene transactions reach the requested revision.
Pin viewport, DPR, browser version, quality tier, fixture hashes, frame, seed, and scene recipe; disable autoplay and settle camera transitions for comparison shots.

Concrete loop, repeated for each milestone:

1. Launch isolated Python/Vite fixture servers using `docs/frontend.md`; keep production data outside the fixture run.
2. Use Playwright to enter the actual owning experiment, expand the workbench, apply a named shot through the test controller, and wait for `ready` plus `document.fonts.ready`.
3. Capture both full UI and canvas detail using `page.screenshot({path})` and the canvas locator's screenshot; produce 1600×1000, 1920×1080, and 390×844 captures. [Playwright screenshots](https://playwright.dev/docs/screenshots)
4. Open those PNGs using `view_image` or equivalent image input. Inspect the arrival, pocket, comparison, clipped surface, error state, and reduced-motion endpoint; inspect three actual sampled trajectory frames if dynamics exists.
5. Critique composition, silhouette, depth, lighting, ligand visibility, callout collisions, hierarchy, scientific legibility, and responsiveness; name specific image regions and observed defects.
6. Change a focused set of camera/material/layout parameters, rerender, reopen the images, and compare with the prior revision. Repeat until the visual criteria pass.
7. Save a revision record: fixture and shot IDs, before/after image hashes, observed defect, change, resulting assessment, remaining issue, and reviewer identity. Do not claim inspection without image-tool evidence.
8. Run deterministic screenshot comparisons as regression checks only after visual approval; screenshot-diff success cannot judge beauty. [Playwright visual comparisons](https://playwright.dev/docs/test-snapshots)

The first visual spike must compare at least two actual treatments: luminous translucent pocket and sculpted matte cutaway, with two camera compositions each.
Select the treatment from opened contact sheets and recorded critique; allow stylistic revision rather than treating initial colors/materials as a locked specification.

## Runtime scientist-agent vision

Propose `scene.describe`, `scene.set_camera`, `scene.focus`, `scene.set_frame`, `scene.set_style`, `scene.capture`, and `scene.measure` as adapter-level aliases for the shared `open_scene`, `set_scene_view`, `capture_scene`, and `inspect_scene_capture` operations, attached to this experiment.
`scene.capture` returns an actual rendered PNG image payload plus image hash, scene revision, input hashes, camera/frame/viewport, visible selections, clipping state, and measurement overlays.
Implement and test new image-bearing transport through the runtime model/session seam; image delivery is not a current capability assumed by this plan. Deliver pixels to the scientist agent or an explicit vision-capable worker; a path, alt text, or DOM summary alone does not satisfy the capture contract.
`scene.focus` accepts grounded atom/residue IDs and padding; `scene.set_camera` accepts explicit vectors/projection or a stored bookmark; all mutations return the resulting revision.
Capture requests specify the expected revision and physical frame; reject stale captures rather than mixing one pose's image with another pose's metadata.
`scene.measure` computes canonical numerical distances/angles independently of pixels and display exaggeration, returning mapped atom IDs and units.
The agent uses vision to notice occlusion, misalignment, suspicious geometry, or useful presentation angles, then uses numerical tools to test those observations.
A runtime report records which captured image prompted which measurement and whether the numerical result supported or corrected the visual impression.
Limit repeated captures by a configurable image budget; allow scientific counterchecks even when a presentation image has been visually approved.

## Milestones, tests, and exit criteria

| Milestone | Deliverable | Exit evidence |
|---|---|---|
| A. Visual selection | Two render treatments, four shots, responsive shell, image-inspection log. | Opened renders and at least one substantive revised render; chosen design rationale. |
| B. Reliable geometry | mmCIF/SDF normalization, selections, surfaces, camera/capture tools. | Known atom distances agree within 0.01 Å; identity survives alignment and picking; stale-frame capture rejected. |
| C. Docking experiment | Preparation audit, seeded docking, recovery benchmark, negative controls. | Reproducible protocol and full score/pose artifacts; unsupported chemistry fails explicitly. |
| D. Agent visual loop | Image delivery, camera/frame control, numeric crosschecks, evidence plate. | Agent actually receives images, requests a second view, measures an observation, and records the outcome. |
| E. Optional dynamics | Parameterized system and recorded trajectory inspection. | Valid system diagnostics, bounded resource use, correct frame/time labels, explicit sampling limitations. |
| F. Integration | Existing experiment-scoped UI/runtime, docs and capability declarations. | Scope/hash/replay tests, all repository commit gates, and final inspected desktop/mobile captures. |

Visual exit: no clipped priority labels or ligand; selected ligand remains identifiable at each required viewport; cutaway reveals the intended pocket; comparison cameras are synchronized; normal text meets 4.5:1 contrast.
Quality exit: a reviewer can identify target, selected candidate, provenance, and the principal comparison within ten seconds; typography/materials/depth earn an explicit visual-review pass, not just a pixel-diff pass.
Performance targets to validate on a recorded reference machine: typical 50k-atom fixture at a 60 fps desktop target and ≥30 fps on the selected laptop/mobile tier while orbiting, median interactive pick feedback under 100 ms, and first usable cached scene within two seconds.
Treat those budgets as targets to benchmark, never already achieved claims; fall back through DPR, surface detail, and effects before removing scientific content.
Test malformed/oversized geometry, empty scenes, interruption, cancellation, recovery, cross-project access, immutable hash mismatch, context loss, and playback before artifact creation.
Before implementation commits run board checks and every repository gate: frontend build/unit/e2e, `uv run pytest tests`, and `git diff --check`; report local missing-data failures explicitly.

## Principal risks and decisions

Custom molecular rendering is more engineering than a viewer wrapper; isolate geometry/identity from art direction and use known fixtures to detect scientific regressions.
Preparation and force-field support can dominate scientific validity; keep unsupported covalent ligands, metal coordination, unusual residues, and ambiguous states out of the initial protocol unless explicitly supported.
Translucency can hide the ligand or produce sorting artifacts; retain the inspected matte cutaway treatment as a first-class visual choice.
Docking ranks can be unstable and overinterpreted; preserve complete distributions, controls, preparation branches, and measured-versus-inferred labels.
Vision can mistake perspective or artistic styling for geometry; require canonical numeric checks for every structural assertion retained in a report.
The plan's sources document component capabilities; the proposed combination, visual quality, throughput, and scientific suitability remain to be demonstrated through the milestones above.
