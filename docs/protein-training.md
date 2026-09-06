# Protein development training record (scratch baseline, superseded below)

The first real development run used the public LinkedOmics CPTAC pan-cancer
`data_freeze_v1.2` tumor protein matrices. It was CPU-only and completed before any
GPU request. BRCA (122 donors) and COAD (97) were the TRAIN cohorts; LUAD (110) was
the whole-cohort VALIDATION set; PDAC (105) was reserved as DEV. No Fudan data,
grade labels, or confirmation source entered the run.

The source files are the published log2 reference-intensity matrices. Version
suffixes were removed from feature IDs and duplicate canonical IDs retained their
first row. I selected the 2,000 highest-coverage features using TRAIN only, filled
missing values with TRAIN feature medians, then fit TRAIN center/scale and a seeded
32-component randomized PCA. Validation used the frozen transform. The exact
machine-readable record is [protein_pca_real.json](../data/interim/protein/protein_pca_real.json)
and the numerical artifact is `protein_pca_real.npz` (both local, gitignored data).

Measured results:

- TRAIN donors: 219; VALIDATION donors: 110.
- Feature coverage after selection: TRAIN 100.0%, VALIDATION 99.45%.
- PCA fit time: 0.33 seconds; peak process RSS: 283,852 KiB.
- TRAIN reconstruction MSE: 0.1691; VALIDATION reconstruction MSE: 1.7295.
- PC1 explained variance: 52.16%; 32-component cumulative variance is recorded in the JSON artifact.

The large train/validation reconstruction gap is a transfer warning, not evidence
of a useful encoder. It likely reflects cohort and assay/reference differences. The
next development step is to compare fixed module means and a frozen rank/PCA baseline
against the masked denoiser on donor-disjoint data, with no cross-cohort alignment.
The PCA run does not establish the grade endpoint, native wealth, independent sampling,
or 80% minimum-effect power. This scratch artifact is superseded by the reproducible
exact-identifier import and measured GPU pilot below.

## Reproducible measured run

Run `protein-s10-20260906-v2`, 2026-09-06: 219 TRAIN cases (BRCA+COAD), 110 whole-cohort
VALIDATION cases (LUAD), and 105 DEV cases (PDAC). No confirmation matrices accessed.
The importer rejects duplicate feature/header IDs and cross-cohort case overlap,
preserves exact versioned identifiers, joins every case to metadata, and selects
2,000 features using TRAIN coverage only (descending coverage, identifier tie break).
Case IDs do not establish raw specimen/aliquot/run independence; those mappings,
upstream normalization and treatment are explicitly unaudited. Raw data stays local.

```sh
uv run python scripts/build_protein_data.py --raw data/raw/protein --output data/interim/protein/new-run
uv run python scripts/train_protein_encoder.py --train data/interim/protein/new-run/train.json --validation data/interim/protein/new-run/validation.json --output data/interim/protein/new-run/pca.npz --max-features 2000
# Run on the GPU host with Torch installed, in a fresh job directory:
timeout 1800 python scripts/train_protein_encoder.py --train data/interim/protein/new-run/train.json --validation data/interim/protein/new-run/validation.json --output data/interim/protein/new-run/denoiser-seed0.npz --kind denoising --max-features 2000 --latent 32 --epochs 50 --seed 0 --device cuda
uv run python scripts/evaluate_protein_models.py --data data/interim/protein/new-run --raw data/raw/protein --panel data/interim/protein/new-run/panel.json --output data/interim/protein/new-run/comparison.json
```

CUDA acquires `/tmp/dnhacks-gpu.lock` with `flock` for the full training call;
there are no child training processes or heartbeat expiry. PyTorch allocation is
capped at 16 GiB and elapsed time checked each epoch. The shared host availability
check remains required. No unprofiled concurrent GPU jobs are permitted.

The denoiser used width 256, latent 32, seed 0, 20% corruption, 50 epochs, selecting
checkpoints with a fixed mask of hidden observed validation entries. Evaluation
uses another fixed mask. PDAC labels never enter encoder training/selection.
L40S training took 3.704 seconds including preprocessing/loading within the fit call;
mean epoch 0.01789 seconds. Peak CUDA allocation: 53,716,992 bytes; reserved:
73,400,320 bytes; process peak RSS: 1,386,036 KiB (includes Torch/CUDA runtime).
The best checkpoint was epoch 50, the tested budget boundary; convergence and
exhaustive model search are not claimed. The GPU lock was released after the run.

| Frozen reconstruction | Hidden-entry standardized MSE |
| --- | ---: |
| Training feature mean | 2.9318 |
| PCA, 32 components | 1.8243 |
| Masked denoiser | 2.1067 |

Rank-PCA hidden-entry MSE was 0.06665 versus 0.08173 for its training-mean baseline,
in rank units, not comparable to abundance MSE. PCA outperformed the tested denoiser;
no neural advantage is demonstrated. All prediction views use identical five
stratified donor folds, fixed hyperparameters and fold-fitted scaling:

| View and classifier | Out-of-fold PDAC grade AUROC |
| --- | ---: |
| Fixed module means, linear | 0.6607 |
| Missingness only, linear | 0.5959 |
| Abundance, linear | 0.7623 |
| Abundance, RBF kernel | 0.6563 |
| Frozen PCA, linear | 0.7027 |
| Frozen denoiser, linear | 0.6262 |
| Frozen rank-PCA, linear | 0.7816 |

These are development diagnostics, vulnerable to purity, assay and missingness.
The measured PDAC grades are G1=6, G2=72, G3=26, unknown=1: 104 graded cases,
but only 26 grade pairs before any treatment exclusions, below the 48-pair policy.
No subgroup substitution or threshold reduction is made. Module identifiers come
from the Ensembl symbol API with response hashes; ambiguous version mappings stay
unresolved. The fixed mitotic module's standardized grade difference was 0.4791;
the simulation minimum effect is frozen at 0.4 before running power sweeps. This
development estimate is not a causal effect or a confirmatory lower bound.

`data/interim/protein/curated-v2/` contains `audit.json` (URLs, hashes, bytes, joins),
cohort JSONs, `pca.npz`, `denoiser-seed0.npz`, `panel.json` and `comparison.json`
(fold identities, hidden-entry losses, retrieval stability and module coverage).
Both encoder artifacts load through `ProteinEncoder.load` and work with the CLI.

The [Fudan primary study](https://link.springer.com/article/10.1186/s13045-022-01384-3)
reports treatment-naive primary tumors and pathologist-assigned grades. Its published
matrix is cohort-filtered (detection in at least one sixth of samples), and prior
analyses already concern proliferation. Raw proteomics is deposited as IPX0002796002.
The subsequently authorized [external benchmark](protein-external.md) downloaded
the Fudan clinical/protein supplements and evaluated CUDA-fitted source-only models.
It found 65 grade pairs, or 60 after the fixed 80% coverage filter. This resolves
the external sample-count shortage; untouched-cohort history and per-sample
processing/sampling review remain necessary for confirmation. No raw mass spectra
were reprocessed.
