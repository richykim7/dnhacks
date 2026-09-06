---
name: tissue-interface
description: Build and run conditional spatial tumor–stroma alanine simulations, inspect exact 3D frames, record agent scene actions and review actual rendered pixels within an owning experiment.
---

# Tissue interface

**One line:** Scoped PhysiCell/BioFVM alanine experiments with immutable artifacts and image-bearing review.
**Category:** Exploratory simulation sensitivity; not an audited biological test.
**Open-source:** PhysiCell 1.14.2 and bundled BioFVM, pinned revision dbd3499250141b27600e91e501c54c46f68f2763.
**Install:** Repository Python environment, C++ compiler with OpenMP, frontend dependencies and Playwright Chromium.

Before repository implementation work, run `python3 scripts/board.py show` and answer required coordination questions on the board; claim files before editing. This repository coordination requirement does not require a research end user to use the shell.

Use the runtime `tissue` action after receiving this skill through `get_skill`. Every call has
`{"experiment_id":"<owning experiment>","operation":"<name>","args":{...}}`.
Create an exploratory experiment with `run_experiments` first; use its actual experiment ID from the runtime record. Never invent ownership IDs. No tools or paths in this skill authorize biological verification.

1. Read full source methods and limitations. Declare the question, units, boundary condition, geometry, endpoint and parameter origin before simulation. `build_model` accepts `question`, `parameters` (diffusion, secretion, uptake, boundary, threshold, growth), `geometry` (tumor_radius_um, caf_shell_um, caf_count, caf_offset_um), plus `source_context` (source identifiers, method context and provenance). Returned `model_id` identifies an immutable specification. Defaults are **assumed**, including fixed cell centers, continuous volume growth without division, and an assumed damage/death law. They are not fitted to patient data.
2. `simulate` takes `model_id`, optional `conditions`, `seeds` (one to three unique computational seeds), and `duration_minutes` (1–2880). Conditions: baseline, uptake_suppressed, secretion_off, double_off, alanine_rescue. Suppression means 5% of baseline uptake; rescue sets outer alanine to 1 mM and removes secretion. Default: all five, seed 0, 1440 min. Returns a durable `job_id`. Poll `job_status` with that ID; `cancel` requests process-group cancellation. Completed status returns collected `artifacts`; failed/canceled/timeout outputs cannot be analyzed as completed simulations. Two concurrent CPU jobs maximum. Missing pinned engine is an explicit setup failure.
3. `analyze` takes a collected `artifact_id`. Compare paired conditions within computational seeds, with cells nested within simulation. Report living count, living volume, radial survival and field range. No simulation seeds or cells are biological n; no p-values or verification promotion. Repeat declared parameter alternatives, including secretion, uptake and boundary alanine, before interpreting robustness. Diffusion diagnostics and timestep/grid convergence are separate from biological validity.
4. `open_scene` takes `artifact_id`, optional `preset` (Exterior, Core, Neighborhood), and a short action `note`. `set_scene_view` takes the latest `recipe_sha256`, a `view` patch and a `note` explaining its purpose. Patch keys: preset, exact integer frame, section (z in µm, −160..160), opacity (0..1), comparison, condition index, selection (cell ID/null), azimuth, elevation (−1.1..1.1 radians), zoom (.6..2.8). Camera changes are recorded agent actions, not simulation frames. Preserve shared scale/time/camera in paired comparisons. Stale revisions fail; fetch `history` before retrying.
5. `capture_scene` takes `recipe_sha256` and optional `viewport` [1600,1000] (width320..1920,height320..1080). It renders the real application and returns a `capture_id`. A mobile capture requires one condition. Additional view keys: `theme` dark/light, `fieldMaximum` (one fixed positive mM maximum for both compared conditions), `diagnosticSlice` boolean. The diagnostic shows exact source voxels and saturation counts. Changing the range must be reported; never hide clipped values or use different scales across a pair. `inspect_scene_capture` takes the capture ID and a concrete `question`; it sends actual PNG bytes to a tools-disabled vision model. A filename, capture receipt or render-success flag alone is not visual inspection. If vision is unavailable, report incomplete; do not substitute verbal metadata.
6. Critique visible cells, section clipping, field contrast, legends, scales and paired-condition exaggeration. Record defects using `record_visual_review` with capture_id, unresolved_defects and disposition incomplete. Revise the recipe, recapture and inspect the new pixels. Complete requires a successful image observation and no unresolved defects. Review the first draft and at least two revisions during renderer development; retain their receipts. Biological validity remains separate from visual acceptance.

Users open Living tissue from the owning experiment. They can watch the recorded agent action timeline at .5×–4× speed, independently explore exact physical-time frames, and return to their own view without rewriting agent history. Scene PNG exports include shared legends, units and a JSON recipe.

Operator setup and CLI contract: [runtime reference](../agent-runtime/references/tissue-interface.md).

`neighborhood` accepts artifact_id, condition index, exact frame index, cell_id and optional
radius_um (default35). It uses full source positions and returns neighbor IDs/counts and local
alanine summaries; the UI's35µm halo/readout uses this same distance definition. The shared scene
budget is128 actions and48 captures per experiment, including revisions. Renderer jobs join the
host browser queue and release it before a model reviews the image.

Use `cells` to discover source IDs before selecting one: artifact_id, condition, frame, optional
state alive/dead, offset and limit (1–100, default50). It returns a bounded page and total count.
Do not infer cell IDs from their screen position or invent identifiers.
