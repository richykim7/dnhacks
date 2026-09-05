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

## Paper-fidelity audit and GPU check (2026-09-05)

Conclusion: the implementation follows the paper's **DAVT-Projection** statistical construction
under the supported independent-unit null. It is an adaptation with explicit implementation choices,
not a reproduction of the paper's published benchmark results. Real-expression suitability remains
unverified because no real cohort has been evaluated.

| Paper component | Repository implementation | Assessment |
| --- | --- | --- |
| Section 6 projection operators | A scalar network applied separately to X and Y | Matches DAVT-Projection; the plan's earlier term “projection-swap” was imprecise and is corrected |
| Equation (5), product batch score | Sum of log pair scores, added to log wealth | Equivalent construction, with conservative finite serialization |
| Equation (6), learning log growth | Adam minimizes negative mean log score on past training pairs | Same unregularized objective up to scaling; weight decay and optimizer resets are implementation choices that can affect power |
| Algorithm 1, fresh scoring before reuse | Current scoring rows enter neither training nor early-stopping validation until after scoring | Direct call-order audit and future-data perturbation tests check this |
| Section 11.1, validation and transformed payoff | Latest past batch is validation; `tanh(clip(d, -4, 4))` is odd, bounded and monotone | Preserves conditional fairness for the independent two-sample setting; not an automatic extension to every operator/null in the paper |
| Initial batches | Two unscored training/validation batches | Follows the experimental training setup; choosing not to bet initially is valid, but Algorithm 1 itself describes scoring from the initial model |
| Stopping rule | Continue to a fixed horizon; return final wealth and separately report crossings | Valid fixed-horizon e-value adaptation; final rejection rates are not the paper's stopped-test power metric |
| Blob architecture and optimization | Benchmark uses 16/16 ReLU layers, no LayerNorm, 20 epochs, patience 5, learning rate 0.005 | Different from the paper's 30/30 LayerNorm/ReLU architecture and 500-epoch, patience-10, 0.0005 Blob settings; no benchmark-reproduction claim |
| Representation learning | Separately trained frozen expression PCA/autoencoder | Repository extension; null validity requires fixed preprocessing and independent data, while information loss can reduce power |

The arithmetic audit additionally enumerates all 64 orientations of six fixed unordered pairs with
an adaptive learner. Conditional on unordered iid-null pairs, the orientations are independent fair
coins; their average final wealth should be one. This checks adaptation together with scoring under
that finite setup. It does not establish validity for all data distributions or justify arbitrary
dependent samples. Another test instruments actual fitting/scoring calls to reject any scored row
that has already entered training or validation.

Audit validation: all 23 e-value tests pass; the combined repository suite has 615 passing tests
and 12 existing skips. Frontend build, two unit tests, ten browser scenarios and document checks pass.

GPU availability was checked through the local `gpu-ssh-handoff/connect.sh` launcher: the remote
device reports **NVIDIA L40S, 46,068 MiB memory**. The earlier training and benchmarks used CPU;
hardware availability was not checked before those runs and should have been. Pointers now exist
in local `CLAUDE.md` and shared `AGENTS.md` so future compute planning starts with the handoff.

This was a hardware/connectivity check, not a GPU training run. The remote default system Python
does not currently import Torch; other environments were not inventoried. The current bettor and
encoder trainer explicitly construct CPU tensors, so installing CUDA Torch alone will not move
training to the GPU. A GPU iteration needs an isolated environment, explicit device support,
device/replay validation and a timed smoke run before larger training. Connection information stays
in the local handoff; it is not copied into this document.
