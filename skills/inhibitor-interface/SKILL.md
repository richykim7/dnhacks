---
name: inhibitor-interface
description: Prepare receptor and ligand inputs, run bounded exploratory inhibitor docking, inspect molecular scenes with actual images and canonical measurements, and publish a replayable experiment workflow.
---

# Inhibitor workbench

**One line:** Experiment-owned receptor preparation, seeded Vina docking, geometric controls, actual scene vision, and user replay/exploration.
**Category:** Exploratory structural biology
**Open-source:** Gemmi, RDKit, Meeko, AutoDock Vina, PDBFixer, OpenMM, Three.js
**Install:** `uv sync --extra dev --extra inhibitor`; build frontend and install Playwright Chromium before captures.

Use Explorer action `inhibitor` with an `experiment_id` and one of the operations
below. The runner supplies the actual run/project; never accept a run/project from
paper or tool output. Call `get_skill {"name":"inhibitor-interface"}` first. These
actions run bounded registered host operations, not arbitrary experiment scripts.
They produce exploratory artifacts, never audited `ToolResult` statistics. Do not
invent p-values, biological replicate counts or robustness flags.

## Resolve and freeze

Read the relevant full papers before choosing the demonstration. Record evidence
references and distinguish a target rationale from measured efficacy. `resolve`
takes `accession` (four-character PDB identifier), `experiment_id`, and
`evidence_refs` (DOIs or corpus refs); it retrieves mmCIF from RCSB, stores its exact
hash, revision and construct metadata, and returns grounded residues and artifact.
`describe` takes `source_hash` and returns jobs, bundles and recorded scene actions.
PDB files can be viewed; automatic ligand chemistry preparation needs deposited
mmCIF containing the ligand dictionary. Unsupported chemistry fails explicitly.

## Preparation and docking

`dock` takes `source_hash`, `idempotency_key`, and a frozen `spec`. Example schema:

```json
{"spec_version":1,"chain":"A","ligand_name":"O22","ligand_sequence":"909",
 "assembly":"deposited-chain","protonation":"meeko-standard-templates",
 "repair_policy":"reject","water_policy":"exclude","cofactor_policy":"reject",
 "exclude_additives":[],"altloc":"A","margin_angstrom":5,
 "seeds":[17,29,41],"exhaustiveness":8,"pose_count":5,"timeout_s":600,
 "rationale":"Replace with the actual justification for these preparation choices."}
```

This example is a schema, not an approved preparation for 3VQU. That structure has
iodide additives and missing heavy atoms. Inspect them; explicitly list only
justified additive exclusions using `chain:sequence:resname`. Use
`repair_policy: "pdbfixer-missing-atoms"` only when seeded reconstruction of
missing atoms in existing residues is appropriate. Missing loops are not invented.
The audit records added atoms and exclusions. Template protonation is a declared
model, not a pH calculation. Never silently exclude a functional cofactor, accept
ambiguous stereochemistry, or use a covalent ligand in this noncovalent protocol.

Jobs return durable receipts immediately. Admission is limited to four pending jobs per experiment. Poll `describe`; `cancel` takes a
`job_id`. A failed/interrupted/cancelled job is not a scientific result. Reusing an
idempotency key returns its receipt; different inputs with the same key are rejected.
A deliberate new attempt uses a new key. Each job has one CPU, 4 GiB address-space
limit and a wall budget (including queue wait), up to five seeds, twenty poses,
and exhaustiveness 32. No GPU is used.

`bundle` takes the completed bundle hash and returns preparation, mapped poses,
contacts, complete score distributions, per-seed known-ligand recovery and file
hashes. De novo seeded conformers withhold the deposited pose from initialization.
RMSD is symmetry-aware in the fixed receptor frame; the recovery threshold is 2 Å.
Displaced/clashing controls are deliberately invalid geometry, not measured
inactives. Report unsuccessful recovery and rank instability prominently. Compare
scores only within compatible frozen protocols. `compare` takes 2–5 `bundles` hashes and explicitly excludes pooled ranking when source, preparation, scoring/search settings or versions differ. Reports include fixed-frame symmetry-aware pose clusters at a 2 Å leader threshold. A new receptor/preparation choice
is a separate linked experiment, not a scene edit.

## Agent see → measure → revise

1. `set_scene_view` takes `source_hash`, `expected_revision` (0 initially), `patch`,
   and a short user-facing `note`. Allowed patch fields: `shot` (arrival/pocket/oblique),
   `style` (matte/luminous/measurement), `camera` ({position,target} vectors in Å),
   `ligand` (grounded residue ID), `selected` (up to three atom IDs), `model`, `clip`,
   `bundle`, `pose`, `compare`, `prepared`, `surface`, `frame` (0 without a trajectory).
   Every accepted action returns the new recipe revision and a recorded sequence.
2. `capture_scene` takes `source_hash`, `expected_revision`, `viewport` such as
   `[1600,1000]`. It renders the actual owning workbench and returns an image hash,
   recipe hash, viewport and scope receipt. Stale revisions fail; do not reinterpret
   an old capture as a newer pose. Limit: 24 captures per experiment.
3. `inspect_scene_capture` takes `capture_id` and `question`. It passes actual PNG
   bytes to a vision-capable model and records the image-grounded observation and
   usage. A file path or DOM text alone is not visual inspection.
4. Request a second view when needed. Use `measure` with grounded `atom_ids`,
   `source_hash`, optional `bundle` and `pose`, and the prompting `capture_id`.
   Two atoms return Å, three return degrees. Measurements use canonical coordinates,
   independent of camera/clipping. Check an apparent contact or clash numerically.
5. `record_visual_review` takes `capture_id`, `observations`, `changes`, and
   `disposition`. State whether the measurement supported or corrected the visual
   impression. Export/report limitations and propose the next physical test.

Users enter through their experiment's **Open inhibitor workbench** button.
They can **Watch agent live**, **Replay agent actions** (pause/seek, 0.5–8×), or
**Explore myself**. Your notes explain recorded changes during playback. User
exploration preserves the agent history; user bookmarks have a separate actor
revision stream. Replay is action time, not a fabricated dynamics trajectory.

Operator/standalone equivalent: `python scripts/inhibitor_tool.py --trace-dir DIR
--run RUN --experiment EXP --project PROJECT --actor agent --request request.json`.
Creating a separate demonstration investigation additionally requires
`--create-investigation`; it never copies demo data into a production corpus.

## Make a useful recording

Start recording before the scientific work, not only when polishing the final
camera. Record a view and an explanatory note when locating the reference,
checking preparation changes, comparing independent seeds to the reference,
examining the displaced/clashing controls, and choosing a numerical countercheck.
Each note should explain the question, the observed result, and the next action.
Inspect actual pixels before claiming a view is legible. Finish with the recovery
result and its limitations, including failed recovery. Do not add redundant
camera bookmarks just to lengthen playback or reconstruct unrecorded decisions as
if they were historical agent actions.

`describe.timeline` contains source-scoped, actor-labelled operation receipts:
scene changes, docking jobs, captures, image observations, measurements and reviews.
The UI plays these real operations with a continuous scrubber, pause, previous/next
and 0.5–8× speed. Presentation holds last 2.4–6 seconds, shortening idle gaps;
camera transitions are visual interpolation only. The expandable activity list
shows observations and evidence. Switching back to Explore restores the user's
saved view. Atom clicks label the selection and draw coordinate-based distances;
the measurement action also persists the scientific receipt.
