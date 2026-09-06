# experimental-rigor

**One line:** The non-negotiable soundness floor every experiment must clear — the same gates the engine's falsifier uses to KILL results, stated up front so you build them in instead of getting killed.
**Category:** stats-core
**Open-source:** yes (numpy / scipy / statsmodels)
**Install:** none beyond the sandbox default stack

## Why this skill is different

Every other skill tells you HOW to run one method. This one tells you the bar every result has to clear no
matter the method, because the independent verifier re-derives soundness from your reported numbers and
**kills anything that fails** — before a human ever sees it. Build these in from the first line of code and
your good findings survive; skip them and even a real effect gets thrown out. These mirror
`falsifier._soundness_core` exactly; the thresholds below are the actual ones it enforces.

## The floor (ALL must hold; the checker applies them in this order)

1. **No estimable effect → dead.** If the statistic is `None`/`NaN`, it's underpowered. Guard your code so
   it returns a real number or a clear "underpowered" reason.
2. **Enough units.** `n_units ≥ 8` at the *exchangeable unit* (per group where there are groups). Report
   `n_units` accurately.
3. **Direction.** If your hypothesis predicts a sign (`expected_sign = +1` or `-1`), the observed effect
   must have that sign, or it's `unsound`. Two-sided hypotheses use `expected_sign = 0` (direction not
   gated) — but then you can't claim a direction.
4. **Significance vs a real null.** `p_null ≤ 0.05`, where `p_null` comes from a **permutation/resampling
   null at the exchangeable unit** (not a parametric p from a formula that assumes independence you don't
   have). Report it Phipson–Smyth style, `(ge + 1) / (n_perm + 1)`, so it is **never exactly 0**.
5. **Effect-size floor.** Report a **standardized** `effect_size` and clear `|effect_size| ≥ 0.15`.
   Significant ≠ real: with thousands of rows a microscopic effect can be "significant" yet meaningless.
6. **Robustness.** Re-estimate under a **leave-one-group-out** (drop each lineage / batch / age-decile /
   platform in turn). Set `robust = true` only if the **sign is stable** across all folds. A result that
   flips when you remove one group is an artifact, not a finding.
7. **Multiple comparisons.** Declare the full family of experiments and report all planned
   attempts. Do not select only favorable variants or claim investigation-wide error control
   from a single experiment result.

## The exchangeable unit (the concept people get wrong most)

The unit you permute/resample must be the thing that is actually **independent**. Cell lines, donors,
patients, shuffled promoter regions — yes. Individual reads, cells from the same donor, timepoints from the
same subject — **no** (those are pseudoreplicates; permuting them fabricates significance). State the unit
in one line in `null_model`. If observations are nested (cells within donors), aggregate to the donor first
(pseudobulk) or use a mixed model — see `mixed-models-pseudoreplication`.

## The trap the floor does not catch — so YOU must

The soundness floor checks whether the *statistics* are sound. It does **not** know whether you **tuned the
analysis until it passed**. Decide the analysis — unit, null, covariates, threshold — **before** you look at
the result. Do **not** sweep parameters until `p < 0.05`; that is p-hacking (an "immunizing stratagem") and
it produces a number that clears every gate above while meaning nothing. If you must try several reasonable
specifications, commit to them in advance and report all of them, not the best one. Prefer a hypothesis that
**forbids** a concrete outcome (a near-tautology that can't be wrong tells you nothing).

## Expression experiment submissions

For independent-donor TPM distribution comparisons, use the `expression-experiment` skill's
submission command. It returns a receipt only; do not attach extra statistics or fabricate a
RESULT for it. The result shape below applies to ordinary exploratory analyses.

## Minimal shape your code should print

```python
print("RESULT:", json.dumps({
    "effect": eff,               # point estimate, native units
    "effect_size": std_eff,      # standardized; must clear |.|>=0.15
    "p_null": p_perm,            # permutation p at the exchangeable unit; (ge+1)/(n_perm+1)
    "null_model": "shuffled <UNIT> labels, N=<n_perm>",
    "n_units": n,                # >=8 (per group)
    "robust": lolo_sign_stable,  # leave-one-group-out sign stability
}))
```

Include a **negative control** wherever you can (a pair/label that *should* show nothing) — it's the cheapest
evidence your pipeline isn't manufacturing signal.
