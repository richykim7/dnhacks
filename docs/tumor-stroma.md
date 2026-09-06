# Living tissue

The instrument implements native conditional simulation, immutable frame collection, the selected-
experiment theater, scoped agent tools, recorded scene-action playback and actual PNG-bearing review.
The165-run source-grounded sensitivity demonstration, analytical/replay checks and actual image-
review workflow completed. The image inspection report records the full native capture set and
capacity measurements. The60/30fps targets are not met on the tested SwiftShader host; hardware-
accelerated throughput remains unverified. No biological validation or deployment is implied.

The model uses PhysiCell 1.14.2 at `dbd3499250141b27600e91e501c54c46f68f2763` and bundled BioFVM.
Build with `dnhacksbio.tissue.engine.build_engine(source, destination)` after cloning that exact
revision from https://github.com/MathCancer/PhysiCell. A compiler/executable/source receipt is saved.
The adapter runs in one CPU thread, with a bounded duration, grid, step count and wall time.
Cancellation preserves an explicit incomplete record and incomplete conditions cannot be collected.

Geometry is assumed: a 92 µm radius tumor spheroid with 356 fixed tumor centers and 95 surrounding
CAF centers in a 320 µm cube. Tumor volume changes continuously without cell division or migration.
Secretion, uptake and an outer Dirichlet alanine concentration drive BioFVM. An assumed saturating
uptake-support law controls volume and accumulated damage; dead cells remain explicitly identified.
The model excludes treatment delivery, redox and other CAF mechanisms. The defaults are exploratory
assumptions and have not been fitted to measured biological outcomes.

The default CAF shell has radius 126 µm and x offset 15 µm. `build_model` also accepts an explicit
question and geometry: tumor_radius_um (30–100), caf_shell_um (at least tumor radius+10, at most140),
caf_count (1–500), caf_offset_um (0 through150 minus shell radius). All geometry is illustrative
model geometry, never a reconstructed biopsy. Source physical radii are authoritative; elongated
CAF shapes and procedural membrane normals are separately identified presentation choices.

| Quantity | Default | Origin / interpretation |
| --- | --- | --- |
| Alanine diffusion | 300 µm²/min | Assumed effective tissue coefficient; not fitted |
| CAF secretion coefficient | 0.1 min⁻¹ | Assumed BioFVM source coefficient, saturation1 mM |
| Tumor uptake coefficient | 0.01 min⁻¹ | Assumed sink coefficient; suppression multiplies by0.05 |
| Outer alanine | 0.05 mM | Assumed low-nutrient scenario, not a measured TIF estimate |
| Growth coefficient | 0.0005 min⁻¹ | Assumed volume law |
| Support threshold | 0.3 | Assumed dimensionless threshold |
| Support / damage | `(uptake/0.01)*A/(A+0.1)`; death when integrated deficit>120 min | Assumed response law; no SLC38A2 mechanistic calibration |
| Extracellular rescue | 1 mM with secretion off | Transferred from in-vitro alanine supplement context, not fitted |

Frozen scientific cutoff:2026-01-25. Full paper narrative and methods were read for refs9,18,21:
[Sousa et al.](https://doi.org/10.1038/nature19084),
[Sullivan et al.](https://doi.org/10.7554/eLife.44235), and
[Parker et al.](https://doi.org/10.1158/2159-8290.CD-19-0959).
Raw source hashes and context are retained in numerical-validation.json. These studies motivate
exchange and transporter controls. Bulk TIF measurements cannot identify secretion/uptake rates;
transporter loss has additional metabolic effects omitted here. The reported lack of a significant
cleaved-caspase increase in ref21's initiation tumors is specifically not evidence for our death law.

Conditions are CAF secretion on/off, tumor uptake at normal/5% levels, their combined perturbation,
and extracellular-alanine rescue with secretion off. Initial positions are paired by computational
seed. Endpoints include living tumor count/volume, radial survival and field summaries. All output
uses `analysis_class: simulation_sensitivity`; no p-value or biological sample size is generated.

The declared 11 scenarios vary secretion, uptake, boundary nutrient, CAF spacing and abundance,
using three computational seeds and all five controls (165 native runs). Seed0 reference living
volume is1,163,804 versus1,109,441 µm³ with secretion off (about4.9% difference); both have356
living tumor cells. At the declared0.01 mM boundary,57 survive with secretion and0 without.
At1 mM boundary, the secretion effect is negligible. The low-boundary case is selected for
visual explanation because it exhibits partial conditional rescue; the other scenarios remain
in the report. This selection is not a new calibrated prediction or a biological significance test.

Analytical closed-domain diffusion maximum errors fall from0.0018509 to0.00074473 to0.00031966 mM
as spacing/timestep refine40/1→20/0.5→10/0.25 µm/min. Relative mass errors are below1.6×10⁻¹⁵.
Same-binary, same-seed frame replay matched exactly. Native endpoint refinements preserve356 living
cells and give1.1615–1.1648 million µm³ volume; local field maxima remain grid-sensitive and should
not be interpreted as resolved subcellular measurements. See the
[numerical report](tissue-review/numerical-validation.json) and [plot](tissue-review/sensitivity.png).

Reproduce (local publisher source text stays uncommitted):

```sh
uv run python scripts/validate_tissue.py --engine /path/to/tissue-build/tissue \
  --corpus /path/to/pdac-frozen --output /path/to/new-validation-output
uv run --with matplotlib python scripts/plot_tissue_validation.py \
  --report docs/tissue-review/numerical-validation.json --output /tmp/tissue-sensitivity
```

An experiment output `manifest.json` declares `{kind: "tissue_simulation", path: "tissue.json"}`.
The collector checks finite values, dimensions, units, IDs, time order and quotas before converting
frames to immutable JSON cell chunks and little-endian float32 field chunks. The main manifest
contains dimensions, chunk hashes and metadata. `/api/runtime/<run>/tissue/<hash>?condition=0&frame=0`
uses the same exact-run, project and replay-cursor containment check as blob delivery.
Fields use x-fastest order and right-handed micrometer coordinates. The browser uses exact frames
and nearest-voxel sampling; it does not infer birth/death between frames.

The viewer requests `part=metadata` and `part=field` separately; the latter is bounded little-endian
float32 data, avoiding large JSON field inflation. Chunk hashes alone do not grant public blob access.
The parent manifest, exact run and cursor must authorize each request. Mobile groups over2000 cells
by location/type/state, conserving counts and occupied volume and retaining every member ID. Selecting
a group restores individual source cells. Mobile volume rendering uses at most64³ block-mean voxels;
inspection/analysis and the exact diagnostic slice use the original arrays.

Agent entrypoint: `get_skill tissue-interface`, then runtime action `tissue` with experiment_id,
operation and args. The CLI is `scripts/tissue_tool.py`; both use the same scope checks. Model specs,
bounded detached CPU jobs (maximum two), cancellation records, analyses, scene recipes, captures,
pixel observations and critiques are durable. `TISSUE_ENGINE` points to a built executable with its
matching build.json. `TISSUE_RENDER_URL` is the trusted local serving origin. The capture worker
navigates the real project/run/experiment API, renders the production component and decodes actual
PNG pixels before publication. It kills browser descendants after errors/timeouts. Missing/flat
canvas pixels or failed vision cannot produce a completed visual review.

Users can watch agent scene actions at0.5–4×, scrub them, independently explore physical-time frames,
and restore their own view. User interactions never mutate the recorded agent history. Saved PNG
figures include common legends/units and a recipe sidecar. Stored agent captures and observations
are expandable within the owning experiment, subject to the investigation replay cursor.

Large populations use lower tessellation and24 volume steps without discarding cells. The original
small native demonstration retains its membrane detail. Normal scene captures do not run a moving-
camera performance test; only the explicit benchmark does. Figure recipe exports include the exact
artifact SHA-256 and numerical analysis. The focused Neighborhood view centers the selected source
cell and clips at its surface, using the same35µm source-distance neighborhood calculation.

Reproduce capacity measurements with `uv run python scripts/benchmark_tissue.py --output /tmp/new-capacity`.
It records a separate status for each profile, preserving an unavailable result if a bounded capture
fails. See [performance and visual interpretation](tissue-review/README.md); successful rendering is
not evidence that the frame-rate target passed.

The scene inspector exposes a shared fixed field maximum and exact-voxel diagnostic; saturated
voxels are counted. The diagnostic labels the actual voxel-center z as well as the requested plane.
The3D cutaway is a half-volume, not a thin histological section. Whole-volume cell counts are labeled
explicitly. A hidden field in the initial Exterior view establishes geometry; it is not a nutrient
result. Use Core/Comparison and numerical sampling to examine outcomes.

An isolated actual-runtime demonstration (no production changes):

```sh
TISSUE_ENGINE=/path/to/tissue-build/tissue uv run python scripts/demo_tissue_scene.py \
  --output /tmp/new-tissue-demonstration --corpus /path/to/pdac-frozen \
  --boundary 0.01 --vision --all-views
```

It serves only its isolated project/journal on8924 while capturing. `--reuse` repeats visual review
of an existing collected artifact without rerunning the native model. No tissue result enters the
audited verification pipeline or changes production deployment state.

Visual revisions are documented in [the inspection record](tissue-review/README.md).
