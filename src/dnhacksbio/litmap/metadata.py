"""Verified paper identity: resolve DOI / PMID / title / year for a paper, and check the answer.

No LLM touches this path. Every field is either read out of the paper itself or fetched from an authority
(Crossref, NCBI) and then checked against the paper's own text before it is accepted. A record that cannot
be checked is returned unresolved, never guessed, because every downstream dedup, join and citation trusts
the metadata.

A title-overlap check is required even when a DOI is printed in the PDF: a paper's text also contains
the DOIs of everything in its reference list. The overlap check is what separates the two, the same guard
find.py uses on PMC fetches.

Resolution ladder, best evidence first:
  1. doi-in-front-matter  DOI printed in the paper's first pages -> Crossref -> title must overlap the
                          paper's own head text
  2. doi-anywhere         DOI found later in the text (weaker: could be a reference) -> same overlap gate
  3. title-search         Crossref bibliographic search on a title hint -> returned title must overlap
  4. UNRESOLVED           nothing cleared the gate; caller decides what to do (we do NOT invent an id)

  from dnhacksbio.litmap import metadata as M
  ident = M.resolve(text=paper_text, title_hint="Smith2018", year_hint=2018)
  if ident.verified: ...
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field, asdict

import requests

from dnhacksbio.litmap.find import EUTILS, POLITE_EMAIL, UA, _resolve_pmcid

CROSSREF = "https://api.crossref.org/works"
# Two overlap bars, because the two routes carry different evidence. A DOI printed in the paper is
# evidence the document supplies about itself, so the overlap check only confirms it. A search hit is a
# guess being scored, and author agreement cannot rescue it (the search was by that author), so only a
# near-exact title match is accepted: rejecting a correct paper is cheap, accepting a wrong one corrupts
# every downstream join.
MIN_OVERLAP = 0.6           # DOI routes
MIN_OVERLAP_SEARCH = 0.85   # search routes
MIN_HEAD_AGREE = 0.5        # ...and the paper's own title line must agree, when it has one
FRONT_MATTER = 3000     # chars of the paper that count as "front matter" for a self-declared DOI
# Verification scans the whole paper. That is safe only because distinctive tokens are scored: a long
# window would make stopwords match by chance.
HEAD_FOR_CHECK = 40000

_DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"'<>,;)\]}]+)")
_STOP = {"the", "and", "for", "with", "from", "that", "this", "are", "its", "via", "into", "role",
         "roles", "new", "novel", "study", "studies", "analysis", "review", "using", "based", "human",
         "cell", "cells", "gene", "genes", "protein", "proteins", "effect", "effects", "cancer"}


def _distinctive(title: str) -> list[str]:
    """Content-bearing tokens of a title: >3 chars, not a stopword, not a bare number."""
    toks = re.sub(r"[^a-z0-9]+", " ", (title or "").lower()).split()
    return [t for t in toks if len(t) > 3 and t not in _STOP and not t.isdigit()]


@dataclass
class PaperIdentity:
    """What we believe about a paper, and WHY. `method` and `overlap` are the audit trail — a consumer can
    always ask how a field was obtained and how strongly it was checked."""
    doi: str = ""
    pmid: str = ""
    pmcid: str = ""
    title: str = ""
    year: int | None = None
    journal: str = ""
    kind: str = ""                  # Crossref work type: journal-article, dataset, component, ...
    authors: list = field(default_factory=list)
    method: str = "unresolved"      # doi-front-matter | doi-anywhere | title-search | unresolved
    overlap: float = 0.0            # how well the authority record matched the paper's own text
    verified: bool = False          # cleared MIN_OVERLAP against the paper text
    notes: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def _get(url: str, params: dict | None = None, timeout: int = 25) -> dict:
    for k in range(3):
        try:
            r = requests.get(url, params=params or {}, headers=UA, timeout=timeout)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (404, 400):
                return {}
        except Exception:
            pass
        time.sleep(0.5 * (k + 1))
    return {}


def dois_in_text(text: str) -> list[tuple[str, bool]]:
    """Every DOI printed in the paper, as (doi, is_front_matter), order preserved and de-duplicated.
    Position is a weak prior; the overlap check decides."""
    out, seen = [], set()
    for m in _DOI_RE.finditer(text or ""):
        d = m.group(1).lower().rstrip(".,;")
        # strip a trailing publisher artefact like "10.1234/foo.pdf"
        d = re.sub(r"\.(pdf|full|abstract)$", "", d)
        if d in seen:
            continue
        seen.add(d)
        out.append((d, m.start() < FRONT_MATTER))
    return out


def _record_from_crossref(item: dict) -> PaperIdentity:
    title = " ".join(item.get("title") or []).strip()
    parts = ((item.get("published-print") or item.get("published-online")
              or item.get("issued") or {}).get("date-parts") or [[None]])
    yr = parts[0][0] if parts and parts[0] else None
    authors = [f"{a.get('family','')} {a.get('given','')}".strip()
               for a in (item.get("author") or [])][:20]
    return PaperIdentity(doi=(item.get("DOI") or "").lower(), title=title,
                         year=int(yr) if isinstance(yr, int) else None,
                         journal=" ".join(item.get("container-title") or [])[:200],
                         kind=(item.get("type") or ""), authors=authors)


def crossref_by_doi(doi: str) -> PaperIdentity | None:
    d = _get(f"{CROSSREF}/{doi}", {"mailto": POLITE_EMAIL})
    item = d.get("message") if isinstance(d, dict) else None
    return _record_from_crossref(item) if item else None


def crossref_by_title(query: str, year: int | None = None, rows: int = 5) -> list[PaperIdentity]:
    params = {"query.bibliographic": query, "rows": rows, "mailto": POLITE_EMAIL,
              "select": "DOI,title,author,container-title,published-print,published-online,issued,type"}
    if year:
        params["filter"] = f"from-pub-date:{year-1}-01-01,until-pub-date:{year+1}-12-31"
    d = _get(CROSSREF, params)
    return [_record_from_crossref(i) for i in ((d.get("message") or {}).get("items") or [])]


def crossref_by_author_year(surname: str, year: int | None, topic: str = "",
                            rows: int = 20) -> list[PaperIdentity]:
    """Candidates by first-author surname and publication year, optionally narrowed by topic words from
    the paper's own body. The route for rows whose only identity is a label. Recall matters more than
    precision here; the overlap gate decides."""
    if not surname:
        return []
    params = {"query.author": surname, "rows": rows, "mailto": POLITE_EMAIL,
              "select": "DOI,title,author,container-title,published-print,published-online,issued,type"}
    if topic:
        params["query.bibliographic"] = topic
    if year:
        params["filter"] = f"from-pub-date:{year-1}-01-01,until-pub-date:{year+1}-12-31"
    d = _get(CROSSREF, params)
    return [_record_from_crossref(i) for i in ((d.get("message") or {}).get("items") or [])]


def topic_terms(text: str, k: int = 6) -> str:
    """The k most frequent distinctive words in the paper's opening, a cheap topical fingerprint used to
    narrow an author search."""
    words = [w for w in re.sub(r"[^a-z0-9]+", " ", (text or "")[:6000].lower()).split()
             if len(w) > 4 and w not in _STOP]
    freq: dict[str, int] = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1
    return " ".join(w for w, _ in sorted(freq.items(), key=lambda kv: -kv[1])[:k])


def pmid_for(doi: str = "", title: str = "") -> str:
    """PMID via NCBI esearch, DOI-exact or exact-title. An ambiguous search returns nothing."""
    for term in ([f"{doi}[DOI]"] if doi else []) + ([f'"{title}"[Title]'] if title else []):
        d = _get(f"{EUTILS}/esearch.fcgi",
                 {"db": "pubmed", "term": term, "retmode": "json", "retmax": 2,
                  "email": POLITE_EMAIL, "tool": "litmap"})
        ids = ((d.get("esearchresult") or {}).get("idlist") or [])
        if len(ids) == 1:            # exactly one hit = unambiguous
            return str(ids[0])
    return ""


def verify_against_text(record: PaperIdentity, text: str) -> float:
    """Fraction of the authority title's distinctive tokens that occur in the paper: does this record
    describe the document in hand? Distinctive-only scoring is what makes a whole-document window safe."""
    if not record.title or not text:
        return 0.0
    toks = _distinctive(record.title)
    if len(toks) < MIN_TITLE_TOKENS:
        return 0.0      # unverifiable, so unverified
    body = re.sub(r"[^a-z0-9]+", " ", text[:HEAD_FOR_CHECK].lower())
    words = set(body.split())
    return sum(1 for t in toks if t in words) / len(toks)


NON_ARTICLE = {"component", "dataset", "peer-review", "grant", "other", "journal-issue",
               "journal-volume", "book-part", "report-component"}
# a title with fewer content words than this cannot be verified, so it is not accepted
MIN_TITLE_TOKENS = 3


# Front matter is mostly not the title (bylines, affiliations, journal straplines), and a wrong title
# becomes both the search query and its check.
_AFFIL = re.compile(r"\b(universit|department|institute|hospital|school of|college|laborator|"
                    r"cancer cent(er|re)|division of|faculty|academy|foundation|inc\.|ltd)\b", re.I)
_JOURNAL = re.compile(r"\b(proc\.?\s*natl|vol\.?\s*\d|pp\.\s*\d|issn|volume\s+\d|no\.\s*\d|"
                      r"press|elsevier|springer|wiley|©)\b", re.I)


def _looks_like_byline(s: str) -> bool:
    """True if the line is an author list, an affiliation, or journal front matter rather than a title."""
    if _AFFIL.search(s) or _JOURNAL.search(s):
        return True
    if re.search(r"\b[A-Z]\.\s*[A-Z]?\.?\s*[A-Z][a-z]+", s):     # "W. M. Liu", "A. B. Smith"
        return True
    if s.count(",") >= 3 and len(re.findall(r"\d", s)) >= 2:
        return True
    words = s.split()
    if words and sum(1 for w in words if w[:1].isupper()) / len(words) > 0.85 and len(words) <= 8:
        return True                                              # a short all-capitalised name run
    return False


def head_title(text: str) -> str:
    """The paper's own title when its text still carries front matter, else ''. A missing head title is
    "no extra evidence", not a failure."""
    for line in (text or "")[:1200].split("\n"):
        s = re.sub(r"^\s*title\s*[:\-]\s*", "", line.strip(), flags=re.I)
        if not (25 <= len(s) <= 250):
            continue
        if s.lower().startswith(("doi", "http", "www", "received", "abstract", "keywords",
                                 "correspondence", "published", "accepted", "copyright")):
            continue
        if len(_distinctive(s)) < 3:
            continue
        if _looks_like_byline(s):
            continue
        return s
    return ""


def _head_agrees(rec_title: str, head: str) -> float:
    """Overlap between the authority title and the paper's own title line, far stricter than scattered
    body tokens. When the paper states its own title, that is the evidence to use."""
    if not head:
        return 1.0                      # no head title available: this test abstains
    a, b = set(_distinctive(rec_title)), set(_distinctive(head))
    if not a or not b:
        return 0.0
    # symmetric on purpose: a shorter title must not score perfectly just because it is a subset
    return min(len(a & b) / len(a), len(a & b) / len(b))


def _accept(rec: PaperIdentity, text: str, method: str, note: str) -> PaperIdentity | None:
    """Gate + enrich. Returns the record only if it clears MIN_OVERLAP against the paper's own words."""
    if rec.kind in NON_ARTICLE:
        rec.overlap, rec.notes = 0.0, f"rejected: work type {rec.kind!r} is not an article"
        return None
    if len(_distinctive(rec.title)) < MIN_TITLE_TOKENS:
        rec.overlap, rec.notes = 0.0, f"rejected: title {rec.title!r} too generic to verify"
        return None
    bar = MIN_OVERLAP_SEARCH if method.endswith("-search") else MIN_OVERLAP
    ov = verify_against_text(rec, text)
    if ov < bar:
        rec.overlap = round(ov, 3)
        return None
    # When the paper states its own title, that beats scattered body tokens as evidence. Search routes
    # must clear it too; DOI routes are exempt because the paper already named the identifier itself.
    if method.endswith("-search"):
        agree = _head_agrees(rec.title, head_title(text))
        if agree < MIN_HEAD_AGREE:
            rec.overlap = round(ov, 3)
            rec.notes = f"rejected: title disagrees with the paper's own title line ({agree:.2f})"
            return None
    rec.method, rec.overlap, rec.verified = method, round(ov, 3), True
    rec.pmid = pmid_for(doi=rec.doi, title=rec.title)
    rec.pmcid = _resolve_pmcid(rec.doi, rec.pmid)
    rec.notes = note
    return rec


def resolve(text: str, title_hint: str = "", year_hint: int | None = None,
            known_doi: str = "", author_hint: str = "") -> PaperIdentity:
    """Best verified identity for one paper. Returns method='unresolved' rather than a guess."""
    text = text or ""
    tried: list[str] = []

    # 0/1/2 — a DOI we already hold, then DOIs the paper prints about itself.
    candidates: list[tuple[str, bool]] = []
    if known_doi:
        candidates.append((known_doi.lower(), True))
    candidates += [c for c in dois_in_text(text) if c[0] != known_doi.lower()]

    best: PaperIdentity | None = None
    for doi, front in candidates[:12]:          # a reference list can hold hundreds; front ones first
        rec = crossref_by_doi(doi)
        if not rec:
            tried.append(f"{doi}:no-crossref")
            continue
        got = _accept(rec, text, "doi-front-matter" if front else "doi-anywhere", "")
        tried.append(f"{doi}:{rec.overlap:.2f}{'' if got else ('/' + rec.notes if rec.notes else '')}")
        if got:
            got.notes = "; ".join(tried[-3:])
            return got
        if best is None or rec.overlap > best.overlap:
            best = rec

    # 3a: the paper's own title line is the best query available, the paper naming itself
    own = head_title(text)
    if own:
        for rec in crossref_by_title(own, year_hint):
            got = _accept(rec, text, "own-title-search", f"paper's own title line: {own[:60]!r}")
            if got:
                return got
            if best is None or rec.overlap > best.overlap:
                best = rec

    # 3b: search by whatever title hint we have and gate the result the same way
    if title_hint:
        for rec in crossref_by_title(title_hint, year_hint):
            got = _accept(rec, text, "title-search", f"title-search on {title_hint!r}")
            if got:
                return got
            if best is None or rec.overlap > best.overlap:
                best = rec

    # 4: author + year + the paper's own topic words, for rows whose only identity is a label
    if author_hint:
        topic = topic_terms(text)
        for rec in crossref_by_author_year(author_hint, year_hint, topic):
            got = _accept(rec, text, "author-year-search",
                          f"author={author_hint!r} year={year_hint} topic={topic!r}")
            if got:
                return got
            if best is None or rec.overlap > best.overlap:
                best = rec

    # nothing cleared the bar: return the near-miss for a human, marked unverified
    out = best or PaperIdentity()
    out.method, out.verified = "unresolved", False
    out.notes = f"best overlap {out.overlap} < {MIN_OVERLAP}; tried: {'; '.join(tried[:6]) or 'nothing'}"
    return out
