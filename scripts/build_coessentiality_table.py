"""Materialize the DepMap 24Q4 gene-effect matrix for offline co-essentiality analysis in the sandbox.

Co-essentiality = correlation of two genes' CRISPR dependency (Chronos) profiles across cell lines. The
full gene x cell-line matrix lets the engine rank any query gene's top co-essential partners genome-wide.

Output: data/interim/explorer_ready/depmap_24q4_gene_effect.parquet  (index ModelID, columns = HGNC symbols,
values = Chronos gene effect; more negative = more essential). Re-derivable from data/raw/depmap_24q4/.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

RAW = Path("data/raw/depmap_24q4/CRISPRGeneEffect.csv")
OUT = Path("data/interim/explorer_ready/depmap_24q4_gene_effect.parquet")


def main() -> None:
    df = pd.read_csv(RAW, index_col=0)
    df.columns = [c.split(" (")[0] for c in df.columns]   # "SYMBOL (ENTREZ)" -> "SYMBOL"
    df.index.name = "ModelID"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT)
    print(f"wrote {OUT}  ({df.shape[0]} cell lines x {df.shape[1]} genes)")

    cat = OUT.parent / "CATALOG_coessentiality.md"
    cat.write_text(
        f"""# DepMap 24Q4 gene-effect matrix (co-essentiality) — FROZEN, offline

`depmap_24q4_gene_effect.parquet` — index ModelID; columns = HGNC gene symbols; values = CRISPR Chronos
gene effect (more negative = more essential). {df.shape[0]} cell lines x {df.shape[1]} genes.

**Data vintage:** DepMap 24Q4.

**Co-essentiality:** correlate two genes' columns across cell lines (Pearson, pairwise-complete). A query
gene's TOP-ranked partners reveal its functional module. Null =
the empirical genome-wide distribution of correlations with the query gene. See skills/co_essentiality.
""")
    print(f"wrote {cat}")


if __name__ == "__main__":
    main()
