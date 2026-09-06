# Native spindle runtime review

The engineering pilot actually ran the pinned 3D Cytosim worker through the registered
runtime dispatcher and published its trajectory and numerical ensemble metrics into
its owning experiment. It used one seed, two initial centrosomes, 32 filaments per
aster, 1 s duration and 0.1 s sampling. Control and fixed cortical-motor conditions
shared initial geometry. These are upstream-scale engineering assumptions, not PDAC
calibration. Both conditions remained two-pole controls; that is not evidence of a
centrosome-clustering intervention effect.

A linked scientific follow-up used four initial centrosomes with the same seed,
other parameters and frozen classifier. Both conditions retained four poles at
1 s, with zero bipolar dwell and right-censored clustering time. The receipts
include its complete protocol and numerical outputs; neither short pilot supports
a biological motor-effect conclusion.

The production capture script opened that actual experiment; it substituted no
fixture or API response. The scope, specification/recipe/capture hashes, actual
camera/viewport, native numerical output, served renderer assets and image-bearing
model observations are in [the receipts](spindle-review/receipts.json).

The developer opened the actual draft, revision, final single-cell and final
comparison PNGs through the image tool, and opened the ten-view browser fixture
contact sheet. Independent runtime inspections passed exact immutable PNG bytes to
`llm.acomplete(images=[...])`, retained image-linked observations, and informed
subsequent view/rendering changes. A textual filename was not used as a substitute.

| Pass | Visible finding and resulting change |
|---|---|
| [Draft](spindle-review/draft.png) | The cell rim clipped the viewport. Capture readiness could acknowledge pre-expansion dimensions. Camera fitting and current-canvas readiness were corrected. Opaque label boxes obscured filaments. |
| [Revision](spindle-review/revision.png) | The complete silhouette fit. Label boxes were subsequently removed; nonselected filaments brightened and the broad core halo reduced. A small open-shell patch looked like an unexplained dark ellipse, so the default cortex became a complete translucent shell. |
| [Comparison](spindle-review/comparison.png) | Both native conditions use identical camera/lens and saved physical time. The initial comparison had unequal caption typography; count, condition and time labels now match, with centered shared units/provenance. |

Vision observations were treated as visual evidence, not unquestioned truth. Some
suggestions to normalize apparent pole size or recenter an off-center aster were
not applied: perspective and actual simulated positions must remain intact. Tiny
native pole movements can make enabled amber tracks difficult to see. No missing
motor-force, chromosome or viability measurements were inferred from pixels.

Accepted here: the scoped native capture/see/revise workflow, pole identity and
balanced two-condition engineering comparison. Remaining full-plan work includes
independent motor/filament and timestep validation, source-audited calibration and
held-out assessment, motor-field presentation, broader dense-ensemble/cinematic
review and measured performance on reference hardware. This record does not certify
those remaining scientific or visual milestones.
