# Spindle observatory

Implementation is in progress. The first milestone adds a selected-experiment
Three.js viewer for immutable `filament_trajectory` artifacts and exploratory
clustering analysis. It does not yet run Cytosim, provide calibrated mechanics,
register an audited method, or deliver captures to a research vision agent.

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
This bounded display format is not yet the planned lossless chunked solver archive.

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
Classifier parameters must be frozen before running comparisons; durable plan
registration will be part of the job milestone.

Browser fixtures are explicitly illustrative and remain under `frontend/e2e`.
The actual app does not offer fabricated example experiments. Run the spindle
browser test with `SPINDLE_REVIEW_PASS=draft|revision|final` to save matching views
under `/tmp/spindle-<pass>-*.png`. The development visual review is recorded in
`docs/spindle-visual-review.md`. Remaining plan milestones include production
scene/capture contracts, cancellable Cytosim execution, calibration/held-out
assessment, a real runtime vision loop, performance and accessibility acceptance.
