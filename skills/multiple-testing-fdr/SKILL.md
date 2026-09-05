# Multiple Testing and FDR Control

**One line:** Correct for the full family of tests actually run — including implicit ones — so that the expected proportion of false discoveries among reported results is bounded.
**Category:** stats-core
**Open-source:** statsmodels — BSD; scipy — BSD
**Install:** `pip install statsmodels scipy`

## When to use it (and when not)

- Use when: you run more than one hypothesis test and any result might propagate as a finding. This means virtually every experiment in a discovery engine. Use BH-FDR for large exploratory searches (gene lists, feature scans, model comparisons). Use Holm-Bonferroni when you have a small, pre-committed confirmatory family and need FWER control (the probability of even one false positive). Use Benjamini-Yekutieli (BY) when tests are negatively correlated or the dependence structure is unknown — BH technically requires either independence or PRDS (positive regression dependence on a subset of the null hypotheses), and BY provides a valid correction under arbitrary dependence.
- Do not use when: you have a single pre-registered confirmatory hypothesis with no other tests run in the same analysis — multiple testing correction is not needed and would be overcorrection. Do not apply BH after cherry-picking the tests to include in the family; the correction is valid only if the full family is declared before looking at results. Do not interpret a q-value as the posterior probability that a specific finding is false — FDR bounds the expected proportion among all rejections in the aggregate, not a per-hypothesis probability.

## Inputs → outputs

- Inputs: a vector of raw p-values p_1 … p_m, where m is the full family size (every test run in this analysis, including those in exploratory branches); the desired FDR threshold q (typically 0.05 or 0.10); the dependence structure (independence/PRDS → BH; unknown/negative → BY).
- Outputs: adjusted p-values (q-values) for each test; a binary rejection vector at the chosen q threshold; the pi_0 estimate (proportion of true nulls) if using Storey's method.

## Rigor — the invariants a good analysis must honor

- **Count the full family — this is the core invariant:** m must include every hypothesis test the engine ran or considered in the session, not just the ones that look interesting. This means: every feature/gene/variant tested, every subgroup split, every model compared, every threshold scanned, every lag or window tried, and every round of an iterative search. The most reliable failure mode of an autonomous engine is silently narrowing m post-hoc after seeing results. Lock the family manifest (the list of all planned tests) before touching data and hash it; any change is a new non-confirmatory analysis.

- **Unit of observation / exchangeable unit:** Each test should correspond to one independent hypothesis. Tests on the same feature computed on overlapping samples, or on subgroups that are nested within larger groups, are not independent — BH still bounds FDR in expectation under positive dependence (PRDS), but the q-value envelope is tighter under dependence and you may be overcounting m. Organize the hierarchy before correction (see the hierarchical note below).

- **Null model:** BH and BY make no assumption about the null distribution beyond the validity of the input p-values. If the p-values themselves are miscalibrated (e.g. from a test that violates its assumptions), the FDR guarantee is void. Validate p-value calibration on negative controls before applying correction: under the global null, p-values should be uniform on [0,1].

- **Confounders to adjust:** Batch effects and other confounders inflate test statistics, producing a surplus of small p-values. The correct sequence is: adjust for confounders in the model first, then correct for multiple testing on the residual p-values. Applying BH to p-values from a model that ignores a strong batch effect produces a "corrected" list that is still dominated by batch artifacts.

- **Multiple testing:** BH is the default for large exploratory families. The BH procedure: sort p-values p_(1) ≤ p_(2) ≤ … ≤ p_(m); find the largest k such that p_(k) ≤ k·q/m; reject all hypotheses 1 through k. BY multiplies the BH cutoff by the harmonic number H_m = sum(1/i for i in 1..m) ≈ ln(m) + 0.577; it is valid under arbitrary dependence but substantially more conservative. Storey's q-value estimates pi_0 (the fraction of truly null hypotheses) and inflates power when many true effects exist; use it only when you have a principled estimate of pi_0, not just to pass more tests.

- **Effect size + floor:** Rejection at FDR q=0.05 means the list is expected to contain at most 5% false positives — it says nothing about the magnitude of true effects. Always report the effect size and its confidence interval alongside the q-value. A gene with q=0.001 and Cohen's d=0.05 is "significant" in the FDR sense but may be biologically trivial.

- **Robustness check:** Sweep the q threshold from 0.01 to 0.20 and plot the number of rejections vs q (the "significance curve"). A smooth, roughly linear rise is reassuring. A sudden jump at a specific threshold suggests the result is threshold-sensitive — interpret with caution. Re-run on a data subset (80% of samples) and check whether the same features are rejected.

- **Common pitfalls / failure modes:** (1) Undercounting m: treating only the printed tests as the family. Instrument the pipeline to accumulate a running test count across all rounds and branches. (2) Procedure-shopping — trying BH, BY, and Holm and reporting whichever clears threshold; pre-commit the method to the known dependence structure. (3) Interpreting q as a per-hypothesis posterior probability — it is not. (4) Applying BH to p-values from tests that are strongly negatively correlated (e.g. a test and its complement) — use BY in that case. (5) Treating the FDR-corrected gene list as "the truth" and feeding it directly into a second analysis without acknowledging the expected contamination from false positives.

## Data sources

These skills operate on the experiment's own data. The input is the vector of p-values produced by the experiment's primary tests. No external datasets are required.

## Minimal worked example

```python
import numpy as np
from statsmodels.stats.multitest import multipletests

rng = np.random.default_rng(0)

# Simulate 1000 tests: 900 true nulls, 100 true effects
m = 1000
n_true_effects = 100
# True null p-values: uniform
p_null = rng.uniform(0, 1, m - n_true_effects)
# True effect p-values: small (beta-distributed to mimic real signal)
p_signal = rng.beta(0.3, 10, n_true_effects)
p_values = np.concatenate([p_null, p_signal])

# --- BH-FDR (assumes independence / PRDS) ---
reject_bh, p_adj_bh, _, _ = multipletests(p_values, alpha=0.05, method='fdr_bh')

# --- BY-FDR (valid under arbitrary dependence — more conservative) ---
reject_by, p_adj_by, _, _ = multipletests(p_values, alpha=0.05, method='fdr_by')

# --- Holm (FWER; use for a small, confirmatory family) ---
reject_holm, p_adj_holm, _, _ = multipletests(p_values, alpha=0.05, method='holm')

print(f"Total tests (m): {m}")
print(f"BH rejections: {reject_bh.sum()}  (expect ~100 at q=0.05)")
print(f"BY rejections: {reject_by.sum()}  (valid under arbitrary dependence)")
print(f"Holm rejections: {reject_holm.sum()}  (FWER; very conservative)")

# Reminder: report q-values alongside effect sizes, not just rejection status
top_10_idx = np.argsort(p_adj_bh)[:10]
print("\nTop 10 by BH q-value:")
for i in top_10_idx:
    print(f"  test {i:4d}: raw p = {p_values[i]:.4f}, BH q = {p_adj_bh[i]:.4f}")
```
