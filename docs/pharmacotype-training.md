# Pharmacotype real-development model card

Run date: 2026-09-06. This pilot trained on measured public PRISM/CCLE data.
It establishes a reproducible development baseline, with no PDO confirmation
result or demonstrated clinical utility. Full trial values and model hashes are
in [training results](pharmacotype-training.json); exact public source hashes,
licenses, panel and aggregate exclusions are in [source audit](pharmacotype-sources.json).
Matrices, crosswalks and model artifacts remain in ignored local data directories.

## Data and frozen design

Acquired the secondary dose-response release from [PRISM 19Q4](https://api.figshare.com/v2/articles/9393293),
expression from [DepMap 19Q4](https://api.figshare.com/v2/articles/11384241), and
publisher PatientID mapping from [DepMap 24Q4](https://api.figshare.com/v2/articles/27993248).
The releases declare CC BY 4.0. Downloads verify publisher MD5; the audit records SHA256.
RNA is log2(TPM+1). Response is source ComBat-adjusted log2 fold-change versus
DMSO, not fraction viability. Source technical replicates are already median
collapsed, so replicate variation is unavailable rather than zero.

The four-drug panel was chosen from treatment metadata before reading response
values: gemcitabine, irinotecan, oxaliplatin and paclitaxel, each with eight
source doses converted from micromolar to molar and 120-hour exposure. Preferred
MTS010 oncology redos follow the source readme. No 5-FU substitution was made.
Among 588 PRISM rows and 1,249 expression rows, require STR-passing metadata,
resolved publisher PatientID, and the lexicographically first model per patient.
Choose that model before testing curve completeness; an incomplete preferred
model does not trigger selection of a different derivative.

This yields 356 complete patient-origin groups: 245 training, 40 validation,
71 test. All 22 pancreatic groups belong to test. Other groups use the frozen
SHA256 PatientID bucket rule recorded in the audit. Top 1,000 finite genes are
selected by training-only variance; fill, centering, scaling and PCA use training
only. Publisher identifiers are not independently reverified biological identity.
Complete-case selection, pooled screens and cohort ComBat make this development
data unsuitable for the independent-donor confirmation process.

## Training and results

Separate molecular and response encoders use identity, PCA or a masked tanh
autoencoder; neither encoder consumes the other view. Latent dimension 32,
ridge penalty 10, seeds 0/1/2, maximum 150 epochs, validation patience 15.
The GPU pilot trained both encoders and a bounded matched/crossed bilinear critic.
Architecture selection compares average validation RMSE across all three seeds,
without selecting a seed or using test errors. Identity/PCA are deterministic
controls; repeating seeds does not create independent experimental replicates.

| Model | Validation curve RMSE (three-seed mean) | Test curve RMSE (three-seed mean) |
| --- | ---: | ---: |
| Standardized identity + ridge | 1.1387 | 0.9964 |
| PCA + ridge | 0.9936 | 0.9583 |
| NumPy masked MLP + ridge | 1.0776 | 0.9716 |
| Torch/CUDA masked MLP + ridge | 0.9969 | 0.9501 |

PCA remains selected. GPU seed test RMSE varies from 0.9133 to 0.9717; the best
test seed cannot be selected retrospectively. The training-mean baseline test
RMSE is 0.9594. On the 22 pancreatic groups, PCA RMSE is 0.9692 versus 0.8994
for the training mean: this pilot does not establish PDAC predictive utility.
Per-drug held-out RMSE and descriptive predicted/observed log-dose-mean Spearman
correlations are in the machine-readable report. They are exploratory outcomes.

The serial L40S pilot used Torch 2.10.0+cu128, 25,926,144 peak allocated bytes
and 31,457,280 reserved bytes (30 MiB). Total training per seed was 2.663 seconds
including first-use overhead, then 0.459 and 0.465 seconds; effective training
donors/second are approximately 92, 534 and 526 for the complete paired-model
pipeline. These are pipeline throughput, not per-epoch examples/second. Peak
host RSS was 1,217,148 KiB. CPU PCA took about 0.10 seconds; NumPy MLP about
0.82–0.88 seconds. NumPy SGD and GPU Adam differ, so these measurements do not
establish GPU acceleration. The common `/tmp/dnhacks-gpu.lock` lease covered
each GPU trial, with a 600-second outer timeout and five-minute per-view limit.
No concurrent GPU experiments were launched.

## Reproduction

```sh
python scripts/build_pharmacotype_data.py --download --raw data/raw/pharmacotype --output data/interim/pharmacotype --public-audit docs/pharmacotype-sources.json
OPENBLAS_NUM_THREADS=2 python scripts/train_pharmacotype.py --data data/interim/pharmacotype --epochs 150
# On the verified GPU host with the optional Torch environment, use a separate
# copy of development.json and splits.json so CPU model artifacts are retained:
python scripts/train_pharmacotype.py --data data/interim/pharmacotype/gpu --backend torch --device cuda --epochs 150
python scripts/report_pharmacotype_training.py --data data/interim/pharmacotype --output docs/pharmacotype-training.json
python scripts/validate_pharmacotype_adaptive.py --output docs/pharmacotype-adaptive-validation.json
```

The acquired prepared development format has an integrity hash, matrix-shape
checks and explicit source/contract provenance. It cannot enter confirmation
preparation. Hashes detect alteration, not malicious re-signing. The original
CPU report predates addition of backend resource metadata; its recorded artifact
hashes refer to those actual runs. Timings and hashes will vary on reproduction.

## PDO access and scientific release

The Tiriac primary molecular record is [dbGaP phs001611.v1.p1](https://www.ncbi.nlm.nih.gov/projects/gap/cgi-bin/study.cgi?study_id=phs001611.v1.p1).
It requires authorized access and a data-use certification, and includes normal
and tumor material. Its 71 consented subjects are not a usable endpoint count.
The [author-hosted publication](https://escholarship.org/content/qt50b3r2ms/qt50b3r2ms_noSplash_b6e236520590c29f129b0938c8cf7cf9.pdf)
is accessible; publication availability does not provide paired raw curves and RNA.
A public [reanalysis notebook](https://github.com/Urogenus/GDSC_Pancreatic_study/blob/main/pancreatic_RNAseq_prediction.ipynb)
references local Pancreatic_RNAseq_tpm.csv, viability.csv and metadata.csv, which
are absent from that repository's public tree. Prediction files are not original
paired measurements. External notebook code and pickle files were not executed.

[Driehuis EGA EGAD00001005217](https://ega-archive.org/datasets/EGAD00001005217)
requires DAC approval and lists noncommercial use restrictions. Its 31 sequencing
samples do not establish independent PDAC donors with complete curves. Reserved
confirmation outcomes remain unopened. No access application was submitted on
behalf of an institution. An authorized paired PDO dataset is still required
for the first scientific endpoint; this cell-line pilot cannot substitute for it.

Adaptive diagnostics use 10,000 streams per case at a synthetic 32-donor budget.
Anytime rejection: IID null 0.01%, heavy-tail null 0.10%, simple alternative
35.52%, nonlinear alternative 0%. The [report](pharmacotype-adaptive-validation.json)
includes Wilson intervals and detection delays. Production scalar arithmetic
is cross-checked against every batched diagnostic step. Existing
[frozen diagnostics](pharmacotype-validation.json) separately cover deliberately
invalid shared-control, current-block fitting and pseudoreplication controls.
The proposed 80% power target is unmet. No audited fresh PDO denominator, reviewed
sampling/normalization proof, or deployed private OS boundary is claimed. These
remain explicit scientific release requirements rather than manufactured results.
