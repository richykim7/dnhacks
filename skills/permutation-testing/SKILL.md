# Permutation Testing

**One line:** Build an empirical null distribution by relabelling data at the correct exchangeable unit, then compute a p-value that can never be exactly zero.
**Category:** stats-core
**Open-source:** numpy, scipy — BSD; statsmodels — BSD
**Install:** `pip install numpy scipy statsmodels`

## When to use it (and when not)

- Use when: the analytical null distribution is unknown, the test statistic is non-standard (e.g. a correlation difference, a custom enrichment score, or a ratio of medians), the data clearly violate the normality or variance-homogeneity assumptions of a parametric test, or you need to confirm that a parametric result holds under a model-free null.
- Do not use when: the sample size is so small that the permutation space is exhausted and you cannot reach the desired p-value resolution (e.g. n=4 per group gives only C(8,4)=70 label arrangements; you cannot ever reach p=0.01). Do not use when the exchangeable unit is ambiguous and you have no principled way to resolve it — a permutation on the wrong unit produces an invalid null. Permutation tests also do not magically resolve confounding: if a batch effect is perfectly confounded with the label, permuting labels still produces a biased null.

## Inputs → outputs

- Inputs: observed data matrix or vector; group/treatment labels; a test statistic function T(data, labels) → scalar; number of permutations n (typically 10 000 – 100 000); the exchangeable unit (row, subject ID, cluster ID).
- Outputs: observed statistic T_obs; empirical null distribution {T_perm_i}; permutation p-value using the Phipson-Smyth formula; optionally a one-sided or two-sided variant.

## Rigor — the invariants a good analysis must honor

- **Unit of observation / exchangeable unit:** This is the single most important decision. Permute at the level where the null hypothesis asserts exchangeability. For a two-sample comparison of subjects, permute subject labels. For a paired design, permute within-pair signs. For cell-level data with multiple subjects per group, permute subject labels and keep all cells from a subject together — never permute individual cell labels as if cells were independent. Permuting at the wrong level produces an anti-conservative null (inflated apparent significance) by factors of 10–100× in realistic single-cell and cell-line studies.

- **Null model:** The null is that the label assignment is uninformative — not that the data are i.i.d. normal. Permuting labels at the correct unit embeds the null directly in the combinatorics of your design without any distributional assumption. The permuted statistic must be computed with exactly the same pipeline (normalization, covariate adjustment, statistic extraction) as the observed statistic; if you skip any step in the null you are testing a different null than you think.

- **Phipson-Smyth p-value formula:** Always use p = (b + 1) / (n + 1), where b is the number of permutations whose statistic is at least as extreme as T_obs and n is the total number of permutations run. Never use b/n — when b=0 that gives p=0, which is a logical impossibility (the observed data is itself a valid permutation, so p ≥ 1/(n+1)). For a two-sided test, count permutations with |T_perm| ≥ |T_obs|. Reference: Phipson & Smyth (2010), Statistical Applications in Genetics and Molecular Biology.

- **Minimum permutation count:** For a target p-value floor of alpha, you need at least 10/alpha permutations for a stable estimate. To reliably detect p < 0.001, run n ≥ 10 000; for p < 0.0001, n ≥ 100 000. For BH-FDR at q=0.05 with m tests, the effective per-test floor is q/m, so scale n accordingly. The minimum permutation count should be declared before running, not adjusted after seeing a near-miss.

- **Confounders to adjust:** If covariates confound the label-outcome relationship, regress them out of both the data and the label before permuting (residual permutation), or include them in the test statistic computation and permute only the primary label. Permuting raw labels when a batch is confounded with the label does not give a valid null for the biological effect — it gives a null that is still inflated by the batch.

- **Multiple testing:** Raw permutation p-values feed directly into BH-FDR or Holm over the full family (count every test). For correlated tests (e.g. genes in a pathway), max-statistic permutation provides FWER control with implicit correlation structure: the null distribution of the maximum statistic across all features is built from each permuted replicate, and individual p-values are derived from that joint null. This is stronger than BH but much more conservative.

- **Effect size + floor:** A significant permutation p-value tells you the observed statistic is unlikely under the null; it says nothing about practical importance. Always pair with a standardized effect size and its bootstrap CI. A statistically significant p=0.001 can correspond to a biologically trivial difference.

- **Robustness check:** Re-run with a different number of permutations (e.g. 1 000 vs 10 000) to verify p-value stability. Stratified permutation (preserve nuisance label balance) vs unstratified permutation should give similar results if the covariate is truly nuisance; large disagreement signals confounding.

- **Common pitfalls / failure modes:** (1) Permuting at the wrong unit — cells instead of subjects, genes instead of samples, or time-points across subjects — inflates Type I error severely. (2) Computing the statistic differently under the null vs observed (e.g. re-normalizing after permutation but not before, or skipping a covariate step). (3) Reporting p = 0 when b = 0 — use Phipson-Smyth. (4) Using too few permutations and then interpreting a near-threshold p as definitive. (5) Applying a permutation test when the design has perfect confounding — the permutation is valid for the null label × outcome relationship but cannot separate batch from biology.

## Data sources

These skills operate on the experiment's own data. No external datasets are required. The permutation procedure is a method applied to whatever matrix and labels the experiment produces.

## Minimal worked example

```python
import numpy as np
from scipy import stats

rng = np.random.default_rng(42)

# Simulate: 20 subjects, 2 groups, one measurement per subject
n_per_group = 10
group_a = rng.normal(loc=0.5, scale=1.0, size=n_per_group)
group_b = rng.normal(loc=0.0, scale=1.0, size=n_per_group)
data = np.concatenate([group_a, group_b])
labels = np.array([1]*n_per_group + [0]*n_per_group)

def test_stat(x, lbl):
    """Mean difference — the exchangeable unit is the subject (row)."""
    return x[lbl == 1].mean() - x[lbl == 0].mean()

T_obs = test_stat(data, labels)

n_perm = 10_000
T_perm = np.empty(n_perm)
for i in range(n_perm):
    shuffled = rng.permutation(labels)  # permute subject labels
    T_perm[i] = test_stat(data, shuffled)

# Phipson-Smyth: p = (b+1)/(n+1), two-sided
b = np.sum(np.abs(T_perm) >= np.abs(T_obs))
p_perm = (b + 1) / (n_perm + 1)

# Cohen's d as effect size
pooled_sd = np.sqrt(((n_per_group-1)*group_a.std(ddof=1)**2 +
                     (n_per_group-1)*group_b.std(ddof=1)**2) / (2*n_per_group - 2))
cohens_d = (group_a.mean() - group_b.mean()) / pooled_sd

print(f"T_obs = {T_obs:.3f}")
print(f"Permutation p (Phipson-Smyth, two-sided) = {p_perm:.4f}")
print(f"Cohen's d = {cohens_d:.3f}")
# Compare with parametric t-test (should be close under normality)
t_stat, p_param = stats.ttest_ind(group_a, group_b)
print(f"Parametric t-test p = {p_param:.4f}")
```
