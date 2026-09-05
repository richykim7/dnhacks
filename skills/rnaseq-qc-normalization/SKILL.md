# rnaseq-qc-normalization

**One line:** Before any differential expression or enrichment analysis, assess library quality, remove outlier samples, filter uninformative genes, and choose the correct expression unit for each downstream purpose.
**Category:** bulk-rna-seq
**Open-source:** MultiQC — GPL-3; pydeseq2 — BSD-3 (for size factors / VST); pandas / scikit-learn — BSD-3 (for PCA)
**Install:** `pip install multiqc pydeseq2 scikit-learn` or `conda install -c bioconda multiqc`

## When to use it (and when not)
- Use when: starting any new bulk RNA-seq dataset — always. QC and normalization are not optional preprocessing steps. A miscalibrated library-size normalization, an undetected outlier sample, or an uninformative gene retained in the analysis will corrupt every downstream test. The earlier these problems are caught, the cheaper they are to fix.
- Do not use when: you are working with an already-validated, QC-passed count matrix. Do not re-normalize an already-normalized matrix; doing so compounds the transformation and produces a nonsensical input for count-based DE models.

## Inputs → outputs
- Inputs: raw count matrix (genes × samples, integer counts from salmon/kallisto or STAR + featureCounts); alignment/quantification QC metrics (mapping rate, duplication rate, insert-size distribution — from MultiQC HTML reports); sample metadata (library size, batch, RNA integrity number if available).
- Outputs: (a) a filtered count matrix with low-count genes removed, ready for DE; (b) size-factor-normalized counts (DESeq2 median-of-ratios) or TMM-normalized log-CPM (edgeR/limma) for PCA visualization; (c) VST or rlog counts for heatmaps and ML features; (d) TPM matrix for cross-experiment visualization. QC flags: outlier samples, low-mapping-rate samples, samples with extreme library sizes relative to the group.

## Rigor — the invariants a good analysis must honor

- **Unit of observation / exchangeable unit:** one biological replicate = one library/sample column. Do not average replicates before QC — outlier detection requires seeing individual samples. Do not remove samples post-hoc after inspecting DE results (that is double-dipping); remove only on pre-specified, analysis-blind QC criteria applied before running DE.
- **Null model:** QC and normalization have no formal statistical null — they are data-processing steps. However, outlier sample detection should use quantitative, pre-specified thresholds: flag any sample with (a) < 70% overall alignment/mapping rate, (b) < 500,000 mapped reads (low-depth), (c) PCA position > 3 SD from its condition centroid on PC1 or PC2 of the size-factor-normalized log-count matrix. Samples failing two or more criteria warrant investigation before exclusion.
- **Confounders to adjust at the normalization step:** (a) Sequencing depth / library size: corrected by DESeq2 size factors (median-of-ratios method, robust to outlier genes) or TMM normalization (edgeR). Do not use simple CPM — it is sensitive to highly expressed genes dominating the library total. (b) Gene length: TPM corrects for length (within-sample); raw counts do not. (c) GC-content bias: corrected at the quantification step by salmon's `--gcBias`; if correction was not applied upstream, EDASeq or CQN can apply it at the count level. (d) Composition bias: a sample with a few extremely highly expressed genes (e.g., hemoglobin in blood) can compress the apparent counts of all other genes; TMM and DESeq2 size factors are compositionally robust — simple total-count normalization is not.
- **Multiple testing:** normalization decisions affect the multiple-testing family in DE downstream. The critical rule is: gene filtering decisions must be made before running DE, on criteria blind to DE results (e.g., "keep genes with ≥ 10 counts in at least N samples, where N = size of the smallest group"). Filtering based on DE results (e.g., "remove genes with padj = NA" and then re-adjust p-values) is post-hoc manipulation of the family and inflates false discovery.
- **Effect size + floor:** the filtering threshold "≥ 10 counts in ≥ N samples" is a heuristic. Its purpose is to remove genes with near-zero counts that carry no statistical power — they inflate the multiple-testing burden without contributing true discoveries. Retaining them does not increase sensitivity; it decreases the power of the BH correction on the genes that matter. If you lower the threshold (e.g., ≥ 5 counts), more genes are retained but the proportion of NA-padj genes increases.
- **Robustness check:** PCA on VST- or rlog-normalized counts is the primary visual QC tool. After normalization, samples should cluster by the biological variable of interest, not by library size or batch. If PC1 or PC2 strongly correlates with library size (Spearman |r| > 0.5) after normalization, the normalization was inadequate and must be revisited. Compute per-sample correlation of log-count profiles with the median profile of its condition group — samples with Spearman r < 0.85 against their group median are outlier candidates.
- **Common pitfalls / failure modes:** (1) Using TPM as DE model input — TPM removes both library-size and gene-length variation, making counts non-comparable across genes for a count model. The NB-GLM requires raw counts because its noise model depends on Poisson count variance. (2) Using RPKM/FPKM — these are compositionally dependent: a highly expressed gene inflates every other gene's denominator across the whole sample, making them non-comparable between samples. They are obsolete; do not use them for any cross-sample comparison. (3) Filtering genes after testing — filtering based on padj < threshold and then recomputing adjusted p-values on the survivors under-counts the multiple-testing family. (4) Feeding VST or rlog output back into DESeq2 — these transformations are for visualization and ML features only. DESeq2's own model requires raw integer counts. (5) Ignoring QC metrics and running DE directly — a single outlier sample with 10x the library size of others can dominate the size-factor estimate and suppress true DE signals.

### The right unit for the right task — reference table

| Unit | Formula | Corrects for | Use for |
|---|---|---|---|
| Raw counts | integer | nothing | DE model input (DESeq2/edgeR/limma) |
| CPM | count / (total × 10⁶) | library size | quick sanity checks only |
| TPM | (count / length) / sum × 10⁶ | library size + gene length | within-sample comparison, cross-experiment visualization, GSVA/WGCNA input |
| DESeq2 norm counts | count / size_factor | library size (robust) | count-scale visualization within a study |
| TMM log-CPM | log2(TMM-normalized CPM + offset) | library size + composition | limma-voom input, cross-sample log-scale PCA |
| VST / rlog | variance-stabilized | depth + mean-variance trend | PCA, heatmaps, clustering, ML features |

## Data sources
- Input counts: output from salmon-kallisto skill or STAR + featureCounts. MultiQC HTML reports come from FastQC (on FASTQ) and samtools flagstat / salmon log (on alignments/quants). Network not required if files are already local.
- Public datasets for testing: recount3 (Bioconductor, network required); GEO (network required via `GEOquery` or manual download). Pre-download to `data/interim/` for offline analysis.
- Sandbox: network not required if counts and QC files are already local.

## Minimal worked example
```python
import numpy as np
import pandas as pd
from pydeseq2.dds import DeseqDataSet
from sklearn.decomposition import PCA
import matplotlib.pyplot as plt

# --- Load raw counts and metadata ---
counts   = pd.read_csv("counts_matrix.csv",  index_col=0)   # genes x samples (integers)
metadata = pd.read_csv("metadata.csv",        index_col=0)   # samples x covariates

# === STEP 1: Library-size QC ===
lib_sizes = counts.sum(axis=0)
print("Library sizes (mapped reads per sample):")
print(lib_sizes.describe())
# Flag samples with < 500,000 mapped reads
low_depth = lib_sizes[lib_sizes < 500_000].index.tolist()
if low_depth:
    print(f"WARNING — low-depth samples: {low_depth}")

# Check mapping rates (from salmon/STAR log files; load separately):
# mapping_rates = pd.read_csv("mapping_rates.csv", index_col=0)
# low_map = mapping_rates[mapping_rates["rate"] < 0.70].index.tolist()

# === STEP 2: Gene filtering — before DE, blind to results ===
# Keep genes with >= 10 counts in at least min_samples samples
min_samples = metadata["condition"].value_counts().min()  # smallest group size
keep = (counts >= 10).sum(axis=1) >= min_samples
counts_filtered = counts.loc[keep]
print(f"Genes before filter: {counts.shape[0]}")
print(f"Genes after filter:  {counts_filtered.shape[0]}")
# (Approximately 12,000–18,000 for human; far fewer means the data or filter are off)

# === STEP 3: Size-factor normalization + VST for PCA (visualization only) ===
# pydeseq2 computes DESeq2-style size factors
dds = DeseqDataSet(
    counts=counts_filtered.T,   # samples x genes
    metadata=metadata,
    design_factors=["condition"],
    n_cpus=4,
)
dds.fit_size_factors()          # median-of-ratios normalization
norm_counts = dds.layers["normed_counts"]   # size-factor-corrected counts (not for DE model)

# Log-transform for PCA
log_norm = np.log1p(norm_counts)  # samples x genes
pcs = PCA(n_components=10).fit_transform(log_norm)

# === STEP 4: PCA outlier detection ===
# Per-condition centroid; flag samples > 3 SD from centroid on PC1/PC2
for cond in metadata["condition"].unique():
    idx = (metadata["condition"] == cond).values
    centroid = pcs[idx, :2].mean(axis=0)
    dists = np.linalg.norm(pcs[idx, :2] - centroid, axis=1)
    outliers = np.where(dists > 3 * dists.std())[0]
    if len(outliers):
        print(f"Outlier candidates in '{cond}': {metadata.index[idx][outliers].tolist()}")

# === STEP 5: TPM computation for visualization / GSVA ===
gene_lengths = pd.read_csv("gene_lengths.csv", index_col=0)["length"]  # bp
# (gene lengths from Ensembl GTF or from salmon effective lengths)
counts_kb = counts_filtered.div(gene_lengths / 1000, axis=0)           # count / kb
tpm = counts_kb.div(counts_kb.sum(axis=0) / 1e6, axis=1)               # TPM
print("TPM matrix shape:", tpm.shape)
# tpm → GSVA, WGCNA, visualization
# counts_filtered → pydeseq2 DE model (see pydeseq2 skill)

# === STEP 6: Quick PCA plot colored by condition and batch ===
fig, axes = plt.subplots(1, 2, figsize=(10, 4))
for ax, col in zip(axes, ["condition", "batch"]):
    for val in metadata[col].unique():
        idx = (metadata[col] == val).values
        ax.scatter(pcs[idx, 0], pcs[idx, 1], label=str(val), alpha=0.8)
    ax.set_xlabel("PC1"); ax.set_ylabel("PC2"); ax.set_title(f"Colored by {col}"); ax.legend()
plt.tight_layout()
plt.savefig("pca_qc.png", dpi=150)
# After normalization: samples should cluster by condition, not by batch or library size.
```
