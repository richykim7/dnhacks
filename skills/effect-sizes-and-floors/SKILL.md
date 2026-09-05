# Effect Sizes and Triviality Floors

**One line:** Quantify how large an effect is in domain-meaningful units and declare in advance the smallest effect that would matter, so statistical significance cannot be confused with scientific importance.
**Category:** stats-core
**Open-source:** pingouin — BSD; scipy — BSD; statsmodels — BSD; numpy — BSD
**Install:** `pip install pingouin scipy statsmodels numpy`

## When to use it (and when not)

- Use when: you run any inferential test. Effect sizes are not optional — they are the primary scientific quantity, with the p-value as a secondary compatibility index. Use standardized effect sizes (Cohen's d, Hedges' g, Pearson r, eta-squared / omega-squared, odds ratio, relative risk, risk difference) when you want to compare across studies or data types. Use domain-native units (fold-change, regression coefficient in original units, survival hazard ratio) alongside the standardized form so the finding is interpretable to a biologist without statistical training.
- Do not use when: you want to claim a null result purely from a non-significant p-value — that conflates "absence of evidence" with "evidence of absence." To conclude that an effect is absent or trivially small, run an equivalence test (TOST) or Bayesian ROPE analysis. Do not use Cohen's d thresholds (small=0.2, medium=0.5, large=0.8) as universal biological cutoffs — they were calibrated on social psychology data; declare your own SESOI from domain knowledge.

## Inputs → outputs

- Inputs: raw data for the two (or more) conditions; the pre-declared Smallest Effect Size of Interest (SESOI) in the chosen standardized metric; a sample size (for power and Type-M calculations).
- Outputs: point estimate of the effect size; 95% confidence interval (bootstrap or analytic); SESOI comparison (is the CI entirely inside the trivial zone, outside it, or ambiguous); optionally a retrodesign exaggeration ratio if power is low.

## Rigor — the invariants a good analysis must honor

- **Declare the SESOI before looking at data:** The SESOI is the smallest effect you would care about scientifically — below it, the effect is trivially small regardless of p-value. Lock this number (in the pre-analysis plan) before any results are computed. For cancer dependency scores it might be "Cohen's d < 0.2 in CERES units is not actionable." For gene expression it might be "fold-change < 1.5 is not worth following up." Pre-declaring the SESOI transforms a non-significant result into a meaningful one: if the 95% CI falls entirely within [−SESOI, +SESOI], you have positive evidence of a trivially small effect (equivalence test passes).

- **Unit of observation / exchangeable unit:** The effect size is estimated on the same unit as the test statistic. If the test is over subjects (pseudobulk), the effect size is over subjects. Computing Cohen's d over individual cells when the test was run at the subject level gives a misleadingly large denominator and a shrunken effect estimate.

- **Null model:** Effect sizes do not have a null distribution by themselves, but their confidence intervals do. Use bootstrap CIs for non-Gaussian or small-n settings (see bootstrap-confidence-intervals skill). Use analytic CIs (e.g., the noncentrality parameter approach for Cohen's d) when distributional assumptions are met and n is large.

- **Confounders to adjust:** Report the partial effect size (e.g., partial eta-squared or the coefficient from a regression that includes covariates) when confounders are adjusted. The marginal effect size mixes the biological effect with confounding; the partial effect size is what you are actually estimating.

- **Choice of standardized metric by data type:** Cohen's d assumes equal or at least similar variances; Hedges' g uses the pooled SD with a bias correction and is preferred for small or unequal-n groups. For ordinal or non-normal data, rank-biserial correlation r (from Mann-Whitney U) is more robust. For ANOVA or regression, report omega-squared (unbiased) rather than eta-squared (biased upward, especially for small n and many groups). For binary outcomes, both odds ratio and risk difference should be reported — the OR is stable near 50% prevalence but inflates near 0 or 1.

- **Type-M and Type-S errors under low power:** When a study is underpowered (power < 50%), conditional on achieving statistical significance the observed effect size is inflated relative to the true effect (Type-M / exaggeration ratio) and has a non-trivial probability of being the wrong sign (Type-S error). Compute the retrodesign exaggeration ratio for the design's actual power so the engine knows whether to trust the magnitude of a significant result. The retrodesign calculation requires only the true effect size (from the literature or a prior estimate) and the design's power.

- **Multiple testing:** Effect sizes are not corrected for multiple testing — only p-values are. Report the effect sizes for all tested hypotheses, not just the rejected ones. Selective reporting of effect sizes for rejected hypotheses (winners' curse) inflates the apparent magnitude of effects in a discovery set.

- **Robustness check:** Report the effect size on a replication fold or a held-out subset. Shrinkage of effect sizes from discovery to replication (winners' curse) is the expected pattern for underpowered studies; quantify the expected shrinkage using the exaggeration ratio.

- **Common pitfalls / failure modes:** (1) Declaring significance based on p alone and ignoring a tiny effect size. (2) Using Cohen's "small/medium/large" benchmarks in a domain where they do not apply. (3) Reporting partial eta-squared from a multi-factor ANOVA without noting its upward bias — use omega-squared. (4) Forgetting that a 95% CI for an effect size that includes zero is not the same as an equivalence test; for equivalence you need to show the CI is entirely within [−SESOI, +SESOI]. (5) Under low power, treating a significant effect size estimate as unbiased — always compute the exaggeration ratio when power < 0.80.

## Data sources

These skills operate on the experiment's own data. No external datasets are required. The SESOI should come from domain knowledge (prior literature, mechanistic thresholds) declared in the analysis plan before data analysis.

## Minimal worked example

```python
import numpy as np
from scipy import stats
import pingouin as pg

rng = np.random.default_rng(7)

# Simulate two groups (n=30 each)
n = 30
group_a = rng.normal(loc=0.4, scale=1.0, size=n)
group_b = rng.normal(loc=0.0, scale=1.0, size=n)

# --- Cohen's d (pingouin; includes Hedges' g and CI) ---
result = pg.compute_effsize(group_a, group_b, eftype='cohen')
hedges_g = pg.compute_effsize(group_a, group_b, eftype='hedges')
print(f"Cohen's d = {result:.3f}")
print(f"Hedges' g = {hedges_g:.3f}  (bias-corrected; prefer for small n)")

# Bootstrap 95% CI for Cohen's d
def cohens_d(a, b):
    pooled = np.sqrt(((len(a)-1)*a.std(ddof=1)**2 + (len(b)-1)*b.std(ddof=1)**2)
                     / (len(a)+len(b)-2))
    return (a.mean() - b.mean()) / pooled

ci = pg.compute_bootci(group_a, group_b, func=cohens_d, n_boot=5000,
                       confidence=0.95, seed=42)
print(f"Bootstrap 95% CI for Cohen's d: [{ci[0]:.3f}, {ci[1]:.3f}]")

# --- Pre-declared SESOI = 0.2 (trivial below this) ---
SESOI = 0.2
d_obs = cohens_d(group_a, group_b)
if ci[0] > SESOI:
    verdict = "effect exceeds SESOI — potentially meaningful"
elif ci[1] < SESOI:
    verdict = "effect < SESOI — trivially small (equivalence)"
else:
    verdict = "ambiguous — CI straddles SESOI threshold"
print(f"SESOI verdict: {verdict}")

# --- Retrodesign: exaggeration ratio at this power level ---
# Using a simple simulation (full retrodesign package in R; approx here)
t_crit = stats.t.ppf(0.975, df=2*n-2)
true_d = 0.4
power_approx = 1 - stats.t.cdf(t_crit - true_d * np.sqrt(n/2), df=2*n-2)
print(f"Approximate power at true d={true_d}: {power_approx:.2f}")
# At power ~0.5, exaggeration ratio is typically ~1.5-2x — interpret magnitudes cautiously
```
