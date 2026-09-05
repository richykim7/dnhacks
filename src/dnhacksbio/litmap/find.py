"""Literature discovery and open-access full text.

Each Europe PMC query is an independent capture channel; candidates are deduplicated across channels,
which also feeds a capture-recapture estimate of how complete the search is. Full text is fetched
open-access only (Europe PMC, PMC, Unpaywall), never scraped from paywalls, with the licence recorded
per article.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import requests

POLITE_EMAIL = "research@example.org"
UA = {"User-Agent": f"dnhacksbio/0.1 (mailto:{POLITE_EMAIL})"}
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
IDCONV = "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/"


@dataclass
class Candidate:
    key: str                    # canonical id (DOI preferred, else "PMID:x" / "PMC:x")
    doi: str = ""
    pmid: str = ""
    pmcid: str = ""
    title: str = ""
    abstract: str = ""
    year: int | None = None
    is_oa: bool = False
    channels: set = field(default_factory=set)   # which discovery channels found it (capture-recapture)
    score: float = 0.0          # relevance score


def _cand_key(doi: str, pmid: str, pmcid: str) -> str:
    if doi:
        return doi.lower().strip()
    if pmid:
        return f"PMID:{pmid}"
    return f"PMC:{pmcid}" if pmcid else ""


# ----- Channel A: Europe PMC tight-query search ---------------------------------------------------
def europepmc_search(query: str, max_results: int = 400, channel: str = "epmc") -> list[Candidate]:
    """Paginated Europe PMC search (cursorMark). Returns candidates with title+abstract+OA flag."""
    out: list[Candidate] = []
    cursor = "*"
    while len(out) < max_results:
        params = {"query": query, "format": "json", "pageSize": 100, "cursorMark": cursor,
                  "resultType": "core"}
        try:
            r = requests.get(EPMC, params=params, headers=UA, timeout=30)
            data = r.json()
        except Exception:
            break
        results = data.get("resultList", {}).get("result", [])
        if not results:
            break
        for d in results:
            doi = (d.get("doi") or "").strip()
            pmid = str(d.get("pmid") or "")
            pmcid = str(d.get("pmcid") or "")
            key = _cand_key(doi, pmid, pmcid)
            if not key:
                continue
            out.append(Candidate(
                key=key, doi=doi, pmid=pmid, pmcid=pmcid,
                title=d.get("title", ""), abstract=d.get("abstractText", ""),
                year=int(d["pubYear"]) if str(d.get("pubYear", "")).isdigit() else None,
                is_oa=(d.get("isOpenAccess") == "Y"), channels={channel}))
        nxt = data.get("nextCursorMark")
        if not nxt or nxt == cursor:
            break
        cursor = nxt
        time.sleep(0.2)
    return out[:max_results]


def dedup_candidates(cands: list[Candidate]) -> dict[str, Candidate]:
    """Merge candidates by key, unioning discovery channels (for capture-recapture)."""
    merged: dict[str, Candidate] = {}
    for c in cands:
        if c.key in merged:
            merged[c.key].channels |= c.channels
            if not merged[c.key].abstract and c.abstract:
                merged[c.key].abstract = c.abstract
        else:
            merged[c.key] = c
    return merged


import html as _html
import re as _re
import xml.etree.ElementTree as _ET

_TAG = _re.compile(r"<[^>]+>")


def _jats_to_text(xml: str) -> str:
    try:
        root = _ET.fromstring(xml)
        chunks = ["".join(el.itertext()) for tag in (".//article-title", ".//abstract", ".//body")
                  for el in root.findall(tag)]
        text = "\n\n".join(c for c in chunks if c.strip())
        if len(text.strip()) < 300:
            raise ValueError
    except Exception:
        text = _html.unescape(_TAG.sub(" ", xml))
    return _re.sub(r"[ \t]+\n", "\n", text).strip()


def _jats_license(xml: str) -> str:
    m = _re.search(r"<license[^>]*>(.*?)</license>", xml, _re.S)
    return _re.sub(r"\s+", " ", _TAG.sub(" ", m.group(1))).strip()[:60] if m else ""


def _pdf_bytes_to_text(data: bytes) -> str:
    try:
        import fitz
        with fitz.open(stream=data, filetype="pdf") as doc:
            return "\n".join(p.get_text("text") for p in doc)
    except Exception:
        return ""


def _resolve_pmcid(doi: str = "", pmid: str = "") -> str:
    """DOI/PMID -> PMCID via the NCBI ID Converter, the exact id map. Europe PMC's search record often
    omits the PMCID for papers outside its OA subset. Never resolve a PMCID by keyword search or an
    unrestricted elink."""
    for idv in (doi, pmid):
        if not idv:
            continue
        try:
            r = requests.get(IDCONV, params={"ids": idv, "format": "json", "tool": "litmap",
                             "email": POLITE_EMAIL}, headers=UA, timeout=25).json()
            for rec in r.get("records", []):
                if rec.get("pmcid"):
                    return rec["pmcid"]
        except Exception:
            pass
    return ""


def _pmc_html(pmc: str) -> str:
    """PMC article HTML as the last full-text route."""
    try:
        r = requests.get(f"https://pmc.ncbi.nlm.nih.gov/articles/{pmc}/", headers=UA, timeout=35)
        if r.status_code == 200 and len(r.text) > 3000:
            body = _re.sub(r"(?is)<(script|style|nav|header|footer)[^>]*>.*?</\1>", " ", r.text)
            return _re.sub(r"[ \t]{2,}", " ", _html.unescape(_TAG.sub(" ", body))).strip()
    except Exception:
        pass
    return ""


def _title_overlap(title: str, text: str) -> float:
    """Fraction of the expected title's tokens present in the head of the fetched text, used to verify
    a PMCID fetch is the right article. 1.0 when there is no title to check against."""
    it = set(_re.sub(r"[^a-z0-9]+", " ", (title or "").lower()).split())
    if not it:
        return 1.0
    tt = set(_re.sub(r"[^a-z0-9]+", " ", (text[:600] or "").lower()).split())
    return len(it & tt) / len(it)


def fetch_fulltext(cand: Candidate) -> dict:
    """{text, source, is_full_text, license, url}. Open-access routes only, in order: Europe PMC OA XML,
    NCBI PMC efetch, PMC article HTML, Unpaywall PDF, then the abstract. Every PMC-route fetch must pass
    a title-overlap check against the candidate."""
    pmcid = cand.pmcid or _resolve_pmcid(cand.doi, cand.pmid)
    pmc = (pmcid if pmcid.upper().startswith("PMC") else f"PMC{pmcid}") if pmcid else ""

    # 1) Europe PMC OA full-text XML
    if pmc and cand.is_oa:
        try:
            r = requests.get(f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmc}/fullTextXML",
                             headers=UA, timeout=30)
            if r.status_code == 200 and len(r.text) > 500:
                text = _jats_to_text(r.text)
                if len(text) > 800 and _title_overlap(cand.title, text) >= 0.5:
                    return {"text": text, "source": f"epmc-oa:{pmc}", "is_full_text": True,
                            "license": _jats_license(r.text) or "oa-subset", "url": pmc}
        except Exception:
            pass
    # 1b) NCBI PMC efetch: PMC is a superset of the Europe PMC OA subset. Require a real <body> so a
    #     front-matter-only record is not mistaken for full text.
    if pmc:
        try:
            r = requests.get(f"{EUTILS}/efetch.fcgi",
                             params={"db": "pmc", "id": pmc.replace("PMC", ""), "rettype": "full",
                                     "retmode": "xml", "email": POLITE_EMAIL}, headers=UA, timeout=35)
            if r.status_code == 200 and "<body" in r.text:
                text = _jats_to_text(r.text)
                if len(text) > 800 and _title_overlap(cand.title, text) >= 0.5:
                    return {"text": text, "source": f"pmc-efetch:{pmc}", "is_full_text": True,
                            "license": _jats_license(r.text) or "pmc", "url": pmc}
        except Exception:
            pass
    # 1c) PMC article HTML, title-verified like the rest
    if pmc:
        text = _pmc_html(pmc)
        if len(text) > 2500 and _title_overlap(cand.title, text) >= 0.5:
            return {"text": text, "source": f"pmc-html:{pmc}", "is_full_text": True,
                    "license": "pmc", "url": pmc}
    # 2) Unpaywall, best legal PDF (DOI-exact; a PDF's title is not reliably first, so no title guard)
    if cand.doi:
        try:
            up = requests.get(f"https://api.unpaywall.org/v2/{cand.doi}",
                              params={"email": POLITE_EMAIL}, headers=UA, timeout=30).json()
            if up.get("is_oa"):
                locs = [up.get("best_oa_location")] + (up.get("oa_locations") or [])
                pdf = next((L for L in locs if L and L.get("url_for_pdf")), None)
                if pdf:
                    doc = requests.get(pdf["url_for_pdf"], headers=UA, timeout=45)
                    if doc.status_code == 200 and len(doc.content) > 2000:
                        text = _pdf_bytes_to_text(doc.content)
                        if len(text) > 800:
                            lic = pdf.get("license") or (up.get("oa_status") == "bronze"
                                                         and "bronze-no-license") or "other-oa"
                            return {"text": text, "source": "unpaywall-pdf", "is_full_text": True,
                                    "license": lic, "url": pdf["url_for_pdf"]}
        except Exception:
            pass
    # 3) abstract-only fallback
    return {"text": f"{cand.title}. {cand.abstract}".strip(), "source": "abstract",
            "is_full_text": False, "license": "metadata-open", "url": ""}


# ----- Capture-recapture completeness (Chao2 incidence estimator) ---------------------------------
def estimate_completeness(channels_by_paper: dict[str, set]) -> dict:
    """Chao2 incidence estimate of the field size, a floor: correlated channels inflate overlap and bias
    the total down. Q1/Q2 are papers found by exactly one/two channels; small-sample corrected, with a
    log-normal 95% CI never below the observed count."""
    import math
    s_obs = len(channels_by_paper)
    counts = [len(ch) for ch in channels_by_paper.values()]
    q1 = sum(c == 1 for c in counts)
    q2 = sum(c == 2 for c in counts)
    t = len({c for chs in channels_by_paper.values() for c in chs})
    corr = (t - 1) / t if t else 1.0
    f0_bc = corr * q1 * (q1 - 1) / (2 * (q2 + 1))          # bias-corrected missing (defined at q2=0)
    if q2 > 0:
        f0 = corr * q1 * q1 / (2 * q2)
        r = q1 / q2
        var = q2 * (0.5 * r ** 2 + r ** 3 + 0.25 * r ** 4)
    else:
        f0, var = f0_bc, f0_bc
    s_hat = s_obs + f0
    if f0 > 0 and var > 0:
        k = math.exp(1.96 * math.sqrt(math.log(1 + var / f0 ** 2)))
        ci = (round(s_obs + f0 / k), round(s_obs + f0 * k))
    else:
        ci = (round(s_hat), round(s_hat))
    return {"observed": s_obs, "estimated_total": round(s_hat), "missing_est": round(f0),
            "completeness": round(s_obs / s_hat, 3) if s_hat else 1.0, "ci95": ci,
            "Q1": q1, "Q2": q2, "channels": t}
