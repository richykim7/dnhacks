# Bootstrap Confidence Intervals

**One line:** Use resampling to build confidence intervals for any statistic without assuming a parametric distribution, and know when the bootstrap itself breaks down.
**Category:** stats-core
**Open-source:** scipy — BSD; numpy — BSD; statsmodels — BSD
**Install:** `pip install scipy numpy statsmodels`

## When to use it (and when not)

- Use when: the sampling distribution of your statistic is unknown or non-normal (medians, correlations, ratios, custom enrichment scores, AUC), when the sample size is moderate (n ≥ 30 per group as a rough floor), when analytic CIs make distributional assumptions you cannot verify, or when you need a CI for an effect size derived from a complex model.
- Do not use when: n is very small (n < 15–20 per group) — the bootstrap resamples the same small pool of values and the resulting CI undercovers badly, especially in the tails. Do not use when the statistic is not smooth (e.g. the maximum value of a distribution, an extreme quantile above the 95th percentile, or a test statistic that changes discontinuously with the sample) — the bootstrap is inconsistent for non-smooth statistics. For clustered data, bootstrap at the cluster level, not the observation level; otherwise the CI is anti-conservative by the same pseudoreplication logic as any other analysis. When the model is trusted and the likelihood is well-specified, a parametric CI (from the Fisher information or from a likelihood-ratio inversion) will be tighter and at least as valid.

## Inputs → outputs

- Inputs: observed data (n observations, possibly clustered); a statistic function T(sample) → scalar; number of bootstrap replicates B (typically 2 000 – 10 000); confidence level (typically 0.95); the cluster variable if data are clustered.
- Outputs: a (lower, upper) confidence interval; the bootstrap distribution of the statistic; bias estimate (T_boot_mean − T_obs) and acceleration for BCa correction.

## Rigor — the invariants a good analysis must honor

- **Percentile vs BCa — always prefer BCa:** The percentile bootstrap uses the 2.5th and 97.5th percentiles of the bootstrap distribution directly. It is simple but anti-conservative when the statistic is biased (i.e., E[T(X*)] ≠ T(X)). The bias-corrected and accelerated (BCa) bootstrap corrects for both bias (using z_0, estimated from the fraction of bootstrap replicates below T_obs) and skewness in the bootstrap distribution (using the acceleration a, estimated via jackknife). BCa is the default for any statistic that is not a simple mean of i.i.d. data. Use percentile only when you have verified that the bootstrap distribution is approximately symmetric and unbiased.

- **Unit of observation / exchangeable unit:** Resample at the unit that is independent in your design. For a study with n subjects each measured k times, resample subjects (drawing n subjects with replacement, taking all k of each subject's observations) — do not resample individual observations. Resampling observations in a repeated-measures design breaks the within-subject correlation structure and produces CIs that are too narrow. For two-sample comparisons, resample within each group separately (stratified bootstrap).

- **Null model:** The bootstrap builds a CI, not a p-value null distribution. For a permutation-based p-value, use the permutation test (see permutation-testing skill). You can build a bootstrap-based p-value by shifting the bootstrap distribution to be centered at the null value and counting the fraction of shifted replicates beyond T_obs, but this is less interpretable and less powerful than a direct permutation test.

- **Minimum B:** For a 95% CI, B = 1 000 gives rough stability; B = 2 000–5 000 is standard; B = 10 000 is needed for stable BCa tail estimates or for 99% CIs. The BCa acceleration requires a jackknife (n additional evaluations of T), which is cheap for simple statistics but expensive for model-based ones; consider B = 2 000 with BCa for model fits, B = 10 000 for simple statistics.

- **Confounders to adjust:** If the statistic T involves a regression with covariates, the bootstrap must resample the full dataset (observations × covariates + outcome) and refit the model in each replicate, not just resample the residuals. Resampling residuals (the "residual bootstrap") is valid only under homoscedasticity and correct model specification. For heteroscedastic regression, the wild bootstrap (multiply residuals by random signs or a Rademacher variable) provides valid CIs without assuming constant variance.

- **Multiple testing:** Bootstrap CIs for multiple statistics are not automatically corrected for simultaneous coverage. If you want a 95% simultaneous confidence band (all intervals cover their true parameters at the same time with 95% probability), you need the maximum-statistic bootstrap or Bonferroni-corrected individual CIs. For FDR-controlled lists, report individual CIs alongside q-values and note they are not simultaneous.

- **Effect size + floor:** Bootstrap CIs directly quantify the precision of an effect size estimate. If the 95% BCa CI for Cohen's d is [0.05, 0.45], the uncertainty is large enough that you cannot distinguish a trivial effect (d=0.05) from a moderate one (d=0.45) — report this uncertainty explicitly rather than pointing to the point estimate.

- **Robustness check:** Compare percentile and BCa CIs — if they differ substantially, the statistic is biased and BCa is essential. Compare the CI width at B=1 000 vs B=5 000 to confirm convergence. For clustered data, compare observation-level resampling vs cluster-level resampling; the cluster-level CI will typically be wider, and that wider interval is the correct one.

- **Common pitfalls / failure modes:** (1) Using the percentile bootstrap for a biased statistic (e.g., a maximum-likelihood estimate of a variance component in a small sample) — BCa is required. (2) Resampling observations in clustered data instead of clusters — produces CIs that are too narrow by sqrt(cluster_size). (3) Too few bootstrap replicates for BCa — the BCa correction depends on a tail quantile of the bootstrap distribution, which is poorly estimated at B = 200. (4) Applying the bootstrap to an extreme quantile or a maximum statistic — the bootstrap is inconsistent for these and the CI is unreliable. (5) Treating the bootstrap CI as a test: a CI that excludes zero is not equivalent to p < 0.05 unless the CI was constructed to have exactly that coverage — BCa CIs for skewed statistics can have this relationship but it is not guaranteed.

## Data sources

These skills operate on the experiment's own data. No external datasets are required.

## Minimal worked example

```python
import numpy as np
from scipy.stats import bootstrap

rng = np.random.default_rng(13)

# Simulate two groups (n=40 each) — compute a correlation and its BCa CI
n = 40
x = rng.normal(size=n)
y = 0.4 * x + rng.normal(scale=0.9, size=n)

def pearson_r(x, y):
    return np.corrcoef(x, y)[0, 1]

r_obs = pearson_r(x, y)
print(f"Observed Pearson r = {r_obs:.3f}")

# scipy.stats.bootstrap with BCa method
res = bootstrap(
    (x, y),
    statistic=pearson_r,
    n_resamples=5000,
    confidence_level=0.95,
    method='BCa',        # bias-corrected and accelerated
    random_state=42,
    paired=True          # resample (x_i, y_i) pairs together
)
ci_low, ci_high = res.confidence_interval
print(f"BCa 95% CI: [{ci_low:.3f}, {ci_high:.3f}]")

# Compare with percentile bootstrap
res_pct = bootstrap(
    (x, y),
    statistic=pearson_r,
    n_resamples=5000,
    confidence_level=0.95,
    method='percentile',
    random_state=42,
    paired=True
)
ci_low_p, ci_high_p = res_pct.confidence_interval
print(f"Percentile 95% CI: [{ci_low_p:.3f}, {ci_high_p:.3f}]")

# ---- Cluster bootstrap example (resample clusters, not observations) ----
# n_clusters subjects, k_obs observations each
n_clusters, k_obs = 15, 4
cluster_ids = np.repeat(np.arange(n_clusters), k_obs)
outcome = rng.normal(size=n_clusters * k_obs)

B = 3000
cluster_means_boot = np.empty(B)
for i in range(B):
    sampled_clusters = rng.choice(n_clusters, size=n_clusters, replace=True)
    boot_data = np.concatenate([outcome[cluster_ids == c] for c in sampled_clusters])
    cluster_means_boot[i] = boot_data.mean()

ci_cluster = np.percentile(cluster_means_boot, [2.5, 97.5])
print(f"\nCluster-bootstrapped CI for mean: [{ci_cluster[0]:.3f}, {ci_cluster[1]:.3f}]")
print("(Compare to observation-level bootstrap — cluster CI will be wider and correct)")
```
