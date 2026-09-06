---
name: pydeseq2
description: Estimate model-based gene differential expression from raw counts with PyDESeq2; audit replication, design and approximate inference.
---

# pydeseq2

**One line:** Estimate gene-level differential expression from raw integer counts using a negative-binomial model.
**Category:** bulk-rna-seq
**Open-source:** PyDESeq2, BSD-3
**Install:** `uv sync --extra expression` (PyDESeq2 0.5.4).

Use a samples × genes nonnegative integer count matrix and aligned sample metadata.
Never supply TPM, VST, normalized counts, or counts reconstructed from TPM. Fractional
quantifier estimates need a justified count-import workflow; rounding is not one.
Aggregate sequencing lanes first. For single-cell input, sum by donor × condition ×
externally defined cell type. Cells and passages do not provide independent replication.

Freeze the gene family, eligibility, design, contrast, filtering and analysis before
confirmation. Check design rank and biological replication. Pairing uses `~ donor + condition`;
a justified independent design can use `~ batch + condition`. Adding covariates cannot fix
perfect confounding. Small samples remain uncertain: dispersion shrinkage does not prove
finite-sample validity or guarantee FDR control.

```python
from pydeseq2.dds import DeseqDataSet
from pydeseq2.ds import DeseqStats

# counts: samples × genes raw integer DataFrame; metadata has matching row IDs.
dds = DeseqDataSet(counts=counts, metadata=metadata,
                   design="~ donor + condition", refit_cooks=True, n_cpus=1)
dds.deseq2()
stats = DeseqStats(dds, contrast=["condition", "treatment", "control"], n_cpus=1)
stats.summary()
results = stats.results_df.copy()  # unshrunk log2FoldChange, lfcSE, Wald pvalue, BH padj
# Optional, separate shrinkage: inspect the actual coefficient names first.
# stats.lfc_shrink(coeff="condition[T.treatment]")
```

Shrinkage is a `DeseqStats` method, not a `DeseqDataSet` method. It is not applied by default;
record whether each effect estimate was shrunk. `refit_cooks` handles supported outlier-count
replacement/refitting; it does not simply remove samples. `normed_counts` is normalized counts,
not a variance-stabilizing transformation.

Prespecified, label-independent low-count filtering can be appropriate; it is not inherently
invalid. Independent filtering and Cook's filtering can produce missing p/padj values. Preserve
those missing values and the full tested family; do not selectively rescue them after testing.
There is no universal fold-change floor or sample-size cutoff that establishes biological relevance.

The NB coefficient null and the fixed normalized-score randomization null differ. Wald p-values
are model-based approximate outputs; calibrating them does not establish finite-sample-valid
expression evidence. The private registered expression adapter keeps these estimates alongside
its separately justified paired-score test, without feeding either into verification or recall.

API audit: [PyDESeq2 0.5.4 workflow](https://pydeseq2.readthedocs.io/en/v0.5.4/auto_examples/plot_minimal_pydeseq2_pipeline.html).
