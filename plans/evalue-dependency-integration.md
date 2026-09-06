# Dependency and CRISPR background evidence

Proposed plan, 2026-09-05. Planning only; no implementation, ingestion or experiments performed.
Prepared by the dependency reviewer concurrently with the drug-response and expression reviewers;
parent review aligned the transport requirements. Implementation requires a subsequent request.

## First endpoint and validity

Candidate benchmark: MTAP deletion versus intact MTAP for PRMT5 Chronos dependency within PDAC.
[PDAC PRMT5 research](https://pmc.ncbi.nlm.nih.gov/articles/PMC12717533/) motivates the question, but
complete gene knockout and MTA-cooperative drug inhibition are different interventions. The endpoint
does not presume a positive result or establish pharmacological sensitivity.

Use one independent donor-derived model per unit. Resolve aliases, shared donors, repeated screens
and release overlap. Use a curated, release-specific deletion annotation; a generic OR of mutation,
copy loss and expression silencing is not an MTAP-deletion call.

The null is uniform exchangeability of event labels within prespecified blocks, conditional on frozen
scores, eligibility, block membership and group counts. Restrict to PDAC and justify any screen/library
blocks before confirmation. This is observational association under an invariance assumption, not
random assignment of deletion or causal synthetic lethality. If that assumption is indefensible,
privately report unavailable evidence. OLS adjustment does not validate unrestricted label shuffling.

Freeze `T = sum_s w_s * (mean_intact_s - mean_deleted_s)` with weights based only on block sizes.
Positive T means stronger dependency in deleted models. Freeze treatment of uninformative blocks.
Eight unique models per group is an operational floor, not a power justification; insufficient
support must not trigger outcome-driven pan-cancer expansion.

Enumerate allowed permutations when feasible; otherwise use B=9,999 uniformly sampled permutations
with a fixed seed. Exact p is the full-orbit exceedance fraction; Monte Carlo uses `(1+b)/(B+1)`.
Count ties conservatively. Apply existing `p_to_e(p)=p**(-0.5)-1` once. This is fixed-data evidence,
not an e-process. Audit the invariance implications of shared Chronos fitting/copy-number correction.
See [Chronos](https://link.springer.com/article/10.1186/s13059-021-02540-7),
[permutation theory](https://arxiv.org/abs/1411.7565) and [calibration](https://arxiv.org/abs/1912.06116).

## Existing capability and proposed contracts

`expression_experiment.py` and `expression_scoring.py` provide durable receipt-only submission,
frozen settings, worker ownership, subprocess scoring and private export. They require TPM and an
encoder today. Dependency/MAGeCK scoring does not exist and must not masquerade as expression input.

Proposed command: `python -m dnhacksbio.dependency_experiment --spec FILE --request-id ID`.
Use a strict versioned `{request_id, spec, input}` envelope. Spec identifies `schema_version`,
`method`, `protocol_id`, `hypothesis`, and `family_id`. Input references `cohort_id` and its registered
`manifest_sha256`. The operator protocol fixes target/event, eligibility, direction, blocks, statistic
and permutation configuration. Reject unknown keys and conflicting declarations.

Private table: `unit_id, model_id, disease, event_status, block_id, target_effect`; missing event calls
stay unknown. Manifest: source/release URLs, hashes, annotation scales, biological-unit mapping and
discovery/confirmation overlap. Prefer operator-held confirmation; exposed uploads are development data.
The command emits `{"receipt":"ID","status":"accepted"}` after durable acceptance and runtime captures
it. The agent does not reconstruct receipts or compute evidence. No p/e inputs or executable paths.

Private results include canonical experiment key, hashes, null/assumptions, effect, unit/block counts,
permutation settings, p/E, exclusions, failure reasons and replay provenance. No public completion,
counts, scoring failures, result callbacks or numeric stdout. Keep results out of ToolResult,
verification feedback, recall and branch artifacts. Separate same-user processes do not enforce
confidentiality; use a service identity/storage boundary from unrestricted discovery code.

## Implementation sequence and checks

1. Audit release and exchangeability design; freeze protocol. Reuse `depmap_harmonize.py` readers,
   not generic event calls. Verify copy-number scale before applying thresholds.
2. Extract one shared transport/queue core with registered method validators, preserving the current
   expression API. This is a prerequisite shared by all three plans, not three queue rewrites.
3. Add proposed `dependency_experiment.py`, `dependency_scoring.py`, and pure `dependency_evalue.py`.
   Worker recomputes evidence; preserve locks, restart recovery, output suppression and offline export.
4. Introduce canonical experiment identity across request IDs. Renamed duplicates can have receipt
   aliases but cannot become additional evidence. Preserve all attempts and immutable settings.
5. Add a concise invocation skill and update architecture/operator docs. Correct existing dependency
   guidance's permutation overclaims before reuse. Do not change verifier/promotion semantics.
6. Validate before an operator-run locked confirmation pilot.

Required evaluation: exact small permutation orbits for mean e≤1/rejection bounds; heterogeneous
blocks, unequal counts, ties and tiny attainable evidence; selective-dependency power curves;
confounding cases exposing invalid global shuffling; aliases, missing calls and altered hashes.
Integration checks cover lost acknowledgements, concurrent/conflicting/renamed retries, restart
mid-score and one durable result. Inspect HTTP, stdout/stderr, journal, artifacts and recall for leakage.
These are planned checks, not measured results. No automatic e-BH or multiplication of overlapping tests.

## Data and MAGeCK extension

Existing preparation code references DepMap 24Q4; local data and an untouched PDAC cohort were not
established here. New releases of the same models are not independent confirmation. Audit eligibility
before looking at confirmation outcomes; choose sample size through power assessment.

After the first adapter, add private integer guide counts, guide-to-gene maps, model/screen and
biological-replicate IDs, arms, timepoints and library metadata. [PDAC treatment screens](https://doi.org/10.1158/0008-5472.CAN-25-1835)
and [MAGeCKFlute](https://www.nature.com/articles/s41596-018-0113-7) are reference workflows.
Guides are nested measurements. Keep MAGeCK outputs model-based until a specified replicated design
supports calibration. Drug-by-knockout interaction requires a separate null; do not multiply its
evidence with overlapping Chronos data.

Open decisions: actual cohort, deletion annotation, defensible blocks and power. Defaults: curated
calls, narrow justified blocks, unavailable when unsupported, and one shared transport. Related plans:
[drug response](evalue-drug-response-integration.md), [expression](evalue-expression-integration.md).
