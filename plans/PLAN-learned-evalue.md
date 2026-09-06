# Plan: learned betting e-values for expression experiments

Status: standalone CPU/CUDA diagnostics, real-expression encoder training/evaluation, and a
standalone wealth-path report are implemented. The expanded synthetic validation includes 10,000
null repetitions and 100 repetitions for each of three predefined alternatives. Verification and application UI integration remain
separate reviewed phases. Coordinate ownership on the Board before editing shared interfaces.

Confirmed initial scope: standalone diagnostics, with existing verification decisions unchanged.
Real expression inputs require donor identifiers and documented sampling assumptions. Synthetic or
already aggregated inputs use an explicit independent-row mode; independence cannot be inferred
from a matrix or from unique identifiers alone. Verification integration is a later reviewed phase.

## 1. Repository baseline and scope

The integration points in this repository are:

- `src/dnhacksbio/methods.py`: `ToolResult`, including the primary effect and its `p_null`.
- `src/dnhacksbio/falsifier.py`: per-experiment soundness checks, including the primary null test.
- `src/dnhacksbio/explorer/explorer.py`: experiment execution, RESULT parsing and submission.
- `src/dnhacksbio/explorer/verifyqueue.py`: conversion to `ToolResult` and verification writeback.
- `src/dnhacksbio/webui/data.py`: experiment result retrieval for presentation.
- `frontend/src/`: the current React presentation layer for any later diagnostic visualization.
- `pyproject.toml`: package dependencies and test configuration.

Existing modules remain the source of truth for their current interfaces. Paths outside the
implemented scope below remain proposed deliverables.

The first implementation is `src/dnhacksbio/learned_evalue.py`, `expr_encoder.py`, and `evalues.py`,
with `scripts/train_expr_encoder.py`, `scripts/evalue_harness.py`, tracked regression tests and
`skills/learned-evalue/SKILL.md`. The executable API extends the sketch below with a required
`SamplingContract` and replay metadata; encoder artifacts use non-pickle NPZ, and identity features
are supported explicitly. Install with `uv sync --extra dev --extra evalue`.
Initial synthetic results and limitations are recorded in
`research/learned-evalue-validation/README.md`. Real-expression measurements and the frozen
GSE212041 protocol are in `research/learned-evalue-validation/real-expression/README.md`.
The real encoder uses an independent training partition of that study; GTEx was not used.

The first deliverable is a standalone two-sample test with reproducible artifacts and validation.
Gate integration follows only after the null hypothesis and evidence-selection rules are specified.
The experiment runtime must be able to import the package and load the configured encoder artifact;
verify that through the actual experiment entry point before integration.

## 2. Objective and terminology

Given two groups of expression vectors, produce a multivariate e-value using a neural bettor on
features from a frozen expression encoder. Compare a learned encoder with a frozen PCA baseline and
predefined scalar and permutation baselines. Improved power is a measurement target, not a promised
result.

- **Bettor / payoff function g**: the trainable network inside an experiment. It is distinct from the
  LLM fork judge and from the falsifier.
- **E-value**: a nonnegative random variable with expectation at most one under its stated null.
- **Wealth process W**: the sequence of accumulated betting scores. Its final value supplies evidence
  for one specified experiment; its path supports diagnostics and an anytime threshold plot.

Methodological basis: Pandeva, Forré, Ramdas and Shekhar, *Deep anytime-valid hypothesis testing*
(AISTATS 2024). Implement the construction directly, with its assumptions documented alongside the
code. Public references are listed at the end.

## 3. Statistical construction

### 3.1 Observations and null

Observations are pairs Z = (X, Y), with X from group A and Y from group B. The initial supported
setting is independent, identically distributed units within each group and independent groups.
The null is equality of the two expression distributions: H0: P_X = P_Y.

Pair units by a data-independent rule: choose the seed before examining the experiment, shuffle
within groups, pair by index, and truncate to the smaller group. Record unused units and the order.
Shuffling does not turn dependent samples into independent units.

This omnibus null is different from a claim about a particular gene, pathway, effect direction, or
causal mechanism. A large e-value may reflect a difference unrelated to the primary readout. Keep the
primary readout's own null evidence unless a reviewed contract explicitly makes the omnibus null the
experiment's hypothesis.

### 3.2 Payoffs, training, and scoring

Use DAVT-Projection: T1(x, y) = x and T2(x, y) = y, with g mapping a single sample to a scalar.
The resulting payoff is antisymmetric under exchange; this is distinct from the paper's
DAVT-Swap variant, whose network takes paired inputs. Choose one consistent sign convention for
training and scoring:

    h(x, y) = tanh(clip(g(x) - g(y), -4, 4))
    S_t = product over pairs j in batch t of (1 + h(x_j, y_j))
    W_0 = 1
    W_t = W_(t-1) * S_t

Under the null, exchanging X and Y negates h, so its conditional expectation is zero when the
current bettor depends only on past data and the next pairs satisfy the sampling assumptions.
Independence of fresh pairs makes the product batch score have conditional expectation one. The
resulting nonnegative martingale supports Ville's bound:

    P_H0(any t with W_t >= 1/alpha) <= alpha

Train the network to maximize the sum of log(1 + h(x, y)) on past training pairs. Warm-start each
update from the previous network. Use Adam and early stopping, holding the most recent available
batch out of the optimization set for validation.

Sequence:

1. B1 is training data and B2 is validation data; neither is scored.
2. Score B3 with that trained network, then update using only B1 through B3.
3. Repeat: score each fresh batch before using it in any training or validation decision. When the
   newest scored batch becomes validation, move the former validation batch into training.
4. Return final wealth after the predefined data stream. Log the full path separately.

Accumulate wealth in log space. Define finite serialization behavior for very large wealth without
inflating it; never replace final wealth with the running maximum and call that maximum an e-value.
A separately specified stopping rule can return stopped wealth, but is not required for the initial
final-wealth implementation.

### 3.3 Independent units and preprocessing

Aggregate repeated samples to one vector per independent unit when unit identifiers are available.
Reject unsupported dependence structures rather than treating unrecognized samples as independent.
If a donor appears in both groups, the independent-group construction does not apply unchanged.

An average batch score, S_t = 1 + mean_j h(x_j, y_j), can relax independence within a batch when the
payoffs remain conditionally centered. It does not repair dependence between training data and
future batches. Do not use averaging as a fallback for unknown donor identifiers or arbitrary batch
effects.

Use a frozen encoder and preprocessing learned from external training data, with experiment data
excluded. Store gene identifiers, transformation rules, training means/scales, and the training
manifest with the artifact. Do not fit PCA, scaling, or feature selection on future scored batches.
For initial validation, keep encoder training, hyperparameter tuning, and final evaluation units
separate. Treat any transductive alternative as a separate construction requiring justification.

A frozen lossy encoder preserves null validity but can hide alternatives. Include a benchmark with
signal outside the retained features; do not inherit a universal consistency claim from the paper.
Donor aggregation must follow a predeclared, group-compatible measurement protocol: unequal replicate
counts can change aggregate distributions even when individual measurements have the same law.

## 4. Proposed implementation

### 4.1 Learned bettor

New module: `src/dnhacksbio/learned_evalue.py`.

```python
@dataclass(frozen=True)
class LearnedEConfig:
    batch_pairs: int = 8
    burn_in: int = 2
    hidden: tuple[int, int] = (64, 64)
    lr: float = 5e-4
    patience: int = 10
    max_epochs: int = 500
    weight_decay: float = 1e-2
    tanh_clip: float = 4.0
    seed: int = 0
    encoder: str | None = None  # TPM input requires an explicitly supplied frozen NPZ artifact

@dataclass
class LearnedE:
    e_value: float | None
    status: str
    reason: str
    per_batch: list[float]
    log_wealth_path: list[float]
    n_pairs: int
    n_batches: int
    n_scored: int
    config: LearnedEConfig

def learned_two_sample_e(Xa, Xb, *, genes, sampling, unit_a=None, unit_b=None,
                         config=LearnedEConfig()) -> LearnedE:
    ...
```

The initial data-size policy requires four scored batches after the two burn-in batches: with b = 8,
that is 48 pairs. This is a proposed operational threshold, not a theorem about sufficient power.
Below the threshold, return an explicit unavailable status with `e_value=None`; the primary p-value
path remains available. A valid but uninformative e-value of one is a different outcome.

Validate dimensions, gene identifiers, supported input units, finite values, and configuration.
Specify label-symmetric missing-data handling and report dropped/unused units. Seed NumPy and Torch
randomness, and record software versions, artifact identity, and the pairing order needed for replay.

### 4.2 Encoder and baseline artifacts

New modules: `scripts/train_expr_encoder.py` and `src/dnhacksbio/expr_encoder.py`.

- Start with a PCA-64 encoder fitted on a separate bulk RNA-seq training set. GTEx gene TPM is a
  candidate source; record the exact release, accessions, units, and exclusions in a manifest.
- For the learned encoder, start with a masked-gene autoencoder: approximately 19k genes to 512 to
  128 dimensions, 15% input masking, and MSE on masked entries. These are initial settings to tune
  on development data, not guaranteed optimal choices.
- Store a fixed gene list and preprocessing based on log1p(TPM) and training-set mean/standard
  deviation. Reject incompatible input scales unless an explicit supported conversion exists.
  Impute missing genes in the correct transformed space using stored training statistics.
- Write versioned artifacts beneath `data/processed/`, which the repository excludes from Git.
  The PCA and learned encoders should use the same loading interface.
- Additional training sources or alternative architectures are optional follow-up work after the
  PCA baseline and validation are complete.

### 4.3 Evidence utilities and verification

Proposed new module: `src/dnhacksbio/evalues.py`, using only the standard library where practical.
Candidate utilities are `p_to_e(p) = 1/sqrt(p) - 1`, `e_to_p(e) = min(1, 1/e)`, e-BH, a mean merger,
and a product merger with explicit independence or conditional-validity requirements. Define edge
cases, including e = 0 and the prohibition on treating a zero Monte Carlo p-value as valid evidence.

Proposed additions to `ToolResult` and RESULT are optional `e_value` and `e_method` fields. Require
finite, nonnegative native e-values and identify the null they test. Preserve `p_null`, `effect`,
`expected_sign`, and unit counts for the primary readout. Unavailable native evidence must not
silently override the existing p-value path.

Before a native e-value can control a falsifier decision, specify:

1. How its null matches the submitted hypothesis and primary readout.
2. How adaptively chosen hypotheses are confirmed on data not used to choose them.
3. Which experiments belong to the multiple-testing family, including unsubmitted attempts.
4. How repeated queue drains and any filters interact with the declared error guarantee.
5. Which evidence source is selected in advance; do not choose whichever result looks stronger.

E-BH tolerates dependence between valid e-values; it does not make selectively reported or otherwise
invalid e-values valid. A drained queue is not automatically the full investigation family. Treat
family-level integration as a separate reviewed step after the standalone test works.

### 4.4 Agent and dashboard integration

Proposed skill: `skills/learned-evalue/SKILL.md`, describing the supported null, independent-unit
requirements, minimum data policy, invocation, and RESULT fields. State separately how primary
readout effects and null evidence are computed. Unit counts must have an explicit meaning rather
than silently conflating samples, donors, and pairs.

Add a wealth-path view to the web UI, carrying the artifact and method identity through result
storage and retrieval. Display the threshold 1/alpha alongside the path, and distinguish the plotted
path from the final evidence and verification verdict. Check the current UI/API owners on the Board
before changing presentation or result contracts.

## 5. Validation and comparisons

Proposed files: `tests/test_learned_evalue.py` and `scripts/evalue_harness.py`. The repository currently
ignores `tests/`; implementation must ensure the new tests are deliberately tracked and runnable.

Fast validation should cover:

- Repeatability with the same seed and environment.
- Unavailable results for too few independent units, unequal-group truncation, invalid input,
  missing-data accounting, and unsupported dependence.
- Score-before-training order, frozen encoder behavior, and bounded antisymmetric payoffs.
- E-value utility edge cases and the native-evidence/primary-p-value routing contract.
- A deliberately invalid control that trains on the labels of the batch it scores, demonstrating
  that the validation setup can detect a concrete leak. Label-blind scaling alone is not a guaranteed
  negative control with a prescribed amount of error inflation.

The simulation harness should report final-wealth distributions and threshold-crossing rates under
nulls, followed by power curves under alternatives. Start with independent synthetic data. For real
data resampling, define a valid null assignment scheme at the independent-unit level and document
its relationship to the sampling model.

Target 10,000 null repetitions for final evaluation if measured runtime permits. Report uncertainty
for rejection rates and account for the heavy tails of wealth when describing sample means. Null
simulations diagnose implementation failures; they do not prove validity over every null distribution.
Keep tuning runs separate from final evaluation.

Compare learned-encoder DAVT, PCA DAVT, a specified scalar bettor, and permutation testing under
matched data budgets and nulls. A scalar bettor is a deliverable if no suitable implementation exists
in the repository. Include the ordinary permutation test as well as calibrated-p evidence: calibration
can materially reduce power. Do not enforce a predetermined ordering of methods in unit tests.
Report cases where PCA, scalar, or permutation methods perform better.

## 6. Execution order and dependencies

1. Finalize the supported statistical contract and independent-unit checks.
2. Build the standalone bettor and synthetic validation, using fixed features initially.
3. Produce a frozen PCA artifact and measure per-run CPU/GPU cost.
4. Train the expression encoder and compare it with PCA on held-out evaluation data.
5. Integrate optional result fields and persistence, then the reviewed verification behavior.
6. Add the skill, run one experiment end to end, and add the wealth-path visualization.
7. Run the final frozen-configuration evaluation and record replayable demo artifacts.

Add required dependencies through `pyproject.toml`. The proposed stack uses Torch, NumPy, pandas,
scikit-learn, and plotting support; additional format readers depend on the chosen training data.
Select CPU or CUDA packages for the execution environment actually available. Benchmark training
and evaluation, then set run budgets from measured throughput.

For parallel implementation, the numerical module/harness and encoder training can be separate
scopes after the artifact interface is agreed. Verification and UI changes require Board coordination
with their current owners. This plan itself assigns no active implementation ownership.

## 7. Acceptance criteria and remaining risks

- The supported null and conditioning assumptions are stated and enforced by the data contract.
- Validation covers independent units, future-data leakage, numerical stability, and unavailable
  evidence without weakening the primary readout's existing checks.
- A fresh checkout can run documented validation with explicitly provided dependencies and artifacts.
- Results include reproducible configuration, artifact provenance, and uncertainty on comparisons.
- The demonstration describes the actual experiment and measured power; it does not claim that
  pretraining improves power unless held-out comparisons support that statement.

The main risks are small usable cohorts, unidentified dependence or confounding, an omnibus null
that does not support the submitted biological claim, adaptive reuse of confirmation data, unstable
wealth estimates, and an encoder that adds cost without improving power. Resolve these before
claiming investigation-wide error control or making native e-values a default verification gate.

## 8. Public methodological references

- Pandeva, Forré, Ramdas, Shekhar. *Deep anytime-valid hypothesis testing*. AISTATS 2024.
  https://proceedings.mlr.press/v238/pandeva24a.html
- Pandeva, Bakker, Naesseth, Forré. *E-valuating classifier two-sample tests*. arXiv:2210.13027.
- Shekhar, Ramdas. *Nonparametric two-sample testing by betting*. IEEE TIT 2023.
- Waudby-Smith, Ramdas. *Estimating means by betting*. JRSS-B 2024.
- Vovk, Wang. *E-values: calibration, combination and applications*. Annals of Statistics 2021.
- Wang, Ramdas. *False discovery rate control with e-values*. JRSS-B 2022.
  https://arxiv.org/abs/2009.02824
