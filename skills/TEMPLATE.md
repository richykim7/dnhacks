# <skill-name>

> Canonical format for an explorer SKILL.md. A skill is **informational + rigorous guidance a competent
> computational biologist would stand behind**, not a frozen function. The explorer reads it and writes
> its own code; the skill tells it *what the method is, when to reach for it, and the statistical
> invariants it must not violate*. Nothing here is enforced by machinery — it's the standard of care.

**One line:** <what question this method answers, in one sentence>
**Category:** <single-cell | bulk-rna-seq | variant-effect | structure | pathway-enrichment | stat-genetics | sequence-models | multi-omics | epigenomics | networks | stats-core>
**Open-source:** <library name(s)> — <LICENSE (must be permissive/commercially-usable: MIT/BSD/Apache/LGPL/GPL; never a non-commercial license — if the best-known tool is NC, name the open-source alternative instead)>
**Install:** `pip install ...` or `conda install -c bioconda ...`

## When to use it (and when not)
- Use when: <the hypothesis shapes / questions this fits>
- Do not use when: <mismatches — what a significant result does and does not imply>

## Inputs → outputs
- Inputs: <data + parameters>
- Outputs: <the estimate(s), effect size, uncertainty>

## Rigor — the invariants a good analysis must honor
(These are the non-negotiables of *method*, stated as guidance. The explorer writes the code; it should
not deviate from these without a stated reason.)
- **Unit of observation / exchangeable unit:** <what a row/sample is; what the null permutes>
- **Null model:** <the correct null — permutation/knockoff/analytic; never a naive N(0,1) if the data violate it>
- **Confounders to adjust:** <batch, library size, lineage, cell composition, ancestry, etc.>
- **Multiple testing:** <BH-FDR over the full family; count every test>
- **Effect size + floor:** <report a standardized effect + a triviality floor; significance ≠ importance>
- **Robustness check:** <leave-one-out / cross-platform / subsample — an artifact check needing no answer key>
- **Common pitfalls / failure modes:** <the classic ways this method lies (batch effects, pseudoreplication, double-dipping, leakage)>

## Data sources
- <public dataset(s) + how to obtain; prefer LOCAL/pre-materialized; note if network is required so the
  sandbox needs `network='bridge'` or the data pre-fetched>

## Minimal worked example
```python
# a short, runnable sketch the explorer can adapt — imports, the estimate, the null, the effect size
```
