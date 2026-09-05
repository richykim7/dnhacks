# pydeseq2

**One line:** Given a gene × sample raw count matrix and sample metadata, which genes are differentially expressed between conditions according to the DESeq2 negative-binomial GLM — in pure Python?
**Category:** bulk-rna-seq
**Open-source:** pydeseq2 — BSD-3
**Install:** `pip install pydeseq2`

## When to use it (and when not)
- Use when: you have raw integer count data from bulk RNA-seq (from salmon/kallisto estimated counts or STAR + featureCounts) and want rigorous gene-level DE with empirical-Bayes shrinkage of dispersion estimates. PyDESeq2 is a faithful Python reimplementation of the Bioconductor DESeq2 model (Love et al. 2014), making it the default for pure-Python workflows. The NB-GLM is the field standard for small-to-medium n (3–50 samples per group); it handles overdispersion that a Poisson model ignores and that a t-test on TPM assumes away entirely.
- Do not use when: you have fewer than 2 biological replicates per condition — there is no valid inference without replication, full stop. Do not use when your design matrix is non-full-rank (batch perfectly confounds condition; see batch-correction-combat-sva skill). Do not use for transcript-level DE (use sleuth or DTU methods). Do not feed normalized data (TPM, VST, rlog) as input — pyDESeq2 requires raw counts because its NB model depends on the Poisson noise structure of integer counts.

## Inputs → outputs
- Inputs: `counts` — genes × samples DataFrame of raw integer counts (do not pre-filter; let pyDESeq2's independent filtering decide); `metadata` — samples × covariates DataFrame with at minimum a `condition` column; `design_factors` — list of column names defining the linear model (e.g., `["batch", "condition"]`; condition last); `ref_level` — the baseline condition label for contrast. Optional: `refit_cooks` (True by default; removes Cook's-distance outlier samples automatically).
- Outputs: results DataFrame indexed by gene: `baseMean`, `log2FoldChange` (MAP-shrunken via apeglm or ashr), `lfcSE`, `stat` (Wald), `pvalue`, `padj` (BH-FDR over all tested genes). Normalized count matrix (via `ds.layers["normed_counts"]`) for visualization — not for DE input.

## Rigor — the invariants a good analysis must honor

- **Unit of observation / exchangeable unit:** one biological replicate = one sample/library row. A sequencing lane is not a biological replicate. Technical replicates (same RNA, re-sequenced) add no statistical power and must not be modeled as independent observations — sum their counts before passing to pyDESeq2.
- **Null model:** the NB-GLM null is β (the condition coefficient) = 0, tested by a Wald statistic with an analytic chi-squared reference distribution. Dispersions are estimated per gene and then shrunken toward a fitted trend using empirical Bayes — this shrinkage is what gives validity at small n by borrowing strength across genes. The Wald test is not a t-test on TPM means; the two are answering different questions with different noise models.
- **Confounders to adjust:** include `batch` in `design_factors` when batches are known. Include `RIN` (RNA integrity number) as a continuous covariate if it varies across samples. Include any known technical or biological covariate that is not of primary interest but correlates with expression. Do not include variables that are rank-deficient with condition in the design matrix — check `rank(model_matrix)` before running.
- **Multiple testing:** `padj` is BH-FDR applied over all genes passing pyDESeq2's independent filtering (genes with very low mean counts are filtered because they have no power, and filtering before running inflates FDR). Do not re-filter after testing to rescue genes that became NA — that is post-hoc cherry-picking. The correct threshold is `padj ≤ 0.05`; the conventional secondary filter is `|log2FoldChange| ≥ 1` (2-fold change).
- **Effect size + floor:** always report the MAP-shrunken `log2FoldChange` (not the unshrunken MLE), because MLE log2FC is noisy for low-count genes and inflates rankings. Apply `ds.lfc_shrink(coeff=..., method="apeglm")`. A triviality floor of `|log2FC| ≥ 0.5` (1.4-fold) is the minimum worth reporting; `|log2FC| ≥ 1` is the conventional biological significance bar. Genes that are statistically significant at tiny effect sizes (|log2FC| < 0.3) at large n are usually not actionable.
- **Robustness check:** (a) run with and without the batch covariate and compare top 200 hits — if the hit list changes substantially, the batch effect is real and must be included; (b) re-run after removing the single most extreme sample (Cook's distance outlier) and verify top hits survive; (c) cross-check with edgeR QL F-test or limma-voom on the same data — concordant hits across two methods are far more credible than hits unique to one method.
- **Common pitfalls / failure modes:** (1) Feeding TPM or normalized counts instead of raw integer counts — this is the single most common error; pyDESeq2 will run and produce numbers that are statistically invalid. (2) n < 3 per group — with 2 vs 2 samples the dispersion estimate is essentially a guess; reported FDR is anti-conservative. (3) Pseudoreplication — treating mouse tumors from the same animal as independent replicates, or treating technical replicates as biological. (4) Omitting a known strong batch effect from `design_factors` — inflates false positives dramatically. (5) Filtering low-count genes before running instead of after — pyDESeq2's independent filtering is calibrated to the NB model; removing genes beforehand with an ad-hoc threshold distorts the multiple-testing correction. (6) Not using shrinkage on log2FC — unshrunken LFCs for low-count genes can be 10+ fold; always shrink before ranking or plotting.

## Data sources
- Input counts: output from salmon-kallisto skill (estimated counts, imported via pyroe or pandas) or STAR + featureCounts (integer counts directly). Do not mix count sources within a study.
- Public datasets for testing: GEO (network required; use `GEOparse` or manual download); recount3 (`recount` Bioconductor package or its REST API, network required). Pre-download to `data/interim/` to avoid network dependency in analysis runs.
- Sandbox: network not required if counts are already local.

## Minimal worked example
```python
import pandas as pd
from pydeseq2.dds import DeseqDataSet
from pydeseq2.ds import DeseqStats

# --- Load data ---
# counts: genes x samples, raw integer counts (NOT TPM)
counts = pd.read_csv("counts_matrix.csv", index_col=0).T  # samples x genes
metadata = pd.read_csv("metadata.csv", index_col=0)       # samples x covariates
# metadata must have columns: "batch", "condition" (at minimum)
# Reference level: "control" is baseline
metadata["condition"] = pd.Categorical(
    metadata["condition"], categories=["control", "treated"]
)

# --- Fit the NB-GLM ---
dds = DeseqDataSet(
    counts=counts,
    metadata=metadata,
    design_factors=["batch", "condition"],  # batch first; condition last
    ref_level=["condition", "control"],
    refit_cooks=True,   # remove Cook's-distance outlier samples
    n_cpus=4,
)
dds.deseq2()  # estimate size factors → dispersions → GLM coefficients

# --- Wald test + LFC shrinkage ---
stat_res = DeseqStats(dds, contrast=["condition", "treated", "control"])
stat_res.summary()
stat_res.lfc_shrink(coeff="condition_treated_vs_control")  # apeglm shrinkage

results = stat_res.results_df
hits = results.query("padj < 0.05 and log2FoldChange.abs() >= 1").sort_values(
    "log2FoldChange", key=abs, ascending=False
)

print(f"Total genes tested: {results.shape[0]}")
print(f"Significant hits (padj<0.05, |log2FC|≥1): {hits.shape[0]}")
print(hits[["baseMean", "log2FoldChange", "lfcSE", "padj"]].head(10))

# --- PCA on VST-normalized counts (visualization only — NOT for DE input) ---
vst_counts = dds.layers["normed_counts"]  # or compute VST separately
# Feed hits to gsea-prerank skill using the full ranked stat list:
rank_metric = results["stat"].dropna().sort_values(ascending=False)
```
