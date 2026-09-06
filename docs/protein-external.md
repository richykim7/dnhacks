# Prospective protein external benchmark

Authorized follow-up, 2026-09-06. Before opening the Fudan quantitative supplement,
freeze the following evaluation choices. The published cohort is an external
benchmark, not an untouched confirmation cohort; its prior analyses and joint
processing remain part of the interpretation.

Primary endpoint: published poorly differentiated/G3 versus well/moderately
differentiated/G1/G2 primary PDAC tumors. Exclude unknown or incompatible histology,
retain one measured tumor per canonical patient, and do not count adjacent tissue,
technical replicates or existing CPTAC reanalyses as additional independent cases.
Report every exclusion and both grade-group counts before claiming a pair budget.

Freeze source/annotation hashes, deterministic unambiguous gene matching and
within-sample transforms before external prediction. Do not fit external-label
thresholds, scalers, feature selectors or model hyperparameters. Reference-normalized
CPTAC and label-free Fudan are distinct assays: existing encoders may only be used
where their input contract is satisfied. A separately named rank-transfer baseline
can test a specified cross-assay hypothesis without silently overriding that contract.

Compare missingness, fixed mitotic/stress/integrin modules and fixed 32-component
rank/PCA representations. Fit supervised heads using CPTAC development grades only;
all supported fitting, including ranks, centering and scaling, runs on CUDA under
the shared full-worker GPU lock. Small evaluation summaries run locally after fitting.
Prespecify regularization and seed before scoring external outcomes. Report external
AUROC and uncertainty, balanced accuracy at the source-fixed threshold, measured
coverage and purity/missingness sensitivity. Keep every prespecified view in the
report, including failures and incompatible views. Search additional independent
cohorts if actual counts do not meet the retained 48-pair floor. More cases alone
do not settle sampling, processing, power or independent-review requirements.

Frozen numerical configuration before external scoring: seed 0; at most 2,000
unambiguously matched genes with TRAIN detection at least 80%, plus available
fixed-module genes; within-donor average percentile ranks and fixed 0.5 for missing
ranks; 32 TRAIN-fitted PCA components. Supervised heads are balanced ridge
classifiers with penalty 1, fitted only on CPTAC grades. Report raw rank, rank-PCA,
fixed-module and missingness views, plus an RBF rank kernel with gamma 1/feature-count
and ridge penalty 1. Primary readout is rank-PCA AUROC; no view or sign is selected
using external grades. Existing abundance/PCA and denoiser artifacts remain
assay-incompatible and are not silently transformed into these models.

## Acquired data and measured external result

The primary [Tong et al. study](https://link.springer.com/article/10.1186/s13045-022-01384-3)
provides clinical Supplement 23 and quantitative Supplement 25. The clinical table
has 229 unique patients. All 226 tumor columns in the 7,055-protein table map
one-to-one to patient IDs and experiment IDs. Their grades are 159 poorly
differentiated, 65 moderately differentiated and two unknown: **65 grade pairs**.
The study's methods specify primary PDAC without prior chemotherapy/radiotherapy.
Its 217 tumor/adjacent pairs are a different count; adjacent tissues are not new
patients and are not used in this grade comparison. The published protein table
uses cohort-wide detection filtering and FOT normalization, so it is a benchmark,
not an untouched sequential confirmation source.

HGNC approved Ensembl IDs and unambiguous previous symbols supply the frozen bridge;
duplicate CPTAC versions or conflicting symbols are excluded, never kept arbitrarily.
Annotation files come from the [official HGNC download](https://www.genenames.org/download/).
The model uses 2,000 TRAIN-selected/mapped genes. Nine fixed-panel genes are present:
PPP1R12A, PPP1CB, GSK3B, ATM, HMOX1, GPX4, ITGB1, ITGA5 and PTK2. Other requested
panel genes remain unresolved/unmeasured under this strict bridge.

All five views were specified before scores were inspected. Every head was fitted
on the 104 graded CPTAC cases; PCA used the separate 219 non-PDAC TRAIN cases.
Fudan grades were stored separately and never transferred to the GPU worker.
The L40S fit/prediction call took 0.620 seconds, excluding Python/Torch startup,
with peak CUDA allocation 29,251,072 bytes. No CPU fitting or large host training
tensor expansion was used. A first attempt failed before fitting on an object-dtype
identifier array; the successful input archive uses explicit Unicode and loads
with pickle disabled. The shared lock was released when the worker exited.

| Prespecified view | AUROC, all 224 graded tumors | 95% stratified bootstrap interval |
|---|---:|---:|
| Rank-PCA (primary) | 0.552 | 0.471–0.634 |
| Linear rank model | 0.588 | 0.506–0.674 |
| Fixed modules | 0.491 | 0.410–0.576 |
| Missingness | 0.480 | 0.401–0.565 |
| RBF rank kernel (secondary) | 0.694 | 0.625–0.764 |

The fixed 80% measured-feature coverage filter retains 199 graded patients:
139 G3 and 60 G2, hence **60 independent grade pairs**. Kernel AUROC there is
0.712 (0.637–0.782). Rank-PCA remains weak at 0.549. At the source-fixed decision
threshold, kernel balanced accuracy is only 0.554; this is encouraging ranking
transfer, not a ready calibrated grade classifier. Grade prevalence differs across
cohorts; published categories do not prove identical grading practice across
institutions. Kernel scores correlate with
pathologist purity (Spearman 0.266); subgroup diagnostics are included, not adjusted
away by fitting on external outcomes. Intervals condition on the frozen model and
observed cases; they do not cover source-model selection or multiple comparisons.
The primary model did not demonstrate transfer. The secondary kernel result is a
promising follow-up candidate requiring a further independent evaluation before
making a selected-model confirmation claim. No result was flipped, and no external
threshold, hyperparameter or model was fitted after seeing scores.

Machine-readable records: [source audit](protein-external-audit.json),
[GPU training](protein-external-training.json), [all results and sensitivity checks](protein-external-results.json).
Local numerical artifacts are under `data/interim/protein/external-v2/`:
`inputs.npz`, `external-labels.json`, `result-v2/model.npz`,
`result-v2/predictions.npz`, `result-v2/training.json`, and `comparison.json`.
Raw copyrighted/data supplements stay local under `data/raw/protein/fudan/`.

## Reproduce

```sh
uv run --with openpyxl python scripts/build_protein_external.py --raw data/raw/protein/fudan --cptac data/raw/protein --curated data/interim/protein/curated-v2 --output data/interim/protein/new-external
# Transfer only inputs.npz and the evaluation script to the GPU worker:
timeout 1800 python scripts/evaluate_protein_external.py --inputs inputs.npz --output result
```

The CUDA script acquires `/tmp/dnhacks-gpu.lock` for its complete worker lifetime
and rejects a host without CUDA. Use a unique job directory and a 16-GiB allocation
cap; CPU is limited to source parsing, serialization and small metric summaries.
After freezing/pulling the predictions, call
`protein_external.summarize(root, predictions_path, new_report_path)` locally.
It joins all donor IDs exactly, reports fixed 50% purity strata and 80% coverage
sensitivity, and uses 2,000 stratified bootstrap resamples with seed 20260906.
These summaries never refit a model. Do not reuse this evaluated cohort as unopened
confirmation data in a subsequent model-selection cycle.
