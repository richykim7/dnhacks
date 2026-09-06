# Learned pharmacotype association

Implementation status (2026-09-06): development operations, audited public PRISM/CCLE
acquisition, real CPU and three-seed GPU training/evaluation, and private frozen or
adaptive score-before-train replay are implemented. See the [model card](../../docs/pharmacotype-training.md)
and [operations and remaining gates](../../docs/pharmacotype.md). PCA remains selected;
PDAC utility and the synthetic power target are not established. Paired PDO access,
fresh independent donor audit and reviewed scientific confirmation remain required.
The specification below retains the full target and original source proposals.

Original planning specification, 2026-09-06. The document itself did not authorize implementation, acquisition, training or confirmation; subsequent user instruction authorized the implementation described above. Read together with [the shared native evidence contract](native-evidence-contract.md). The target interfaces below extend beyond the current implementation.
All training follows the [shared single-GPU scheduling rule](native-evidence-contract.md#coordination-on-the-shared-gpu): CPU work can overlap, but initial GPU pilots run serially; concurrency requires measured combined memory and throughput, a shared queue/lease, and separate artifacts. Individual job caps are not simultaneous GPU reservations.

## Biological tool and first endpoint

Build a reusable relationship tool between a model's baseline molecular state and its complete measured response profile. A pharmacotype is a registered vector of drug/dose/time responses; the neural critic's scalar is only the evidence interface. Retaining slopes, partial responses and plateaus permits nonlinear alternatives that one biomarker–AUC rank correlation discards.

The first endpoint is baseline bulk RNA versus a complete, fixed single-agent dose-response profile in one PDO assay population. Accept a registered drug list of length one or more, with per-drug dose grids and one exposure time. Start with a coverage-supported chemotherapy panel; do not require combinations, arbitrary time series or one hard-coded drug pair. Restrict confirmation to a single compatible panel and assay. Broader panels remain possible through new registrations after development evaluation.

Proposed operations:

| Operation | Parameters | Development output |
| --- | --- | --- |
| `profile` | cohort, panel, dose grid, exposure, assay version | Observed curves, replicate variation, donor coverage and exclusions |
| `neighbors` | query molecular state or observed pharmacotype, encoder, reference cohort, k | Similar development models with modality-specific distances and applicability flags |
| `predict-response` | baseline molecular profile, frozen predictor, registered panel | Predicted curve with held-out development error; no calibrated patient benefit probability |
| `compare-programs` | frozen division/redox/proteostasis gene set, population, panel | Development response contrasts, program ablations and candidate marker hypotheses |
| `submit-association` | registered null, model hashes, private cohort reference, request ID | Durable receipt only |

PDAC examples are hypotheses to investigate: division-state representations associated with paclitaxel or DNA-damage response shapes; redox/nutrient-stress programs associated with differential responses across an available compound panel; proteostasis/UPR states associated with measured proteasome/chaperone inhibitor responses where those drugs exist. A coverage query must precede the latter two uses; unavailable compounds cannot be substituted silently. Bulk expression remains a molecular proxy, and epithelial PDOs do not directly measure stromal protection. Pharmacological association establishes neither synergy, mechanism, nor clinical efficacy.

## Observations and assay contract

One unit is one independent patient-origin model, with a frozen selection rule for multiple biopsies, cultures, passages, clones or timepoints. Preserve them as nested records but choose one eligible baseline culture, or aggregate a prespecified comparable hierarchy, before scoring. Never count wells, doses, genes or culture derivatives as donors. Cell-line development splits use canonical donor/model lineage, resolving aliases across releases and repositories; unresolved origins are excluded from confirmation.

A manifest declares compound identifier/formulation, molar doses, exposure hours, viability technology/scale, vehicle and positive controls, media, passage, seeding protocol, plate/pool/run, technical replicates and molecular sampling time. Preserve source response scale: log fold-change, fraction viability and growth-rate measures are different assays. The old `drug_response.prepare` rejects viability outside [0,1]; do not silently inherit that restriction for assays whose normalized measurements legitimately exceed one. Define assay-specific finite-value and QC rules before outcomes are viewed.

For v1, require complete registered curves; no extrapolation or outcome-dependent panel pruning. Fix replicate-to-plate-to-donor aggregation and interpolation, if needed, from development. Missing molecular features use frozen training-derived fill values only within a registered tolerance. Log every exclusion privately. Complete-case selection itself can induce association: require missingness/eligibility determined independently of the molecular-response pairing under the registered null, or redefine and justify the eligible population. A mask encoder is a development option, not a proof that missingness is ignorable.

Fit RNA scaling, gene order, response scaling and all batch transformations on development donors. Apply separate frozen transformations to each view. Shared plate controls, pooled screens, cohort-wide quantile normalization and batch corrections fitted with future donors can create dependence across updates. Document the conditioning argument or fail confirmation eligibility; unique IDs do not repair this. Pooling study strata or residualizing covariates does not provide general conditional independence testing.

## Public source feasibility and split decisions

The following records are the original source proposals. The completed PRISM/CCLE
audit and verified PDO access limitations are recorded in the model card above;
none is a verified untouched confirmation set.

- **Broad PRISM/CCLE: training and development.** The primary study reports 4,518 compounds across 578 cell lines using pooled molecular barcoding. Those are neither 578 PDAC patients nor 4,518 complete dose-response series. Audit primary versus dose-response releases, CCLE expression joins and donor aliases. Use this broad source to train response representations and predictors, with PDAC held-out development slices; do not transfer its assay scale directly to PDO viability. Shared pools are a particular confirmation obstacle. [Broad primary study record](https://www.broadinstitute.org/publications/broad650611), [author-hosted study](https://golublab.broadinstitute.org/files/golub-lab/files/corsello-2020-discovering-the-anticancer-potentia_1.pdf).
- **Tiriac PDO library: preferred PDAC development candidate.** The primary publication is verified; reviewer inventories report 114 cultures from 101 patients and 66 pharmacotyped PDOs. These figures require source-table rechecking: this session's PMC full text was challenged and the Europe PMC XML endpoint unavailable. They must not become confirmation denominators. Audit paired baseline expression, donor repeats, exact drug/dose coverage and downloadable processed responses before selecting splits. Published signature/outcome exposure makes development the conservative default. An untouched split is a candidate only if the operator documents no outcome-informed selection. [Primary publication record](https://pubmed.ncbi.nlm.nih.gov/29853643/).
- **Driehuis independent PDO collection: external development or conditional confirmation candidate.** The publication reports 30 PDO lines from pancreas/distal bile-duct tumors and screening of 76 compounds. The EGA RNA dataset instead lists 31 samples; neither number establishes independent PDAC donors with complete molecular-response joins. EGA explicitly requires committee approval. Resolve histology, normal cultures, repeat samples, overlap with other libraries and response-table access before counting units. Public metadata is not unrestricted molecular data. [Publication](https://pubmed.ncbi.nlm.nih.gov/31818951/), [primary full-text record](https://pmc.ncbi.nlm.nih.gov/articles/PMC6936689/), [EGA RNA/access record](https://ega-archive.org/datasets/EGAD00001005217).

Prefer PRISM training → Tiriac development → separately governed, untouched PDO confirmation if access and compatible measurements permit. If Driehuis is too small or inaccessible, prospective fresh-donor acquisition is an unresolved dependency, not an implied assignment. Repartitioning an inspected cohort does not restore freshness. The first deliverable can therefore be a useful development tool with confirmation explicitly unavailable.

## Encoders, critic and native evidence

Train the molecular encoder and response encoder separately: RNA masked reconstruction with a small bottleneck, and response-curve reconstruction with dose-aware features. Start with compact MLPs; compare identity/frozen pathway features and PCA. A separate supervised prediction head provides development predictions. Neither view encoder may consume the other view at confirmation, and both freeze before confirmation.

Train a bounded cross-modal critic `c_t(X,Y)=tanh(f_t(X,Y))` on matched versus donor-crossed development pairs, optionally optimizing expected log factor after a stable discriminative initialization. Freeze architecture, seeds, training budget and stake rule through development. Critic training does not replace representation training and does not establish calibration by itself.

Declare H0: the two frozen measured representations are independent in the specified eligible PDO population/assay stratum. It is not a null of raw biological independence or zero causal effect. For two fresh iid independent donor units, use exactly the shared canonical kernel:

```
h_t = (c_t(X1,Y1) + c_t(X2,Y2) - c_t(X1,Y2) - c_t(X2,Y1)) / 4
factor_t = 1 + lambda_t * h_t        # 0 <= lambda_t <= 0.9
log_W_t = log_W_previous + log1p(lambda_t * h_t)
```

The critic and stake are measurable before this block. Under H0 all four terms have equal conditional expectations; boundedness gives a positive factor of conditional mean one. There is one factor per two donors. This follows the shared application of [sequential independence betting](https://proceedings.mlr.press/v202/podkopaev23a.html), subject to the actual sampling assumptions.

Use an externally trained critic to score the first eligible block. Persist the score transition, then train the critic on permitted past scored blocks for the next block; validation/early stopping may use only earlier data. Keep encoders frozen. A constant critic yields wealth one, distinct from unavailable evidence. No selecting the best seed or endpoint after confirmation, no multiplying hypotheses, and no presenting maximum wealth as a final e-value. A finite-cohort replay is auditable only under its original sampling justification; random ordering is not an iid proof. The expression code's two-burn-in/four-scoring-batch minimum is an existing policy, not a sample-size theorem for this new endpoint.

## Compute, interfaces and delivery

The parent centrally verified an idle L40S with approximately 46 GB memory; it is not reserved, and this planning task does not connect. Following authorization, benchmark a bounded pilot: one RNA encoder, one response encoder and one critic, three development seeds, capped epochs with early stopping. Measure examples/second, peak memory, training time and donor-held-out curve error before expanding. Compare CPU pathway/PCA plus ridge prediction, AUC/Spearman descriptions, and bounded kernel critics using the same native factors and donor budgets. Select the learned variant only for reproducible development utility or power gain; GPU occupancy is not a success criterion.

Proposed modules are `pharmacotype_data.py` for contracts/joins, `pharmacotype_encoder.py` for artifacts, `pharmacotype.py` for development operations and `pharmacotype_scoring.py` for private registration/worker glue. Shared native-core modules own association arithmetic and process ledger; these names remain to be coordinated. Reuse `experiment_transport.QueueStore`, durable receipts, private worker/export patterns and encoder hashes. Preserve `drug_response.py` as the conventional baseline and reuse suitable curve logic. Do not rewrite the queue or substitute this method into `learned_two_sample_e`.

Proposed CLI verbs are `prepare-dev`, `train`, `profile`, `predict`, `register`, `submit`, and operator-only `replay/export`. Artifacts contain feature/panel order, scales, training donor keys, source hashes, architecture, software and split provenance. The ledger records null/family/population, model/preprocessing/kernel hashes, canonical donor/segment IDs, cursor, critic/optimizer/RNG state, stake, log wealth and audit transitions. Aliases cannot reset evidence. Atomic transitions and deterministic replay must prevent double increments after crashes; append-new-data support waits for explicit exactly-once tests.

Development curves, predictions and error reports enter ordinary exploratory artifacts. Confirmation observations, effects, exclusions, failures and wealth remain outside agent filesystem permissions, HTTP responses, logs, recall and journals. A same-user subprocess is insufficient isolation. Keep falsifier, `ToolResult`, branch monitoring and human promotion unchanged.

## Incremental milestones and release gates

1. Audit source access, panel joins, donor identities and normalization; publish development counts, a prespecified required confirmation budget and locked schemas. Keep the realized eligible confirmation count, coverage and exclusions operator-private so they cannot guide adaptive panel/cohort selection. Stop confirmation work if independence or access is unsupported.
2. Deliver development profiles and CPU baselines; validate dose units, aliases, repeated cultures, missingness and assay incompatibility fixtures.
3. Train/evaluate compact encoders and critic on development only; release model cards with split and domain-shift limitations.
4. Implement shared-kernel integration and private replay. Test conditional-mean symmetry, score-before-train instrumentation, artifact tampering, restart at every transition, reordered releases, overlap and receipt aliases.
5. Before confirmation release, simulate at least 10,000 null streams with rejection uncertainty at final and anytime thresholds; examine heavy tails, shared-control contamination and invalid current-block training/pseudoreplication controls. Estimate power/detection delay at the audited donor budget against nonlinear and simple alternatives. Predeclare a target such as 80% power for a development-sized alternative; insufficient power blocks the scientific pilot, not the development UI.

Release confirmation only after statistical review of preprocessing/sampling, sufficient fresh donors, frozen endpoint selection, tested privacy and deterministic recovery. No confirmation result is promised. Limited matched PDO counts, controlled access, culture selection and shared normalization are material unresolved risks.
