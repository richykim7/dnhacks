"""Build analysis-ready tables from a chosen DepMap release directly from the public CSVs.

Reads a DepMap Public release directory (CRISPRGeneEffect.csv, Model.csv,
OmicsSomaticMutationsMatrixDamaging.csv) and writes the same tables the explorer sandbox reads, so a run
can be pinned to a chosen data release. Overwrites whatever is in
data/interim/explorer_ready/. Token-free.

  uv run python scripts/build_frozen_depmap_tables.py --raw data/raw/depmap_<release> --release <release> --driver KRAS
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

OUT = Path("data/interim/explorer_ready")

CATALOG = """# Explorer analysis-ready tables — DepMap **{release}** — mounted at /data/interim/explorer_ready/
Data vintage {release}, pinned so the sandbox data predates the run's literature cutoff.

- cell_line_meta.parquet — index ModelID; columns: Sex (Male/Female/Unknown), OncotreeLineage,
  {col} (bool: True = {driver} damaging mutation present, False = WT).
- gene_dependency.parquet — index ModelID; columns = HGNC gene symbols; values = Chronos dependency
  (more negative = more essential).
"""


def _sym(cols) -> list[str]:
    return [re.sub(r"\s*\(\d+\)\s*$", "", str(c)).strip() for c in cols]   # 'A1BG (1)' -> 'A1BG'


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True, help="directory holding the DepMap release CSVs")
    ap.add_argument("--release", required=True, help="release label written into the catalog, e.g. 22Q4")
    ap.add_argument("--driver", required=True, help="HGNC symbol whose damaging-mutation status is stratified on")
    args = ap.parse_args()
    RAW = Path(args.raw)
    driver = args.driver.upper()
    col = f"{driver.lower()}_lof"

    chronos = pd.read_csv(RAW / "CRISPRGeneEffect.csv", index_col=0)
    chronos.columns = _sym(chronos.columns)
    chronos = chronos.loc[:, ~chronos.columns.duplicated()]
    chronos.index.name = "ModelID"

    model = pd.read_csv(RAW / "Model.csv")
    id_col = "ModelID" if "ModelID" in model.columns else model.columns[0]
    model = model.set_index(id_col)
    keep = [c for c in ("Sex", "OncotreeLineage") if c in model.columns]
    meta = model[keep].copy()

    dmg = pd.read_csv(RAW / "OmicsSomaticMutationsMatrixDamaging.csv", index_col=0)
    dmg.columns = _sym(dmg.columns)
    lof = (dmg[driver] > 0) if driver in dmg.columns else pd.Series(False, index=dmg.index)
    meta[col] = lof.reindex(meta.index).fillna(False).astype(bool)
    meta = meta.reindex(chronos.index)               # analysis-ready = lines with dependency data
    meta.index.name = "ModelID"

    OUT.mkdir(parents=True, exist_ok=True)
    meta.to_parquet(OUT / "cell_line_meta.parquet")
    chronos.to_parquet(OUT / "gene_dependency.parquet")
    (OUT / "CATALOG.md").write_text(CATALOG.format(release=args.release, driver=driver, col=col))

    print(f"{args.release} tables: meta {meta.shape} | dependency {chronos.shape}")
    print(f"{driver}-LOF lines: {int(meta[col].sum())} of {len(meta)}")
    print(f"wrote -> {OUT}/ (DepMap {args.release})")


if __name__ == "__main__":
    main()
