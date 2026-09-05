"""Materialize analysis-ready DepMap tables for the explorer sandbox.

The clean tables let sandbox code read one file and group by, instead of wrangling the raw DepMap files.
The driver gene whose loss-of-function status is stratified on is a parameter; its column is named
`<driver>_lof`. Token-free.

  uv run python scripts/build_explorer_data.py --driver KRAS
"""
from __future__ import annotations

import argparse
from pathlib import Path

from dnhacksbio.depmap_harmonize import DepMap

OUT = Path("data/interim/explorer_ready")

CATALOG = """# Explorer analysis-ready tables — mounted read-only at /data/interim/explorer_ready/
Read these directly instead of wrangling raw DepMap files.

- cell_line_meta.parquet — index ModelID; columns: Sex (Male/Female/Unknown), OncotreeLineage,
  {col} (bool: True = {driver} loss-of-function/mutant, False = WT).
- gene_dependency.parquet — index ModelID; columns = HGNC gene symbols; values = Chronos dependency
  (more negative = more essential to that line).

Worked example — {driver}-WT vs {driver}-LOF dependency on a gene, with a permutation null over the label:
    import pandas as pd, numpy as np
    meta = pd.read_parquet("/data/interim/explorer_ready/cell_line_meta.parquet")
    dep  = pd.read_parquet("/data/interim/explorer_ready/gene_dependency.parquet")
    df = meta.join(dep[["BRCA2"]], how="inner").dropna(subset=["BRCA2"])
    obs = df[df["{col}"]]["BRCA2"].mean() - df[~df["{col}"]]["BRCA2"].mean()
    rng = np.random.default_rng(0); lab = df["{col}"].values
    null = []
    for _ in range(2000):
        p = rng.permutation(lab)
        null.append(df["BRCA2"][p].mean() - df["BRCA2"][~p].mean())
    pval = (np.sum(np.abs(null) >= abs(obs)) + 1) / (2000 + 1)   # n_units = len(df)
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--driver", required=True, help="HGNC symbol whose LOF status stratifies the lines")
    args = ap.parse_args()
    driver = args.driver.upper()
    col = f"{driver.lower()}_lof"

    dm = DepMap()
    chronos = dm.chronos
    meta = dm.model.loc[:, ["Sex", "OncotreeLineage"]].copy()
    meta[col] = dm.lof_call(driver).reindex(meta.index).fillna(False).astype(bool)
    meta = meta.reindex(chronos.index)          # analysis-ready = the lines that have dependency data
    meta.index.name = "ModelID"

    OUT.mkdir(parents=True, exist_ok=True)
    meta.to_parquet(OUT / "cell_line_meta.parquet")
    chronos.to_parquet(OUT / "gene_dependency.parquet")
    (OUT / "CATALOG.md").write_text(CATALOG.format(driver=driver, col=col))

    print(f"meta {meta.shape} | dependency {chronos.shape}")
    print(f"{driver}-LOF lines: {int(meta[col].sum())} of {len(meta)}")
    print(f"wrote -> {OUT}/")


if __name__ == "__main__":
    main()
