# Confounding and Causal Inference

**One line:** Build a DAG before touching data, use it to derive the adjustment set, estimate the causal effect, then run the DoWhy refuter battery as a required promotion gate before calling anything a finding.
**Category:** stats-core
**Open-source:** dowhy — MIT; econml — MIT; networkx — BSD; statsmodels — BSD
**Install:** `pip install dowhy econml networkx statsmodels`

## When to use it (and when not)

- Use when: the question is causal — "does disrupting gene X change cell viability?" or "does high CERES score in a cell line cause sensitivity to compound Y?" — not merely associational. Use whenever you want to claim that an association is not explained by a third variable that causes both X and Y. Use DoWhy's refuter battery before any discovery claim propagates out of the explorer, to confirm that the estimate is not driven by residual confounding or analytic fragility.
- Do not use when: the question is purely predictive (you want a model with low held-out error, not an unbiased coefficient). Causal adjustment requires a valid DAG — if you have no domain knowledge about the causal structure and the DAG is entirely speculative, a causal claim is no more reliable than an association claim and may be worse (adjusting for a collider opens a spurious path). Do not use if the treatment is not adequately supported across the covariate space (no positivity / no overlap) — extrapolating outside common support is not causal inference, it is extrapolation. Do not use for time-varying treatments where prior exposures confound later ones — use g-methods (g-computation, IPW with time-varying weights) instead.

## Inputs → outputs

- Inputs: a pre-committed DAG (drawn from domain knowledge before data analysis begins); the treatment variable T and outcome variable Y named in the DAG; the observed data matrix; the backdoor adjustment set derived from the DAG (or identified automatically by DoWhy).
- Outputs: the Average Treatment Effect (ATE) or Conditional ATE (CATE) estimate with uncertainty; refuter test results (placebo treatment, random common cause, subset, dummy outcome); E-value for unmeasured confounding sensitivity.

## Rigor — the invariants a good analysis must honor

- **The DAG must be drawn before data analysis:** A DAG (directed acyclic graph) encodes your causal assumptions about which variables cause which. It determines the adjustment set — which variables to condition on (confounders: common causes of T and Y that block back-door paths), which to avoid conditioning on (mediators: variables on the causal path from T to Y; colliders: variables caused by both T and Y or by T or Y and an unmeasured variable). The DAG is not optional and is not derived from the data. It is a scientific commitment, written down and hashed before analysis begins. Changing the DAG after seeing results is a form of p-hacking.

- **Backdoor criterion — what to adjust for and what not to:** A set Z satisfies the backdoor criterion for estimating the effect of T on Y if: (1) no element of Z is a descendant of T, and (2) Z blocks every back-door path between T and Y (paths that start with an arrow into T). Adjusting for a collider (a variable downstream of both T and Y, or downstream of T or Y and an unmeasured common cause) opens a spurious path rather than blocking one — a classic error is adjusting for a variable on the causal pathway or for a consequence of both exposure and outcome. DoWhy's `identify_effect` with the `backdoor` criterion automates the identification step from a declared DAG.

- **Unit of observation / exchangeable unit:** The observation must correspond to an independent unit. If multiple measurements come from the same subject, the treatment effect estimate is biased toward the within-subject effect, not the population-average effect. Use the correct unit as specified in your pre-analysis plan.

- **Estimation method choices:** Linear regression on the adjustment set is the standard estimator when the outcome model is approximately linear. Doubly-robust estimators (Augmented IPW) are preferred when either the outcome model or the propensity score model may be misspecified — they are consistent if at least one is correct. Double/debiased ML (DML via EconML) uses cross-fitting to estimate the nuisance functions (outcome model, propensity) without overfitting bias, and is the appropriate choice when the covariate set is high-dimensional or when nonlinear nuisance models are needed.

- **The refuter battery is not optional — it is a promotion gate:** Before a causal claim can pass verification, it must pass all four DoWhy refuters. (1) Placebo treatment: replace the real treatment with a random variable that has no causal effect on Y; the effect estimate should shrink to near zero. A non-null placebo effect signals residual confounding or a broken identification strategy. (2) Random common cause: add a randomly generated variable as a confounder in the model; the ATE estimate should not change substantially (a large change indicates the estimate is unstable with respect to small model changes). (3) Data subset: estimate on 80% random subsets of the data repeatedly; the effect should be stable (coefficient of variation < 20–30% is a rough guide). (4) Dummy outcome: replace Y with a randomly generated outcome; the effect estimate should be null. A non-null result indicates a coding error or data leakage.

- **E-value for unmeasured confounding:** The E-value quantifies the minimum strength of association that an unmeasured confounder would need (with both the treatment and outcome, on the risk-ratio scale) to explain away the observed effect. An E-value of 3 means the confounding would need to produce a 3-fold association with both T and Y to fully explain the result. Report the E-value alongside every causal estimate. An E-value near 1 means even weak unmeasured confounding could explain the result — do not call this a discovery.

- **Confounders to adjust:** Derive the adjustment set from the DAG, not from p-value screening of covariates in the data ("stepwise selection of controls"). Data-driven covariate selection for the adjustment set conflates confounders with instruments (which should not be included in the adjustment set when using instrumental variable methods) and with colliders.

- **Multiple testing:** Each causal effect estimate is one entry in the FDR correction family. The refuter p-values from each refuter test are not an additional multiple-testing problem within a single causal analysis — they are internal validity checks, not discovery tests.

- **Effect size + floor:** Report the ATE in original units with a 95% CI. Pre-declare the minimum clinically or scientifically meaningful effect before analysis. An E-value well above the SESOI-equivalent confounding strength gives more confidence than a large E-value for a tiny effect.

- **Robustness check:** Compare the linear backdoor adjustment estimate to a doubly-robust estimate. If they agree, the result is robust to modest model misspecification. If they disagree substantially, the linear model's parametric assumptions are load-bearing — report both and investigate which covariates drive the divergence. Run the subset refuter on 10 different random 80% subsets and plot the distribution of estimates.

- **Common pitfalls / failure modes:** (1) Adjusting for a collider — the most reliable way to introduce a spurious association while believing you are removing one. (2) Adjusting for a mediator — this blocks the causal path you are trying to measure. (3) Reading adjustment-covariate coefficients as independent causal effects (the Table 2 fallacy) — each coefficient in a multi-variable regression is the effect adjusted for all other variables in that model, which is rarely the target estimand for the covariates. (4) Using a DAG built from the data (e.g., from a correlation or mutual information scan) as if it were domain knowledge — the data-derived DAG embeds the same confounding it is supposed to help resolve. (5) Not checking positivity: if treated units have propensity scores near 1 and controls near 0, the overlap region is empty and any estimator will extrapolate wildly. (6) Running the refuter battery only when the effect is significant and skipping it otherwise — the refuters are required regardless of significance.

## Data sources

These skills operate on the experiment's own data. The DAG is drawn from domain knowledge before analysis. No external datasets are required.

## Minimal worked example

```python
import numpy as np
import pandas as pd
import dowhy
from dowhy import CausalModel

rng = np.random.default_rng(55)
n = 500

# Simulate: W causes T and Y (confounder); T causes Y
W = rng.normal(size=n)               # confounder (e.g. cell line basal expression)
T = 0.5 * W + rng.normal(size=n)    # treatment (e.g. CERES dependency score, continuous)
Y = 0.8 * T + 0.6 * W + rng.normal(scale=0.5, size=n)  # outcome (e.g. drug sensitivity)
# True ATE of T on Y = 0.8 (W is a confounder, not in naive estimate)

df = pd.DataFrame({'T': T, 'Y': Y, 'W': W})

# --- Step 1: Declare the causal graph (from domain knowledge, before data) ---
causal_graph = """
    digraph {
        W -> T;
        W -> Y;
        T -> Y;
    }
"""

model = CausalModel(
    data=df,
    treatment='T',
    outcome='Y',
    graph=causal_graph
)

# --- Step 2: Identify the estimand ---
identified_estimand = model.identify_effect(proceed_when_unidentifiable=False)
print(identified_estimand)

# --- Step 3: Estimate (linear regression on backdoor adjustment set {W}) ---
estimate = model.estimate_effect(
    identified_estimand,
    method_name='backdoor.linear_regression',
    test_significance=True
)
print(f"\nATE estimate: {estimate.value:.3f}  (true = 0.8)")
print(f"95% CI: {estimate.get_confidence_intervals()}")

# --- Step 4: Refuter battery (all four; REQUIRED before claiming a finding) ---
# 4a: Placebo treatment
ref_placebo = model.refute_estimate(
    identified_estimand, estimate,
    method_name='placebo_treatment_refuter',
    placebo_type='permute',
    num_simulations=100
)
print(f"\nPlacebo refuter: new_effect={ref_placebo.new_effect:.3f}, "
      f"p={ref_placebo.refutation_result['p_value']:.3f}  "
      f"[should be ~0 and p~1 to pass]")

# 4b: Random common cause
ref_rcc = model.refute_estimate(
    identified_estimand, estimate,
    method_name='random_common_cause',
    num_simulations=100
)
print(f"Random common cause refuter: new_effect={ref_rcc.new_effect:.3f}  "
      f"[should be close to {estimate.value:.3f}]")

# 4c: Data subset
ref_subset = model.refute_estimate(
    identified_estimand, estimate,
    method_name='data_subset_refuter',
    subset_fraction=0.8,
    num_simulations=100
)
print(f"Subset refuter: new_effect={ref_subset.new_effect:.3f}  "
      f"[should be close to {estimate.value:.3f}]")

# E-value: requires RR-scale; for continuous outcomes, convert to Cohen's d first
# Here we just demonstrate the reporting obligation
print(f"\nReport alongside ATE: E-value = compute from evalue package or manual formula")
print("(E-value = ATE_rr + sqrt(ATE_rr*(ATE_rr-1)) for risk-ratio scale effects)")
```
