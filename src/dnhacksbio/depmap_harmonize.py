"""Harmonize raw DepMap 24Q4 CSVs into analysis tables + the operational LOF call.

Raw DepMap wide matrices are `ModelID` x `"SYMBOL (ENTREZ)"`. We clean columns to bare HGNC symbols,
downcast to float32, and write parquet (fast per-gene columnar reads later). Then we define the
generic LOF call used to stratify cell lines by driver status.

LOF call (identical for any driver):
    a line is LOF for gene G iff any of
      (i)  a damaging coding mutation in G            (OmicsSomaticMutationsMatrixDamaging > 0)
      (ii) deep/homozygous deletion of G             (relative CN < CN_DEL_THRESH)
      (iii) expression silencing of G                (log2(TPM+1) below the EXPR_LOF_PCTL percentile)
This is a generic operational definition.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "depmap_24q4"
INTERIM = ROOT / "data" / "interim" / "depmap_24q4"

# --- LOF thresholds ---------------------------
CN_DEL_THRESH = 0.30        # relative (linear) copy number below this = deep/homozygous deletion
EXPR_LOF_PCTL = 10.0        # expression below this within-gene percentile = silencing
# lineage column we adjust for (confounder); Oncotree lineage is DepMap's harmonized tissue axis
LINEAGE_COL = "OncotreeLineage"

_SYMH = re.compile(r"^(.*?)\s+\(\d+\)$")


def _clean_symbol_cols(df: pd.DataFrame) -> pd.DataFrame:
    """`"GENE (1234)"` -> `"GENE"`; drop duplicate symbols (keep first), keep ModelID index."""
    new = {}
    for c in df.columns:
        m = _SYMH.match(c)
        new[c] = m.group(1) if m else c
    df = df.rename(columns=new)
    df = df.loc[:, ~df.columns.duplicated(keep="first")]
    return df


def _load_matrix(fname: str, dtype=np.float32) -> pd.DataFrame:
    df = pd.read_csv(RAW / fname, index_col=0, low_memory=False)
    df.index.name = "ModelID"
    df = _clean_symbol_cols(df)
    return df.astype(dtype)


def harmonize() -> dict[str, Path]:
    """Load all raw matrices, write cleaned parquet, return the written paths."""
    INTERIM.mkdir(parents=True, exist_ok=True)
    out: dict[str, Path] = {}

    # Chronos dependency (negative = stronger dependency) — the primary readout
    chronos = _load_matrix("CRISPRGeneEffect.csv")
    p = INTERIM / "chronos.parquet"; chronos.to_parquet(p); out["chronos"] = p

    # cell-line metadata (lineage = confounder)
    model = pd.read_csv(RAW / "Model.csv", low_memory=False).set_index("ModelID")
    keep = [c for c in ["OncotreeLineage", "OncotreePrimaryDisease", "OncotreeSubtype",
                        "OncotreeCode", "DepmapModelType", "PrimaryOrMetastasis", "Sex"]
            if c in model.columns]
    p = INTERIM / "model.parquet"; model[keep].to_parquet(p); out["model"] = p

    # damaging mutations (LOF signal i), copy number (ii + confounder), expression (iii + confounder)
    dmg = _load_matrix("OmicsSomaticMutationsMatrixDamaging.csv")
    p = INTERIM / "damaging.parquet"; dmg.to_parquet(p); out["damaging"] = p

    cn = _load_matrix("OmicsCNGene.csv")
    p = INTERIM / "cn.parquet"; cn.to_parquet(p); out["cn"] = p

    expr = _load_matrix("OmicsExpressionProteinCodingGenesTPMLogp1.csv")
    p = INTERIM / "expression.parquet"; expr.to_parquet(p); out["expression"] = p

    _assert_harmonized(chronos, model, dmg, cn, expr)
    print(f"harmonize OK: chronos{chronos.shape} model{model[keep].shape} "
          f"dmg{dmg.shape} cn{cn.shape} expr{expr.shape}")
    return out


def _assert_harmonized(chronos, model, dmg, cn, expr) -> None:
    # ingestion asserts: shapes sane, well-known genes present, index type correct
    assert chronos.shape[0] > 800 and chronos.shape[1] > 15000, f"chronos shape off: {chronos.shape}"
    for g in ["KRAS", "BRCA1", "EGFR", "PTEN", "RB1"]:
        assert g in chronos.columns, f"{g} missing from Chronos"
    assert all(str(i).startswith("ACH-") for i in chronos.index[:20]), "ModelID index malformed"
    assert LINEAGE_COL in model.columns, "lineage column missing"
    # Chronos orientation sanity: common essentials (e.g. RPL/RPS) should be strongly negative
    ess = [g for g in ["RPL3", "POLR2A", "RPS19"] if g in chronos.columns]
    if ess:
        assert chronos[ess].median().median() < -0.5, "Chronos orientation looks wrong (essentials not negative)"


class DepMap:
    """Lazy accessor over the harmonized parquet tables (loaded once, cached)."""

    def __init__(self):
        self._cache: dict[str, pd.DataFrame] = {}

    def _get(self, name: str) -> pd.DataFrame:
        if name not in self._cache:
            self._cache[name] = pd.read_parquet(INTERIM / f"{name}.parquet")
        return self._cache[name]

    @property
    def chronos(self) -> pd.DataFrame: return self._get("chronos")
    @property
    def model(self) -> pd.DataFrame: return self._get("model")
    @property
    def damaging(self) -> pd.DataFrame: return self._get("damaging")
    @property
    def cn(self) -> pd.DataFrame: return self._get("cn")
    @property
    def expression(self) -> pd.DataFrame: return self._get("expression")

    def lof_call(self, gene: str) -> pd.Series:
        """Generic operational LOF call for `gene`: bool Series over ModelIDs (True = LOF line).

        OR of: damaging mutation, deep deletion, expression silencing. Lines lacking the data needed
        for every branch are still callable (a branch with missing data contributes False, not NaN).
        """
        idx = self.chronos.index
        dmg = self.damaging[gene].reindex(idx) if gene in self.damaging.columns else pd.Series(0.0, idx)
        cn = self.cn[gene].reindex(idx) if gene in self.cn.columns else pd.Series(np.nan, idx)
        ex = self.expression[gene].reindex(idx) if gene in self.expression.columns else pd.Series(np.nan, idx)

        mut = dmg.fillna(0) > 0
        deldel = cn < CN_DEL_THRESH               # NaN < x -> False (safe)
        thr = np.nanpercentile(ex, EXPR_LOF_PCTL) if ex.notna().any() else -np.inf
        silenced = ex < thr
        return (mut | deldel.fillna(False) | silenced.fillna(False)).astype(bool)

    def lof_frame(self, gene: str) -> pd.DataFrame:
        """LOF call joined with lineage — the stratification table the executor consumes."""
        lof = self.lof_call(gene).rename("lof")
        lin = self.model[LINEAGE_COL].reindex(lof.index).rename("lineage")
        return pd.concat([lof, lin], axis=1)


def run(sanity_genes: tuple[str, ...] = ("KRAS", "BRCA1")) -> dict[str, Path]:
    print("== DEPMAP HARMONIZE ==")
    paths = harmonize()
    # materialize a couple of LOF calls as a sanity check
    dm = DepMap()
    for g in sanity_genes:
        f = dm.lof_frame(g)
        n = int(f["lof"].sum())
        print(f"  {g}-LOF lines: {n}/{len(f)} ({100*n/len(f):.1f}%)  "
              f"top lineages: {f[f.lof].lineage.value_counts().head(3).to_dict()}")
    return paths


if __name__ == "__main__":
    run()
