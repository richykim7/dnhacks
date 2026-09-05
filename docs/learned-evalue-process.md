# Learned e-values: process and slide notes

## What we set out to build

A learned statistical judge for expression experiments: a small neural network learns from earlier
observations how to bet on differences between two groups. Fresh observations determine whether
those bets accumulate evidence. This is a numerical two-sample test, separate from the LLM judge.

The method comes from Pandeva et al., **Deep anytime-valid hypothesis testing**, AISTATS 2024.
We saved the [published paper and complete searchable text](../research/deep-anytime-valid-hypothesis-testing/README.md)
in the repository, including all appendices, with a reading guide for the construction and proofs.

## Important steps and decisions

1. **Reviewed the statistical claim before connecting it to the application.** The test asks whether
   two expression distributions differ. It cannot by itself establish a specific gene effect,
   direction, or biological mechanism. We agreed to implement standalone diagnostics first; existing
   verification decisions remain unchanged.
2. **Made the independent-unit assumptions explicit.** Real inputs require donor identifiers,
   provenance and a documented sampling design. Unknown dependence is not repaired by shuffling.
   Shared donors across groups are rejected. Technical-replicate aggregation requires an explicit
   compatible protocol. Synthetic and already aggregated data have explicit modes.
3. **Separated representation learning from evidence collection.** PCA and a masked-gene autoencoder
   train on a separate cohort. Their gene alignment, log1p(TPM) preprocessing, means, scales and
   weights are frozen before testing. Artifacts record training provenance, and known training/test
   donor overlap is rejected. Unique identifiers cannot prove independence or detect every alias.
4. **Implemented the learned bettor.** The first two batches provide training and validation.
   Each new batch is scored before entering either set. The neural payoff is bounded and
   antisymmetric under exchanging the groups. Batch scores multiply into wealth, accumulated in
   log space. We return final wealth and preserve the complete scoring path separately.
5. **Tested the failure modes directly.** Tests cover future-batch perturbations, exact averaging
   over pair swaps under the null, repeatability, donor overlap, insufficient samples, frozen
   preprocessing, missing-gene imputation and evidence-utility edge cases. Both encoder-training
   CLIs were exercised on a separate synthetic fixture. The repository skill loader finds the new
   usage guide.
6. **Ran a pilot and fixed report serialization.** Small pilot runs exercised the complete pipeline,
   including an intentionally invalid judge that memorizes the labels it then scores. A NumPy
   integer in the report initially prevented JSON serialization; explicit numeric conversion fixed
   the export. The larger evaluation used separate seeds and a frozen configuration.
7. **Compared against simpler methods and recorded losses as well as wins.** The initial evaluation
   contains 200 null runs and 50 runs each for mean shifts, variance shifts and a difference hidden
   from a fixed projection. It compares learned-encoder, PCA, identity, scalar and fixed-projection
   bettors with ordinary permutation p-values and calibrated-p evidence.

## How the judge works

```text
Separate training cohort → frozen encoder
                                  ↓
Earlier test batches → train bettor → score fresh batch → update log wealth
                           ↑                 ↓
                           └── use that batch only after scoring
```

For one fresh pair, the score is `1 + tanh(clip(g(x) - g(y), -4, 4))`.
Under equal distributions and the stated independence assumptions, exchanging the pair negates the
payoff, making the score conditionally fair. This provides the statistical basis for monitoring
wealth against `1/alpha`. Simulations check the implementation; they do not prove the theorem.

## Results useful for slides

All figures below are synthetic and use alpha = 0.05. The two rejection summaries are different:
**final wealth** is the returned e-value; **ever crossing** means the path reached the threshold at
some earlier batch, even if wealth later fell.

| Finding | Measured result | What it supports |
| --- | --- | --- |
| Learned-encoder null behavior | Final rejection 0/200; crossing 2/200, with pointwise 95% interval about 0.27%–3.57% | No obvious inflation in this simulation; limited precision |
| Concrete leakage control | Invalid label-memorizing judge rejected 200/200 null runs | The harness detects this specific misuse of scored data |
| Mean-shift comparison | Final rejection: learned encoder 70%, PCA 10%, scalar 88%, ordinary permutation 100% | Learned features help relative to PCA here, but simpler baselines can win |
| Information lost by projection | When only the eighth coordinate shifts, a fixed first-four-coordinate bettor has 0/50 final rejections | Compression can hide a real difference; null validity does not imply universal power |
| Verification boundary | E-values are separate diagnostic artifacts | A large distribution-level score is not automatically a biological verdict |

See the [evaluation record](../research/learned-evalue-validation/README.md) for the full table,
uncertainty, timing, configuration and replay commands. The permutation comparator uses mean
distance; its low variance-shift power is not evidence against permutation methods in general.

The null benchmark took 106.9 seconds for 200 repetitions across the compared methods. Extrapolating
that measured throughput gives roughly 89 minutes for the proposed 10,000 repetitions. We have
run the reported initial budgets, not that larger evaluation. Exact floating-point replay depends
on the recorded software environment.

## What is implemented and what remains

Implemented: standalone CPU bettor, explicit sampling contract, log-wealth diagnostics and replay
metadata, PCA/autoencoder training and loading, evidence utilities, tests, benchmark harness and
agent usage instructions. [Usage guide](../skills/learned-evalue/SKILL.md).

Integration validation on the combined code at base `f7564fd`: **594 Python tests passed, 12 skipped**,
including all 21 targeted e-value tests. The frontend production build, two frontend unit tests,
all ten browser scenarios, document links and diff checks passed. Skips belong to existing local
data/event-dependent tests; the new e-value suite ran with its optional dependency installed.

Still required: select a real expression cohort and comparison; establish disjoint encoder
training/development/evaluation units; measure biological utility and realistic training costs.
Investigation-wide multiple-testing control, verification integration and a UI wealth view require
separate contracts and work. No real-cohort power improvement is claimed.

## Suggested two-slide structure

- **Slide 1 — From a trained judge to valid evidence:** distinguish encoder and bettor; show the
  past-data training → fresh-data scoring loop; state the independent-donor and diagnostic-only
  decisions.
- **Slide 2 — What the validation taught us:** show the null/leakage comparison and the baseline
  results; emphasize that simpler methods sometimes win and compression can hide signal; finish
  with the real-cohort evaluation still needed.
