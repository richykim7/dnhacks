# co_essentiality
**One line:** What is a gene's function? Rank its top co-essential partners in DepMap and test whether they form a known complex/pathway.
**trust_class:** audited-statistic

## Tests (hypothesis shape)
`GENE → functional module` — a poorly-characterized gene shares a CRISPR dependency profile with the members
of a known protein complex/pathway, implying it participates in that module. This is the classic
co-essentiality inference: genes in the same complex are co-essential (knocking out any one has the same
fitness consequence), so a query gene's top-correlated dependency partners reveal its function.

- **Worked example (schematic):** take a poorly-characterized query gene; rank its top-25 co-essential
  partners; if those partners are enriched (hypergeometric) for the members of some known complex C — where
  C's membership is read off the literature map, not assumed — then hypothesise the query gene functions in
  C. Form the hypothesis from the DATA + the literature, never from prior knowledge of the gene.

## OFFLINE path (use this in the sandbox — network is OFF)
Data: `/data/interim/explorer_ready/depmap_24q4_gene_effect.parquet` (index ModelID, columns = HGNC symbols,
values = Chronos gene effect; more negative = more essential). See `CATALOG_coessentiality.md`.

```python
import json, numpy as np, pandas as pd
df = pd.read_parquet("/data/interim/explorer_ready/depmap_24q4_gene_effect.parquet")  # lines x genes

def coessential_partners(gene, top=25):
    x = df[gene]
    # Pearson of the query profile vs every gene, pairwise-complete (DepMap has NaNs)
    r = df.corrwith(x).drop(index=[gene]).dropna()
    ranked = r.sort_values(ascending=False)
    # EMPIRICAL null: a partner's significance = its RANK / percentile in the genome-wide r distribution
    # (weakly-essential genes have small absolute r ~0.2, so judge by rank, NOT magnitude).
    out = [{"gene": g, "r": round(float(rv), 3), "rank": i + 1,
            "pctile": round(100 * (1 - i / len(ranked)), 2)} for i, (g, rv) in enumerate(ranked.head(top).items())]
    return ranked, out

def module_enrichment(ranked, gene_set, top=25):
    """Hypergeometric: are `gene_set` members over-represented in the query's top-N co-essential partners?"""
    from scipy.stats import hypergeom
    universe = set(ranked.index)
    S = set(gene_set) & universe                    # known-module genes that are testable
    topN = set(ranked.head(top).index)
    k = len(topN & S)                               # module genes in the top-N
    p = hypergeom.sf(k - 1, len(universe), len(S), top) if k > 0 else 1.0
    return {"module_hits_in_topN": k, "module_size": len(S), "topN": top, "p_null": float(p),
            "hit_genes": sorted(topN & S)}

# --- example run: pick QUERY_GENE from the literature map; MODULE = a candidate complex's members from papers ---
QUERY_GENE = "<an under-characterized gene you chose>"
MODULE = ["<complex member>", "<complex member>", "..."]   # membership taken from the literature, defined independently
ranked, partners = coessential_partners(QUERY_GENE, top=25)
enr = module_enrichment(ranked, MODULE, top=25)
print("RESULT:", json.dumps({"effect": partners[0]["r"], "effect_size": enr["module_hits_in_topN"],
      "p_null": enr["p_null"], "null_model": "hypergeometric enrichment of the module in top-N partners",
      "n_units": int(df[QUERY_GENE].notna().sum()), "robust": enr["module_hits_in_topN"] >= 3,
      "top_partners": [p["gene"] for p in partners[:12]]}))
```

## Finding a NEW member of a complex (the rigorous approach = a genome-wide scan)
Testing genes one at a time from the literature only re-finds KNOWN members — a gene that genuinely belongs
to a complex but isn't annotated to it will never be on your literature shortlist (that's exactly what makes
it a discovery). So to find a NEW member, scan the whole genome, don't hand-pick candidates:

1. Define the target complex's membership (the `MODULE`) from the literature.
2. For every gene in the matrix, compute the rank-based module-enrichment above (how many `MODULE` genes fall
   in that gene's top-N co-essential partners → hypergeometric p).
3. Rank all genes by that enrichment. The top of the list is dominated by the known members (a sanity
   check); the DISCOVERY is a top-ranked gene whose CURRENT annotation is UNRELATED to the complex — a
   surprising annotation↔function mismatch.
4. Confirm the strongest surprise: its partner enrichment, and robustness on a random cell-line subsample.

**Mean-correlation to the module is INVALID for a membership claim — do not use it to score/rank
candidates.** A semi-essential gene is weakly correlated with *many* genes, so it can post a positive mean
correlation to any gene set without the set being its actual partners → a false positive (e.g. a
metabolic/prenylation enzyme scoring high against a loose centrosome set while its real top partners are
its own subunit). The only valid signal is the **rank-based hypergeometric enrichment**: are the complex's
members significantly over-represented in this gene's TOP-N co-essential partners? Judge every candidate by
that test; a candidate that passes mean-correlation but has ~0 module genes in its top-N is not a member.

```python
# genome-wide scan for new members of MODULE (a complex defined from the literature)
import numpy as np
from scipy.stats import hypergeom
MODULE = ["<complex member>", "..."]                 # from papers, defined independently of the data
C = df.corr()                                        # gene x gene co-essentiality (or a fast z-scored X.T@X/n)
U = C.shape[0] - 1; S = len([m for m in MODULE if m in C.columns]); TOP = 25
scan = {}
for g in C.columns:
    part = C[g].drop(g).nlargest(TOP).index
    k = len(set(part) & set(MODULE))
    scan[g] = hypergeom.sf(k - 1, U, S, TOP) if k else 1.0
# rank ascending by p; inspect the top genes whose annotation is NOT already in the complex -> candidates
```

## Audited statistic and null model
**Statistic:** Pearson correlation of two genes' Chronos dependency vectors across cell lines
(pairwise-complete; DepMap has missing values). For a functional claim, the reported effect is the
**enrichment** of a known module among the query gene's top-N co-essential partners.

**Primary null — hypergeometric enrichment:** given the query's top-N partners, `p_null` = probability of
seeing ≥k members of the candidate module by chance, drawing N genes from the ~17,900-gene universe. This is
the appropriate test of "the top partners are a coherent complex," and it is robust to the small absolute r of
weakly-essential genes.

**Rank, not magnitude:** for a weakly-essential query gene (small dependency variance) absolute r's are
small (~0.2). Judge partners by RANK / percentile and by module enrichment — never threshold on r, and
never rank candidates by mean-correlation-to-a-module (it false-positives on diffusely-essential genes).

**Robustness:** the module hit should be stable — re-rank on a random 70% subsample of cell lines a few
times; the module's top-N hits should persist (sign/membership stability), not depend on a few lines.

## Gotchas / when not to use  (operationalization-mismatch triggers)
1. **Common-essential genes** (essential in ~all lines, e.g. core ribosome/proteasome) have near-zero
   dependency variance → they correlate with nothing meaningful (or spuriously with each other). If the
   query or partners are pan-essential (mean gene effect ≪ 0 in nearly all lines, low variance), the
   co-essentiality signal is degenerate — flag operationalization-mismatch.
2. **Non-expressed / never-dependent genes:** a gene never essential in any line has no profile to
   correlate — `n_units` effectively zero variance → underpowered.
3. **The module must be defined independently** of the data (from the literature map), or the enrichment is
   circular. Take the candidate complex's membership from papers, then test it against the dependency ranks.
4. **Direction:** co-essentiality is symmetric and undirected — it asserts shared function/module, not a
   regulatory direction. Do not over-read a mechanism from correlation alone.
