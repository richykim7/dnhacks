# Real-expression validation

Open [the standalone report](index.html) or use the [SVG](wealth.svg) / [PNG](wealth.png) in slides.
This is a diagnostic comparison on one observational cohort, not a clinical or causal claim.

## Data and frozen protocol

Source: [GSE212041](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE212041), neutrophil bulk
RNA-seq TPM, GRCh38/GENCODE v35, RSEM 1.3.0. Downloads are pinned by SHA-256 in the preparation
script and [manifest](manifest.json). No raw sequencing is downloaded. All data/model files and
donor-level replay stay in ignored `data/processed/evalue-real/`; these tracked reports contain
aggregate outputs only.

The source includes 781 longitudinal samples. We keep 374 unique day-zero donors: 299 COVID-positive
and 75 symptomatic COVID-negative. We exclude healthy controls and all later/event-driven draws.
The source's donor labels support deduplication; they do not establish absence of confounding or
prove independence between patients.

A fixed stratified 40%/20%/40% split (floored train/development counts) yields:

| Partition | COVID+ | Symptomatic COVID− | Purpose |
| --- | ---: | ---: | --- |
| Training | 119 | 30 | Gene selection, preprocessing, PCA and autoencoder |
| Development | 59 | 15 | Device timing only; no architecture/epoch tuning |
| Evaluation | 121 | 30 | Primary comparison, declared order sensitivity, artificial null audit |

Training-only log1p(TPM) variance selects 19,000 human genes. PCA uses 64 components. The masked
encoder uses 19,000 → 512 → 128, mirrored decoder, 15% masking, 100 epochs, batch size 64, Adam
learning rate 0.001 and seed 20260905. It runs on CUDA in float32; its frozen weights load on CPU.
The decoder is used during training and is not included in the inference artifact. Different latent
widths mean this is not an isolated comparison of architecture at equal representation size.

## Measurements

[Training record](training.json): PCA fitting 0.22 s; GPU autoencoder fitting 3.41 s on an NVIDIA
L40S. Masked training MSE fell from 1.1001 to 0.1161. This is training loss, not a held-out
reconstruction/generalization estimate. Small-cohort fitting time excludes downloading/transferring
inputs and setting up the environment.

[Device benchmark](device-benchmark.json): after one warm-up per device, the same development
comparison took 0.194 s on CPU and 0.355 s on CUDA. Maximum log-path difference was 1.78e-15.
The small bettor therefore uses CPU/float64; the encoder was actually trained on GPU.

The primary seed 20260906 was fixed before outcomes. Each method gets the same selected 30 pairs;
91 positive evaluation donors are unused in that comparison. The bettor has 64/64 ReLU layers,
maximum 100 epochs per update, patience 10, lr 0.0005 and weight decay 0.01. Four pairs per batch:
eight burn-in pairs, 22 scored pairs, six scoring batches including a final partial batch.

| Method | Final e-value | Final ≥ 20 | Ever ≥ 20 |
| --- | ---: | --- | --- |
| Learned encoder | 3,652.81 | Yes | Yes |
| PCA | 85.76 | Yes | Yes |
| IFIT3 scalar | 5,964.41 | Yes | Yes |
| Calibrated permutation | 99.00 | Yes | N/A |

The ordinary mean-distance permutation p-value is 0.0001, its minimum at 9,999 random permutations
with the plus-one correction. Its statistic uses the frozen standardized 19,000-gene matrix, not
the learned representation. This compares evidence methods; the scalar null is only about that
specified feature. No evidence source was selected after seeing the results and no values are merged.

Ten additional predeclared seeds examine order/subsample sensitivity on the same held-out donors.
Final rejections: learned encoder 9/10, PCA 5/10, scalar 8/10. These are correlated reuses of one cohort,
not independent power estimates or confidence intervals. The primary result remains the original
seed even if another ordering produces stronger evidence. Learned features exceed PCA in this
comparison, while the simpler scalar has greater final evidence in the primary run.

## Conditional real-expression null

Fix 75 disjoint unordered pairs among the evaluation donors (one donor unused), then assign each
pair an independent fair orientation. Preserve that pair stream with `pairing="in_order"` so
past training never contains either member of a future pair. Clinical labels are not used in this
artificial null and are not assumed randomized. Repeat with 200 independent sign draws.

| Representation | Final rejections | Ever crossed | Crossing rate, pointwise Wilson 95% interval |
| --- | ---: | ---: | --- |
| Learned encoder | 0/200 | 5/200 | 2.5%, 1.07%–5.72% |
| PCA | 0/200 | 4/200 | 2.0%, 0.78%–5.03% |
| IFIT3 scalar | 0/200 | 0/200 | 0%, 0%–1.88% |

This is a conditional fairness audit on real feature geometry, not validation of clinical
exchangeability. Final wealth is extremely skewed: observed sample quantiles do not establish its
expectation. An early threshold crossing and a small final e-value can both occur in the same run.
The full real evaluation took approximately 268 s in the initial run; final rerun timing is in
[evaluation.json](evaluation.json). No claim of biological power or universal encoder superiority.

## Reproduce

```sh
uv sync --extra dev --extra evalue
uv run --no-sync python scripts/evalue_real_data.py prepare
# Run on a CUDA host; transfer only the prepared split files/manifest and task source.
uv run --no-sync python scripts/evalue_real_data.py train
uv run --no-sync python scripts/evalue_real_data.py benchmark
uv run --no-sync python scripts/evalue_real_data.py evaluate --device cpu
```

For the measured GPU environment, create a separate Python 3.12 venv and install
`numpy==2.4.6`, pandas and pytest, then `torch==2.10.0` from
`https://download.pytorch.org/whl/cu128`. Recorded package versions and artifact identities take
precedence over whatever versions a future dependency resolver chooses. Source hashes and the
split/protocol manifest detect changed inputs; bitwise training replay across Torch/CUDA versions
is not promised. Use the existing local GPU launcher; never copy its connection information or keys
into commits. Large files are not automatically available in another checkout or on another host.

Figure rendering needs matplotlib (also declared by the repository's `litmap` extra):

```sh
python scripts/evalue_report.py research/learned-evalue-validation/real-expression/evaluation.json research/learned-evalue-validation/real-expression
```

The existing falsifier, primary p-value path and family-wide testing decisions remain unchanged.
[Process and slide notes](../../../docs/learned-evalue-process.md) explain the adaptation and remaining
contracts for application integration.
