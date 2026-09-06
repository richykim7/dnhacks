# Inhibitor workbench

Open an investigation's **Experiments** tab and choose **Open inhibitor workbench**
on its collected molecular structure. The workbench belongs to that exact run,
project, experiment and immutable structure. No artifact means no workbench button.
Merging source does not restart a deployed server or manufacture experiment data.

## Run and view a real example

```sh
uv sync --extra dev --extra inhibitor
npm --prefix frontend ci
npm --prefix frontend run build
uv run --extra inhibitor python -m playwright install chromium
uv run --extra inhibitor python scripts/inhibitor_demo.py --trace-dir /tmp/inhibitor-example --serve --port 8787
```

The command performs actual CPU docking, prints the result and a direct browser
link, then serves the isolated example. It leaves your usual research data alone.
The prepared inputs, immutable result blobs, logs and journal remain under the
chosen directory. Repeating the same request reuses its durable receipt. Use a
new directory for a deliberate new demonstration. The initial demo bookmark is
labelled as an operator action; it does not impersonate agent research.

The owning-view URL uses `project`, `experiment`, `artifact`, `sceneTool=inhibitor`
and `#investigations/<run>`. Add `sceneRevision` and `sceneActor` for a recorded
view. `through` also restricts artifact/event availability for historical playback.
Return to experiment retains the owning run and project.

## Interact or watch

- **Explore myself:** orbit, pan, zoom, choose a pose, search/select atoms, change
  treatment/cutaway, compare original/prepared structures and measure coordinates.
- **Watch agent live:** follow its latest recorded scene.
- **Replay agent actions:** play, pause, seek and change speed from 0.5× to 8×.
  Action time is not physical molecular-dynamics time. Exploring stops replay and
  preserves the agent history. Saved user bookmarks have their own revision stream.
- **Docking:** inspect/edit the frozen protocol, start preparation and docking,
  follow the durable receipt, cancel, and download completed output files.
- **Evidence plate:** records a user bookmark, captures the actual composed
  workbench, and exports its PNG with a JSON scientific report. Historical,
  read-only playback permits a local canvas export without new journal events.

## Agent instructions and vision

The runtime method guide is [inhibitor-interface](../skills/inhibitor-interface/SKILL.md).
Explorer requires delivery of that skill before executing `inhibitor` actions.
The same scoped adapter serves the UI, `scripts/inhibitor_tool.py`, and Explorer.
It offers structure resolution, durable docking/cancellation, bundle access,
revision-checked scene mutation/capture, canonical measurements and visual review.
`inspect_scene_capture` sends actual bounded PNG bytes through the existing model
transport. Capture IDs are checked against the owning experiment; counterchecks
must reference the same source, bundle and pose as the prompting capture.

The runtime's run/project identity is supplied by the runner. HTTP mutations are
always user-authored. Model-authored and user-authored scene events are append-only
and do not modify immutable structures. Camera/clip changes never modify scientific
coordinates. Capture rejects stale revisions and has a 24-image experiment budget;
numerical tools remain usable after the image budget is exhausted.

## Scientific protocol and limits

V1 is a known-ligand recovery workflow using deposited mmCIF chemistry, a selected
deposited chain, explicit water/additive/alternate choices, Meeko template
protonation and optional seeded PDBFixer missing-atom reconstruction. It does not
expand biological assemblies or invent missing loops. Unsupported chemistry,
metals/covalent attachments and preparation failures produce failed receipts.
The user must justify exclusion choices; the adapter cannot establish biological
suitability automatically. PDB files remain viewable but lack the required deposited
ligand dictionary for automatic chemistry preparation.

RDKit creates a seeded de novo conformer; the deposited pose is withheld from
initialization. Vina uses one CPU, bounded seeds/exhaustiveness/poses, a 4 GiB
address-space cap and a declared wall budget including queue wait. At most four
jobs may be pending per experiment. Completed
bundles contain inputs, mapped SDF poses, native-unit score tables, preparation
deltas, controls, contacts, protocol/version hashes, JSON/Markdown reports and
an approximate solvent-accessible pocket mesh. Cancelled, timed-out and failed
jobs never publish partial completed bundles. Deployment leases persist through
worker/child lifetimes when a deployment lock is configured.

RMSD is symmetry-aware in the fixed receptor coordinate frame; recovery is
predefined at 2 Å. Displaced/clashing controls are geometric counterchecks, not
measured inactive compounds. Contacts measure proximity, not hydrogen bonds.
Scores are not affinities or evidence of cellular inhibition. This does not
produce audited p-values or promote a candidate through the human-review gate.

The surface is marching tetrahedra on the union of vdW spheres inflated by a
1.4 Å solvent probe, locally selected within 8 Å. Its algorithm, source frame,
0.6 Å grid spacing and triangle-to-atom map are exported. Finite grid resolution
and the pocket-local selection limit its accuracy. It is approximate SAS, not SES.
CA tubes, distance-inferred display bonds and luminous atom envelopes are
illustrative representations. No optional dynamics trajectory is generated.

## Observed validation

Two real three-seed runs of the frozen 3VQU protocol completed. The initial run's
best-ranked scores were approximately −8.73, −8.69 and −8.66 kcal/mol; none recovered
the deposited ligand within 2 Å. This is a negative exploratory benchmark, not a
reason to tune the metric after observing results. See the exported report for
all poses and each seed's result.

[The PDAC study](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0174863)
provides a TTK target rationale with heterogeneous cell-line responses to AZ3146.
The [3VQU structure](https://www.rcsb.org/structure/3VQU) contains O22, a different
compound. Docking O22 does not reproduce the AZ3146 cellular experiment.

Actual image-bearing review of the first workbench PNG identified occlusion by
bright backbone traces and foreground atoms. A clipped second view, subdued
traces and reduced display clutter improved ligand visibility. The model chose
a grounded O22 N2 / GLN670 OE1 countercheck; canonical prepared-receptor measurement
was 2.713622 Å, supporting proximity without assigning a hydrogen bond. The journal
links both captures, the requested view change, the measurement and review outcome.

The rendering is demand-driven with instanced atom meshes and bounded geometry.
50k-atom/60-fps and laptop/mobile throughput remain performance targets requiring
hardware-specific measurement; they are not claims established by the small
3VQU software-rendering validation.

## Playback and hands-on use

The transport below the molecule replays actual source-scoped operation receipts,
including docking, captures, image review and measurement, rather than treating
camera bookmarks as a trajectory. The slider tracks presentation seconds; idle
gaps use 6–10 second animated operations, with a separate original-recorded-timing option. Pause, seek, step backward
or forward and change speed from 0.5–8×. Expand **Activity & evidence** to read
observations and jump to an operation. Every supported operation has an approach, reveal/construction, and inspection phase. Camera motion and annotations are sampled continuously; ligand poses remain discrete scientific outputs. Reduced-motion users get immediate
camera changes. Sparse histories remain sparse; no extra actions are fabricated.

Choose **Explore myself** to restore your own view after watching. Drag to orbit,
scroll to zoom and select atom pairs for labelled distances. **Clear selection**
starts another measurement. The pose gallery changes the actual mapped geometry,
including when leaving a prepared-receptor comparison. Deposited-reference
measurements use deposited coordinates; docked-pose measurements use the prepared
receptor. Nearby receptor bonds and a muted backbone keep the ligand readable.

The Docking tab provides preparation/search fields and **Reuse last docking
protocol** for an existing experiment. Review the rationale and explicit additive
exclusions before submitting; advanced JSON remains available. Failed jobs show
the scientific error in the panel, and running jobs show their current stage.
Reusing a protocol is a new computational attempt, not independent biological
replication. A fresh standalone demo has operator-generated results; it does not
claim an agent authored a workflow until an agent actually records its operations.


## Animated operations and node embedding

[Watch the recorded action-animation review](inhibitor-review/action-motion.md).

Follow agent is the initial mode. Each real receipt drives a deterministic visual
sequence: structure/pocket approach and proximity tracing; recorded preparation
change highlights; the declared docking-region outline and presentation scan;
real first-ranked pose overlays; a ruler drawn between the selected atoms; or
capture framing with the actual recorded image. The activity note remains the
agent's original note. These sequences describe inspection work, not molecular
dynamics or an invented optimizer trajectory. Added/removed atom markers and pose
overlays come from the completed bundle; a pending job cannot reveal future poses.

The animation clock supports seeking within an operation and 0.5–8× playback.
Result loading pauses playback and the start of a live Follow sequence.
Animated presentation compresses waits into 6–10 second sequences; Original
recorded timing retains receipt intervals and settles a completed visual sequence
while a long wait continues. Reduced motion uses the final view immediately.
Pointer-down takes control immediately; returning to Follow starts from the
currently displayed camera. Capture-pinned scene revisions remain exact static
views for scientific image inspection.

`InhibitorWorkbench` accepts optional `embedded={true}` alongside its existing
artifact, scoped geometry URL, owner, experiment ID and close callback. Embedded
mode mounts in place without a portal or body-scroll lock and keeps detailed
controls in an overlay. The node workspace should mount one selected inhibitor
artifact, keyed by its immutable hash; it owns the adjacent real activity feed.
