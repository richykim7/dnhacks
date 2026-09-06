# Proposed shared native evidence contract

Planning specification, not implemented functionality or an authorization to train. All three selected plans depend on one reviewed common core rather than three independently invented scoring/queue engines. Existing `experiment_transport.py`, encoder artifact provenance and `learned_evalue.py` are reuse points; their current APIs do not implement all requirements below.

## Two useful surfaces

**Discovery surface:** reusable parameterized biological operations on explicitly exposed development/discovery data. Return profiles, coverage/QC, exploratory model predictions, maps, comparisons and candidate hypotheses with source and model provenance. These results are not calibrated confirmation or accepted graph findings.

**Confirmation surface:** submit a registered scientific hypothesis/process and frozen data/model references; return a durable receipt only. Private operators own observations, scoring, exclusions, effects, failures, wealth trajectories and export. No hidden-data success hints, filtered target rankings, completion callbacks or other proxies return through discovery artifacts. A separate same-user process does not enforce this boundary.

Scientific observation and evidence have distinct types. A drug-response vector or donor cell-state distribution is the phenotype; the witness's scalar output is its betting interface. A final scalar is valid only for its declared null. A process accumulates evidence from fresh biological observations for that same null; it does not multiply unrelated hypotheses or repeatedly viewed datasets.

## First native constructions

Require a locked independent-unit sampling contract. A frozen encoder may be trained on separate donor-disjoint sources; lossy encoding can hide alternatives. All transformations, feature definitions and model selection must respect the stated filtration. Do not claim raw distribution equality or independence is established by a result concerning only frozen measured representations.

### Independent-group distribution comparison

For fresh conditionally exchangeable X and Y under the registered null, with a past-measurable witness g_t, use the current expression pattern:

    h_t = tanh(clip(g_t(phi(X)) - g_t(phi(Y)), -4, 4))
    W_t = W_(t-1) * (1 + h_t)

The odd contrast changes sign under exchange, yielding zero conditional mean. Multiply across pairs only when the joint conditional sampling contract warrants it. Paired tissue from one patient is not the current independent-group construction. Observation-level independence cannot be inferred from distinct IDs.

### Native two-view association

Under independence of measured representations X and Y in a specified population/stratum, consume two fresh independent identically distributed biological units (X1,Y1),(X2,Y2). A bounded predictable critic c_t in [-1,1] gives:

    h_t = [c_t(X1,Y1) + c_t(X2,Y2) - c_t(X1,Y2) - c_t(X2,Y1)] / 4
    W_t = W_(t-1) * (1 + lambda_t*h_t), 0 <= lambda_t <= 0.9

Score all four terms with the same critic in evaluation mode: no batch-normalization updates, dropout-driven inconsistent comparisons, current-block fitting or future-unit preprocessing. Any scoring randomness must be fixed independently of the scored observations and replayable.

All four terms have the same conditional expectation under this null, and |h_t| <= 1. Therefore the factor is positive and has conditional mean one. This is one factor per two-unit block. Critic and stake depend only on permissible past/development data. Use separate frozen transformations of the two views; a jointly mixed encoding may manufacture dependence. Do not multiply the four evaluations as if they were independent factors.

An odd bounded transform of the four-term contrast is an alternative under full response-swap invariance, but the first implementation should use one reviewed canonical kernel. Categorical strata require their own sampling justification; residualization does not supply arbitrary conditional-independence testing. Nonstationarity, shared normalization and without-replacement sampling from an inspected finite dataset are not automatically covered by the independent-unit proof.

These are specifications applying established [DAVT](https://proceedings.mlr.press/v238/pandeva24a.html) and [sequential independence betting](https://proceedings.mlr.press/v202/podkopaev23a.html) principles. No new statistical theorem or universal neural-power advantage is claimed.

## Learning, process state and repeat use

Representation training and architecture/feature selection use training/development donors, separate from confirmation. GPU use is justified by measured training throughput and held-out utility; CPU PCA/fixed-feature/kernel baselines remain required. Do not train a large model simply to occupy the L40S.

Two explicit bettor schedules may be investigated: the existing two-burn-in-batch schedule, or an externally trained/selected critic that scores the first confirmation block. Neither relaxes unit independence. Small PDAC cohorts require predeclared power studies and acceptance budgets; the existing 48-pairs policy cannot silently be relabeled as a theorem or bypassed by counting cells/sites/genes.

A proposed private process record should identify schema/method/kernel version, scientific null/panel/population, immutable model/preprocessing hashes, sampling/stratum protocol, family, parent experiment, training/development exclusions and the canonical donor/data segment ledger. A receipt alias must not reset wealth or create fresh evidence. Reusing a donor across different experiments needs an explicit investigation-level policy; queue deduplication alone is not that policy.

For a locked finite cohort, a private worker may deterministically replay the original process and export its path. An eventual append-new-data mode must atomically persist cursor, consumed unit IDs, critic/optimizer/RNG state, current log wealth and audit events before acknowledging a scoring-state transition. Resume exactly once, or replay deterministically without counting a previous factor twice. This mode requires new tests and is not already supplied by the job queue. Biological units must be genuinely new; a new release or reordered matrix is not new data.

Store log wealth for stability; expose final or prespecified stopped wealth privately. The running maximum is useful for a threshold-crossing diagnostic but is not a replacement e-value. Do not automatically select the strongest seed, representation or endpoint after scoring. Do not multiply across tools, overlapping modalities or different nulls; preserve distinct processes and defer family combination to a separately reviewed policy.

## Validation and release gates

- Review the conditional-mean argument against the actual assay preprocessing and sampling, including shared references and pooled assays.
- Test fresh-unit bookkeeping, score-before-train, frozen artifacts, aliases, replays, interrupted updates and no duplicate increments.
- Use mathematically generated nulls plus deliberately invalid training-on-current-data and pseudo-replication controls. Real-label shuffling is a valid diagnostic only under its own specified transformation null.
- Measure final and anytime rejection rates, uncertainty, heavy-tail sensitivity, power and detection delay at equal independent-unit budgets. Compare frozen simple/PCA/kernel and learned approaches without requiring a predetermined winner.
- Verify useful development outputs separately from hidden evidence containment through HTTP, stdout/stderr, journals, artifacts, recall and human-facing exports.
- Fail closed when sampling, identity, access, effect coverage or sample-size design is unsupported. Exploratory functionality can still be useful, explicitly labeled; an uninformative e-value of one and unavailable evidence are different states.

No change to `ToolResult`, ordinary falsifier behavior, branch-future-success monitoring or human promotion is authorized by these plans. Biological association/distribution evidence does not establish that a subtree will produce a future discovery. Any future consumer must preserve this distinction and receive a separately specified contract.
