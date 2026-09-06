# Donor-level cellular ecosystems

**Research route cancelled and plan deprecated, 2026-09-06.** Insufficient accessible independent eligible donors left the biological power gate unmet. Models, data, results, audits and reusable code are preserved. The workflows below document retained capabilities; they do not authorize further research or autonomous resumption. See the [deprecated plan](../plans/evalue-tool-council/PLAN-cellular-ecosystems.md).

The `ecosystem` command implements exposed development preparation, separate
compartment count encoders, donor profiles, exploratory coupling/comparison and
segmented-cell spatial summaries. Private registration/scoring is an operator
surface that uses the [shared native core](native-evidence.md). Public Peng and Lin development count cohorts have been acquired and audited,
and real compartment models trained and evaluated; see the [initial training report](ecosystem-training.md).
The [expanded CUDA run](ecosystem-expansion.md) adds Werba, Steele and Zhang: 72 donor
records, 338,900 prepared cells, three-seed neural models and exact GPU PCA controls.
Confirmation remains unavailable; the research route is cancelled.

## Development workflow

Install normally, then run `ecosystem --help`, or use
`PYTHONPATH=src uv run python scripts/ecosystem.py --help` from the repository.
PCA uses NumPy; optional NB/set training requires the `evalue` extra (Torch).
Source preparation and figure export use the `ecosystem` extra (SciPy/Matplotlib/h5py).
For historical GPU training reproduction, see the [expanded workflow](ecosystem-expansion.md#reproduce);
its CUDA-only scripts include GPU PCA and hold the shared GPU lease. The original
CLI examples below describe the earlier CPU-capable artifact format. Expanded
checkpoints use a separate development schema and are not native registrations.

```sh
ecosystem prepare --input training-csr.json --output training.npz
ecosystem prepare --input development-csr.json --output development.npz
ecosystem train --input training.npz --compartment malignant --components 32 \
  --cells-per-donor 64 --output malignant.npz
ecosystem train --input training.npz --compartment fibroblast --method nb \
  --components 32 --epochs 20 --cells-per-donor 64 --output fibroblast.npz
ecosystem profile --input development.npz --model malignant.npz \
  --states state-a,state-b --cells-per-donor 64 > malignant-profile.json
ecosystem evaluate --input development.npz --model malignant.npz \
  --states state-a,state-b --cells-per-donor 64
ecosystem couple --left malignant-profile.json --right fibroblast-profile.json
ecosystem compare --left population-a-profile.json --right population-b-profile.json
```

State names are externally frozen ontology selections, not biological labels
inferred by these commands. Train each compartment independently. `couple`
requires different compartments from the same assay population. `compare`
requires the same model, states and measurement rule and disjoint donor sets;
paired tissues are rejected. Both return development effects without calibrated
evidence. The profile includes mean/variance embeddings, within-compartment
occupancy, entropy, representative expressed genes, individual cell embeddings,
coverage/missingness and deterministic disjoint-half subsampling instability.
Gene examples are descriptive mean expression, not inferred causal programs.

`evaluate` reports donor-held-out reconstruction error, coverage, measurement
stability and whether the development accession is unseen. Compare PCA and NB
using the same externally selected training genes, independent held-out donors,
assay and cell budget. Reconstruction alone does not establish transferable
biological utility or a confirmatory power advantage. No trained model is shipped.

## Count and source contract

Preparation input is JSON with `data`, `indices`, `indptr` (canonical CSR cell ×
gene arrays), `genes` (unique ordered strings), `cells` and `manifest`. Each cell
has `cell_id`, `accession`, `specimen`, `compartment`, `state`. Every manifest has:

- `schema: ecosystem-counts-v1`, `scale: UMI counts`;
- `population`, `organism`, `tissue`, `assay: scRNA|snRNA`, `ontology`,
  `state_dictionary`, `sampling_justification`;
- `specimen_rule: one-preselected-specimen-per-donor`;
- `sources`: unique accession records with `accession`, `license`,
  `access_status: verified-local`, `role: training|development`, `sha256`;
- `crosswalk`: unique accession/specimen records with canonical `donor`,
  `timepoint`, and operator-attested `identity_reviewed: true`.

This schema validates the operator's audit record; it cannot establish consent,
licensing or donor independence from strings or booleans. The operator must
reconcile aliases across studies, releases, atlas components, organoids and
modalities before preparing input. Raw-source checksums identify externally
verified source bytes; the tool additionally hashes the complete prepared
counts/metadata. It does not fetch or automatically verify upstream sources.
[The source inventory](ecosystem-sources.json) records verified Peng/Lin/Werba/Steele/Zhang development
inputs and unresolved/reserved alternatives. Original counts, source hashes,
donor crosswalks, all-gene library offsets and preparation reports remain local
under `data/interim/ecosystems/`; acquisition never downloads reserved Hwang data.

One preselected specimen per donor is supported in release one. Multiple lanes
or cells within it remain nested measurements. Repeated specimens/sections need
another explicit measurement version. Overlapping training/development roles,
unresolved crosswalks, missing labels, negative/fractional counts, duplicate CSR
indices, zero-library cells encountered during inference and unsupported assays
fail closed. Prepared NPZ artifacts have non-pickle arrays and bounded headers,
expansion and dense batch sizes. The complete atlas is never densified; PCA caps
its training gene covariance at 4,000 genes.

`min_cells` must be positive and no greater than `cells_per_donor`. The stricter
fixed subsample size determines eligibility: donors below it are unavailable,
not zeros. Sampling uses donor/compartment/seed-derived ordering and unique cell
IDs. Repeated subsamples do not increase donor n. Whole-tissue composition,
shared cell totals and library sizes are excluded from association view vectors.
They can still affect the measurement indirectly; this is not a proof against
capture-depth or complete-case selection bias.

Models require exact gene order, assay, ontology and state dictionary at
inference. No imputation, joint integration, transductive labeling or implicit
scRNA/snRNA transfer is performed. These strict checks deliberately reject
unreviewed transfer. Training genes and labels must be selected using training
or exposed development information, never private donors.

## Count model and compute

PCA uses measured-library log1p normalization and equally many cells per donor.
The optional NB model learns a modest tanh cell encoder and softmax decoder,
negative-binomial dispersion and masked-gene reconstruction loss. Decoder rates
are multiplied by each cell's measured all-gene library size; an extra residual
bin accounts for counts outside the selected gene panel. This corrected artifact
is `ecosystem-nb-v2`; older v1 count artifacts are rejected rather than silently
reinterpreted. Preparation records `library_size_rule: measured-all-genes` and
integer `library_size` on each cell; that rule and offsets remain frozen at inference. Each model sees one
compartment only. Inference uses frozen NumPy arrays; its safe artifact includes
training donor/source identity, losses and execution provenance. It is an
implementation of a count reconstruction model, not the existing TPM encoder
or a claim of equivalence to scVI. The default aggregation remains frozen mean/variance/occupancy. A small
permutation-invariant set encoder was trained using same-compartment donor-summary
reconstruction and subbag stability, but underperformed the summary PCA baseline
in the real pilot. `profile --set-model FILE` can expose its experimental embedding
alongside the default summary, with the frozen cell/set model hashes. It does not
change the default coupling vector or select private evidence after scoring.

The initial NB implementation caps 100,000 training cells, 4,000 genes, 64 latent
dimensions, 20 epochs, batch size 512 and two hours. It reports throughput, peak
host RSS and peak reserved GPU memory; nonfinite loss, projected overrun or
reserved memory above 32 GiB stops without saving a model. These are pilot caps,
not simultaneous GPU reservations. GPU runs additionally require `--device cuda`
and `--lease-path /operator/shared/gpu-training.lock`. All GPU training tools on
that host must honor the same operator-managed lock; different paths do not
coordinate. A process-held flock releases on worker exit rather than expiring
a live lease. CPU is the default. No 12-hour expansion is supported in this CLI.

## Spatial development

`ecosystem spatial-profile --input spatial.json` accepts exposed development
segmented single cells only. The JSON declares `role: development`,
`resolution: segmented-single-cell`, assay, segmentation hash, coordinate units,
positive radius, two compartments, frozen state panel, and
`specimen_rule: one-preselected-section-per-donor`. Each cell has unique
`cell_id`, canonical donor, section, compartment, state, measured `xy`, and
`identity_reviewed: true`. Each anchor in the first compartment receives the
state distribution of second-compartment cells within the radius. Outputs are
one donor summary plus neighborhood coverage and within-donor dispersion.
No neighbors means unavailable coverage. GeoMx, mixed spots, dissociated cells
without coordinates and multiple sections per donor are rejected. Dispersion
is not an independent-cell confidence interval. Spatial confirmation is absent.

## Private operator workflow

Discovery calls only:

```sh
ecosystem register --registration REGISTRATION_SHA256 --request-id stable-id \
  --endpoint http://private-service:8797
```

A configured service durably accepts syntactically valid references with the
same receipt shape regardless of eventual eligibility, unknown registration,
failure or wealth. There is no HTTP result/status/export route. Worker stdout
and stderr are discarded by `experiment_transport`; errors/results stay in the
private queue. Registration retries and new aliases cannot reset evidence.

The operator, under a separate filesystem/service identity, runs
`configure-private --state DIR --input private-design.json`, then
`serve-private --state DIR`. Configuration is immutable. It contains:

- `ledger_directory`: absolute common private ledger path used by **all** tools
  in the investigation, required for cross-tool canonical donor exclusion;
- `spec`: the exact [native process specification](native-evidence.md), with
  first null `independence-of-measured-malignant-and-fibroblast-states`, population
  `untreated-primary-human-PDAC`, frozen separate views and critic;
- `observations`: ordered records `{donor, x, y}` whose canonical JSON hash
  equals `spec.data_hash` and whose donors equal `spec.eligible_donors`;
- `gates`: operator-reviewed identity, access, sampling, transfer, selection,
  privacy and novelty records (`approved`, reviewer, artifact SHA256), plus
  predeclared power evidence (`null_streams >= 10000`, `alpha: 0.05`,
  `power_lower_bound >= 0.8`, matching `available_donors`, artifact SHA256).

The operator must inspect the referenced reports: entering a hash is not
independent validation. Gate approval is not part of discovery submission.
The private operator's evidence export is
`export-private --state DIR --receipt ID`. Aliases resolve to the same result.
The baseline uses `fully-frozen-v1`, storing explicit null optimizer/RNG state.
After separate design and power review, the operator can opt into the shared
`past-block-bilinear-sgd-v1` schedule: each block is scored with its prior critic,
then deterministic SGD updates only from that consumed block. Scored and next
critic state commit atomically. This option is not a measured ecosystem power
advantage. Append requests through HTTP remain unsupported; only the private
core advances fresh locked blocks.
Odd final donors contribute no factor. Never multiply unrelated processes.

Private storage must be inaccessible to discovery through actual service/OS
permissions, including logs, journals, artifacts and recall. Launching both
surfaces as the same user does not enforce privacy. These commands do not
configure that deployment boundary or modify the graph, falsifier, human
promotion gate or branch-success monitor.

## Validation and remaining release gates

```sh
PYTHONPATH=src uv run python scripts/simulate_ecosystems.py --output /tmp/ecosystem-simulations.json
uv run pytest tests/test_ecosystem.py tests/test_native_evidence.py
```

The seeded CPU diagnostic runs 10,000 independent streams per condition at
18, 24, 40, 60 and 100 donors, including nonlinear/rare-state coupling, low-cell
dropout, capture noise, batch confounding, missing-compartment selection,
shared denominators, current-block memorization and cell pseudoreplication.
Frozen linear/nonlinear/RBF critics use equal donor budgets. Reports preserve
final/anytime rejection, Wilson intervals and detection-delay histograms with
noncrossers. Confounded/selected scenarios are stress tests, not valid raw
biological-independence nulls.

The default seed's 130 conditions yielded valid-null anytime rejection between
0 and 1.11%, final rejection between 0 and 0.52%; the best tested 18-donor
alternative had only 0.67% anytime rejection. These diagnostics do **not**
meet the 80% power gate or validate a real cohort. Deliberately invalid controls
are labeled and never offered as evidence methods.

Real-data donor/source preparation and separate compartment training/comparison
are now completed for development. Still required before confirmation: independent
review of the reserved cohort and sampling, resolved untreated status/assay transfer,
a predeclared assay-specific alternative with adequate power, deployment privacy
audit and a separately authorized sequestered pilot. No confirmation donor
counts, spatial donor inventory, learned advantage or accepted discovery are
claimed by this implementation.
