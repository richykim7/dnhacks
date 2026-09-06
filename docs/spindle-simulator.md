# Spindle observatory

Implementation is in progress. The viewer renders selected-experiment immutable `filament_trajectory` artifacts.
A scoped durable worker now executes a pinned Cytosim 3D aster model and exports
raw trajectories, float64 chunks, display frames and prespecified clustering
analysis. It does not yet provide calibrated mechanics, register an audited
method, or establish biological validity. Scoped runtime captures and image-bearing vision review are available.

A `manifest.json` artifact entry uses `kind: filament_trajectory`, `format: json`,
and ordinary artifact provenance. Category is `illustration` for illustrative
trajectories or `derived_geometry` for simulations. The collector rejects
mismatched provenance, invalid units/dimensionality, nonfinite coordinates,
duplicate replicate/entity identities, missing filament owners, oversized
geometry, and symlink paths. Existing journal storage and scoped playback blob
routes preserve experiment ownership and event visibility.

The JSON bundle has schema version 1, category `illustration` or `simulation`,
model_id, dimensionality 2 or 3, units `{length: um, time: s}`, cell `radius`
(three positive semiaxes), and `runs`. Each run has a seed, condition and sampled
frames. A frame contains physical time, poles (`id`, `position`) and filaments
(`id`, owning `pole`, ordered `points`). Geometry must remain planar when marked
2D. No interpolation invents coordinates between samples or across entity births.
The bounded JSON display format is separate from the lossless exported-coordinate
chunks and raw solver archive described below.

Select the owning experiment in Investigations and expand the spindle scene.
Choose a condition/seed, front/oblique/detail camera, filament treatment and
centrosome. Picking isolates its aster; the readout measures saved physical
coordinates. Condition switching chooses the nearest recorded physical time and
preserves camera state. Saved frames are manually stepped, including under reduced
motion. `data-scene-ready` becomes true after shader compilation and an explicit
render; exported PNGs require that revision to be ready. Local PNG export is not
an immutable runtime capture or proof that a model viewed pixels.

`spindle.analysis` computes distance-connected components, exactly-two-pole onset
with prespecified sampled dwell, censoring, pairwise distances, final pole-count
distributions, replicate dwell dispersion and threshold sensitivity. Single-pole
collapse is distinct from bipolarity. Simulation seeds are the replicate unit;
no biological sample count, p-value or verification submission is manufactured.
Classifier parameters are frozen into the content-addressed protocol before
execution; changing them creates a different specification hash.

Browser fixtures are explicitly illustrative and remain under `frontend/e2e`.
The actual app does not offer fabricated example experiments. Run the spindle
browser test with `SPINDLE_REVIEW_PASS=draft|revision|final` to save matching views
under `/tmp/spindle-<pass>-*.png`. The development visual review is recorded in
`docs/spindle-visual-review.md`. Remaining plan milestones include independent
mechanical convergence/interaction validation, calibration/held-out assessment,
final performance/accessibility acceptance and a broader scientifically assessed ensemble.


## Frozen numerical model

`spindle.protocol.prepare_spindle_experiment` accepts a complete
`spindle_protocol.v1` document. `PARAMETERS` in that module defines required
parameters and numerical safety bounds, not plausible biological intervals.
Every parameter includes value, source and assumed/measured/fitted status.
The protocol records model/source versions, 3D um/s/pN units, explicit ellipsoid
semiaxes, simulation seeds, control/perturbation initial positions, motor counts
and localization, and clustering threshold/dwell/sensitivity choices. No PDAC
parameter preset is bundled. The upstream-scale values in the regression tests
are engineering fixtures only.

The stock Cytosim objects are confined dynamic microtubules, aster solids,
fixed cortical minus-end motors and symmetric minus-end motor crosslinkers.
The worker passes the seed on the native command line before Cytosim initializes
its random generator; setting it in the configuration alone is too late in this
release. The crosslinkers are an explicitly provisional motor hypothesis; they do not
encode the full CEP215–HSET mechanism. Chromosomes, segregation, viability,
Eg5/KIF15 antagonism, dynamic dynein relocalization, drug concentrations and gene
knockdowns are not represented. The model is distinct from paper 57's planar
model. Initial aster geometry and the native random seed are matched when
conditions share the declared initial state; stochastic trajectories can diverge.

Cortical positions use equal-area directions on a sphere, mapped to ellipsoid
semiaxes. `uniform` means uniform solid-angle sampling, **not** uniform ellipsoid
surface-area density. `positive_x_crescent` maps those directions to the positive
X cortex. Motor activity begins at the initial time. Raw configuration records
all anchor positions. Conditions and seeds are not independently calibrated
biological replicates. Source linking records provenance without proving that a
parameter is identified or calibrated.

## CPU build

The tested source commit is `0780e265cb6a2bb3536c6f89d2143ba9bb016ff0` from
[the authors' repository](https://gitlab.com/f-nedelec/cytosim).
Their [build documentation](https://gitlab.com/f-nedelec/cytosim/-/blob/master/doc/compile/index.md)
describes BLAS/LAPACK and terminal library prerequisites. Pin that commit, apply
`src/dnhacksbio/spindle/cytosim-report-precision.patch`, then build:

```sh
cmake -S <cytosim-source> -B <build-dir> -DDIMENSION=3 -DMAKE_PLAY=OFF -DMAKE_PYSIM=OFF -DMAKE_TESTS=OFF
cmake --build <build-dir> --target sim report --parallel 2
```

The export-only patch sets precision on the actual output stream; upstream's
`precision=17` otherwise left that stream at its default precision. It changes
no force or integration code. Record binary SHA-256 hashes, source commit,
dimensionality, compiler/flags and patch hash in an operator-owned build manifest.
The executed pilot record is `docs/spindle-build-pilot.json`. It proves a 3D build
and small engineering export, not model convergence or biological calibration.
Local development extracted missing system-library packages under `/tmp` and
supplied CMake library locations; it installed no global packages and used no GPU.

## Job operations

`uv run python scripts/spindle_tool.py request.json` reads a JSON object with
`action`, `args`, and (for durable operations) a `store` directory. Operations:

- `prepare_spindle_experiment`: `args.protocol`; returns frozen `spec_ref` and
  bounded step/frame/replicate estimate. Wall time is explicitly unmeasured.
- `run_spindle_experiment`: complete protocol, scope containing project_id,
  run_id and experiment_id, idempotency_key, and budget containing integer
  wall_seconds (1–1800) and artifact_bytes (1024–209715200). Returns a queued
  receipt. Identical retries reuse it; changed science/budget under the same key
  is rejected.
- `status`: receipt, scope and optional event cursor `after`. Returns state,
  timestamp, cancellation state, progress and immutable artifact references.
- `cancel`: receipt and scope. Queued jobs cancel immediately; the active worker
  checks cancellation while supervising its process group and before publication.
- `analyze_spindle_ensemble`: receipt, scope, and `analysis_plan_ref` (SHA-256 of
  canonical sorted compact JSON for the frozen analysis plan). Requires a complete
  ensemble and refuses an unregistered analysis change.
- `export_artifact`: receipt, scope and new output directory; writes the runtime
  artifact manifest plus display JSON for the existing experiment collector.

The explicit operator worker is separate from submission:

```sh
uv run python scripts/spindle_tool.py worker-request.json --worker --sim /absolute/build/bin/sim --report /absolute/build/bin/report --build-manifest build-manifest.json
```

Its request has `store` and `args` containing receipt and scope. The manifest must
match the actual executable bytes and declared pinned 3D commit. Binary paths
and build approval are operator configuration, never numerical-protocol fields.
This does not install the worker into the existing experiment execution environment.
It runs at most one job per store, enforces wall time and disk-output limits,
records accepted frames only after validating exports, terminates the whole child
process group on cancellation/timeout and preserves bounded partial files.
An interrupted worker is not automatically rerun: an operator verifies the old
process is gone, then calls `SpindleStore.interrupt(receipt, scope, reason)`.
A new idempotency key starts an explicit fresh run. Store timestamps distinguish
recorded state from worker liveness; `running` alone is not proof of a live process.

## Archives and verification

Completed and failed jobs have scoped immutable `archive.json` records linking
protocol, build, configuration, stdout/stderr and file hashes. Raw `objects.cmo`
and `properties.cmp` are retained byte-for-byte. Reports retain exported stable
IDs and explicit native filament-to-aster ownership. The importer verifies every
expected frame and native physical clock; missing frames never yield invented
completion. `trajectory.json` is a bounded browser stream. `chunks/index.json`
indexes per-frame little-endian float64 positions, offsets and entity IDs, exact
checksums/bounds and sampled filament presence. These chunks are lossless relative
to exported coordinates; no claim is made that the upstream binary format stores
more precision than it actually does. Metrics are exported as JSON and CSV.

The worker rejects incomplete ensembles for analysis/export. Failure and resource
exhaustion remain distinct from clustering failure. Numerical/biological validity
is not inferred from a successful process exit. There are no generated p-values,
biological sample counts, verification verdicts or automatic graph promotion.

```sh
uv run pytest tests/test_spindle.py
SPINDLE_CYTOSIM_BIN=/absolute/build/bin uv run pytest tests/test_spindle.py
```

The second command enables a real two-condition native CPU execution test; without
the operator build it skips explicitly. Tests cover protocol determinism, matched
initial poles/filaments, physical clocks and 3D displacement, receipt ownership and
idempotency, duplicate execution rejection, failure archives, active cancellation,
timeout process-group termination and lossless/corrupt binary chunks.

## Runtime integration and visual review

The explorer's `spindle` action requires delivered `spindle-interface` guidance.
It derives project/run ownership from the active researcher. Numerical preparation,
submission, status/cancel and frozen-plan analysis are registered operations. The
operator sets `SPINDLE_CYTOSIM_BIN` and `SPINDLE_CYTOSIM_BUILD` to the pinned native
build directory and build-manifest file; the runner launches a separate bounded
worker and collects its actual trajectory and numerical metrics into the selected
experiment. An experiment ID cannot change its specification, idempotency key or
budget. A new ID plus `parent_experiment_id` links a scientific follow-up. Receipt
retries do not relaunch a worker. Operator recovery remains explicit for interrupted
processes; native jobs remain exploratory and do not create a statistical RESULT.

`open_scene`, `set_scene_view`, `capture_scene`, `inspect_scene_capture` and
`record_visual_review` now operate on collected trajectory hashes. Immutable
recipes retain adapter/scope/source, parent revision, shot, treatment, selection,
sampled frame/run, trails, comparison and camera. Historical cursors cannot reveal
future recipes/captures. Obsolete or concurrently changed recipes cannot publish
captures. A recorded review requires an image-bearing observation; the vision
worker receives exact scoped PNG bytes through the tested SDK images parameter.
Visual revisions do not change numerical protocols or outputs.

Captures open the actual owning experiment through Playwright, apply a bounded
controller view, wait for shader/render readiness and current canvas dimensions,
and save PNG plus actual camera, physical time, pole positions, viewport/DPR,
browser version and hashes of served JavaScript/CSS. `SPINDLE_SCENE_BASE_URL`
selects a trusted local workspace server (default `http://127.0.0.1:8765`). No
fixture substitution occurs in that renderer. Pixel observations and review
verdicts remain separate from numerical measurements and statistical verification.

The viewer checks artifact SHA-256, labels persistent poles, offers synchronized
comparison with identical cameras, and restores a lost graphics context on request.
Agent scene actions have their own follow/replay selector, separate from saved
physical time and human exploration. Numerical ensemble tables report every seed,
censoring, final pole counts, dwell variability and sensitivity; one simulation
seed has no across-seed SD estimate. The native review log records the real
see/revise workflow and its remaining visual/scientific limits.

Isolated native motor direction/speed and unopposed filament growth now pass three
timestep refinements; see [measured mechanics probes](spindle-mechanics.md). This
does not establish convergence of the coupled spindle model.

Native exports now include cortical anchors, bound filament identities, abscissae
and force vectors in pN; the viewer shows the saved anchors and a measurement
table. Every anchor is checked against its prescribed surface position at every
frame. [Motor-field validation and the earlier placement erratum](spindle-motors.md)
explain why original origin-anchored runs are unsuitable for localization comparisons.

The runtime can now export bounded, scoped WebM movies from exact saved frames;
see [movie delivery and measured rendering](spindle-movie.md). GPU draw time is
reported separately from full frame-update, screenshot and encoding costs. The
reference interactive frame-rate target is not yet certified.

## Full scientific data and bounded display

Larger native ensembles retain every scientific frame in lossless float64 chunks
and compute metrics before display sampling. The separate JSON display keeps all
conditions/seeds and every entity/coordinate within selected frames, always including
first and last samples. Its explicit source-frame mapping and full-trajectory hash
are recorded in the display artifact, and the viewer identifies the sampled count; no filament thinning or interpolation is introduced.
A native regression reconstructs the complete source hash from the archived chunks.
If even the endpoints exceed display limits, the job reports that limit explicitly.
Zero-temperature native runs use an explicit absolute solver tolerance of 1e-6;
finite-temperature runs retain the existing upstream tolerance behavior.

The [source audit and 192-run numerical assessment](spindle-validation.md) records
an inconclusive total-filament-length convergence result. No biological calibration
or held-out PDAC accuracy is claimed.

Clustered pole labels use deterministic screen placement and leader lines to the
unchanged measured coordinates. Mobile comparisons show one full-size cell at a
time with Selected run / Comparison run controls; both views retain the shared
physical time and camera. Desktop comparisons remain side by side.
