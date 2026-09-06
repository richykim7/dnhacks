# Pharmacotype development and private association

`python -m dnhacksbio.pharmacotype` provides reusable development operations on
operator-prejoined baseline RNA and complete single-agent response curves. No
cohort is bundled. Outputs describe measured assay profiles or development
predictions, never patient benefit probabilities, synergy or mechanism.

The implementation provides bounded CPU and optional Torch/CUDA training: separate identity/PCA or
compact masked-reconstruction tanh encoders, a ridge curve predictor, and a
bounded bilinear critic trained on matched versus crossed development donors.
Real PRISM/CCLE training and three-seed GPU evaluation are recorded in the
[model card](pharmacotype-training.md). PCA remains selected; the learned model
did not reproducibly improve validation error. The shared core supports an opt-in
past-block critic update. The scientific PDO confirmation pilot remains gated.

## Development input

A JSON document has schema `pharmacotype.data.v1`, role `development`, and:

- `genes`: unique ordered gene identifiers; `panel`: ordered objects with
  `compound`, `formulation`, and at least two increasing positive `doses` in M.
- `assay`: `version`, `technology`, source `scale`, `media`, `seeding`,
  `vehicle_control`, `positive_control`, `molecular_sampling`, `population`,
  `source_sha256`, `license`, positive `exposure_hours`, `dose_unit: "M"`, and
  assay-specific finite `response_bounds: [lower, upper]`.
- `aliases`: source origin → canonical patient-origin identifier, including
  canonical self-mappings. Chained or unresolved aliases are rejected.
- `selected_cultures`: canonical donor → prespecified eligible baseline culture.
- `cultures`: objects with `origin`, unique `culture`, `passage`, `baseline_time`,
  ordered `rna` (JSON null marks missing genes), and `responses`.
  Each response has `compound`, molar `dose`, `plate`, `run`, `pool`, `replicate`,
  and finite `value`. Use explicit `unpooled` when appropriate.

Keep all nested cultures in source records. Selection cannot be based on observed
responses. Repeated wells are not independent donors. Within each dose, average
technical replicates within a run/plate, then weight plates equally. Require the
entire registered curve; no interpolation, extrapolation or panel substitution.
Exclusions, replicate standard deviations and observed log-dose mean responses (area
divided by observed log-dose width, on the source scale) are returned for development. The
same preparation result must stay private for confirmation. Bounds may exceed
one; they must be fixed for the actual source assay. Normalization across donors
or shared controls requires a separate independence argument.

`contract_hash` binds ordered genes, panel and assay protocol, excluding only the
source-file hash and license so separately sourced compatible cohorts can join.
`source_hash` binds the entire supplied document. The producer must verify actual
source files against their declared hashes; this tool cannot authenticate an
upstream dataset from a string declaration.

```sh
python -m dnhacksbio.pharmacotype prepare-dev --data dev.json --output coverage.json
python -m dnhacksbio.pharmacotype profile --data dev.json --output curves.json
python -m dnhacksbio.pharmacotype train --data dev.json --splits splits.json --kind pca --output model.json
python -m dnhacksbio.pharmacotype predict --data dev.json --model model.json --output predictions.json
python -m dnhacksbio.pharmacotype neighbors --data dev.json --model model.json --query query.json --modality molecular --k 5 --output neighbors.json
python -m dnhacksbio.pharmacotype compare-programs --data dev.json --model model.json --genes GENE1,GENE2 --output program.json
```

The split JSON contains `train`, `validation`, and `test` canonical donor lists,
exhaustively disjoint with at least two donors each. These minima are software
requirements, not a power claim. Scaling/fill/PCA are fit on training donors;
MLP early stopping sees validation donors only. Test error is reported once and
must not guide model/seed/panel selection. `--kind identity|pca|mlp`, `--seed`, and
`--epochs` choose bounded training settings. Python APIs also expose latent size,
ridge penalty and missingness tolerance. JSON models bind feature order, splits,
source and protocol hashes, both view encoders, predictor/critic, software,
training time and held-out curve RMSE. Hash checks detect accidental alteration,
not malicious re-signing by an untrusted operator.

For an unmeasured model, `predict --data query.json` accepts schema
`pharmacotype.query.v1` with ordered `genes`, the frozen model's `contract_hash`,
unique `ids`, and a two-dimensional `rna` matrix. No drug responses are required.
The contract hash is an explicit declaration of matching assay/feature scope;
it is not inferred from unknown future measurements.

Neighbors use Euclidean distances in the chosen separately encoded modality.
Program comparison reports descriptive Spearman correlations with the observed
log-dose response mean, a development median split, and prediction ablation to
training means. Both are exploratory and uncalibrated. Queries outside the
training distribution have no calibrated applicability guarantee.

## Private frozen replay

Run the scorer as an OS identity whose state and shared ledger are inaccessible
to research agents. Owner modes on files and a same-user subprocess alone do not
enforce confidentiality. Bind the submission service to a controlled network.
There are no result-reading HTTP routes or result callbacks. Do not attach private
exports, failures, exclusions, curves or evidence paths to ordinary agent artifacts.

The private manifest has `protocol_id`, `hypothesis_id`, `family_id`, `cohort_id`,
`cohort` (same schema, role `confirmation`), complete frozen `model`, and `protocol`.
The protocol declares:

- `schedule: "fully-frozen-v1"` or `"past-block-bilinear-sgd-v1"`, `sampling: "iid-independent-donors"`, `stake` in
  [0, .9], `null`, `population` matching the assay, `family` matching `family_id`,
  `parent`, `eligibility_justification`, and `normalization_justification`.
- A prespecified even `required_donors` and canonical sorted `donor_order`.
  The actual eligible count must equal the budget; these values remain private.
- SHA256 review references `access_review`, `identity_review`, `sampling_review`,
  `power_review`, `privacy_review`; `release: "operator-reviewed"`, at least
  10,000 `null_streams`, and `power_lower_bound` at least .8.

The supported null string is exactly `independence of frozen measured RNA and response representations`.
Confirmation v1 rejects pooled wells and plates shared across selected donors;
unique plates still do not establish independence without the reviewed argument.

These fields are operator attestations bound into the manifest. They do not
perform statistical review, establish an OS boundary, verify upstream files or
prove adequate power. Operators must inspect the referenced evidence before
registration. No real reviewed cohort/registration is supplied by this release.

```sh
python -m dnhacksbio.pharmacotype_scoring register --state /private/pharm-queue --ledger /private/shared-native-ledger --manifest private.json --output registration.json
python -m dnhacksbio.pharmacotype_scoring serve --state /private/pharm-queue --port 8797
# Discovery process receives only registration.json and this durable receipt:
python -m dnhacksbio.pharmacotype submit --spec registration.json --request-id request-1
# Operator-only replay and export:
python -m dnhacksbio.pharmacotype_scoring replay --state /private/pharm-queue
python -m dnhacksbio.pharmacotype_scoring export --state /private/pharm-queue --output private-export.json
```

All native tools must use the same private ledger directory for global donor
reuse enforcement. Independent directories cannot detect overlap. Queue aliases
resolve to one job; the shared core commits each two-donor factor, cursor and
observation digest atomically. The operator-only `replay` command retries interrupted and failed jobs under the
queue worker lock; permanent validation failures stay failed. Interrupted replay repeats identical transitions,
which do not increment twice. Reordering or changed observations fails. Software,
manifest and model changes invalidate the frozen registration. No append endpoint
is provided. The adaptive schedule persists scored/next critic and fixed
stateless SGD parameters atomically; see [core recovery semantics](native-evidence.md).

The null concerns independence of the two frozen measured representations in the
eligible assay population. The shared kernel evaluates four matched/crossed terms
using the same frozen critic and records final log wealth. It does not multiply
different hypotheses or report maximum wealth as a final e-value. See the
[shared native evidence contract](../plans/evalue-tool-council/native-evidence-contract.md)
and [sequential independence testing](https://proceedings.mlr.press/v202/podkopaev23a.html).

## Source audit and remaining release work

No independent PDO denominator is established by the published library sizes.
The [EGA record](https://ega-archive.org/datasets/EGAD00001005217), checked
2026-09-06, lists 31 sequencing samples and committee-controlled access; it does
not establish 31 eligible independent PDAC donors. No access request was sent.
Tiriac raw sequencing access is controlled at [dbGaP phs001611.v1.p1](https://www.ncbi.nlm.nih.gov/projects/gap/cgi-bin/study.cgi?study_id=phs001611.v1.p1),
but processed RNA quantification is open through
[GDC](https://portal.gdc.cancer.gov/projects/ORGANOID-PANCREATIC). Public
PRISM/CCLE acquisition, canonical metadata join and real CPU/GPU training are
complete; [source audit](pharmacotype-sources.json) and [model card](pharmacotype-training.md)
record the counts, hashes, outcomes and domain limitations.
The training script now defaults to CUDA for all model fitting, including PCA,
ridge and critic optimization. The model card includes the completed nine-fit
CUDA rerun and the ongoing public PDO source audit.

Remaining scientific release work: accessible paired PDO measurements and donor
audit, sufficient untouched independent donors, assay-specific power and
sampling review, and deployment behind a separate OS identity. Published cohort
sizes do not establish these gates. The synthetic 32-donor power result fails
the target and cannot be used as a release attestation.
The development code can be used before those gates pass. Falsifier, ToolResult,
branch monitoring and human promotion behavior are unchanged.

## Reproducible synthetic diagnostics

`python -m dnhacksbio.pharmacotype validate --donors 32 --output validation.json`
runs 10,000 independent simulation streams for each of seven registered synthetic
cases, using the shared canonical factor. The checked-in
[diagnostic report](pharmacotype-validation.json) includes final/anytime rejection
rates, 95% Wilson intervals and detection delay among detected streams. The
pseudoreplication control repeats two actual donors despite a nominal budget of 32.
The current-block fitting and shared-control examples intentionally violate the
scientific assumptions; their inflation is not evidence against the valid null.

At nominal 32 donors, IID and heavy-tail null anytime rejection rates were .02%
and .20%; the strong simple alternative reached only 34.89% and the chosen
nonlinear case 0%. Thus this frozen reference critic does **not** meet the proposed
80% pilot power target. Current-block memorization, shared-control contamination
and pseudoreplication produced 100%, 68.89% and 13.5% anytime crossing. This is a
method diagnostic, not a real donor-budget justification or release review.
