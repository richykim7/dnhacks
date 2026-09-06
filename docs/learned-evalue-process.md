# Learned e-values: process and slide notes

Current status (2026-09-05): GPU encoder training, held-out real-expression evaluation, 10,000
synthetic null runs, slide figures, and the receipt-only background scoring service are implemented.
The trained biological two-sample diagnostic is based on Pandeva et al.; it is not an implementation
of Genentech's E-valuator agent-trajectory monitor. Sections below preserve historical milestones
and distinguish numerical validation, operational integration and remaining scientific evidence.

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

## Initial synthetic pilot (historical)

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

## Initial synthetic milestone (historical)

Implemented: standalone CPU bettor, explicit sampling contract, log-wealth diagnostics and replay
metadata, PCA/autoencoder training and loading, evidence utilities, tests, benchmark harness and
agent usage instructions. [Usage guide](../skills/expression-experiment/SKILL.md).

Integration validation on the combined code at base `f7564fd`: **594 Python tests passed, 12 skipped**,
including all 21 targeted e-value tests. The frontend production build, two frontend unit tests,
all ten browser scenarios, document links and diff checks passed. Skips belong to existing local
data/event-dependent tests; the new e-value suite ran with its optional dependency installed.

At that milestone, still required: select a real expression cohort and comparison; establish disjoint encoder
training/development/evaluation units; measure biological utility and realistic training costs.
Investigation-wide multiple-testing control, verification integration and a UI wealth view require
separate contracts and work. No real-cohort power improvement is claimed.

## Suggested two-slide structure

- **Slide 1 — From a trained judge to valid evidence:** distinguish encoder and bettor; show the
  past-data training → fresh-data scoring loop; state the independent-donor and diagnostic-only
  decisions.
- **Slide 2 — What the validation taught us:** show the 10,000-run null/leakage comparison and
  the real-cohort wealth figure. Actual GPU training and held-out expression evaluation are now
  complete: learned e=3,653, PCA e=86, scalar e=5,964. Emphasize that simpler methods sometimes win;
  one observational cohort does not establish general power or causal effects.

## Paper-fidelity audit and GPU check (2026-09-05)

Conclusion: the implementation follows the paper's **DAVT-Projection** statistical construction
under the supported independent-unit null. It is an adaptation with explicit implementation choices,
not a reproduction of the paper's published benchmark results. At the time of this audit, real-expression suitability was unverified because no real cohort had
been evaluated. The subsequent real-data iteration is recorded below.

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

This was a hardware/connectivity check, not a GPU training run. At that historical check, the
remote default system Python did not import Torch; other environments were not inventoried. At that point, the bettor and
encoder trainer explicitly constructed CPU tensors, so installing CUDA Torch alone will not move
training to the GPU. A GPU iteration needs an isolated environment, explicit device support,
device/replay validation and a timed smoke run before larger training. Connection information stays
in the local handoff; it is not copied into this document.

## Real expression and GPU iteration (2026-09-05)

The next iteration adds explicit CPU/CUDA and float32/float64 execution, recorded in model and
result metadata. Missing CUDA is an error. Initialization and masking draw only from an isolated
CPU RNG, so training leaves both the caller's CPU and CUDA random states intact. GPU tests check
repeatability, agreement with CPU arithmetic, and loading GPU-trained NPZ encoders on CPU.

We selected [GSE212041](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE212041), the public
processed neutrophil TPM cohort from LaSalle et al. The source contains longitudinal samples;
we retain only D0 samples from COVID-positive and symptomatic COVID-negative patients. Healthy
controls and all later/event-driven draws are excluded. The remaining 374 distinct donors split
by a fixed stratified seed into 149 training, 74 development, and 151 evaluation units. Training
contains 119 positive/30 negative donors; evaluation contains 121 positive/30 negative donors.
Unique donor labels and disjoint splits are checked. Recruitment, treatment, severity and cell
composition remain possible explanations of a distribution difference; this is not causal inference.

Before evaluation, `scripts/evalue_real_data.py prepare` freezes a protocol and hashes the source
and split files. We select the top 19,000 human genes by training-only log1p(TPM) variance, freeze
training means/scales, fit PCA64, and train a masked autoencoder with 512 hidden units and 128 latent
features for 100 epochs with 15% masking. This uses a separate training partition of the same study,
not an externally validated foundation model. Both preprocessing and representation fitting exclude
development/evaluation donors. The development partition is available for device benchmarking;
it is not used to choose features, architecture or epoch count in this fixed-budget run.

On the L40S with Torch 2.10.0+cu128, real-data autoencoder training (float32) took 3.41 seconds;
PCA CPU fitting took 0.22 seconds. Timings include model fitting, exclude data transfer, and apply
to this modest 149-donor training set. Fast fitting and decreasing training loss are not evidence
of generalization. Artifacts, source TPM, and donor-level replay remain in ignored data/processed.
The repository contains reproducible scripts and aggregate reports rather than patient-level data.

The primary comparison predeclares a seed, 30 donor pairs, four pairs per batch, and a 64/64 bettor
with at most 100 epochs per update. Two batches are burn-in; six batches are scored, the final one
partial. Comparators are PCA, learned encoder, a predeclared IFIT3 scalar bettor, and a mean-distance
permutation test using frozen standardized genes. Ten other pairing orders are sensitivity checks
on the same donors, not independent power trials; no strongest-seed selection or evidence merger.

A separate real-expression null audit fixes unordered, disjoint held-out donor pairs and gives each
pair an independent fair orientation. Pair order remains fixed (`pairing="in_order"`); reshuffling
would break the conditional construction. This checks the learner on real feature geometry under
an artificial null. It does not assert that observed COVID labels were randomized. The synthetic
null evaluation completed 10,000 repetitions with disjoint seeds and the original fixed
pilot architecture. The real-expression counts and expanded synthetic results are recorded below.

### Held-out real-data results

The predeclared primary seed gave final e-values of **3,652.81 (learned encoder), 85.76 (PCA),
and 5,964.41 (IFIT3 scalar)**, all above the alpha=0.05 threshold of 20. Ordinary permutation
p=0.0001; calibrated e=99. The learned encoder exceeded PCA, but the scalar gave stronger evidence.
Ten predeclared order/subsample checks rejected at final wealth 9/10, 5/10 and 8/10 respectively.
Those checks reuse donors and are sensitivity measurements, not independent estimates of power.

In 200 fair-orientation null repetitions on fixed real donor pairs, final rejections were 0 for
all three representations. Ever-crossing counts were 5 learned, 4 PCA and 0 scalar. Learned
crossing rate: 2.5% with pointwise Wilson 95% interval 1.07%–5.72%. Small observed wealth quantiles
cannot estimate the heavy-tailed expectation reliably. The null audit makes no claim that clinical
COVID labels were randomized or free of confounding.

The public TPM/artifact API is exercised end to end for PCA and autoencoder comparisons, including
its donor-overlap guard and raw-input/artifact replay hashes. Frozen-manifest checks reject changed
source files, changed cohorts, training artifacts from another split, or donor overlap. The small
bettor uses CPU after warm timing (0.194 s CPU / 0.355 s CUDA), while the encoder uses CUDA.

For slides, use [the wealth figure](../research/learned-evalue-validation/real-expression/wealth.svg)
and [the standalone report](../research/learned-evalue-validation/real-expression/index.html).
A current second slide can now say: real RNA-seq training on the GPU; learned features beat PCA in
one predeclared held-out comparison; a single-gene baseline still gives stronger evidence; null
and order-sensitivity checks delimit what the result establishes. It should not claim clinical
validation, causal COVID effects, universal power improvement, or investigation-wide error control.

### Reproducibility and regression checks

CPU/GPU tests exercise the actual L40S, protect caller RNG state, compare device arithmetic and
load GPU-trained encoders on CPU. Additional failure tests reject changed source downloads,
changed training partitions, repeated donor records and duplicated simulation seed streams.
The real-source files are pinned by SHA-256, and the frozen protocol, split hashes, training
losses, execution settings and aggregate results are retained with the report.

The fresh-checkout Python gate needs the repository's optional `llm` extra because the existing
web server imports the Claude SDK. Use `uv sync --extra dev --extra evalue --extra llm` before
that full gate. This iteration also checked the original checkout's wider local suite against
the new numerical code: 615 passed and 12 existing data/event-dependent skips. Frontend production
build, two unit tests and all 14 browser tests passed on the synchronized branch. The standalone
report was checked at desktop/mobile sizes without page errors or page-width overflow.

### Expanded synthetic validation completed

We completed the plan's 10,000 null repetitions across four independent seed ranges, sharing
identical frozen synthetic encoders. Learned-encoder final rejection: **20/10,000 (0.20%)**;
anytime crossing: **112/10,000 (1.12%; pointwise 95% interval 0.93%–1.35%)**. Ordinary permutation
rejected 513/10,000 (5.13%, interval 4.71%–5.58%). The deliberately invalid label-memorizing
control rejected 10,000/10,000, confirming that the harness catches that concrete leakage error.
Four one-thread workers completed in about 22.3 minutes wall time. Rejection counts are pooled;
heavy-tailed wealth quantiles are kept per-shard. The merger verifies disjoint seeds and matching
configuration, software and artifact identity.

The expanded alternative evaluation uses 100 repetitions for each predefined mean, variance and
omitted-coordinate shift, with the same CPU environment as the final null evaluation. Full counts,
uncertainty and replay commands are in the [validation record](../research/learned-evalue-validation/README.md).
These are implementation checks and power measurements for the specified synthetic distributions,
not a universal validity proof. The GPU real-expression study uses its separately recorded environment.

The completed deliverable is a standalone, replayable diagnostic workflow with actual GPU encoder
training, held-out real expression comparisons and a wealth-path report. Native verification,
adaptive confirmation-data selection, investigation-family accounting and application UI wiring
remain the separately reviewed integration phase described in the plan.

Final focused CUDA validation: **33 passed** on L40S. The local CUDA-only test is skipped because
this checkout has no GPU; the same test runs and passes on the remote device.


## Background scoring and agent blinding

The first invocation guide exposed the numerical diagnostic to the discovery agent. The revised
interface separates experiment submission from scoring: an agent saves TPM inputs and a declared
specification, runs `python -m dnhacksbio.expression_experiment`, and receives a durable receipt
from the command. The runtime captures stdout automatically; the agent does not need to repeat,
reconstruct or return the receipt.
The client imports no numerical code and never relays service response bodies or scoring failures.
The self-contained `expression-experiment` skill replaces the direct-call skill. General rigor and
DepMap guidance no longer request native diagnostic emission.

A separate operator service durably queues each request before acknowledgement. Stable IDs make
transport retries idempotent; conflicting retries fail. A worker process calls the tested numerical
implementation with a frozen encoder and fixed settings. Results, failures and complete replay
inputs stay in the operator's database, outside the discovery journal, recall and branch feedback.
There is no result-reading HTTP endpoint. This introduces no verifier or family-selection change.

Validation covers a real command through Explorer, asynchronous scoring using the actual library,
private result persistence, unchanged receipts before/after success or failure, rejected conflicting
retries and malicious response-body suppression. Fixtures are synthetic and model actions scripted;
this is an integration check, not new biological validation or a live-LLM study.

A separate process does not enforce filesystem confidentiality against unrestricted code running
as the same OS user. Production blinding requires the service's state and confirmation data to be
outside the agent's access permissions, and human exports must not be fed back during discovery.
The upload interface cannot prove that submitted donors were untouched during hypothesis selection.
Operator setup and replay procedures are in [the service guide](expression-scoring.md).


## Source-paper identification

Our numerical implementation follows [Pandeva et al., Deep anytime-valid hypothesis testing,
AISTATS 2024](https://proceedings.mlr.press/v238/pandeva24a.html), adapted with a frozen expression
encoder and an independent two-sample contract. Earlier use of “trained judge” described the neural
bettor and should not be read as a claim that we implemented a learned judge of agent trajectories.

The paper the user recalled is [Sadhuka et al., E-valuator: Reliable Agent Verifiers with Sequential
Hypothesis Testing](https://arxiv.org/html/2512.03109v2), with Genentech-affiliated authors (v2,
28 May 2026). It learns from labeled successful/unsuccessful trajectories and verifier-score histories,
then calibrates an alarm threshold on a separate set. Its usual null is a successful trajectory;
its false alarm is incorrectly flagging one. Estimated density ratios need calibration; they do
not automatically inherit exact e-process guarantees. We have not implemented or evaluated this
trajectory-monitoring method. Our biological-null benchmarks are not E-valuator benchmarks.

## Background-scoring rollout and evidence index

[PR #26](https://github.com/richykim7/dnhacks/pull/26) landed the GPU/real-data diagnostic work.
[PR #34](https://github.com/richykim7/dnhacks/pull/34), main `d3d545bd`, landed the submission client,
durable queue, worker, receipt-only skill and explicit exception to Explorer's usual RESULT instructions.
That commit passed **117 Python tests, 6 frontend unit tests, 18 browser tests and the frontend build**.
The two Python skips were local CUDA and opt-in Docker; the background worker tests used native processes.
Eight dedicated integration tests cover instruction delivery, the command/worker path, persistence,
retry identity, failures, timeout, restart recovery, frozen configuration/artifacts and feedback exclusion.
These are scripted model actions plus real command/numerical execution, not a live autonomous-agent trial.

At rollout the local service was started on localhost:8793 with the previously trained autoencoder,
seed 0 and batch size 8. Its result HTTP route returns 404. Default minimum size is 48 donors per group
and the numerical default is at most 500 epochs per update. This differs from the recorded real-data
benchmark (30 pairs, batch size 4, at most 100 epochs) and the small synthetic benchmark. Do not present
any one benchmark as an exhaustive validation of all deployed configurations or future cohorts.
The service files remain outside the normal discovery artifact directory. This prevents routine
feedback leakage, but unrestricted code under the same OS user can still access those files.

| Evidence for slides | Artifact | Claim it supports |
| --- | --- | --- |
| 10,000 null repetitions | [Expanded null summary](../research/learned-evalue-validation/expanded-null.json) | Learned final rejection 0.20%; ever-crossing 1.12% (95% interval 0.93–1.35%) in the specified simulation |
| 100 repetitions per alternative | [Expanded alternatives](../research/learned-evalue-validation/expanded-alternatives.json) | Scenario-specific power and comparison with simpler baselines; no universal winner |
| Real RNA-seq, actual GPU training | [Real-data record](../research/learned-evalue-validation/real-expression/README.md) | A predeclared held-out comparison; learned features beat PCA here, scalar evidence was stronger |
| Real-data evidence accumulation | [SVG](../research/learned-evalue-validation/real-expression/wealth.svg), [PNG](../research/learned-evalue-validation/real-expression/wealth.png), [HTML report](../research/learned-evalue-validation/real-expression/index.html) | Directly reusable figures with the method, comparison and threshold labeled |
| Agent-facing integration | `tests/test_expression_scoring.py` | Numerical results stay out of the tested command output, prompts, journal and recall |

Still unmeasured: scientific benefit during autonomous agent use, replication across independent disease
cohorts, and an investigation-wide error guarantee under adaptive hypothesis/data reuse. A large
expression-distribution e-value does not establish gene-effect direction or a causal mechanism.

The user-requested independent review of candidate follow-on tools is recorded separately in
[the tool council](evalue-tool-council.md). It proposes future work and does not authorize or claim
implementation of those integrations.

## PDAC scope and trajectory-monitoring assessment

The user clarified that future tools should serve pancreatic-cancer therapeutic discovery or relevant
basic science. Two council reviewers independently reassessed the original candidates: both prioritize
functional dependency/resistance; measured drug response rises, while expression/pathway analysis
remains core and survival/co-essentiality become supporting options. Their remaining disagreements,
biological examples and evidence-unit requirements are in the [PDAC reassessment](evalue-tool-council.md#pancreatic-cancer-reassessment).
This did not change tools or establish disease-specific validation of the existing neutrophil benchmark.

Separately, the complete E-valuator v2 paper (27 pages including appendices) was downloaded with
readable page-marked text and source metadata into ignored local `data/research/e-valuator/`.
The [tree-search assessment](evaluator-tree-search-review.md) maps the paper to completed-action
checkpoints, the existing sibling judge, resumable branches and runtime lineage. The user clarified
that the intended intervention is to stop individual children, so the proposed pilot records child
alarms and obtains full continuations before changing live allocation. Whole investigations group
related data for fitting/calibration/test splits; they are not the proposed stopping target.
Independent success labels and additional validation of adaptive branch selection remain necessary.
The key limitations are missing full outcomes for
pruned branches, correlated/adaptively selected descendants, and keeping both numerical scoring systems
outside discovery feedback. No trajectory monitor, new training, GPU run or new evaluation was performed.

For slides: the implemented result is still private biological scoring with the recorded validation.
The next research question is whether a separately calibrated progress monitor can save compute while
rarely discarding useful research branches. Success-versus-cost and false-stop plots remain to be measured.

## Parallel integration planning

At the user's request, three reviewers worked concurrently on concrete implementation plans for
[dependency/CRISPR](../plans/evalue-dependency-integration.md),
[drug response/combinations](../plans/evalue-drug-response-integration.md), and
[pathway/TF/differential expression](../plans/evalue-expression-integration.md).
The parent aligned a single shared queue/transport prerequisite with method-specific validators,
operator-frozen protocols, private cohort references and canonical experiment identity across retries.
The command emits a receipt; the agent never computes or reports numerical evidence.

The first proposed endpoints use fixed-data randomization/permutation evidence where their design
assumptions are justified. MAGeCK/PyDESeq2 model-based outputs and descriptive synergy do not acquire
exact guarantees merely by conversion. Each plan specifies data needs, null/unit, code seams and
validation; named cohorts/endpoints are proposals, not performed experiments or selected confirmation.
The existing tools and private expression service were not changed. The trajectory document now
targets child-branch stopping explicitly, with complete continuations for evaluation and root-grouped
data splits; whole-investigation stopping is not the intended intervention.

## Consolidated branch lifecycle and human review

The [branch-monitoring plan](../plans/PLAN-branch-monitoring.md) consolidates the subsequent discussion.
Research pauses at the action limit and the child must produce a validated report in a separate,
tool-disabled reporting turn. A generated fallback summary does not satisfy this requirement.
Report failures remain paused and operationally blocked. Explicit checkpoints replace ambiguous
end-of-round `done`; parents authorize continuation/forks, and code executes approved forks.

The existing candidate path was checked: an active node submits its own eligible experimental result
without parent approval; automated checks precede human review. Pruning preserves findings and review
jobs. Private expression receipts are not yet integrated into this path. The plan adds an operator-side
review adapter and separates private human review from disclosure to discovery: score-derived decisions,
notes and graph changes must not feed ongoing agents indirectly. No runtime or review behavior changed
in this documentation task. Reporting, allocation and statistical calibration remain separately
testable stages, with observation-only monitoring before active pruning.

## Fixed subtree outcomes and monitor histories

The branch plan now distinguishes the 18-action reporting cadence from the full evaluation horizon.
Each monitored episode has a fixed terminal budget shared with descendants; checkpoints predict
whether that subtree will produce a qualifying new outcome by the same endpoint. The horizon's
numerical size remains a development-pilot choice, to freeze before calibration and held-out testing.
Collect the generated bounded tree, not every possible fork. The paper's action-sequence experiments
do not establish this recursive adaptation's guarantees.

The primary success condition is a relevant, nonduplicate new finding passing applicable verification
and a frozen evidence rubric; useful refutations can qualify. Forks and activity counts earn no
automatic credit. Completed runs without such an outcome are unsuccessful within the budget;
incomplete runs and pending adjudication require separate handling. Judge artifacts rather than
persuasive summaries, and keep private assessment feedback outside research-agent context.

One rollout supplies many checkpoint observations, but shared prefixes and descendant outcomes are
correlated. Report independent root, episode and checkpoint counts separately and split by related
investigations. The planned human view shows per-child latest monitor statistics and actual histories,
with experimental e-values separate. A short history remains short; no invented points, automatic
descendant-score aggregation or claims that more rows supply independent calibration samples.
This update changes planning and process documentation only; no trajectories, training or UI added.

## 2026-09-06 — Branch controller implementation

Started the agreed branch plan separately from the three biological adapters. Replaced ambiguous
end-of-round continuation with durable child-authored reports and explicit parent decisions. Added
atomic fork reservations and stable decision/report identities; fork proposals no longer execute
without parent authorization. Tool-disabled report turns preserve the same transcript and cannot
resume research on a failed format or outage. Observation-only monitoring remains the deployment
constraint. Controller regression tests cover zero allowance, bounded repair, slow-start continuation,
concurrent reservations and duplicate fork delivery; these are engineering checks, not evidence of
pruning accuracy. First milestone gates after integrating the dependency adapter: 179 Python tests passed, two optional hardware/runtime checks skipped; frontend build, six unit tests and 18 browser tests passed.

## 2026-09-06 — Private monitor infrastructure; corpus runs deferred

Implemented frozen subtree episodes, prefix-only verifier input construction, private checkpoint records,
root/group-separated logistic history fitting and Algorithm 1 threshold calibration. Re-read the local
paper's algorithm and density-ratio equations while implementing the numerical wrapper. Tests check
116 versus 115 independent successful calibration units, strict threshold crossing, prior-corrected
ratio direction, missing histories, related-root leakage and model/policy version mismatch. These are
synthetic correctness checks; no PDAC trajectory performance or trained production judge is claimed.

Added an authenticated operator service separate from the research API, with actual checkpoint dots,
missing/uncalibrated states and a distinct experimental-evidence panel. Receipt association imports
already computed private evidence, supports alias deduplication and requires explicit method/null/family
provenance. Private human decisions remain in the operator store; disclosure requires an explicit frozen
boundary export and never writes research feedback or graph changes automatically. Browser tests and
visual inspection cover the single-point display and mobile layout.

User explicitly deferred actual trajectory scoring/training until corpus ingestion. No real scoring,
training, calibration collection or private-service deployment was run. Remaining research/deployment
work: representative frozen-policy corpus rollouts, enforceable total subtree compute horizon and bounded
adjudication, final assessor selection/validation, automatic private routing and actual account separation.
The monitor remains observation-only; neither its scores nor alarms control branch pruning.

Infrastructure milestone gates after integrating the other tools and extraction repair: 304 Python tests passed, six optional checks skipped (Rscript, PyDESeq2 twice, decoupler, CUDA, opt-in Docker); build, six frontend unit tests and 19 browser tests passed. A subsequent read-only database regression also passed in the focused monitor suite. No corpus experiment was run.

Final controller review strengthened restart handling: continuation objectives are reloaded from durable state, concurrent SDK fork claims and same-child execution are serialized, and allocation receives bounded ordinary evidence records with explicit coverage rather than an experiment-count/dead-end proxy.

Final integration gates against main 899651c: 309 Python tests passed with the same six optional dependency/hardware skips; frontend build, six unit tests and 19 browser tests passed. The operator CLI help command also passed.


## Shared subtree budget engineering

Implemented the next controller stage with deterministic fixtures before corpus readiness. A durable
ledger now shares action and operation-time allowances across descendants and continuation rounds,
reserves reporting before granting research, and grants all fork children transactionally. Restart
cannot refresh a contract or refund ambiguous paid work. Concurrency, nested budgets, failed launches,
zero-action reporting and exhaustion across rounds have focused regression coverage.

The time measure is summed operation wall time, not GPU compute or money; interrupted/overrunning
backends are marked as operational violations, not valid completed negative examples. No actual
trajectory collection, model scoring, training or GPU run was performed for this stage.
