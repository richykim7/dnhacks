"""geoharmonize — robust gene-expression loading + harmonization for GEO series.

STANDALONE (no dnhacksbio import): supplied on the host experiment PYTHONPATH, so code can
`import geoharmonize as gh`. Dependencies come from the experiments extra.

Different GEO platform records name the symbol column differently ("Gene Symbol", "GENE_SYMBOL",
"gene_assignment", "ILMN_Gene", ...), pack several genes per probe ("MYC /// LOC391875"), bury symbols
inside Affymetrix `gene_assignment` fields ("NM_001706 // BCL6 // ... // 604"), and drift in case/alias.
This module builds the symbol->probe index once, so two cohorts yield the same genes.

What it will not do (these decisions are the caller's):
  * It does not silently make cohorts comparable. It reports each matrix's value range and flags when two
    matrices are on different scales (e.g. one log2 in [0,18], one unit-normalized in [0,1]); pooling those
    without harmonization is invalid. Use compare_scales([...]).
  * It does not impute or drop samples, and raises on a genuinely missing gene unless you ask for NaN.
  * A regulator's mRNA is a poor proxy for its activity; score a target program with `signature()` and
    partial known covariates (proliferation, sex, cohort subtype) out before attributing a correlation
    to mechanism. See SIGNATURES and the SKILL.

Typical use:
    import geoharmonize as gh
    ds = gh.load("GSE12345", destdir="/cache")     # download+parse (cached in /cache), log2 auto-applied
    print(ds.report())                             # what got loaded / guessed / missed
    g    = ds.gene("MYC")                         # 1 value/sample, MaxMean probe (cross-study robust)
    mat  = ds.genes(["MYC","CDK1"], z=True)      # genes x samples, z-scored
    act  = ds.signature(["MKI67", "TOP2A", "CDK1"], method="singscore")   # any gene set, cohort-independent
    prolif = ds.signature(gh.SIGNATURES["PROLIFERATION"])                  # confounder to partial out
    sex  = ds.infer_sex()                                                   # expression-inferred sex per sample
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

# ------------------------------------------------------------------------------------------------------
# Generic covariate gene sets. Pass your own list to `signature()` for a pathway or target program.
# ------------------------------------------------------------------------------------------------------
SIGNATURES: dict[str, list[str]] = {
    # Proliferation metagene (Rosenwald/Whitfield core). Partial this out before attributing a
    # correlation to a specific regulator, or you double-count growth. MKI67 alone is too noisy.
    "PROLIFERATION": ["MKI67", "PCNA", "TOP2A", "CCNB1", "CCNB2", "CDK1", "CDC20", "CKS1B", "CKS2", "BUB1",
                      "BUB1B", "AURKA", "AURKB", "RRM1", "RRM2", "TYMS", "TK1", "MCM2", "MCM3", "MCM4",
                      "MCM6", "MCM7", "E2F1", "FOXM1", "UBE2C", "BIRC5", "KIF11", "ASPM", "NUSAP1", "TPX2",
                      "MELK", "CENPF", "CENPE", "PLK1"],
    # Sex-QC: verify recorded sex against expression (catches sample swaps).
    "SEX_Y": ["RPS4Y1", "DDX3Y", "KDM5D", "UTY", "EIF1AY", "NLGN4Y"],
    "SEX_XIST": ["XIST"],
}

# Annotation columns that hold a gene SYMBOL, most-specific first (matched case-insensitively, punctuation-
# insensitive). `gene_assignment` is handled specially (two-level parse) but listed so it's detected.
_SYMBOL_COL_HINTS = ("gene symbol", "gene_symbol", "genesymbol", "symbol", "gene name", "gene_name",
                     "ilmn_gene", "gene_assignment", "gene assignment", "orf", "gene", "genes")
_MULTI_SPLIT = re.compile(r"\s*(?:///|//|[|,;])\s*")   # record/field/misc delimiters
_SYMBOLish = re.compile(r"^[A-Z][A-Z0-9\-]{0,9}$")     # a token that looks like a gene symbol (UPPER)
_ACCESSION = re.compile(r"^(NM_|NR_|XM_|XR_|NP_|XP_|ENSG|ENST|GI:|LOC\d)")
# Excel date-corruption of gene symbols (SEPT1->"1-Sep", MARCH1->"1-Mar", DEC1->"1-Dec"): detect + repair.
_MONTHS = {"jan": "", "feb": "", "mar": "MARCH", "apr": "", "may": "", "jun": "", "jul": "", "aug": "",
           "sep": "SEPT", "oct": "", "nov": "", "dec": "DEC"}
_EXCEL_DATE = re.compile(r"^(\d{1,2})[-/](jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
                         r"(?:[-/]\d{2,4})?$|^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[-/](\d{1,2})$",
                         re.I)
# HGNC symbol renamings (treated as equivalent in both directions).
_RENAMES_2020 = {"SEPT": "SEPTIN", "MARCH": "MARCHF", "MARC": "MTARC", "DEC1": "DELEC1"}
# Small curated alias table (upper case). Only unambiguous, safe aliases: a symbol that is itself another
# gene's approved symbol (e.g. FBXO11's old alias "PRMT9", since PRMT9 is a distinct gene) is excluded,
# and the resolver additionally refuses any alias that collides with an approved symbol present
# in the platform (ambiguity guard).
_ALIASES = {
    "MYC": ("C-MYC", "CMYC", "MYCC"),
    "MKI67": ("KIA", "MIB1"),
    "CDK1": ("CDC2", "CDC28A"),
}


def _norm(s) -> str:
    return re.sub(r"\s+", " ", str(s)).strip().lower()


def _repair_symbol(tok: str) -> str:
    """Repair an Excel-date-corrupted symbol ('1-Sep'->'SEPT1'); else return tok unchanged (UPPER)."""
    m = _EXCEL_DATE.match(tok)
    if not m:
        return tok.upper()
    if m.group(1) and m.group(2):        # "1-Sep"
        n, mon = m.group(1), m.group(2).lower()
    else:                                 # "Sep-1"
        mon, n = m.group(3).lower(), m.group(4)
    fam = _MONTHS.get(mon, "")
    return f"{fam}{n}" if fam else tok.upper()


def _rename_equivalents(sym: str) -> set[str]:
    """old<->new HGNC-2020 equivalents for a symbol (e.g. SEPT9 <-> SEPTIN9), so a query hits older
    annotations and vice-versa."""
    out = {sym}
    for old, new in _RENAMES_2020.items():
        if sym.startswith(new):
            out.add(old + sym[len(new):])
        if sym.startswith(old) and sym != old:
            out.add(new + sym[len(old):])
        if sym == old.rstrip("1") or sym == old:
            out.add(_RENAMES_2020.get(old, sym))
    return out


def _explode_symbols(cell: str, gene_assignment: bool) -> list[str]:
    """All gene symbols named in one annotation cell, UPPER, Excel-repaired. gene_assignment cells are
    'accession // SYMBOL // description // band // entrez /// ...': split on '///' (records) then ' // '
    (fields) and take field index 1 (the symbol) — so description words aren't indexed as fake symbols."""
    out: list[str] = []
    if gene_assignment and ("//" in cell):
        for record in re.split(r"\s*///\s*", str(cell)):
            fields = re.split(r"\s*//\s*", record)
            if len(fields) >= 2:
                s = _repair_symbol(fields[1].strip())
                if _SYMBOLish.match(s) and not _ACCESSION.match(s):
                    out.append(s)
        return out
    for tok in _MULTI_SPLIT.split(str(cell)):
        t = tok.strip()
        if not t:
            continue
        s = _repair_symbol(t)
        if _SYMBOLish.match(s) and not _ACCESSION.match(s) and s not in ("---", "NA", "NAN"):
            out.append(s)
    return out


def _pick_symbol_column(table: pd.DataFrame) -> str | None:
    """Choose the annotation column most likely to be gene symbols: among columns whose (punctuation-
    stripped) name matches a hint, take the one with the most symbol-shaped values. Prefer a dedicated
    symbol column over gene_assignment."""
    def key(name: str) -> str:
        return re.sub(r"[^a-z0-9]", "", _norm(name))
    hint_keys = {re.sub(r"[^a-z0-9]", "", h): rank for rank, h in enumerate(_SYMBOL_COL_HINTS)}
    cands = []
    for c in table.columns:
        r = hint_keys.get(key(c))
        if r is not None:
            cands.append((r, c))
        elif "symbol" in key(c):
            cands.append((len(_SYMBOL_COL_HINTS), c))
    if not cands:
        return None

    def symbol_hits(col: str) -> int:
        ga = "assignment" in key(col)
        vals = table[col].dropna().astype(str).head(3000)
        return int(sum(1 for v in vals if _explode_symbols(v, ga)))
    cands.sort(key=lambda rc: (rc[0], -symbol_hits(rc[1])))
    best = cands[0][1]
    return best if symbol_hits(best) > 0 else None


# ------------------------------------------------------------------------------------------------------
class Dataset:
    """One GEO series, harmonized: a probes x samples matrix, a symbol->probes index, sample metadata."""

    def __init__(self, accession, expr, sym_to_probes, approved, meta, symbol_col, raw_char, notes, log2ed):
        self.accession = accession
        self.expr = expr                       # probes (index, str) x samples (cols), float
        self._sym = sym_to_probes              # UPPER symbol -> [probe ids present in expr]
        self._approved = approved              # set of UPPER symbols present as approved (for the guard)
        self.meta = meta                       # samples x characteristic fields
        self._raw = raw_char                   # samples -> full concatenated characteristics text
        self.symbol_col = symbol_col
        self.notes = list(notes)
        self.log2_applied = log2ed
        self.value_range = (float(np.nanmin(expr.values)), float(np.nanmax(expr.values)))

    # --- gene access ------------------------------------------------------------------------------
    def _probes_for(self, gene: str) -> list[str]:
        g = gene.strip().upper()
        # 1) exact / 2020-rename equivalents
        for cand in _rename_equivalents(g):
            if cand in self._sym:
                return self._sym[cand]
        # 3) curated aliases, with an ambiguity guard: skip an alias that is itself an approved symbol here
        for alias in _ALIASES.get(g, ()):
            a = alias.upper()
            if a in self._approved and a != g:
                continue                      # ambiguous: alias is another gene's approved symbol -> refuse
            if a in self._sym:
                return self._sym[a]
        return []

    def has_gene(self, gene: str) -> bool:
        return len(self._probes_for(gene)) > 0

    def gene(self, gene: str, *, collapse: str = "maxmean", z: bool = False,
             missing: str = "raise") -> np.ndarray | None:
        """One value per sample for `gene`. collapse combines multiple probes:
          'maxmean' (default) = the single highest-MEAN-expression probe — most reproducible across studies
                                (Miller 2011 collapseRows benchmark); 'maxvar' = highest-variance probe;
                                'mean'/'median' = average across probes.
        z=True standardizes across samples (nan-aware). missing='raise' | 'nan' | 'none'."""
        probes = self._probes_for(gene)
        if not probes:
            if missing == "nan":
                return np.full(self.expr.shape[1], np.nan)
            if missing == "none":
                return None
            raise KeyError(f"[geoharmonize] gene {gene!r} not found in {self.accession} "
                           f"(symbol col={self.symbol_col!r}; {len(self._sym)} symbols indexed). "
                           f"Try ds.search({gene!r}).")
        sub = self.expr.loc[probes].astype(float)
        if collapse == "maxmean":
            vec = sub.loc[sub.mean(axis=1, skipna=True).idxmax()].to_numpy(float)
        elif collapse == "maxvar":
            vec = sub.loc[sub.var(axis=1, skipna=True).idxmax()].to_numpy(float)
        elif collapse in ("mean", "median"):
            vec = (sub.mean(axis=0) if collapse == "mean" else sub.median(axis=0)).to_numpy(float)
        else:
            raise ValueError("collapse must be 'maxmean', 'maxvar', 'mean', or 'median'")
        return _zscore(vec) if z else vec

    def genes(self, genes, *, collapse: str = "maxmean", z: bool = False,
              missing: str = "nan") -> pd.DataFrame:
        """genes x samples DataFrame (default missing='nan' so one absent gene doesn't abort the batch;
        missing genes are noted and appear as all-NaN rows)."""
        rows, idx, miss = [], [], []
        for g in genes:
            v = self.gene(g, collapse=collapse, z=z, missing="none")
            if v is None:
                miss.append(g)
                if missing == "raise":
                    raise KeyError(f"[geoharmonize] gene {g!r} not found in {self.accession}")
                v = np.full(self.expr.shape[1], np.nan)
            rows.append(v); idx.append(g)
        if miss:
            self.notes.append(f"genes(): {len(miss)}/{len(list(genes))} missing: {miss}")
        return pd.DataFrame(rows, index=idx, columns=self.expr.columns)

    def signature(self, genes, *, method: str = "singscore", min_frac: float = 0.5) -> np.ndarray:
        """Per-sample signature score for a gene set.
          method='singscore' (default): rank-based and COHORT-INDEPENDENT — a sample's score does not depend
              on the other samples in the matrix, so it is stable across cohorts (Foroutan 2018). This is the
              right default when you compare signatures across GEO series.
          method='meanz': mean of z-scored member genes — simple and transparent, but COHORT-DEPENDENT
              (z uses this matrix's mean/sd), so scores are not comparable across separately-loaded cohorts.
        Raises if fewer than min_frac of the set maps (won't score off a couple of probes)."""
        present = [g for g in genes if self.has_gene(g)]
        if len(present) < max(1, int(min_frac * len(list(genes)))):
            raise ValueError(f"[geoharmonize] signature: only {len(present)}/{len(list(genes))} genes map "
                             f"in {self.accession} (< {min_frac:.0%}); refusing to score off too few genes.")
        if method == "meanz":
            mat = self.genes(present, z=True, missing="nan").to_numpy(float)
            return np.nanmean(mat, axis=0)
        if method == "singscore":
            # rank every probe within each sample; take each signature gene's MaxMean-probe percentile;
            # average across the set. Background = all probes -> independent of sample composition.
            ranks = self.expr.rank(axis=0, pct=True)          # probes x samples, in (0,1] per column
            pr = [self._probes_for(g) for g in present]
            best = [self.expr.loc[p].mean(axis=1).idxmax() for p in pr if p]
            return ranks.loc[best].to_numpy(float).mean(axis=0) - 0.5   # center at 0
        raise ValueError("method must be 'singscore' or 'meanz'")

    def search(self, substr: str) -> list[str]:
        s = substr.upper()
        return sorted(k for k in self._sym if s in k)

    # --- sample metadata / covariates -------------------------------------------------------------
    def infer_sex(self) -> pd.Series:
        """Predicted sex per sample from Y-gene expression vs XIST ('male'/'female'). Use to verify a
        recorded Gender field and catch sample swaps."""
        y = self.signature(SIGNATURES["SEX_Y"], method="meanz", min_frac=0.3)
        xist = self.gene("XIST", missing="nan")
        xist = _zscore(xist) if not np.all(np.isnan(xist)) else np.zeros_like(y)
        return pd.Series(np.where(y - xist > 0, "male", "female"), index=self.expr.columns)

    # --- introspection ----------------------------------------------------------------------------
    def report(self) -> str:
        lo, hi = self.value_range
        lines = [f"[geoharmonize] {self.accession}: {self.expr.shape[0]} probes x {self.expr.shape[1]} "
                 f"samples; {len(self._sym)} symbols indexed (col={self.symbol_col!r}); "
                 f"value range {lo:.2f}..{hi:.2f}"
                 + (" (log2 applied)" if self.log2_applied else " (left as-is)") + "."]
        lines += [f"  note: {n}" for n in self.notes]
        return "\n".join(lines)


# --- scoring helpers -----------------------------------------------------------------------------
def _zscore(v) -> np.ndarray:
    v = np.asarray(v, dtype=float)
    sd = np.nanstd(v)
    return (v - np.nanmean(v)) / sd if sd > 0 else v - np.nanmean(v)


def _needs_log2(expr: pd.DataFrame) -> bool:
    """GEO2R's log-space rule: values are linear (need log2) if the 99th pct > 100, or the full range > 50
    with a positive 25th pct. Microarray already-log values sit in ~[0,20]; linear intensities reach 1e3-1e5.
    Data already in [0,1] or [0,~20] is left alone."""
    x = expr.to_numpy(float)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return False
    q = np.percentile(x, [0, 25, 50, 75, 99, 100])
    return bool((q[4] > 100) or (q[5] - q[0] > 50 and q[1] > 0))


def _looks_normalized_unit(expr: pd.DataFrame) -> bool:
    hi = float(np.nanmax(expr.values))
    return hi <= 1.5   # values squeezed into ~[0,1] — a rank/quantile normalization, not raw intensity


# --- metadata parsing ----------------------------------------------------------------------------
def _meta_from_gsms(gse):
    """Return (meta_df, raw_series). meta_df is samples x characteristic fields; raw_series is the FULL
    concatenation of every characteristics_ch1 string per sample."""
    recs, raws = {}, {}
    for name, gsm in gse.gsms.items():
        md = gsm.metadata
        chars = md.get("characteristics_ch1", []) or []
        row = {}
        for i, item in enumerate(chars):
            if ":" in item:
                k, v = item.split(":", 1)
                key = _norm(k)
                if key in row:            # same key repeats -> don't overwrite; disambiguate
                    key = f"{key}#{i}"
                row[key] = v.strip()
            else:
                row[f"char#{i}"] = item.strip()
        title = md.get("title", [""])
        row["title"] = title[0] if title else ""
        recs[name] = row
        raws[name] = " | ".join(list(chars) + [row["title"]])
    return pd.DataFrame.from_dict(recs, orient="index"), pd.Series(raws)


def _build_symbol_index(gpl_table, symbol_col, probes_present):
    """symbol(UPPER) -> [probe ids present in the matrix], plus the set of approved symbols (for the
    ambiguity guard). Built from the platform annotation."""
    if gpl_table is None or gpl_table.empty or symbol_col is None:
        return {}, set()
    id_col = "ID" if "ID" in gpl_table.columns else gpl_table.columns[0]
    ga = "assignment" in re.sub(r"[^a-z0-9]", "", _norm(symbol_col))
    idx: dict[str, list[str]] = {}
    approved: set[str] = set()
    for pid, cell in zip(gpl_table[id_col].astype(str), gpl_table[symbol_col].astype(str)):
        if pid not in probes_present:
            continue
        syms = _explode_symbols(cell, ga)
        # for a plain symbol column, a single-symbol cell is an approved symbol; multi-gene probes and
        # gene_assignment records are not treated as canonical approvals
        if not ga and len(syms) == 1:
            approved.add(syms[0])
        for s in syms:
            idx.setdefault(s, []).append(pid)
    return idx, approved


# --- loading -------------------------------------------------------------------------------------
def load(accession: str, *, destdir: str = "/cache", platform: str | None = None,
         value_col: str = "VALUE", log2: str = "auto") -> Dataset:
    """Download+parse a GEO series and return a harmonized Dataset. `destdir` is the persistent sandbox
    cache (/cache) so a cohort is fetched once. Multi-platform series: the platform carrying the most
    samples is used unless `platform` (a GPL id) is given. log2: 'auto' applies log2 iff the GEO2R rule
    says the values are linear (never on already-log or unit-normalized data); 'never' leaves values as-is.
    Raises with a clear message if the matrix can't be built or the probe-id join is empty."""
    import GEOparse
    try:
        gse = GEOparse.get_GEO(geo=accession, destdir=destdir, silent=True)
    except (EOFError, OSError) as e:
        import glob
        import os
        for f in glob.glob(os.path.join(destdir, f"{accession}*")):
            try:
                os.remove(f)
            except OSError:
                pass
        gse = GEOparse.get_GEO(geo=accession, destdir=destdir, silent=True)
        _ = e
    if not gse.gsms:
        raise ValueError(f"[geoharmonize] {accession}: no samples (GSMs) parsed")
    notes: list[str] = []

    gpls = gse.gpls
    if platform and platform in gpls:
        gpl = gpls[platform]
    elif len(gpls) == 1:
        gpl = next(iter(gpls.values()))
    else:
        counts = {gid: sum(1 for g in gse.gsms.values()
                           if g.metadata.get("platform_id", [None])[0] == gid) for gid in gpls}
        gid = max(counts, key=counts.get)
        gpl = gpls[gid]
        notes.append(f"multi-platform {list(gpls)}; used {gid} ({counts[gid]} samples)")

    try:
        expr = gse.pivot_samples(value_col)
    except Exception as e:
        raise ValueError(f"[geoharmonize] {accession}: could not pivot '{value_col}': {e}")
    if len(gpls) > 1:
        keep = [n for n, g in gse.gsms.items()
                if g.metadata.get("platform_id", [None])[0] == gpl.name and n in expr.columns]
        if keep:
            expr = expr[keep]
    expr = expr.apply(pd.to_numeric, errors="coerce")
    expr.index = expr.index.astype(str)
    # duplicate probe ids (some deposits repeat ID_REF) -> aggregate by median so downstream .loc is 1:1
    if expr.index.has_duplicates:
        n_dup = int(expr.index.duplicated().sum())
        expr = expr.groupby(level=0).median()
        notes.append(f"{n_dup} duplicate probe ids aggregated by median")

    sym_col = _pick_symbol_column(getattr(gpl, "table", None)) if getattr(gpl, "table", None) is not None \
        else None
    sym_to_probes, approved = _build_symbol_index(getattr(gpl, "table", None), sym_col,
                                                  set(expr.index))
    if not sym_to_probes:
        cols = list(getattr(gpl, "table", pd.DataFrame()).columns)
        raise ValueError(f"[geoharmonize] {accession}: could not build a symbol->probe map "
                         f"(symbol col={sym_col!r}; platform columns={cols}). Either no symbol column, or "
                         f"the probe-id join was empty (VALUE table keyed on a different id than the "
                         f"platform). Inspect gpl.table and pass value_col/platform explicitly.")

    # log-space handling (values reported either way; we transform only when the rule is confident)
    log2ed = False
    if log2 == "auto" and not _looks_normalized_unit(expr) and _needs_log2(expr):
        x = expr.to_numpy(float)
        x[x <= 0] = np.nan                      # floor non-positives, then log2 (not log2(x+1))
        expr = pd.DataFrame(np.log2(x), index=expr.index, columns=expr.columns)
        log2ed = True
        notes.append("values looked LINEAR (GEO2R rule) -> applied log2")
    elif _looks_normalized_unit(expr):
        notes.append("values in ~[0,1] (rank/quantile-normalized), not comparable in absolute terms to a "
                     "log2 cohort; do not pool without harmonizing. See compare_scales().")

    meta, raw = _meta_from_gsms(gse)
    return Dataset(accession, expr, sym_to_probes, approved, meta, sym_col, raw, notes, log2ed)


def compare_scales(datasets) -> str:
    """Are these loaded Datasets on a comparable value scale? Reports each range and warns when they differ
    enough that pooling/absolute comparison is invalid. It does not fix them: cross-cohort harmonization
    (within-cohort normalize, then ComBat with subtype+sex as PROTECTED covariates) is a deliberate,
    opt-in step."""
    lines, ranges = [], []
    for ds in datasets:
        lo, hi = ds.value_range
        ranges.append((hi - lo, ds.log2_applied))
        lines.append(f"  {ds.accession}: range {lo:.2f}..{hi:.2f}"
                     + (" (log2)" if ds.log2_applied else ""))
    spans = [s for s, _ in ranges]
    incompatible = max(spans) > 3 * max(min(spans), 1e-6)
    head = ("Incompatible scales; do not pool or compare absolute values without harmonizing:"
            if incompatible else "scales look broadly comparable (still prefer rank-based/within-cohort "
            "analyses):")
    return "[geoharmonize.compare_scales] " + head + "\n" + "\n".join(lines)


__all__ = ["load", "Dataset", "compare_scales", "SIGNATURES"]
