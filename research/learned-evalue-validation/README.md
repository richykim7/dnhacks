# Initial learned e-value validation

Later iteration: [real-expression/GPU results and wealth report](real-expression/README.md);
[expanded synthetic alternatives](expanded-alternatives.json). The initial pilot below is retained
as a historical measurement.

This is an initial **synthetic** evaluation of the standalone diagnostic implementation, with
configuration frozen after a separate small pilot. It provides no real-cohort power claim and no
investigation-wide error guarantee. Existing experiment verification is unchanged.

The [machine-readable summary](summary.json) contains pointwise Wilson 95% intervals, quantiles,
configuration and report hashes. [Replay examples](replay-examples.json) retain the identity bettor's
first repetition in each scenario, without selecting examples by outcome. Full local reports and
encoder artifacts are in ignored `data/processed/` and can be regenerated with the commands below.

## Design

Each run receives 96 independent pairs with eight standard-normal latent features. Frozen expression
encoders receive the corresponding exponentiated values as simulated TPM. Their 256 independent
training units use a separate fixed seed. PCA and the autoencoder each retain four features; the
autoencoder has one 32-unit hidden layer and trains for 30 epochs on masked entries. These are small
synthetic artifacts, not the proposed full-size expression encoders.

The bettor uses two 16-unit ReLU layers, batch size eight, two unscored burn-in batches, learning
rate 0.005, at most 20 epochs per update and patience five. The scalar bettor receives only the first
latent coordinate; the fixed projection receives the first four. No model is selected using these
evaluation results. Pairing/model seeds vary by repetition according to a predetermined schedule.

The ordinary permutation test uses squared multivariate mean distance and 999 permutations with
the plus-one correction. It is a test under the same distribution-equality null, but is not an
omnibus characteristic-kernel statistic; weak variance-shift power is expected for this comparator.
All methods receive the same total pair budget. DAVT reserves 16 pairs for burn-in.

## Results at alpha = 0.05

Each cell below reports **final-wealth rejection percentage / ever-crossing percentage**.
Permutation p-values have a single fixed-horizon rejection decision. Crossing evidence is an
anytime diagnostic; the returned e-value is always final wealth, which can subsequently fall.

| Method | Null (200 runs) | Mean shift (50) | Variance shift (50) | Signal in omitted coordinate (50) |
| --- | ---: | ---: | ---: | ---: |
| Identity bettor | 0.5 / 2 | 54 / 88 | 20 / 42 | 86 / 96 |
| PCA bettor | 1 / 1 | 10 / 26 | 32 / 48 | 80 / 96 |
| Autoencoder bettor | 0 / 1 | 70 / 84 | 40 / 58 | 98 / 100 |
| Scalar bettor | 0 / 0.5 | 88 / 96 | 96 / 98 | 0 / 0 |
| Fixed projection bettor | 0 / 1.5 | 86 / 98 | 76 / 90 | 0 / 6 |
| Ordinary permutation p | 5 | 100 | 4 | 100 |
| Calibrated permutation e | 0.5 | 100 | 0 | 100 |
| **Invalid label-memorization control** | **100** | **100** | **100** | **100** |

The mean shift adds 0.8 to the first two latent coordinates. The variance shift doubles their
standard deviations. The omitted-coordinate scenario adds 1.5 to the eighth coordinate; the scalar
and fixed projection do not observe that coordinate. Their distributions remain equal after
projection, despite a real difference in the full vectors. PCA and the autoencoder have not been
constructed to omit that particular coordinate.

These settings show neither a universal winner nor evidence that the neural encoder should replace
simpler methods. For example, the scalar bettor outperforms the autoencoder in the first two
alternatives, and the ordinary permutation test is strongest on the mean shift. The invalid control
memorizes labels before scoring those same rows and demonstrates that the harness detects that leak.

Null crossing estimates are imprecise: identity 4/200 has a pointwise 95% interval of approximately
0.78%–5.03%; autoencoder 2/200 has 0.27%–3.57%. These intervals are not simultaneous across methods.
The results reveal no obvious null inflation in this design, but cannot establish validity across
all null distributions. The mathematical argument and code-order checks remain necessary.

## Runtime and replay

Measured on the current CPU environment with one Torch thread per harness process: 106.9 seconds
for 200 null repetitions across all methods; 94.3 seconds for 150 alternative repetitions.
The two harness processes ran concurrently. Timings exclude encoder training and report writing.
At this measured null throughput, 10,000 repetitions would take roughly 89 minutes before overhead;
that larger evaluation has **not** been run. The reported 200/50 counts are the actual budgets.

```sh
uv run --extra dev --extra evalue pytest tests/test_learned_evalue.py
uv run --extra evalue python scripts/evalue_harness.py --repetitions 200 --epochs 20 --seed 130363 --scenarios null --output data/processed/evalue-null.json
uv run --extra evalue python scripts/evalue_harness.py --repetitions 50 --epochs 20 --seed 196613 --scenarios mean_shift variance_shift discarded_signal --artifacts data/processed/evalue-synthetic-alternatives --output data/processed/evalue-alternatives.json
```

Software versions, input hashes, artifact hashes, unit order and training/validation batch histories
are stored in each full diagnostic result. Exact floating-point reproduction requires the recorded
environment. The artifact trainers have also been exercised through their CLI on a separate fixture.

## Remaining work

Select a real evaluation cohort and comparison, establish its independent-unit sampling design,
and identify disjoint encoder training/development cohorts before making biological power claims.
Benchmark the actual cohort size before committing to full PCA/SVD and autoencoder training budgets.
Verification decisions, RESULT contracts and UI integration remain separate reviewed work.

## Expanded frozen-configuration evaluation

The [10,000-run null summary](expanded-null.json) combines four compatible, disjoint seed streams
(9000000–9009999), with identical encoder artifact hashes and software. Each repetition has 96
pairs and the original 16/16, maximum-20-epoch synthetic bettor; 999 permutation draws. These
settings were fixed from the initial implementation, not selected from this evaluation. Both
encoders train on the original separate 256-row synthetic cohort. Each worker uses one CPU thread;
four workers took approximately 22.3 minutes wall time (88.8 aggregate worker-minutes).

| Method | Final rejections | Ever crossings | Crossing rate (pointwise Wilson 95% interval) |
| --- | ---: | ---: | --- |
| identity | 13/10,000 | 166/10,000 | 1.66% (1.43%–1.93%) |
| pca | 14/10,000 | 171/10,000 | 1.71% (1.47%–1.98%) |
| autoencoder | 20/10,000 | 112/10,000 | 1.12% (0.93%–1.35%) |
| scalar | 36/10,000 | 141/10,000 | 1.41% (1.20%–1.66%) |
| fixed_projection | 19/10,000 | 165/10,000 | 1.65% (1.42%–1.92%) |
| permutation_p | 513/10,000 | 513/10,000 | 5.13% (4.71%–5.58%) |
| permutation_calibrated_e | 24/10,000 | 24/10,000 | 0.24% (0.16%–0.36%) |
| INVALID_label_memorization | 10000/10,000 | 10000/10,000 | 100.00% (99.96%–100.00%) |

The learned-encoder final rejection rate was 0.20%; anytime crossing rate 1.12%. The ordinary
permutation rate 5.13% is compatible with 5% at this simulation precision. The invalid memorizing
control rejects every null run. These measurements diagnose this implementation/distribution;
they do not prove validity over all distributions or estimate heavy-tailed wealth expectations.
Quantiles remain per-shard; they are not averaged into invalid pooled quantiles.

The [expanded alternatives](expanded-alternatives.json) use 100 repetitions each, starting from
seed 12000000 and the harness's recorded scenario offsets. Null and final alternative summaries
use the same CPU software and frozen encoder configuration. Software: Python 3.12.3, NumPy 2.5.2,
Torch 2.14.0+cu130 (CPU execution). The real-data/GPU study separately records Torch 2.10.0+cu128.

Reproduce each shard with the command below, changing the seed to 9002500, 9005000 and 9007500 and
using separate output/artifact directories. Run at most four one-thread workers for this budget.

```sh
uv run --extra evalue python scripts/evalue_harness.py --repetitions 2500 --epochs 20 --permutations 999 --seed 9000000 --scenarios null --summary-only --output data/processed/evalue-final/null-0.json --artifacts data/processed/evalue-final/encoders-0
uv run --extra evalue python scripts/evalue_harness.py --merge data/processed/evalue-final/null-0.json data/processed/evalue-final/null-1.json data/processed/evalue-final/null-2.json data/processed/evalue-final/null-3.json --output research/learned-evalue-validation/expanded-null.json
uv run --extra evalue python scripts/evalue_harness.py --repetitions 100 --epochs 20 --permutations 999 --seed 12000000 --scenarios mean_shift variance_shift discarded_signal --summary-only --output data/processed/evalue-final/alternatives.json --artifacts data/processed/evalue-final/alternative-encoders
```

The merger rejects overlapping seed streams, mismatched configurations/software and differing
frozen artifacts. The first replay per scenario is retained in each local source report; tracked
summaries retain counts, intervals, source hashes, seeds, software and configuration.
