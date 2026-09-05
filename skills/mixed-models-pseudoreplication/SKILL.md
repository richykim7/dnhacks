# Mixed Models and the Pseudoreplication Trap

**One line:** Use random effects to model grouped, nested, or repeated-measures data correctly, and avoid the pseudoreplication error of treating sub-unit observations as independent replicates.
**Category:** stats-core
**Open-source:** statsmodels — BSD; numpy — BSD; scipy — BSD
**Install:** `pip install statsmodels numpy scipy`

## When to use it (and when not)

- Use when: observations are grouped at a level above the measurement level — subjects with multiple cell lines, patients with repeated measurements, cell lines nested within tissues, samples nested within batches. When you have biological replicates (subjects) and technical replicates (repeat measurements of the same subject), the technical replicates are not independent biological observations. When you want to estimate a population-level effect (fixed effect) while accounting for variability in baselines across groups (random intercept) or variability in the treatment effect across groups (random slope).
- Do not use when: you have very few groups (fewer than 5–6 levels of the grouping variable) — the variance component for the random effect cannot be estimated reliably from so few clusters; in this case, treat the grouping variable as a fixed effect instead. Do not use a mixed model when the grouping structure is so severely imbalanced that some groups have only one observation — the random effect estimate for those groups will collapse to zero and distort the residual variance. Do not use mixed models as a substitute for dealing with batch effects that are confounded with the biological variable of interest; confounding cannot be adjusted away by any statistical model.

## Inputs → outputs

- Inputs: outcome vector; fixed-effect predictors (the biological variables of interest + confounders from the DAG); grouping variable (the random-effect level — subject ID, cell line ID, batch ID); choice of random effect structure (intercept only vs intercept + slope).
- Outputs: fixed-effect coefficient estimates with SEs and 95% CIs; random-effect variance components (between-group variance, within-group residual variance); intraclass correlation coefficient (ICC); likelihood-ratio test for the random effect.

## Rigor — the invariants a good analysis must honor

- **The pseudoreplication trap — the most important thing this skill is about:** Pseudoreplication is treating sub-unit observations as if they were independent biological replicates. Classic example: 5 mice per treatment group, 10 cells per mouse, fit a t-test over 50 "replicates" per group. The effective sample size is 5, not 50. The within-mouse correlation inflates the apparent precision by roughly a factor of sqrt(average_cluster_size) in the SE, producing p-values that are 3–10× too small and confidence intervals that are 3–10× too narrow. In single-cell RNA-seq, cells from the same subject share genetics, environment, and cell-type composition; treating 10 000 cells from 5 subjects as 10 000 independent observations produces near-100% false positive rates at the "subject" level. The correct approach is pseudobulk (aggregate cells to the subject level before DE) or a mixed model with subject as a random effect and cluster-robust standard errors.

- **Unit of observation / exchangeable unit:** The biological replicate (the independent experimental unit — the subject, the animal, the independent cell line passage, the independent patient sample) is the exchangeable unit. Sub-unit measurements (cells, wells, lanes, reads) are not independent replicates. The number of biological replicates, not the number of measurements, determines statistical power. A study with 4 subjects per group and 1 000 cells per subject has power equivalent to a study with 4 subjects per group and 1 measurement per subject, not 4 000 subjects.

- **Random intercept vs random slope:** A random intercept model allows each group to have its own baseline but assumes the treatment effect is the same across groups. A random slope model allows both the baseline and the treatment effect to vary across groups. If you are asking whether the average effect differs across conditions, a random intercept is usually sufficient. If you expect some subjects to respond more strongly than others (effect modification), include a random slope for the treatment variable. Start with the maximal random effect structure justified by your design and simplify by likelihood-ratio test if the model fails to converge.

- **Null model:** Mixed models assume the random effects are drawn from a normal distribution with mean zero and estimated variance. This normality assumption for random effects is rarely testable with few groups. For count outcomes (cells per condition, reads per gene), use a mixed-effects GLM (GLMM) with the appropriate family — statsmodels `MixedLM` handles Gaussian outcomes only; for binary or count outcomes, use `BinomialBayesMixedGLM` or call into R's `lme4` via `rpy2`.

- **Confounders to adjust:** Include in the fixed-effect specification only the covariates identified by your pre-specified DAG. Covariates that are constant within groups (e.g., a subject-level variable like genotype or disease status) cannot be separated from the random intercept — they are absorbed by between-group variance. Covariates that vary within groups (e.g., time of measurement, cell cycle phase) can be estimated as fixed effects while accounting for between-group heterogeneity.

- **Intraclass correlation coefficient (ICC):** ICC = between-group variance / (between-group variance + within-group variance). It quantifies the fraction of total outcome variance attributable to group membership. ICC = 0.3 means 30% of variation is between subjects — ignoring this correlation and fitting OLS would produce SEs that are sqrt(1 + (k−1)×ICC) times too small, where k is the average cluster size. For k=100 cells and ICC=0.3, OLS SEs are about 5.6× too small.

- **Multiple testing:** Fixed-effect p-values from a mixed model enter the same FDR correction family as p-values from any other test. Do not treat each random-effect group separately or apply BH to group-level estimates — the random effects are not hypotheses to be tested individually; they are nuisance parameters.

- **Effect size + floor:** Report the fixed-effect coefficient in original units with a 95% CI based on the mixed-model SEs (not bootstrap, unless the normal approximation fails). The standardized effect size for a mixed model is Cohen's d_z or f^2 (from R^2 including vs excluding the predictor), not the same as in a simple two-group comparison — document which formula you used.

- **Robustness check:** (1) Compare the mixed-model result to a pseudobulk analysis (aggregate sub-units to the group level, then run OLS) — if they disagree substantially, investigate; the pseudobulk approach is more conservative and is the recommended default for single-cell DE. (2) Check convergence warnings — if the optimizer does not converge, simplify the random effect structure. (3) Run the model with and without the random effect (nested models compared by LRT) to confirm the grouping structure is informative.

- **Common pitfalls / failure modes:** (1) Treating cells as biological replicates (pseudoreplication) — the most common and most damaging error in single-cell studies. (2) Using too few random-effect levels (< 5) to estimate the variance component reliably — switch to a fixed effect. (3) Over-specifying the random effect structure (too many random slopes) leading to singular fits — simplify until convergence. (4) Including a grouping variable both as a fixed effect and as a random effect — they are confounded; choose one. (5) Failing to account for heteroscedasticity within groups — add a variance function or switch to a robust SE estimator.

## Data sources

These skills operate on the experiment's own data. No external datasets are required. The grouping variable (subject ID, cell line ID, etc.) must be present in the data.

## Minimal worked example

```python
import numpy as np
import statsmodels.formula.api as smf
import pandas as pd

rng = np.random.default_rng(21)

# Simulate pseudoreplication scenario:
# 10 subjects, 2 groups (5 per group), 20 cells per subject
n_subjects = 10
n_cells = 20
subject_ids = np.repeat(np.arange(n_subjects), n_cells)
group = np.repeat([0]*5 + [1]*5, n_cells)  # 0=control, 1=treatment

# True between-subject SD = 0.8, within-subject SD = 0.5, treatment effect = 0.4
subject_intercepts = rng.normal(0, 0.8, n_subjects)
noise = rng.normal(0, 0.5, n_subjects * n_cells)
y = (0.4 * group
     + subject_intercepts[subject_ids]
     + noise)

df = pd.DataFrame({'y': y, 'group': group, 'subject': subject_ids.astype(str)})

# --- WRONG: OLS treating all cells as independent (pseudoreplication) ---
ols_wrong = smf.ols('y ~ group', data=df).fit()
print(f"OLS (pseudoreplication) p = {ols_wrong.pvalues['group']:.4f}  "
      f"SE = {ols_wrong.bse['group']:.4f}  [WRONG — inflated precision]")

# --- CORRECT: mixed model with random intercept per subject ---
lmm = smf.mixedlm('y ~ group', data=df, groups=df['subject'])
fit_lmm = lmm.fit(reml=True)
print(f"Mixed model (random intercept) p = {fit_lmm.pvalues['group']:.4f}  "
      f"SE = {fit_lmm.bse['group']:.4f}  [CORRECT]")

# ICC calculation
between_var = float(fit_lmm.cov_re.iloc[0, 0])
within_var = fit_lmm.scale
icc = between_var / (between_var + within_var)
print(f"ICC = {icc:.3f}  (fraction of variance between subjects)")
print(f"OLS SE inflation factor: {fit_lmm.bse['group'] / ols_wrong.bse['group']:.1f}x")

# --- ALSO CORRECT: pseudobulk (aggregate per subject, then OLS) ---
df_agg = df.groupby(['subject', 'group'])['y'].mean().reset_index()
pb_fit = smf.ols('y ~ group', data=df_agg).fit()
print(f"Pseudobulk OLS p = {pb_fit.pvalues['group']:.4f}  "
      f"SE = {pb_fit.bse['group']:.4f}  [conservative; recommended default]")
```
