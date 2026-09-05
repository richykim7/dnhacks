# Regression and Generalized Linear Models

**One line:** Estimate the relationship between an outcome and one or more predictors while choosing the right error distribution, link function, and standard errors for the data structure.
**Category:** stats-core
**Open-source:** statsmodels — BSD; scipy — BSD; numpy — BSD
**Install:** `pip install statsmodels scipy numpy`

## When to use it (and when not)

- Use when: the outcome is continuous (OLS), binary (logistic), a count (Poisson/NegBin), a proportion (binomial GLM), or a non-negative continuous (Gamma/log-normal). Use when you need to adjust for covariates while estimating the effect of a primary predictor. Use robust or cluster-robust standard errors when residual diagnostics show heteroscedasticity or when observations are grouped (cell lines within tissue types, patients within hospitals).
- Do not use when: observations are not independent — for repeated-measures or nested designs, use a mixed model (see mixed-models-pseudoreplication skill). Do not use OLS when the outcome is strictly bounded (binary, count) and n is small enough that the approximation fails — the Gaussian approximation to a binomial becomes poor when expected cell counts fall below 5. Do not use a logistic regression coefficient as a causal effect without a DAG and a valid adjustment set — the coefficient is a conditional association, not an intervention effect. Do not use GLMs for survival/time-to-event data; use Cox regression or parametric survival models instead.

## Inputs → outputs

- Inputs: outcome vector y; covariate matrix X (including the primary predictor and any confounders from the pre-specified DAG); choice of distribution family and link function; choice of standard error type (OLS default / HC3 robust / cluster-robust).
- Outputs: coefficient estimates with standard errors and 95% CIs; test statistics and p-values for each coefficient; model fit diagnostics (residual plots, QQ plot, leverage/influence, VIF for multicollinearity); quasi-likelihood dispersion estimate for overdispersed counts.

## Rigor — the invariants a good analysis must honor

- **Link function must match the outcome distribution:** The link function connects the linear predictor Xβ to the mean of the outcome. The canonical link for Gaussian is identity (OLS); for Binomial is logit; for Poisson is log. A mismatch — e.g., fitting OLS to a count outcome with many zeros and a long right tail — produces invalid inference even when the coefficient estimate is approximately correct, because the error structure assumed by OLS (constant Gaussian variance) is wildly wrong for count data. Check: plot residuals vs fitted values. For counts, the variance should grow with the mean; for binary outcomes, residuals will look non-normal by construction — use Pearson or deviance residuals.

- **Overdispersion in count models:** Poisson assumes variance = mean. Real biological count data (read counts, event counts) routinely show overdispersion (variance >> mean), which makes Poisson SEs anti-conservative. Diagnose: the quasi-likelihood dispersion parameter phi = Pearson chi^2 / df_residual; if phi >> 1, switch to NegativeBinomial (which adds a free dispersion parameter) or use quasi-Poisson (which scales SEs by sqrt(phi)). Never report Poisson SEs for count data without checking dispersion.

- **Unit of observation / exchangeable unit:** Each row of the design matrix must correspond to one statistically independent observation. If you have multiple measurements per subject or cell line, OLS treats them as independent and underestimates standard errors. The solution is either to aggregate to the subject level (one row per subject) or to use a mixed model. Cluster-robust SEs are a middle ground: they correct the variance estimate for clustering without requiring a full random-effects specification, but they are asymptotically valid only when the number of clusters is large (≥ 30–50 clusters).

- **Robust standard errors — use HC3 by default, not HC0:** OLS with heteroscedasticity produces biased SEs. HC0 (White) is downward-biased in small samples. HC3 (MacKinnon-White) applies a leverage-based correction and is the standard choice for regression with small to moderate n. In statsmodels, use `model.fit(cov_type='HC3')`. For clustered data, use `cov_type='cluster', cov_kwds={'groups': cluster_var}`.

- **Confounders to adjust:** Include in X only the variables identified by your pre-specified DAG as required for backdoor adjustment. Do not include mediators (they block the causal path you are estimating) and do not include colliders (conditioning on a collider opens a spurious path between the exposure and unmeasured confounders). Including too many variables inflates variance; including the wrong ones introduces bias. The Table 2 fallacy: never interpret the coefficient on a covariate (e.g., age, sex, batch) in the same model as a causal estimate of that variable's effect — it is adjusted for different things than a model designed to estimate that variable's effect.

- **Multicollinearity check:** When predictors are highly correlated, coefficient estimates become unstable (large SEs, sign flips under small perturbations). Compute the Variance Inflation Factor (VIF) for each predictor; VIF > 5–10 signals a problem. Solutions: drop one of the correlated predictors (if that is scientifically justified), use ridge regression for prediction, or reformulate the question.

- **Multiple testing:** Each regression produces one p-value per coefficient. If you run multiple regressions (e.g., one per gene in a gene-by-gene scan), the family size is the number of regressions × the number of tested coefficients per regression. Apply BH-FDR over the full family of p-values for the primary coefficient of interest; do not apply it separately to nuisance covariate coefficients.

- **Effect size + floor:** Report the coefficient in original (unstandardized) units alongside a standardized version. For logistic regression, report the odds ratio with a 95% CI and note its interpretation (a multiplicative change in odds, not in probability). For Poisson/NegBin, report the incidence rate ratio. For continuous outcomes, a standardized beta (coefficient × SD(X)/SD(y)) allows comparison across predictors with different scales. Pre-declare the SESOI in the units of the coefficient.

- **Robustness check:** (1) Refit without influential observations identified by Cook's distance (D > 4/n is a common heuristic). (2) Compare results with and without covariates to assess sensitivity to adjustment set. (3) For Poisson models, compare Poisson and NegBin — large differences in SEs confirm overdispersion. (4) Check linearity of continuous predictors by adding a quadratic term or using a spline; nonlinearity bias inflates apparent effects in the linear model.

- **Common pitfalls / failure modes:** (1) Using OLS SEs when residuals are heteroscedastic — OLS SEs are anti-conservative under increasing variance. (2) Treating multiple rows per subject as independent — inflates effective n and deflates SEs. (3) Using the Poisson model for overdispersed count data — the SEs are anti-conservative and p-values are too small. (4) The Table 2 fallacy — interpreting covariate coefficients as independent causal effects when the adjustment set was designed for a different estimand. (5) Multicollinearity causing sign flips or near-zero coefficients for predictors you know should matter — diagnose with VIF before interpreting.

## Data sources

These skills operate on the experiment's own data. No external datasets are required.

## Minimal worked example

```python
import numpy as np
import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor

rng = np.random.default_rng(99)
n = 200

# Simulate: continuous outcome, two predictors + a batch covariate
batch = rng.choice([0, 1], size=n)
x1 = rng.normal(size=n) + 0.3 * batch   # slight batch confounding
x2 = rng.normal(size=n)
y = 0.4 * x1 + 0.1 * x2 + 0.5 * batch + rng.normal(scale=0.8, size=n)

X = sm.add_constant(np.column_stack([x1, x2, batch]))
col_names = ['const', 'x1', 'x2', 'batch']

# --- OLS with HC3 robust SEs (default to this; check residuals after) ---
model = sm.OLS(y, X)
fit_hc3 = model.fit(cov_type='HC3')
print("=== OLS with HC3 robust SEs ===")
print(fit_hc3.summary2())

# --- VIF check for multicollinearity ---
print("\nVariance Inflation Factors:")
for i, col in enumerate(col_names[1:], start=1):
    vif = variance_inflation_factor(X, i)
    print(f"  {col}: VIF = {vif:.2f}  {'[OK]' if vif < 5 else '[HIGH — multicollinearity]'}")

# --- Poisson GLM for count outcome example ---
count_y = rng.poisson(lam=np.exp(0.3 * x1 + 0.2 * batch + 1.0))
poisson_model = sm.GLM(count_y, X, family=sm.families.Poisson())
fit_poisson = poisson_model.fit(cov_type='HC3')
# Check overdispersion: phi = Pearson chi^2 / df_resid
phi = fit_poisson.pearson_chi2 / fit_poisson.df_resid
print(f"\nPoisson dispersion (phi): {phi:.2f}  "
      f"{'[OK: ~1]' if phi < 1.5 else '[OVERDISPERSED — use NegBin]'}")
if phi > 1.5:
    negbin_model = sm.GLM(count_y, X, family=sm.families.NegativeBinomial())
    fit_negbin = negbin_model.fit(cov_type='HC3')
    print("Refitted with NegativeBinomial:")
    print(fit_negbin.summary2().tables[1])
```
