# Pathway, TF and differential-expression background evidence

Original proposal, 2026-09-05. Implementation requested 2026-09-06; registered paired-score service,
strict preparation, optional approximate count effects and deterministic validation are implemented.
See `docs/expression-scoring.md`. No confirmation ingestion or biological pilot has been performed.
Prepared concurrently with dependency/drug-response reviewers; parent aligned shared interfaces.
Cohort selection, power justification and a locked confirmation pilot remain operator decisions.

## First endpoint and design

Proposed endpoint: TGF-beta treatment increases a fixed PROGENy TGFb transcriptional score in
pancreatic CAF cultures versus paired vehicle at fixed dose/time. [PDAC CAF biology](https://doi.org/10.1158/2159-8290.CD-18-0710)
motivates the readout; it does not establish tumor progression or causal pathway function. Suggested
engineering design: 12 independent human donor-derived cultures with independently randomized paired
aliquots. This is not a located cohort, power justification or instruction to conduct an experiment.

Freeze mapping, organism, coverage, exclusions, endpoint, direction, dose/time, pairing and family.
Proposed defaults: top 100 [PROGENy](https://www.nature.com/articles/s41467-017-02391-6) TGFb targets,
resource hash, weighted sum and at least 90 observed targets. Validate defaults; they are not established
optimal settings. Pin [decoupler weighted aggregation](https://decoupler.readthedocs.io/en/stable/api/generated/decoupler.mt.waggr.html),
use `fun="wsum", times=0` and verify the version's behavior. Do not treat gene-shuffle enrichment p-values
as evidence about independent donors.

TPM pathway input uses fixed `log1p(TPM)`; count pathway input can use per-sample
`log1p(1e6*counts/library_total)`. These measure relative expression and can reflect composition.
PyDESeq2 requires nonnegative integer counts; never supply TPM or reconstruct counts from TPM.
Aggregate technical sequencing lanes. Single-cell counts sum by donor × condition × an externally
defined cell type. Cells, wells and passages are not independent donors.

Compute aliquot score `s=sum_g(w_g*z_g)`, donor difference `D=s_treatment-s_control`, then `T=mean(D)`.
Enumerate permitted within-pair assignments; exact p is the full-orbit exceedance fraction with ties.
Monte Carlo uses `(1+b)/(B+1)` with fixed seed and B=9,999. Under randomized assignment, the sharp null
is no effect on the fixed score for any aliquot, stronger than zero average effect. Without documented
randomization require justified swap symmetry; ordinary matching or before/after sampling is insufficient.

Apply existing `p_to_e(p)=p**(-0.5)-1` once. Twelve pairs permit 4,096 assignments, minimum one-sided
p=1/4,096 and maximum E=63: an evidence ceiling, not predicted power. Retries/new pathways on reused
data are not fresh e-process increments. [Calibration theory](https://arxiv.org/abs/1912.06116)

## PyDESeq2 and TF extensions

Use [PyDESeq2](https://pydeseq2.readthedocs.io/en/stable/auto_examples/plot_minimal_pydeseq2_pipeline.html)
with `design="~ donor + condition"` for a suitable paired design or a separately justified independent
design such as `"~ batch + condition"`; check rank and replication. Preserve fold changes, standard
errors, Wald p and BH results privately as model-based approximate outputs. Wald-p calibration alone
does not confer finite-sample validity.

An exact companion can test a frozen small gene panel using unit-local normalized scores and paired
randomization. State the score null separately from the NB coefficient null; PyDESeq2 supplies effect
estimates, not the validity argument. Future Wald-statistic permutation needs refitting of label-dependent
steps and an audit of shared normalization/shrinkage before gene-specific validity claims. A frozen
STAT3 regulon is a possible later TF endpoint, not a replacement selected after disappointing TGFb results.

## Interfaces and implementation

The TPM/encoder service is preserved. A pinned decoupler weighted-sum reference and optional
PyDESeq2 adapter now accompany the registered paired pathway implementation. Preserve
expression v1 and `learned_evalue.py`. Use the shared transport prerequisite in [the dependency plan](evalue-dependency-integration.md).

1. Register strict schema/method/protocol/hypothesis/family specifications with an operator-frozen
   resource/protocol registry. Reject arbitrary private paths, p/e values and executable plugins.
2. Proposed `expression_experiment --dataset-id` route is mutually exclusive with existing `--input`.
   Resolve only operator-registered cohort IDs and manifest hashes. Exposed uploads are development data.
   Example future command: `python -m dnhacksbio.expression_experiment --dataset-id pdac-caf-confirmation-v1 --spec FILE --request-id ID`.
3. Private artifacts: bounded primitive arrays `X,genes,sample_ids,unit_ids,pair_ids,condition,batch`
   and provenance/design metadata. Preserve NPZ header/size checks; reject aliases and mismatched pairs.
4. Add proposed `expression_design.py`, `pathway_evalue.py`, `count_expression.py`. Generalize frozen
   worker settings to hashed protocols/resources while retaining legacy encoder setup. Pin software;
   workers recompute evidence from registered inputs rather than accept agent-provided statistics.
5. Keep durable receipt/accepted stdout, locks, subprocesses, generic transport errors, no public
   result/status GET or callbacks, private failures/export. Canonical experiment identity prevents
   duplicate evidence under new request IDs while preserving all attempts.
6. Add concise invocation skills and update architecture/operator docs. Audit current PyDESeq2 guide
   APIs and shrinkage/filtering/small-sample claims before reuse. Runtime captures command receipts;
   the agent need not reproduce them or know the evidence calculation.

Private results contain hashes, method/design/null, scale, units, coverage/exclusions, effect, p/E,
randomization settings, approximate DE outputs and replay provenance. No statistics/failures enter
discovery stdout, recall, branch context or verification feedback. Restricted service identity/storage
is required for confidentiality against unrestricted discovery code; same-user processes do not suffice.
No falsifier/promotion change or automatic combination of adaptive evidence families is proposed.

## Data and acceptance

Existing [GSE212041](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE212041) is inspected neutrophil
development data, not PDAC confirmation. The repo uses TPM; raw counts are not established locally.
The CAF paper's [mouse project](https://www.ncbi.nlm.nih.gov/bioproject/PRJNA471312) provides context,
not the proposed human paired cohort. Find and audit eligible data without reading confirmation outcomes.

Then implement deterministic preparation/registry/scoring and evaluate before a locked pilot:

- Exact tiny assignment orbits, mean-e/rejection bounds and the 12-pair evidence ceiling.
- Null/power curves across donor counts, imbalance, heterogeneous effects and feature missingness.
- Donor/pairing/cohort overlap, label-selected pathways, invalid counts, rank-deficient designs and tampering.
- Fixed reference fixtures for weighted scores, scales and pinned PyDESeq2 effects.
- Duplicate/new-ID replay, lost acknowledgements, restart/timeout, immutable settings and no leakage
  through HTTP, stdout/stderr, journal, artifacts or recall.

Report uncertainty and the entire prespecified family; simulation is an implementation check, not a
universal proof. Open decisions: cohort, organism, pairing and power. Default to a fixed pathway
randomization pilot, approximate DE effects alongside, and unavailable evidence when the design is
unsupported. Related plan: [drug response](evalue-drug-response-integration.md).
