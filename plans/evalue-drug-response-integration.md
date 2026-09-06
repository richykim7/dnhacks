# Drug-response and combination background evidence

Plan dated 2026-09-05; first-endpoint implementation authorized and added 2026-09-06.
Registered biomarker/AUC submission, private scoring, fixed Python preparation, optional pinned
PharmacoGx raw export and synthetic validation are implemented. See
[actual behavior and setup](../docs/drug-response-scoring.md). R adapter execution remains unverified
on this host. Cohort selection, biological confirmation and synergy evidence remain pending.
The design rationale and later statistical extension below are preserved.

## First endpoint and evidence

Start with one fixed continuous biomarker versus one drug-response summary across independent PDAC
models. GATA6 expression versus oxaliplatin response is an illustrative candidate motivated by
[PDAC experiments](https://www.jci.org/articles/view/191370), not a selected cohort or treatment
recommendation. Avoid selecting a subtype cutoff on evaluation outcomes.

Use [PharmacoGx](https://bioconductor.org/packages/release/bioc/vignettes/PharmacoGx/inst/doc/PharmacoGx.html)
for metadata/dose-response preparation. Prefer observed-point area over IC50, which may be undefined
for nonresponders. Freeze concentration range, exposure, normalization, aggregation, missing coverage
and clipping. Record input scale and convert percentages to fractional viability explicitly.
Define inhibition area `A=1-integral(viability over log-dose)/log-dose-range`; higher A
means greater inhibition. Use fixed integration; reject missing coverage rather than extrapolate.
Check all-alive/all-dead orientation instead of assuming package AUC conventions.

One donor-derived model contributes one biomarker/response pair. Wells, doses, passages, metastases
from one patient and aliases are nested observations. Null: biomarker/response independence within
prespecified assay strata with justified exchangeability, not absence of causal effect. Use absolute
Spearman correlation and exact allowed permutations, or B=9,999 uniform random permutations with fixed
seed and conservative ties. Monte Carlo `p=(1+b)/(B+1)` enters existing `p_to_e(p)=p**(-0.5)-1` once.
Freeze direction/strata/statistic. No residualization-based conditional-independence claim, or repeated
reuse as fresh wealth. Preserve signed effect privately. [Calibration](https://arxiv.org/abs/1912.06116)

## Interface and implementation status

The optional PharmacoGx preparation adapter is implemented; SynergyFinder integration remains pending.
The strict TPM expression worker cannot accept drug responses. The implementation uses the shared
transport prerequisite in [the dependency plan](evalue-dependency-integration.md).

1. Expression v1 is preserved; `biomarker_auc` uses a method-specific validator and operator-frozen
   protocol. `bliss` registration remains a later extension. No agent-supplied p/e or arbitrary executable/plugin paths.
2. Implemented `drug_response.py`, `drug_response_experiment.py`, `drug_response_scoring.py` and
   the pinned PharmacoGx raw-export adapter under `scripts/r/`. Use `Rscript --vanilla` and fixed
   arguments, never submitted R. R execution remains unverified on this host.
3. Command: `python -m dnhacksbio.drug_response_experiment --spec FILE --request-id ID`.
   Strict `{request_id,spec,input}` envelope; spec identifies schema/method/protocol/hypothesis/family.
   Input is registered cohort ID plus manifest hash; bounded uploads remain deferred.
4. Private AUC rows: `unit_id,plate_id,replicate_id,dose_molar,viability,biomarker`, for fixed drug/time.
   Check biomarker consistency per unit. Synergy rows add `arm,dose_a_molar,dose_b_molar`; protocol
   specifies controls. Preserve raw data, source provenance, units and assay metadata.
5. Emit receipt/accepted only after durable enqueue; runtime captures it. Freeze endpoint/QC,
   software, alias mapping, numerical budget and family identity. Canonical experiment identity prevents
   renamed request IDs from duplicating evidence; record every attempted request and all hashes.
6. Preserve locks, crash recovery, private subprocess output/export. Add concise invocation skill
   and actual-behavior docs; keep verifier/promotion semantics unchanged.

Private results include effects, p/E or wealth, validity/null, failures, exclusions/counts and replay.
No public status/results routes, numerical stdout, callbacks, recall or branch feedback. Operator-held
confirmation needs a separate service identity/storage boundary; same-user processes alone do not
provide confidentiality. The command handles receipts after durable acknowledgement, including the
same receipt for identical retries; the agent never needs to reconstruct one or compute evidence.

## Synergy is a separate statistical extension

[SynergyFinder](https://academic.oup.com/nar/article/50/W1/W739/6586861) supplies HSA, Bliss, Loewe
and ZIP analyses. Scores, bootstrap intervals and fitted p-values are not automatically e-values.
Default to descriptive synergy until the measurement design supports an evidential construction.

Possible native route: fresh single-agent viabilities U,V and combination viability W, each in [0,1],
give `D=U*V-W` in [-1,1]. Under the explicit measured-response null `E[D_i | past] <= 0`, predictable
`0<=lambda_i<=1` yields the nonnegative supermartingale `K_t=product_i(1+lambda_i*D_i)`.
Fixed lambda=0.5 is a simple pilot; fixed nonnegative dose weights summing to one preserve boundedness.
This conditional-mean null is not automatically a population-average Bliss null.
[Bounded betting theory](https://academic.oup.com/jrsssb/article/86/1/1/7043257)

Biological interpretation needs suitable unbiased measurements and independence of single-agent
estimation errors conditional on the underlying unit. Shared vehicle denominators, plate effects,
fitted curves and clipping can break it. A frozen noisy reference is still uncertain. Audit these
assumptions or derive a method accounting for reference uncertainty before enabling synergy evidence;
never plug ordinary fitted Bliss scores into the formula and advertise exact biological validity.

## Data, milestones and evaluation

[PDAC organoid pharmacotyping](https://pubmed.ncbi.nlm.nih.gov/29853643/) and PharmacoGx resources
are candidates, not verified local confirmation data. Audit overlapping models, controls, replication
and provenance. Previously inspected data is development material; hidden scores/new IDs do not
create independent confirmation. Minimum useful cohort size follows power assessment.

Freeze endpoint/schema and audit eligibility; implement preparation, private registry and scoring;
validate before a locked cohort run. Test exact tiny permutations, ties, constant biomarkers, dose
coverage/orientation; null/power across unit counts, noise, strata and effects; confounding/adaptive
biomarker selection; aliases, repeated donors and altered resources. Test lost acknowledgements,
concurrent/conflicting/renamed retries, crash recovery, one durable result, and output containment
across HTTP/stdout/journal/artifacts/recall. Before synergy evidence, simulate shared-control noise,
nonlinear normalization, biased references and heterogeneous nulls. No biological measured results exist yet; software validation uses synthetic fixtures.

Defaults: one biomarker/drug, two-sided Spearman, fixed-p calibration, observed AUC, descriptive
synergy and no automatic family verdict. Open decisions: dataset, drug, pairing, power and measurement
assumptions. Related plan: [pathway and differential expression](evalue-expression-integration.md).
