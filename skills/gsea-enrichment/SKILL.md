# gsea-enrichment

**One line:** Given a ranked list of genes (e.g., by differential expression statistic), does a pre-defined gene set score higher than chance — and how strong and reproducible is that enrichment?
**Category:** pathway-enrichment
**Open-source:** GSEApy — BSD-3; fgsea — MIT; MSigDB gene sets — mostly CC BY 4.0 (strip KEGG-legacy and BioCarta subsets before any commercial use); Reactome gene sets — CC0; WikiPathways — CC0
**Install:** `pip install gseapy` (Python) or `BiocManager::install("fgsea")` (R)

## When to use it (and when not)

- Use when: you have a pre-ranked list of all genes (ranked by fold-change, t-statistic, or signal-to-noise ratio from a differential expression analysis) and want to test whether a curated biological program (hallmark, pathway, regulon) is systematically shifted toward the top or bottom of that ranking — not just whether a few genes pass a threshold.
- Use when: the hypothesis is "pathway X is up-regulated in condition A vs B" rather than "gene Y is differentially expressed."
- Do not use when: your gene list is a small hit-set from a threshold (use ORA instead — see `over-representation-analysis`). GSEA needs a full ranking of all measured genes; clipping it to significant genes breaks the statistic.
- Do not use when: you have fewer than ~7 samples per group and intend to use phenotype-label permutation — the null becomes too coarse. Consider falling back to gene permutation with explicit acknowledgment, or switch to ORA on a threshold-selected set.
- A significant NES does not mean every gene in the set is regulated. It means the set collectively sits at the extremes of the ranking. Individual gene biology still needs follow-up.

## Inputs → outputs

- Inputs: a ranked Series of all genes (index = HGNC symbol, values = ranking metric — signed -log10 p × sign(LFC) or t-statistic; must include all measured genes, not just significant ones); a gene-set library (MSigDB Hallmark, Reactome, or WikiPathways GMT file, loaded locally); `min_size` and `max_size` to filter trivially small/large sets; number of permutations (≥ 1000 for publication).
- Outputs: per gene set — Enrichment Score (ES), Normalized Enrichment Score (NES), nominal p-value, BH-FDR q-value, leading-edge genes (the subset driving the peak enrichment).

## Rigor — the invariants a good analysis must honor

- **Unit of observation / exchangeable unit:** the gene is the unit; what is permuted depends on study design. For preranked GSEA (the common Python/R use case — you supply a pre-computed ranking), the null permutes the gene labels (randomly reassigns which genes are in the set, keeping the ranking fixed). For phenotype GSEA where you have raw expression + sample labels, permute the sample labels (phenotype permutation) — this preserves the gene-gene correlation structure and is strictly preferred when n ≥ 7 per group. `fgsea` and `GSEApy prerank` both do gene permutation by default because they accept a pre-ranked list, not raw data; be explicit about which null you are using.
- **Null model:** competitive null — the gene set is tested against the rest of the genome, not against itself. This answers "does this set score better than a random same-size set drawn from the same ranked list?" The alternative, a self-contained null (is the set enriched relative to a flat ranking?), answers a different question and is more prone to inflation from general DE signal. For most discovery questions, the competitive null is correct. fgsea implements competitive permutation by default.
- **Confounders to adjust:** the ranking metric must come from a confounder-corrected DE analysis (batch, library size, lineage, proliferation already removed before producing t-statistics or LFCs). GSEA inherits whatever biases are in the ranking — garbage in, garbage out.
- **Multiple testing:** apply BH-FDR across all gene sets tested in the same analysis. Do not correct per-set p-values in isolation. GSEApy and fgsea both return `fdr_bh` or `padj` columns — use those. A standard threshold is FDR q < 0.25 (the original Broad GSEA convention) or q < 0.05 for a tighter call; always report the threshold you chose.
- **Effect size + floor:** report NES (the enrichment score normalized by the mean enrichment of random sets of the same size — removes gene-set-size bias). |NES| < 1.5 is a weak signal; results with |NES| < 1.0 are essentially noise and should not be reported as enrichments. Always report NES alongside the q-value; a q < 0.05 with NES = 1.1 is not scientifically interesting.
- **Robustness check:** run GSEA on two independent cohorts or data splits if available. At minimum, check that the leading-edge genes (the core enriched genes) are biologically coherent — if the leading edge is 50 genes with no functional theme, the enrichment is likely spurious. Cross-check the top hits against an orthogonal gene-set library (Hallmark enrichment confirmed in Reactome is more credible than Hallmark alone).
- **Common pitfalls / failure modes:** (1) Gene-set redundancy — MSigDB and Reactome have heavily overlapping sets; reporting "top 20 enriched pathways" when 15 of them are sub-sets of the same pathway is misleading. Collapse redundant results using leading-edge overlap (Jaccard < 0.5 between reported sets). (2) Ranking metric choice — signed log p (common) can rank non-significant genes in unexpected directions when FCs are large but variance is high; t-statistic or signal-to-noise ratio is more stable. (3) Gene-ID mismatch — HGNC symbols in the ranking must match those in the GMT; run a symbol-intersection check and report coverage. (4) Using a thresholded hit list as the "ranked list" — this is ORA, not GSEA; the two are not interchangeable.

## Data sources

- **MSigDB gene sets** (local, preferred): download GMT files from https://www.gsea-msigdb.org/gsea/msigdb/. `h.all.v2023.2.Hs.symbols.gmt` (Hallmark, 50 sets, CC BY 4.0) and `c2.cp.reactome.v2023.2.Hs.symbols.gmt` (Reactome subset, CC BY 4.0) are the safe commercial choices. Strip `c2.cp.kegg*` and `c2.cp.biocarta*` GMT files — those subsets inherit KEGG/BioCarta licensing restrictions. Store GMT files in `data/gene_sets/` so no network access is needed at run time.
- **Reactome** (CC0, fully unrestricted): `pip install reactome2py` or download GMT directly from https://reactome.org/download/current/ReactomePathways.gmt.zip. Preferred for commercial work.
- **WikiPathways** (CC0): https://data.wikipathways.org/current/gmt/ — download `wikipathways-YYYYMMDD-gmt-Homo_sapiens.gmt`.
- Network access is required only for initial download. All subsequent runs are local.

## Minimal worked example

```python
import gseapy as gp
import pandas as pd

# --- 1. Build ranked list from a DE result ---
# de is a DataFrame with columns: 'stat' (t-statistic or signed -log10p),
# index = HGNC gene symbols, all measured genes included (no threshold applied)
de = pd.read_csv("data/interim/de_results.csv", index_col=0)
ranking = de["stat"].dropna().sort_values(ascending=False)
# Sanity check: must include all genes, not just DE hits
assert len(ranking) > 5000, "Ranking too short — did you threshold before passing?"

# --- 2. Load gene sets locally (no network) ---
gmt_path = "data/gene_sets/h.all.v2023.2.Hs.symbols.gmt"  # MSigDB Hallmark, CC BY 4.0

# --- 3. Run preranked GSEA ---
pre_res = gp.prerank(
    rnk=ranking,
    gene_sets=gmt_path,
    min_size=15,
    max_size=500,
    permutation_num=1000,      # >= 1000 for final results
    seed=42,
    threads=4,
)

res = pre_res.res2d.copy()

# --- 4. Multiple testing: BH-FDR across all gene sets ---
# gseapy returns 'FDR q-val' column computed by BH already; verify it
print(res[["Term", "NES", "NOM p-val", "FDR q-val"]].sort_values("FDR q-val").head(10))

# --- 5. Apply effect-size floor ---
sig = res[(res["FDR q-val"] < 0.25) & (res["NES"].abs() >= 1.5)]
print(f"{len(sig)} gene sets pass FDR < 0.25 and |NES| >= 1.5")

# --- 6. Redundancy check: leading-edge Jaccard ---
def jaccard(s1, s2):
    a, b = set(s1.split(";")), set(s2.split(";"))
    return len(a & b) / len(a | b) if (a | b) else 0.0

# If top hits share >50% leading-edge overlap, collapse to representative
le_col = "Lead_genes"  # column name may vary by gseapy version
top = sig.sort_values("FDR q-val").head(20)
# Compare pairwise Jaccard of top[le_col] to flag redundant sets
```
