# Private biomarker/drug-response scoring

The implemented `biomarker_auc` method submits an operator-registered experiment, returns a durable
receipt, and computes a private donor-level Spearman randomization test. It does not send statistics
to the discovery agent, verification queue, branch judge, recall or promotion. No status/results HTTP
route exists. A receipt is accepted input, never a successful biological result.

## Operator setup

Use a separate service OS identity and private storage inaccessible to the discovery agent when
confirmation confidentiality is required. A separate process under the same user is insufficient.
The HTTP submission service must be reachable only by authorized local clients (or an operator-managed
private gateway); it does not implement authentication. Keep exports outside agent-visible directories.

Install the repository Python package. The scorer uses NumPy; no Torch, R or GPU is required for its
fixed numerical endpoint. In an operator-owned directory, prepare a JSON manifest with exactly:

- `protocol_id`, `hypothesis_id`, `family_id`, `cohort_id`: fixed nonempty identifiers, at most 120
  letters/digits/dots/underscores/dashes, starting with a letter or digit.
- `protocol`: the frozen object below.
- `cohort`: `source` (accession/release, raw-file hashes, units, normalization and selection provenance),
  `units` (mapping each observed model/alias ID to `{donor_id, stratum}`), and `rows`.

Each row has exactly `unit_id, plate_id, replicate_id, dose_molar, viability, biomarker`.
Plate and replicate IDs must identify actual nested observations, not artificial replicates. Multiple
aliases, passages or models from one donor map to the same donor ID. Donors cannot cross strata, and
all their biomarker values must agree. Every registered alias must have observations. Each
`donor_id/plate_id/replicate_id/dose_molar` is unique, including across aliases. One queue contains
one fixed drug, biomarker and exposure: the operator must verify this against the source assay metadata.

Example **protocol only** (illustrative defaults; no selected drug or confirmation cohort):

```json
{
  "version": "biomarker_auc.v1",
  "drug": "operator-selected-drug",
  "exposure_hours": 72,
  "biomarker": "operator-selected-continuous-marker",
  "dose_min_molar": 1e-9,
  "dose_max_molar": 1e-6,
  "input_scale": "fraction",
  "normalization": "vehicle_normalized",
  "clipping": "reject",
  "aggregation": "mean_replicates_then_plates_then_donor",
  "missing_coverage": "reject",
  "direction": "two-sided",
  "permutations": 9999,
  "seed": 123,
  "min_units": 8,
  "assumptions": "Replace with actual independence, exchangeability, preselection and power justification"
}
```

`min_units` is operator-frozen, at least three for mathematical definition; three is not a power
recommendation. Select an adequate cohort and freeze the design before inspecting its responses.
Previously inspected data stays development material. Changing IDs, hiding scores or creating another
queue does not make it independent confirmation.

```sh
python -m dnhacksbio.drug_response_scoring register \
  --state /private/drug-queue --manifest /private/manifest.json \
  --output /private/registered-drug-experiment.json
python -m dnhacksbio.drug_response_scoring serve --state /private/drug-queue --port 8795
```

Registration validates the curve and donor design, stores a canonical private snapshot, and pins its
SHA-256, scorer/transport source hashes and Python/NumPy versions. Subsequent registration must match exactly. Source-file edits do
not alter the snapshot; private snapshot tampering, scorer-code changes or Python/NumPy version changes cause failure.
Provision the same environment for replay. There is no arbitrary plugin,
submitted code, numerical upload or p/e-value field. The manifest is bounded to 48 MiB. Registration
output contains only the method/schema/protocol/hypothesis/family IDs and cohort ID/manifest hash;
copy that file into the agent's input directory with appropriate read permission.

The agent runs:

```sh
python -m dnhacksbio.drug_response_experiment \
  --spec registered-drug-experiment.json --request-id investigation-branch-drug-001
```

`DNHACKS_DRUG_RESPONSE_ENDPOINT` defaults to `http://127.0.0.1:8795`. The wire envelope is exactly
`{request_id,spec,input}`. The client exposes only a validated `{receipt,status:"accepted"}` after HTTP
202. Transport errors are generic. Retry lost acknowledgements unchanged with the same request ID.
SQLite FULL synchronous transactions precede acceptance. Concurrent and renamed retries map to one
private job/experiment identity. Each renamed request retains its own stable receipt, with private
alias mapping to the original job; it never creates fresh evidence. Queue scope is the deduplication
boundary; operators must not combine copies across separate queues as fresh evidence.

Shared transport owns worker locks, child-process isolation, timeout handling and recovery of jobs
interrupted while running. Workers suppress stdout/stderr. Private failures leave public retry receipts
unchanged. Operator-only export creates a new mode-0600 file and refuses existing output paths:

```sh
python -m dnhacksbio.drug_response_scoring export \
  --state /private/drug-queue --output /private/drug-results.json
```

The export contains the frozen registry/raw rows, request attempts and aliases, one job result or failure, signed
effect, p/E, assumptions, counts, exclusions (empty because invalid coverage fails the experiment),
protocol, prepared donor observations and replay hashes. No automatic family verdict is produced.

## Fixed numerical endpoint

Viability is vehicle-normalized fractional survival, or explicit `percent` converted by dividing by
100. Reject values outside [0,1], nonfinite values and nonpositive/out-of-range doses. Every curve must
contain the exact frozen lower and upper positive molar doses; no missing-coverage exclusion,
extrapolation, curve fitting or IC50 substitution occurs. Integrate the observed points by the
trapezoidal rule over log dose:

`inhibition_area = 1 - integral(viability d log(dose)) / log(dose_max / dose_min)`.

All-alive curves give zero and all-dead curves give one. Average complete replicate curves within
plate, then average plates within donor with equal plate weight. One donor contributes one continuous
biomarker/response pair. Preserve the signed Spearman effect privately; use its absolute value for
the two-sided randomization statistic. Constant biomarkers/responses and no exchangeable units fail.

Permute response ranks only within the prespecified assay strata. `permutations:"exact"` enumerates
all allowed permutations including identity, capped at 100,000; its p is extreme/total. The default
9,999 uniform random permutations use a frozen seed and `(1 + extreme)/(9999 + 1)`. Ties, including a
1e-12 rounding tolerance on absolute correlation, count as extreme. Apply the existing calibrator
`p_to_e(p)` once. Do not multiply repeated copies as new wealth.

The null is biomarker/response independence within those strata under the declared exchangeability.
This does not establish conditional independence after arbitrary residualization, causal mechanism,
clinical treatment benefit or safety. Assumption declarations are operator assertions, not code proofs.
The calibration follows [Vovk and Wang](https://arxiv.org/abs/1912.06116).

## Optional PharmacoGx preparation

`scripts/r/prepare_pharmacogx.R` is an operator-only adapter pinned to PharmacoGx **3.16.0**. It exports
raw `sensitivityRaw` points and `sensitivityInfo`, sample and treatment metadata from an operator-trusted
PharmacoSet RDS, retaining source dose/viability units. No data download or package installation occurs.
Only the explicit experiment × dose × metric array layout is accepted. It writes to a new directory:

```sh
Rscript --vanilla scripts/r/prepare_pharmacogx.R /private/source.rds /private/prepared
```

Run this fixed script and arguments, never agent-submitted R. The operator maps experiment IDs to
actual donors/plates/replicates, selects one drug/exposure/biomarker, records units and normalization,
and constructs the frozen manifest. The adapter intentionally does not guess unavailable metadata,
convert unknown dose units, impute missing values or use a package's fitted AUC convention. Preserve
source RDS, exported metadata, source hashes and adapter/session provenance privately. These accessors
are documented in the [PharmacoGx reference](https://www.bioconductor.org/packages/release/bioc/manuals/PharmacoGx/man/PharmacoGx.pdf).

Rscript/PharmacoGx are unavailable on the implementation host, so adapter execution remains unverified;
validate it in the pinned R environment before using its output. The Python scoring path is tested
independently with synthetic raw curves.

## Boundaries and validation

SynergyFinder and `bliss` evidence are not registered. Ordinary synergy estimates remain descriptive;
there is no native Bliss wealth computation or fitted-score calibration in this implementation. A
future evidence route requires the separately audited measurement/error design in the integration plan.

Tests cover hand-calculated exact permutations/ties, full tiny-null enumeration, inhibition orientation,
percentage conversion, log-dose coverage, strata confounding, constant biomarkers, aliases/repeated
donors, Monte Carlo reproducibility, frozen resources, renamed/concurrent retries, HTTP containment,
timeouts, process recovery, and actual explorer journal/artifact/recall containment after scoring.
Synthetic tests establish software behavior, not clinical power or independent confirmation. No
biological dataset has been selected, downloaded or scored.
