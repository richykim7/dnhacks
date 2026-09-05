"""Dataset discovery: the analog of litmap.find for data rather than papers. Searches the major public
repositories' documented APIs and returns candidate datasets with enough metadata for the explorer to
choose one, plus a download hint. It does not download or parse anything; the download, inspection and
parsing happen in the agent's own sandbox experiment code, which has network and a persistent /cache.
This module provides access and the agent provides format handling.

Covered now: NCBI GEO (gene-expression / series), EBI BioStudies·ArrayExpress (functional genomics).
Extend by adding a search_<repo> that returns the same dict shape and wiring it into search_datasets.
"""
from __future__ import annotations

import re
import time

import requests

UA = {"User-Agent": "explorer-datasets/0.1 (research)"}
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
BIOSTUDIES = "https://www.ebi.ac.uk/biostudies/api/v1/search"


def _norm(d: dict) -> dict:
    """The common candidate shape every repo search returns."""
    return {"repo": d.get("repo", ""), "accession": d.get("accession", ""), "title": d.get("title", ""),
            "summary": (d.get("summary", "") or "")[:400], "organism": d.get("organism", ""),
            "n_samples": d.get("n_samples", ""), "type": d.get("type", ""), "url": d.get("url", "")}


# ----- NCBI GEO (E-utilities: esearch db=gds -> esummary) -----------------------------------------
def _geo_ids(term: str, limit: int) -> list[str]:
    try:
        return requests.get(f"{EUTILS}/esearch.fcgi", headers=UA, timeout=25, params={
            "db": "gds", "term": term, "retmax": limit, "retmode": "json"}).json(
            ).get("esearchresult", {}).get("idlist", [])
    except Exception:
        return []


_STOP = {"expression", "profiling", "profile", "gene", "genes", "data", "dataset", "datasets", "cell",
         "cells", "analysis", "study", "sequencing", "seq", "rna", "single", "human", "mouse", "and",
         "the", "of", "in", "by", "with", "for", "from"}
# Upper-case tokens that look like gene symbols but are assay or technique words; never treat as genes
_NONGENE = {"RNA", "DNA", "SEQ", "PCR", "QPCR", "CHIP", "ATAC", "WGS", "WES", "CNV", "SNP", "GWAS",
            "CRISPR", "FACS", "SCRNA", "RNA-SEQ", "SC-RNA", "CHIP-SEQ", "ATAC-SEQ", "CUT-RUN"}


def _salient_terms(query: str) -> list[str]:
    """Rank a query's terms for GEO: gene-symbol-like tokens first (the specific anchors), then remaining
    content words longest first, dropping generic stopwords. GEO ANDs terms and only date-sorts, so a
    short, specific AND query is what returns on-topic hits."""
    terms = list(dict.fromkeys(re.findall(r"[A-Za-z0-9][A-Za-z0-9\-]{1,}", query)))
    genelike = [t for t in terms if re.fullmatch(r"[A-Z0-9][A-Z0-9\-]{1,6}", t)
                and t.upper() not in _NONGENE]
    rest = sorted((t for t in terms if t not in genelike and t.lower() not in _STOP
                   and t.upper() not in _NONGENE), key=len, reverse=True)
    return genelike + rest


_GENE_RX = re.compile(r"[A-Z0-9][A-Z0-9\-]{1,6}$")


def search_geo(query: str, limit: int = 8) -> list[dict]:
    """Search GEO DataSets/Series. Returns curated GDS + user GSE records with sample counts + FTP link.
    When the full query misses, relax to a few specific two-term AND combinations
    (gene+disease, then gene+gene). Calls are throttled to respect NCBI's 3/sec unauthenticated limit."""
    sal = _salient_terms(query)
    genes = [t for t in sal if _GENE_RX.fullmatch(t)]
    other = [t for t in sal if t not in genes]
    cands = [query]
    if genes and other:
        cands.append(f"{genes[0]} AND {other[0]}")
    if len(genes) >= 2:
        cands.append(f"{genes[0]} AND {genes[1]}")
    if len(other) >= 2:
        cands.append(f"{other[0]} AND {other[1]}")
    ids: list[str] = []
    for i, c in enumerate(dict.fromkeys(cands)):
        if i:
            time.sleep(0.34)                       # NCBI: 3 req/s without an api_key
        ids = _geo_ids(c, limit)
        if ids:
            break
    if not ids:
        return []
    try:
        res = requests.get(f"{EUTILS}/esummary.fcgi", headers=UA, timeout=25, params={
            "db": "gds", "id": ",".join(ids), "retmode": "json"}).json().get("result", {})
    except Exception:
        return []
    out = []
    for uid in res.get("uids", []):
        r = res.get(uid, {})
        acc = r.get("accession", "")
        ftp = r.get("ftplink", "")
        # Point at the matrix directory, not a single file: multi-platform series have per-platform
        # filenames (GSExxxx-GPLyyyy_series_matrix.txt.gz).
        # GEOparse.get_GEO(acc), pre-installed in the sandbox, resolves the right file.
        url = (f"{ftp}matrix/" if ftp and acc.startswith("GSE") else ftp)
        out.append(_norm({"repo": "GEO", "accession": acc, "title": r.get("title", ""),
                          "summary": r.get("summary", ""), "organism": r.get("taxon", ""),
                          "n_samples": r.get("n_samples", ""),
                          "type": r.get("gdstype", "") or r.get("entrytype", ""), "url": url}))
    return out


# ----- EBI BioStudies · ArrayExpress --------------------------------------------------------------
def search_arrayexpress(query: str, limit: int = 6) -> list[dict]:
    """Search the ArrayExpress collection in BioStudies (functional-genomics experiments)."""
    try:
        hits = requests.get(BIOSTUDIES, headers=UA, timeout=25, params={
            "query": query, "type": "study", "collection": "arrayexpress",
            "pageSize": limit}).json().get("hits", [])
    except Exception:
        return []
    out = []
    for h in hits[:limit]:
        acc = h.get("accession", "")
        out.append(_norm({"repo": "ArrayExpress", "accession": acc, "title": h.get("title", ""),
                          "summary": h.get("abstract", "") or "", "organism": h.get("organism", ""),
                          "type": h.get("type", "study"),
                          "url": f"https://www.ebi.ac.uk/biostudies/arrayexpress/studies/{acc}" if acc else ""}))
    return out


def search_datasets(query: str, limit: int = 8) -> list[dict]:
    """Fan out across repositories; return a merged, de-duplicated candidate list. Each repo failure is
    swallowed so one being down never blocks the others."""
    out: list[dict] = []
    for fn in (search_geo, search_arrayexpress):
        try:
            out += fn(query, limit=limit)
        except Exception:
            pass
        time.sleep(0.1)
    seen, uniq = set(), []
    for d in out:
        k = (d["repo"], d["accession"])
        if d["accession"] and k not in seen:
            seen.add(k); uniq.append(d)
    return uniq[: limit * 2]
