# Four experiment tools with a shared visual studio

Status: proposed plans, 2026-09-06. The user authorized planning and prioritizes beautiful,
futuristic 3D design, including artistic liberties. These documents do not implement tools
or authorize starting the planned scientific runs. Each tool has its own planning-agent author.

| Plan | Visual centerpiece | Experiment |
|---|---|---|
| [Inhibitor workbench](01-inhibitor-workbench.md) | Cinematic journey into a molecular pocket | Compare candidate poses, contacts and receptor states |
| [Binder design](02-binder-design.md) | Sculptural target–binder interface | Generate and inspect candidate binding interfaces |
| [Tumor–stroma](03-tumor-stroma.md) | Luminous living tissue and nutrient fields | Perturb spatial nutrient support and survival |
| [Spindle simulator](04-spindle-simulator.md) | Choreographed microtubules and centrosomes | Compare clustering under motor/geometry perturbations |

## Design comes first

Begin implementation with visual prototypes of all four scenes before completing expensive
scientific pipelines. Use explicitly illustrative development fixtures to establish art direction.
Choose algorithms with exportable geometry and states; choose renderers for artistic control.
The existing 3Dmol viewer is a useful reference inspector, not a ceiling on design quality.

Use a shared React Three Fiber/Three.js scene platform as the starting recommendation:
custom materials, restrained bloom, depth cues, instancing, clipping, volumetric layers,
cinematic cameras, selective labels and synchronized comparison views. Prototype WebGPU
where it materially improves the chosen effect; retain a designed WebGL2 experience.
Do not mix incompatible WebGL postprocessing and WebGPU/TSL recipes. Pin a tested stack
only after the first visual spike. Blender is an optional cinematic export backend; interactive
browser quality is a separate acceptance requirement and cannot be replaced by a polished video.

Art direction: near-black indigo space, pearl/translucent biological forms, cyan/teal active
regions, amber intervention accents, generous negative space and crisp quiet typography.
Each tool gets a distinct silhouette and motion language. Avoid filling the scene with HUD
ornaments; the scientific object should command attention. Carry the style through transitions,
loading, selection and comparison, with static/reduced-motion compositions designed deliberately.

Artistic freedoms include nonphysical lighting and colors, exaggerated radii, glow, trails,
cutaways, time remapping, illustrative membrane context and exploded arrangements. Store those
choices in a reversible presentation recipe. Measurements use underlying coordinates/fields,
not screen-space distances or exploded positions. A small scene badge and optional disclosure
identify reference, prediction, simulation or illustration. This should support confident design,
not bury the experience in warnings. Do not invent a successful experiment to match a storyboard.

## Shared architecture to implement later

User requirement (2026-09-06): every 3D tool must provide discoverable agent
instructions in `skills/`, executable scene controls for the research agent, and
both user modes: watch/replay the agent's actual recorded scene interactions with
pause, seek and adjustable playback speed; or independently explore the same
experiment. User exploration must preserve the agent timeline. Label action
replay time separately from physical simulation time. A static viewer or exported
movie alone does not satisfy this interaction requirement.

Keep selected-experiment ownership and the existing immutable runtime artifact flow. Introduce
versioned molecular, cell/field and filament-trajectory adapters behind a shared scene interface.
Extend the collector deliberately: current PDB/mmCIF collection does not already support spatial
volumes, arbitrary scene bundles, movies or screenshot receipts. All API names below are proposals.

Separate three immutable records:

1. **Experiment:** inputs, method/version, seed, geometry or time-series hashes, units, controls,
   numerical results, source references and scientific status.
2. **Scene recipe:** experiment reference, adapter version, visual preset, materials, camera,
   clip planes, selection, timeline mapping, quality tier and any illustrative transformations.
3. **Visual review:** rendered image references, experiment/recipe hashes, renderer/browser
   versions, camera/time/viewport, image-viewing receipt, observed defects, proposed edits and verdict.

Use one logical camera/state schema across the four plans even where examples use different
command names. Scene recipes are data, not arbitrary executable shader source supplied by an agent.
Keep runtime scene changes scoped to the owning project and experiment. A visual revision does not
rerun science; a scientific parameter change starts a linked experiment revision with fresh outputs.

Suggested common operations:

- `open_scene(experiment_id, preset)` → scene and artifact references.
- `set_scene_view(scene_id, camera, time, clip, selection, style_patch)` → recipe revision.
- `capture_scene(scene_id, recipe_revision, views, viewport)` → image artifacts and capture metadata.
- `inspect_scene_capture(image_refs)` → actual image-bearing observation to a vision-capable agent.
- `record_visual_review(capture_id, observed_defects, changes, disposition)` → review record.

Runtime multimodal delivery is new work. Inspect the model/session adapter's actual supported image
transport, implement it and verify it with a real image task. A filesystem path or prose description
is not an image observation. If the selected runtime model cannot receive images, route inspection
to an explicit vision-capable worker and return its image-grounded findings; never silently pretend
that metadata inspection was visual inspection.

## Mandatory render → see → revise loop

This applies both to the coding agent implementing the experience and to the future research agent
using the experiment tools. The former can revise code/materials; the latter revises bounded scene
recipes and experimental hypotheses through registered tool operations.

1. Set an intended visual outcome: focal subject, readable comparison, camera composition and
   a short reference/style brief. Save the starting experiment and scene recipe.
2. Render the actual application in Chromium through Playwright. Wait for a scene-owned readiness
   signal covering asset loading, shader compilation and a completed render, not a fixed sleep.
3. Freeze simulation time, shader clocks, particles, camera easing and seeded effects explicitly.
   Playwright's CSS animation disabling does not stop Three.js requestAnimationFrame loops.
4. Capture the full UI and canvas close-up, at least front/oblique/detail views, plus beginning,
   middle and end frames for motion. Inspect a contact sheet and a short video for temporal defects; when the agent lacks video input,
   decode the clip into timestamped frames and inspect those actual pixels at a cadence suitable for the motion.
5. Deliver PNGs to the agent's image-viewing capability. In this development environment that can
   be `view_image` on the saved screenshot; future runtime tools must actually attach the pixels.
6. Write image-specific observations: subject is clipped, interface disappears against the surface,
   label occludes the contact, bloom washes out detail, membrane looks flat, trails hide pole motion.
   Console success and DOM existence cannot satisfy this step.
7. Make a targeted change, render again, view again and compare before/after at the same view/time.
   Require an initial draft, an inspected revision and an inspected final pass; keep iterating when
   known high-priority defects remain. A numerical iteration quota is not an aesthetic verdict.
8. Save the accepted capture set and concise visual decision log. A failed/unavailable capture is
   an explicit incomplete review. Do not mark it passed because automated tests are green.

Future implementation sketch (illustrative; these hooks do not exist yet):

```ts
await page.evaluate(async (recipeId) => {
  await window.sceneReview.apply({ recipeId, time: 0.5, camera: 'interface', freeze: true });
  await window.sceneReview.ready();
}, recipeId);
await page.screenshot({ path: capturePath, animations: 'disabled' });
// Next required action: open capturePath with the agent image tool and critique the pixels.
```

Keep captures linked to exact scene revisions. If a subsequent edit changes shaders, camera defaults,
labels or data adapters, old captures cannot certify the new revision. Screenshot equality detects
regressions, not beauty; a vision-based critique judges composition, hierarchy, depth and finish.

## Shared visual acceptance and delivery sequence

For each scene, review desktop 1600×1000, presentation 1920×1080 and mobile 390×844, with a close-up,
comparison view and reduced-motion state. Reference/mobile views need not use identical geometry LOD.
The focal object must be immediately legible, intervention distinguishable without color alone,
labels readable and deliberate motion free of flicker or jumps. Verify picking and numerical readouts
still correspond to source entities after every visual transformation. Capture light/dark shell
integration where supported, even when the scene itself retains its cinematic dark stage.

Set proposed performance targets of 60 fps on the development desktop and 30 fps on the chosen
reference laptop/mobile tier after warmup; record hardware, scene size and p95 frame time. These are
targets, not measured achievements. Adaptive quality may reduce particle count, surface tessellation,
volume resolution and bloom; it must preserve the composition and scientific comparison. Benchmark
locally before choosing exact scene-size limits; remote compute availability does not imply a user's
browser has a powerful GPU. Validate browser context-loss recovery and stale/missing artifact states.

Milestones:

1. Four short art-direction spikes, actual screenshot critiques and a selected shared rendering stack.
2. Common scene recipes, capture/vision tools and immutable visual-review records.
3. One real computational workflow per scene with explicit controls and parameter provenance.
4. Runtime agent demonstrates a complete see/revise loop and a separate science-result-driven iteration.
5. Performance/accessibility pass, interactive demo and optional high-quality cinematic exports.

Required tests include artifact schema/units and experiment ownership, deterministic capture readiness,
real pixel delivery to the vision worker, camera/selection replay, known geometry picking, and a visual
review of accepted frames. Use meaningful backend and browser tests; avoid tests that merely assert a
preferred shader setting. Run the repository's full commit gates when implementing. This planning
change also runs those gates under the repository convention.

## Compute and source notes

The existing GPU connection was checked read-only on 2026-09-06: NVIDIA L40S, 46,068 MiB reported,
0 MiB used and 0% utilization at that instant. Availability is transient. No jobs were launched.
Recheck and coordinate access before future binder inference or high-quality GPU rendering; keep
connection details local and do not commit credentials. Heavy jobs need bounded budgets, queueing,
progress, cancellation and recoverable artifacts. CPU simulation and browser rendering are separate
resources; do not hold a GPU allocation while an agent reviews screenshots.

Primary references verified for this plan:

- [React Three Fiber](https://r3f.docs.pmnd.rs/getting-started/introduction): React renderer for Three.js.
- [Three.js WebGPU renderer](https://threejs.org/manual/en/webgpurenderer): renderer and migration choices.
- [WebGPU postprocessing](https://threejs.org/manual/en/webgpu-postprocessing.html): distinct rendering pipeline.
- [Playwright screenshot assertions](https://playwright.dev/docs/api/class-pageassertions): reproducible browser captures.
- [Blender command-line rendering](https://docs.blender.org/manual/en/latest/advanced/command_line/render.html): optional automated exports.

Local integration references: [architecture](../../ARCHITECTURE.md),
[frontend contract](../../docs/frontend.md), and the local-only frozen corpus manifest at
`data/corpora/pdac-frozen/MANIFEST.json` (100 papers, publication cutoff 2026-01-25).
