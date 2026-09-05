# batch-correction-combat-sva

**One line:** Given a count or normalized expression matrix with known or unknown batch labels, estimate and remove batch variation — but only when batch and condition are not perfectly confounded, or the correction is statistically invalid.
**Category:** bulk-rna-seq
**Open-source:** sva / ComBat / ComBat-seq — Artistic-2.0 (R); inmoose — GPL-3 (Python ComBat-seq port)
**Install:** `BiocManager::install("sva")` (R) or `pip install inmoose` (Python)

## When to use it (and when not)

- Use when: samples were processed across multiple batches — different sequencing runs, library prep dates, labs, instruments, or flowcells — that are not perfectly confounded with the biological condition of interest. Use ComBat-seq on raw counts; use ComBat on log-normalized matrices; use SVA when batch labels are unknown and you want to estimate latent confounders.
- Do not use when: **batch is perfectly confounded with condition.** If every treated sample is in batch 1 and every control in batch 2, there is mathematically no way to separate technical from biological variation. Correction will either fail with a rank-deficient design matrix or silently remove the biology you care about. Stop — report the confound, do not attempt correction. Also do not use ComBat (the original, log-normal) on raw integer counts — use ComBat-seq instead.

### The design-confound check

Before running any batch correction, check the rank of your design matrix explicitly:

```python
import numpy as np, pandas as pd
from patsy import dmatrix
# metadata has columns: batch, condition
mat = dmatrix("batch + condition", metadata, return_type="dataframe")
rank = np.linalg.matrix_rank(mat.values)
full = mat.shape[1]  # number of columns
if rank < full:
    raise ValueError(
        f"Design matrix is rank-deficient ({rank} < {full}): "
        "batch and condition are collinear — correction is invalid."
    )
```

A rank-deficient design matrix is a hard stop. Fix the experimental design (add more batches, sequence more samples) rather than attempting to force-correct.

## Inputs → outputs

- ComBat-seq (raw counts, R/Python): raw integer count matrix (genes × samples), `batch` vector, optional `group` vector (condition) to protect biological signal from being removed alongside batch.
- ComBat (log-normalized, R): log-normalized expression matrix (genes × samples), `batch` vector, `mod` (model matrix including condition) to protect biological signal.
- SVA (R): full model matrix (includes condition), null model matrix (excludes condition), and normalized expression matrix. Returns `n.sv` (estimated number of surrogate variables) and a matrix of surrogate variable columns to add to the DE design.

Outputs:
- ComBat-seq: batch-corrected count matrix (approximately integer; suitable for DESeq2/edgeR input without re-rounding).
- ComBat: batch-corrected log-expression matrix for visualization (PCA, heatmaps) or as limma input.
- SVA: a matrix of surrogate variables to add as columns in the DE design formula — they are not a corrected expression matrix but latent-confounder covariates.

## Rigor — the invariants a good analysis must honor

- **Unit of observation / exchangeable unit:** biological replicate. Batch correction adjusts across samples; it does not touch within-sample gene covariance. Removing batch at the expression level before a correlation analysis (co-expression, WGCNA) can distort the gene-gene covariance structure — prefer including batch in the model instead.
- **Null model:** ComBat uses an empirical-Bayes model for batch-specific location (additive) and scale (multiplicative) parameters, estimated with an informative prior from the pooled gene distribution. SVA uses a two-stage algorithm: (1) permutation of the full model to estimate the number of significant latent components; (2) iterative regression to recover surrogate variable directions without using the condition label. Both methods are designed to be blind to the condition signal when `mod`/`group` is specified correctly.
- **Confounders to adjust:** always pass the biological variable of interest to ComBat's `mod` (R) or ComBat-seq's `group` argument — this instructs the method to protect that signal. Omitting it means ComBat treats condition as noise and partially removes it. For SVA, always pass both `mod` (full model) and `mod0` (null model without condition) to ensure the algorithm targets only non-condition latent structure.
- **Multiple testing:** N/A at the correction step; BH-FDR is enforced in the downstream DE model.
- **Effect size + floor:** after correction, rerun PCA on normalized expression and verify that samples cluster by condition, not by batch. If PC1 or PC2 still aligns with batch after correction, the correction was incomplete — possible causes are partial batch-condition confounding, insufficient sample size, or a strong unmeasured technical covariate.
- **Robustness check:** (a) PCA before and after: the batch axis should collapse; the condition axis should be preserved or clarified. (b) Spike a set of known housekeeping genes (GAPDH, ACTB, RPL19 — genes with stable expression across conditions) and verify their batch-corrected log2FC between conditions is ≈ 0. (c) For SVA: vary k (number of surrogate variables) by ±1 and check that the top DE gene list is stable; an unstable list suggests SVA is over- or under-fitting the latent structure.
- **Common pitfalls / failure modes:** (1) **Batch = condition confound** — the single most dangerous mistake; no correction method rescues this. (2) Applying ComBat (log-normal model) to raw counts instead of ComBat-seq — variance structure mismatch inflates false positives in downstream DE. (3) Omitting `mod` in the ComBat call — the method removes condition signal along with batch. (4) Over-correcting with too many SVs — SVA with k too large removes biologically meaningful variance; use `num.sv()` to estimate k, and treat the estimate as a ceiling, not a floor. (5) Using ComBat-corrected counts as exact integers — they are not; do not re-round to integers before passing to DESeq2 (DESeq2 accepts near-integers). (6) Forgetting that the preferred DE approach is to include `batch` in the model formula, not to correct and then omit it. Reserve ComBat/ComBat-seq for visualization (PCA, heatmaps) and for meta-analysis combining data from different platforms or labs where a joint model is not feasible.

### When to model vs when to correct

Include `batch` as a covariate in the DE model formula whenever batch and condition are not confounded — this is strictly more powerful and statistically valid because it partitions batch variance at the model level. Apply ComBat/ComBat-seq only when you need a corrected expression matrix for a downstream step that cannot accept a design matrix: unsupervised clustering, PCA visualization, co-expression analysis, or cross-study meta-analysis.

## Data sources
- Input data: same count matrices from the DE workflow (salmon-kallisto, STAR + featureCounts).
- Example multi-batch datasets: TCGA (sequencing plate as batch variable); GTEx v8 (multiple sequencing cohorts per tissue); GEO meta-analyses combining datasets across labs (network required). Locally cached in `data/interim/` if pre-downloaded.
- Sandbox: network not required if data are already local.

## Minimal worked example
```python
# Python path via inmoose (ComBat-seq port)
import numpy as np
import pandas as pd
from inmoose.comBatSeq import comBat_seq

# counts: genes x samples (raw integers)
counts   = pd.read_csv("counts_matrix.csv", index_col=0)   # shape: (n_genes, n_samples)
metadata = pd.read_csv("metadata.csv",      index_col=0)   # has 'batch' and 'condition'

# --- CRITICAL: check for batch-condition confound BEFORE correcting ---
from patsy import dmatrix
mat = dmatrix("C(batch) + C(condition)", metadata, return_type="dataframe")
rank = np.linalg.matrix_rank(mat.values)
if rank < mat.shape[1]:
    raise ValueError("Batch and condition are collinear — correction invalid. Stop.")

batch = metadata["batch"].values
group = metadata["condition"].values  # protect biological signal

# --- ComBat-seq: correct raw counts ---
corrected_counts = comBat_seq(
    counts.values,          # numpy array, genes x samples
    batch=batch,
    group=group,            # REQUIRED: protects condition signal
)
corrected_df = pd.DataFrame(corrected_counts, index=counts.index, columns=counts.columns)

# corrected_df → feed into pydeseq2 (see pydeseq2 skill)
# but still include batch in design_factors: ["batch", "condition"]
# (correction is for visualization; model still accounts for batch)

# --- Visual QC: PCA before and after ---
from sklearn.decomposition import PCA
import matplotlib.pyplot as plt

def pca_plot(mat, metadata, title):
    log_mat = np.log1p(mat.T)  # samples x genes, log1p for PCA
    pcs = PCA(n_components=2).fit_transform(log_mat)
    fig, ax = plt.subplots()
    for batch_id in metadata["batch"].unique():
        idx = metadata["batch"] == batch_id
        ax.scatter(pcs[idx, 0], pcs[idx, 1], label=f"batch {batch_id}", alpha=0.7)
    ax.set_title(title); ax.legend(); return fig

pca_plot(counts.values,           metadata, "Before ComBat-seq")
pca_plot(corrected_counts,        metadata, "After ComBat-seq")
# PC1 should shift from separating by batch → separating by condition
```

```r
# R path: SVA for unknown latent confounders
library(sva)
library(DESeq2)

# normalized expression matrix (use vst from DESeq2 for SVA input)
dds   <- DESeqDataSetFromMatrix(counts, colData=metadata, design=~ condition)
vst_m <- assay(vst(dds))

mod   <- model.matrix(~ condition, data=metadata)   # full model
mod0  <- model.matrix(~ 1,         data=metadata)   # null model (intercept only)

n_sv  <- num.sv(vst_m, mod, method="leek")          # estimate number of SVs
svobj <- sva(vst_m, mod, mod0, n.sv=n_sv)

# Add SVs to DE design in DESeq2 or limma:
sv_df <- as.data.frame(svobj$sv)
colnames(sv_df) <- paste0("SV", seq_len(ncol(sv_df)))
metadata_sv <- cbind(metadata, sv_df)

# design: ~ SV1 + SV2 + condition  (add all SVs, condition last)
```
