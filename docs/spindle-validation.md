# Spindle source audit and calibration boundary

The frozen full text, figure legends and references of corpus papers 34, 36, 54,
57 and 62 were read before selecting the coupled-model validation protocol.
The upstream tutorial values and earlier native stress probes remain explicit
engineering assumptions. They were not inferred biological force constants.

| Source | Supported role | Consequence for this implementation |
|---|---|---|
| [34: centrosome amplification in PDAC](https://doi.org/10.1080/15384101.2015.1068478) | Disease context and centrosome phenotype | Does not identify motor rates or establish patient calibration. |
| [36: CEP215–HSET](https://doi.org/10.1038/ncomms11005) | Centrosome–spindle-pole attachment and HSET's distinct motor/tail roles | The symmetric minus-head crosslinker is a provisional interaction; it does not reproduce CEP215 attachment or HSET. Centrosomes and spindle poles are different observables. |
| [54: KIF24 depletion](https://doi.org/10.26508/lsa.202201470) | Perturbation phenotype in PDAC | Does not identify a change in microtubule growth/shrink rates as its mechanism. |
| [57: cortical dynein](https://pmc.ncbi.nlm.nih.gov/articles/PMC10208098/) | A planar stochastic model and experimental clustering reference | Its 2D model, dynamic cortical distribution, longer observation window and classifier cannot silently become validation of this 3D model. Code is described as available upon request. |
| [62: kinesins after WGD](https://doi.org/10.26508/lsa.202402670) | Cell-line heterogeneity and opposing motor hypotheses | KIF11/KIF15 and KIFC1 have distinct roles. Protein abundance is not a direct motor-activity measurement. Our current model lacks the opposing plus-end motors needed to test that proposed balance. Primary data are described as available upon request. |

Paper 62 measures three-dimensional intercentrosomal distances and distinguishes
1:3 and 2:2 arrangements; its four-shortest-distance summary differs from the
all-pair and connected-component metrics here. These summaries must not be mixed
as if they were the same measurement. Its perturbation concentrations cannot be
substituted for the motor-activity parameter.

## Prespecified numerical study

The coupled-aster engineering study uses 16 independent simulation seeds and four
conditions: two centrosomes without cortical motors, four without cortical motors,
four with sphere-direction-uniform anchors and four with a positive-x crescent.
The latter three share initial centrosome positions and motor/filament parameters.
The same seed is used across conditions and three timesteps (0.002, 0.001 and
0.0005 s); this matches initial random draws but does not imply identical stochastic
paths after a timestep or intervention changes.

Every run lasts 2 s with 0.1 s saved sampling. Clustering uses a 1 µm connected-
component threshold, 0.5 s sampled dwell, and thresholds 0.5, 1.5 and 2 µm for
sensitivity. Initial filament length, binding range/rate and counts are engineering
stress assumptions. No short trajectory is extrapolated to completed mitosis.

Before execution, equivalence margins were fixed for final mean pairwise distance
(0.25 µm), total filament contour length (5 µm), bound cortical count (2), and
bipolar dwell fraction (0.1). The fine-minus-middle paired-seed mean and approximate
90% Student-t interval are compared with these margins. Failures and inconclusive
intervals remain in the report; an interval crossing a margin does not establish
convergence. This is a small numerical diagnostic, not a biological confidence
interval or a guarantee over the full parameter space.

## Biological calibration is unavailable

There is no compatible audited training/held-out observation set for the current
3D interaction model in these inputs. The published cell-line endpoints and 2D
simulation cannot identify its several motor, drag and dynamics parameters.
No fitted biological parameter, held-out PDAC accuracy, drug efficacy or biological
sample count is reported. A numerical stability result cannot fill that gap.
A future compatible observation set needs source-linked units, matching model
observables, independent training/held-out groups and an identifiability assessment.

## Observed coupled-model result

All **192/192 native runs completed**, and initial centrosome coordinates matched
across timesteps for every paired seed. The numerical equivalence criterion is
**not established**: final filament-length intervals cross the prespecified
±5 µm margin in every condition. Distance, cortical binding and bipolar dwell
meet their individual tolerances. This points to insufficient precision in the
stochastic length endpoint; it does not establish a systematic timestep bias or
justify relaxing the margin after looking at these results.

| Condition | Fine − middle total length, µm | Approximate 90% interval, µm |
|---|---:|---:|
| Two centrosomes, no cortex | 1.444 | −3.257 to 6.146 |
| Four centrosomes, no cortex | −2.459 | −8.956 to 4.037 |
| Four centrosomes, uniform directions | 2.552 | −3.649 to 8.753 |
| Four centrosomes, crescent | −0.263 | −6.074 to 5.547 |

The [complete report](spindle-validation.json) retains all runs, endpoint values,
configuration/output hashes, frozen design and primary source hashes. The
[interval plot](spindle-validation.png) shows each endpoint against its original
margin. This result remains exploratory and inconclusive. It is not a successful
calibration or a held-out biological validation.

Reproduce with the pinned operator build and the report's `plan` object:

```sh
uv run python scripts/validate_spindle_ensemble.py --plan plan.json \
  --binary-dir /absolute/pinned/bin --build-manifest build.json --output new-study
uv run python scripts/validate_spindle_ensemble.py --assess new-study/report.json
```

The command returns nonzero when numerical equivalence is not established.
It bounds each native command and the total study, retains failed/missing cells,
and never silently reruns a failed seed or converts simulation seeds into biology.

## Native ensemble display and visual review

The finest-timestep subset contains 64 native runs. Its complete scientific JSON
is 52,423,587 bytes; the separate display is 14,820,452 bytes and retains source
frames `[0, 4, 8, 12, 16, 20]` from each 21-frame run. Every pole, filament and motor
field within those samples is preserved. Full-resolution metrics and lossless
scientific chunks remain separate from the sampled view. The runtime collection
was an explicit operator import of the completed study, not a native-worker receipt.

The initial [comparison capture](spindle-review/validation-draft.png) exposed
overlapping C3/C4 labels. Screen-space placement now separates labels from each
other and from projected pole cores, with leader lines preserving their measured
locations. The [revised capture](spindle-review/validation-labels.png) was inspected
with the original. The final review also inspected [front](spindle-review/validation-front.png),
[detail](spindle-review/validation-detail.png), [oblique](spindle-review/validation-final.png)
and [mobile](spindle-review/validation-mobile.png) images. All four pole identities
are readable; the detail view deliberately crops the shell while the full views
preserve its silhouette. Mobile uses one full-size comparison cell at a time,
with the same physical clock and camera in both views.

[Capture states](spindle-review/validation-captures.json) retain the exact scene
recipes and capture identifiers. This is a developer review of actual rendered
pixels, not a model-generated scientific verification or biological validation.
