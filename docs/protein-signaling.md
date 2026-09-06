# Measured protein discovery

`protein_design.py`, `protein_encoder.py` and `protein_tools.py` implement a local,
exploratory measured-protein workspace. No cohort is downloaded, no biological result
is claimed, and private native evidence is **unavailable**. `protein_experiment.Store`
uses the existing queue base but rejects registration and submission unconditionally;
operator assertions cannot enable it. No verifier, promotion or HTTP route changes.

## Input contract

JSON `ProteinObservation-v1` requires `role` (TRAIN, VALIDATION, DEV or CONFIRM),
`cohort_id`, `donor_namespace`, `accession`, `release`, `license`, `access`, `assay`,
`processing_dependencies`, `source_sha256`, `processing_sha256`, `scale`,
ordered unique `feature_ids` and `observations`. Scale is `linear_abundance`,
`log2_abundance` or `log2_ratio`. These are measured proteins, never inferred RNA.
A source hash records provenance; the importer does not independently verify a source file.

Each observation has canonical `donor_id`, `specimen_id`, `aliquot_id`, `run_id`,
`batch`, `reference` (explicit `none` where applicable), `histology`, `tissue`,
`context`, `treatment` (`untreated`, `treated`, `unknown`), `grade` (G1/G2/G3 or
null/unknown), `qc` with boolean `pass`, and aligned `values`/boolean `mask`.
Unmeasured values must be null. One preselected specimen per canonical donor is
required; duplicates are rejected, not averaged or counted as fresh units.
Canonical identity mapping and outcome-independent specimen selection are operator
responsibilities. Distinct identifiers do not prove independent sampling.

Optional `sites` retain accession, isoform (nullable), position (nullable), S/T/Y
residue, localization confidence, parent-protein coverage (both in [0,1]), and
nullable measured value. Ambiguous sites stay unresolved even if their probability
is high. Site abundance is not occupancy, kinase activity or a glycan measurement.

A panel JSON is `{"version":"mitotic-v1","feature_ids":["P0","P1"],
"modules":{"example":["P0"]}}`. Use audited biological accessions in real panels;
P0/P1 are syntax examples. Modules must be subsets of the panel. The entire panel
is hashed, including version and module membership. Keep the source paper's tissue,
intervention and disease context attached to downstream hypotheses.

## Commands

Run from an installed checkout (`uv sync --extra dev`; add `--extra evalue` for
optional Torch denoising training):

```sh
uv run python scripts/protein_tool.py profile --cohort dev.json --panel panel.json
uv run python scripts/protein_tool.py neighbors --cohort dev.json --reference reference.json --panel panel.json -k 5
uv run python scripts/protein_tool.py compare --cohort dev.json --panel panel.json --context-a A --context-b B
uv run python scripts/protein_tool.py sites --cohort dev.json --proteins P0 P1 --localization-threshold 0.75
uv run python scripts/train_protein_encoder.py --train train.json --validation validation.json --output encoder.npz --latent 2
uv run python scripts/protein_tool.py profile --cohort dev.json --panel panel.json --encoder encoder.npz
```

The installed `protein-tool` command exposes the same subcommands.
All discovery operations reject CONFIRM inputs. Profiles carry measured masks,
coverage, QC, observed module means and optional embeddings with source, processing,
panel and model hashes. Linear abundance uses fixed log2(1+x); logged inputs are
unchanged. Raw nearest profiles use RMS over jointly measured features and report
shared coverage; distances with different shared subsets need caution. Encoded
neighbors require exactly matching frozen transforms and exclude the same donor.
Comparisons show donor-level observed means, missing fractions and descriptive
A-minus-B differences; no p-value or native wealth is attached.

## Encoder

Feature coverage filtering, fixed zero imputation in standardized coordinates, center
and scale are fitted on TRAIN only. Masks are a separate input channel. Training and
validation must use one harmonized donor namespace, non-PDAC histology, different
cohort IDs and disjoint canonical donors. The importer cannot verify the truth of
metadata declarations. Reserve whole cohorts and audit release aliases before import.
PCA is the default CPU baseline. Its latent size must fit the available matrix dimensions.

Optional `--kind denoising --latent 32 --epochs 50` uses 2,000–8,000 training-selected
features, width 256, latent 32/64, corrupted value/mask inputs, observed-entry loss,
AdamW and the best past development-validation epoch. The encoder remains frozen
at discovery time. The CPU pilot caps wall time at 30 minutes between epochs.
Artifacts are NPZ numerical arrays plus JSON metadata, loaded with pickle disabled,
shape and content-hash validation. They retain training/validation donor hashes,
source hashes, preprocessing, objective, seed, versions, selected epoch, elapsed time,
throughput, process peak RSS, numerical weight bytes and held-out observed-entry MSE.
RSS is a process-lifetime high-water mark, not an isolated training allocation. This MSE measures reconstruction of visible
validation inputs; it is not an imputation benchmark or evidence of useful transfer.
No assay alignment is fitted on the queried cohort; mismatched assay/scale is rejected.
CUDA training now acquires the shared host lease and enforces the bounded pilot
caps. Real-data acquisition, measured training and held-out comparisons are recorded
in [protein training](protein-training.md). Checkpoints now use hidden observed
validation entries rather than visible-entry reconstruction alone.

## Operator audit and deferred evidence

```sh
uv run python scripts/audit_protein_cohort.py --cohort private.json --panel panel.json --output private-audit.json
```

This operator-only command creates a new owner-only report and prints no counts.
It reports records, unique tumor donors, untreated PDAC, compatible grades, panel/QC
eligibility and G1/G2 versus G3 sizes in sequence. It retains the 48-pair policy and
never substitutes molecular subtypes for grades. Run it inside operator-only storage:
file permissions and role labels alone do not contain a same-user discovery agent.
No public audit endpoint exists. The report does not assert untouched status,
normalization independence, externally interpreted histology or adequate power.

Private registration/scoring, canonical cross-process donor/segment consumption,
replay/append transactions, the 10,000-stream null and prespecified-power studies,
biological power/release review remain pending. Rank/PCA, module, linear/kernel,
and denoiser development comparisons plus a real GPU pilot have run; see the
training record for results and the explicit lack of a neural advantage. Private release requires the
shared native core and audited data described in the [implementation plan](../plans/evalue-tool-council/PLAN-protein-signaling.md).
The discovery release does not certify the private evidence release gates. No
synthetic test result is reported as biological validation or measured cohort power.
