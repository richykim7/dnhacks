# Protein private finite replay

The implemented independent-group adapter reuses `learned_two_sample_e`, its bounded
odd payoff and adaptive neural critic. Eight-pair batches and two burn-in batches
leave 32 scored pairs from the minimum 48 independent pairs. Training uses older
batches, validation uses the preceding batch, and scoring uses the fresh batch.
The null concerns equal measured representation distributions under the declared
conditional sampling model; it does not establish mechanism, grade causality or
assay independence.

`native_group_replay.py` shares the existing native ledger's processes, aliases,
blocks and consumed canonical donors. Registration freezes all representations,
metadata, donor order, exclusions, source/model/panel hashes and runtime code hashes.
Identity sorting is seeded and independent of measured values. The entire finite
replay commits atomically. A crash before commit reruns deterministic computation;
an identical committed replay adds no wealth. All supplied donors, including burn-in
and unused imbalance, are consumed conservatively across modalities in that ledger.
There is no append interface or partially committed optimizer checkpoint. Private
reports retain the exact training/validation/scoring donor sets and final wealth;
running maxima are diagnostic quantities, never exported as an e-value.

The operator CLI is `python -m dnhacksbio.protein_experiment` with subcommands
`register --state QUEUE --manifest MANIFEST --output REGISTRATION`,
`serve --state QUEUE --port 8798`, and `export --state QUEUE --output REPORT`.
Registration output supplies the `spec` and `input` fields for the shared receipt-only
`POST /experiments` envelope plus caller `request_id`. There is no HTTP result or
completion endpoint. Only the operator can export the private queue.

The private manifest contains `spec`, two `groups` of canonical donor IDs/frozen
values, an absolute `ledger_directory`, and `release`. Exact specification fields
are in `native_group_replay.FIELDS`. Release requires approved artifact references
for sampling, preprocessing, untouched history, canonical identity and privacy;
a model/panel-specific power report; and a discovery service UID distinct from the
worker. These are trusted operator attestations: hash syntax and reported thresholds
do not authenticate reviewers or prove their conclusions. Filesystem ownership,
separate accounts, restricted network/process access and an independent privacy
review must enforce deployment containment. Point every modality at the same private
ledger; isolated ledgers cannot prevent cross-tool donor reuse. No production private
worker or biological confirmation manifest is deployed by this release.

## Measured diagnostics and release decision

`scripts/validate_protein_native.py --output REPORT` reproducibly runs ten cases of
10,000 independent streams through the actual canonical payoff. The predictable
cheap witness uses a past-data direction and previous-batch stake selection. It
tests the payoff/schedule cheaply, **not power of the trained neural model**.
The standardized minimum effect was fixed at 0.4, rounded down from the development
mitotic module difference 0.4791 before simulation. Full intervals, final and anytime
rejection rates, detection times and wealth summaries are in
[the generated report](protein-native-validation.json).

| Case | Pairs | Anytime rejection |
|---|---:|---:|
| Gaussian null | 48 | 1.30% |
| Heavy-tail null | 48 | 1.27% |
| Missingness null | 48 | 1.12% |
| Mean shift 0.4 | 48 | 5.47% |
| Nonlinear alternative | 48 | 20.79% |
| Missingness alternative | 48 | 68.95% |
| Batch-shift alternative | 48 | 6.02% |
| Invalid current-batch training control | 48 | 99.99% |
| Shift at observed grade-pair ceiling | 26 | 0.50% |
| Mean shift 0.4 | 96 | 18.76% |

Missingness and batch shifts are alternatives to equality of measured inputs; their
rejection is not biological specificity. The 26-pair case is an ineligible diagnostic,
not an exception to the 48-pair policy. The 80% power requirement fails even for the
96-pair cheap-witness simulation, and no model-specific release certificate is made.
Neural replay tests separately verify deterministic restart, aliases, exact disjoint
critic sets, private queue operation and donor reuse rejection.

The real CPTAC development audit yields 26 G3 versus G1/G2 pairs before treatment
exclusions. The subsequently authorized [Fudan external benchmark](protein-external.md)
acquired 65 grade pairs, with 60 surviving the fixed coverage filter, and evaluated
frozen CUDA-fitted models. The sample-count shortage is therefore resolved for that
benchmark. Its published matrices use cohort-wide detection filtering, and published
analyses already examined proliferation/grade relationships; evaluated Fudan inputs
are not unopened confirmation data. No raw spectra were reprocessed. The secondary
rank-kernel transfer result is promising, while the primary rank-PCA result is weak.
Independent confirmation and reviewed sampling, processing, privacy and model-specific
power remain unsatisfied; additional patients alone do not settle those requirements.
