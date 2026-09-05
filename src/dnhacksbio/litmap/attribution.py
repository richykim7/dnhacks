"""Attribution (whose finding is this?) and the citations that support it.

A paper's own experiment is evidence; a paper restating someone else's result is an echo, and ten echoes
of one experiment are still one experiment. Three layers, each degrading into the one below: attribution
itself (works on every paper), citation markers (cluster echoes within a paper, when markers exist), and
resolved sources (cluster echoes across papers, when a bibliography exists).

Every function here is deterministic and offline. This module extracts (which reference does "(11)" point
at) and does not judge: attribution and certainty are readings of a sentence and come from the model,
which answers with the paper in context.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# --- vocabulary ------------------------------------------------------------------------------------
OWN, PRIOR, UNCLEAR = "own", "prior", "unclear"
ATTRIBUTIONS = frozenset({OWN, PRIOR, UNCLEAR})

# --- the model's answer -> the attribution vocabulary ----------------------------------------------
# Layer 1. `computational_inference` is the paper's own analysis; `curator_inference` and `unspecified`
# name no owner, so they stay unclear.
_MODEL_ATTRIBUTION = {
    "experimental_own": OWN,
    "computational_inference": OWN,
    "author_statement_prior": PRIOR,
    "review_statement": PRIOR,
}

# In-text citation markers, numbered: "(11)", "(3, 7)", "[12-15]". A range is several sources.
_MARK_NUM = re.compile(r"[\(\[]\s*(\d{1,3}(?:\s*[,;–—-]\s*\d{1,3})*)\s*[\)\]]")
# A surname, not an abbreviation: the second character must be lowercase (Koch, McGowan; not DNA, ERK).
_SURNAME = r"[A-Z][a-zà-ÿ][A-Za-zÀ-ɏ'\-]*"
# Author-year — "(Berger et al., 2005)", "(Chen and Chen, 2003)", "(Koch et al, 2007)".
_MARK_AY = re.compile(
    rf"\(\s*((?:{_SURNAME})"
    rf"(?:\s+(?:et\s+al\.?|and\s+{_SURNAME}|&\s*{_SURNAME}))?"
    r",?\s*(?:19|20)\d{2}[a-z]?)\s*\)")
# Narrative author-year: "Berger et al. showed", "Liu et al. (2025) demonstrated". `et al` may stand
# alone; "A and B" is ordinary English and is only accepted with a year. The optional comma before the year
# handles semicolon-separated lists ("(Smith et al., 1994; Jones et al., 2003)"), and the `[a-z]?`
# keeps "2013b" distinct from "2013a".
_MARK_NARR = re.compile(
    rf"\b({_SURNAME}\s+et\s+al\.?)(?:,?\s*\(?((?:19|20)\d{{2}}[a-z]?)\)?)?"
    rf"|\b({_SURNAME}\s+and\s+{_SURNAME})\s*,?\s*\(?((?:19|20)\d{{2}}[a-z]?)\)?")

_DOI = re.compile(r"\b(10\.\d{4,9}/[^\s,;\]\"']+)", re.I)


def _clean_doi(raw: str) -> str:
    """Trim unbalanced trailing brackets and PMC glue. SICI DOIs contain parens and angle brackets, so
    those are allowed in the match and only unbalanced trailing ones are removed; a trailing
    '.Capitalizedword' is a section heading PMC glued onto the last DOI of a list.
    """
    d = raw.rstrip("./")                 # "…/cgi/doi/10.1073/pnas/" — a DOI never ends in a slash
    while ((d.endswith(")") and d.count(")") > d.count("("))
           or (d.endswith(">") and d.count(">") > d.count("<"))):
        d = d[:-1].rstrip(".")
    return re.sub(r"\.[A-Z][a-z]+$", "", d)
_PMID = re.compile(r"\bPMID:?\s*(\d{6,9})\b", re.I)
_YEAR = re.compile(r"\b(19|20)\d{2}\b")
# A cited year with its disambiguating suffix ("2013a" and "2013b" are different papers). Used by `_ay_key`
# only; bibliography text keeps the plain `_YEAR`.
_YEAR_SUFFIXED = re.compile(r"\b((?:19|20)\d{2}[a-z]?)")


@dataclass(frozen=True)
class CitedSource:
    """One thing a claim leans on. `sid` is the identity; its prefix states how firm that identity is."""
    sid: str
    marker: str                 # verbatim, as printed in the quote
    tier: str                   # doi | pmid | author_year | local
    raw: str = ""               # the bibliography entry, when we found one

    @property
    def is_global(self) -> bool:
        return self.tier in ("doi", "pmid", "author_year")


@dataclass
class AttributionVerdict:
    """The answer, plus the signals that produced it."""
    value: str                                       # own | prior | unclear
    basis: list[str] = field(default_factory=list)   # which signals fired, in the order they were checked
    # Tri-state: True = the model agreed, False = it disagreed, None = it said nothing.
    agreed_with_model: bool | None = True
    model_said: str = ""

    def __post_init__(self):
        if not (self.model_said or "").strip():
            self.agreed_with_model = None
        from dnhacksbio.litmap.vocab import CERTAINTY
        if self.value not in ATTRIBUTIONS and self.value not in CERTAINTY:
            raise ValueError(f"value must be an attribution {sorted(ATTRIBUTIONS)} or a certainty "
                             f"{sorted(CERTAINTY)}, got {self.value!r}")


# ---------------------------------------------------------------------------------------------------
# Layer 2 — citation markers, straight out of the quote
# ---------------------------------------------------------------------------------------------------
def _expand(run: str) -> list[str]:
    """'13-15' -> ['13','14','15']; '3, 7' -> ['3','7']. A claim citing a range rests on every source in it."""
    out: list[str] = []
    for part in re.split(r"\s*[,;]\s*", run.strip()):
        m = re.fullmatch(r"(\d{1,3})\s*[–—-]\s*(\d{1,3})", part)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if 0 < a <= b and b - a <= 60:           # a sane span; anything wider is not a citation range
                out.extend(str(i) for i in range(a, b + 1))
            continue
        if part.isdigit():
            out.append(part)
    return out


# Words whose trailing number is a coordinate, not a citation, applied to the ~16 characters before a
# candidate number. `chr` also covers `chromosome`. Months are full names only.
_NOT_A_CITATION_BEFORE = re.compile(
    r"(fig|figure|table|panel|lane|step|day|week|month|year|passage|exon|intron|chr|codon|residue"
    r"|position|age|aged|january|february|march|april|june|july|august|september|october"
    r"|november|december)\w*\.?\s*$")
# The superscript pass also refuses a number directly after "and"/"to" (figure-legend prose such as
# "compare lane 2 to lanes 3 and 4"). The bracket pass does not use this: "in breast (3) and colon (4)"
# is two citations.
_SUPER_NOT_AFTER = re.compile(r"\b(?:and|to)\s+$")

# Superscript citations as PMC flattens them. A bare number is too ambiguous to accept on shape
# alone, so both patterns are consulted only when the paper has a parsed reference list, and a candidate is
# kept only if every number in its run is an entry in that list and it touches a sentence boundary.
_SUPER_AFTER_DOT = re.compile(      # ". 33 This" / "genes.20" — number right after a sentence end
    r"(?<=[a-z])\.\s*(\d{1,3}(?:\s*[,–—-]\s*\d{1,3})*)(?=\s+[A-Z“\"]|\s*$)")
_SUPER_BEFORE_PUNCT = re.compile(   # "suppressor 145 ." / "tRNA, 2<end>" / "139 , 159 – 161 ,"
    r"(?<=[A-Za-z,]\s)(\d{1,3}(?:\s*[,–—-]\s*\d{1,3})*)\s*(?=[.,;:](?!\d)|$)")
# Word-glued superscripts. The lookbehind demands four lowercase
# letters so that gene symbols with short prefixes ("il6") do not read as citations.
_SUPER_GLUED = re.compile(r"(?<=[a-z]{4})(\d{1,3})(?=[.,;\s]|$)")


def uses_bracket_citations(text: str, threshold: int = 8) -> bool:
    """Does this paper cite with bracketed numbers? A paper cites one way: in a bracket-citing paper a
    bare trailing number is a footnote, not a citation.
    """
    n = 0
    for m in _MARK_NUM.finditer(text or ""):
        before = (text[max(0, m.start() - 14):m.start()]).lower()
        if not _NOT_A_CITATION_BEFORE.search(before):
            n += 1
            if n >= threshold:
                return True
    return False


def uses_glued_superscripts(text: str, refs: dict[str, str], min_hits: int = 10,
                            min_ratio: float = 0.6) -> bool:
    """Does this paper cite with word-glued superscripts ('research3.')? A paper-level census: enough
    glued candidates must exist and most must land inside the parsed bibliography.
    """
    if not refs:
        return False
    hits = total = 0
    distinct: set[str] = set()
    for m in _SUPER_GLUED.finditer(text or ""):
        total += 1
        if m.group(1) in refs:
            hits += 1
            distinct.add(m.group(1))
    # Distinct entries, not occurrences.
    return len(distinct) >= min_hits and hits >= min_ratio * total


def find_markers(quote: str, refs: dict[str, str] | None = None,
                 glued: bool = False) -> tuple[list[str], list[str]]:
    """Extract citation markers from a quote. Returns (numbered, author_year). Only what is verbatim in
    the quote is returned, so a marker cannot be invented. `refs` (the parsed bibliography) unlocks the
    superscript pass; callers should withhold it when `uses_bracket_citations(text)` is true.
    """
    q = quote or ""
    nums: list[str] = []
    for m in _MARK_NUM.finditer(q):
        # A bare "(2)" after a word like "Figure" or a unit is not a citation.
        before = q[max(0, m.start() - 14):m.start()].lower()
        if _NOT_A_CITATION_BEFORE.search(before):
            continue
        nums.extend(_expand(m.group(1)))
    if refs:
        pats = [_SUPER_AFTER_DOT, _SUPER_BEFORE_PUNCT] + ([_SUPER_GLUED] if glued else [])
        for pat in pats:
            for m in pat.finditer(q):
                before = q[max(0, m.start(1) - 16):m.start(1)].lower()
                if _NOT_A_CITATION_BEFORE.search(before) or _SUPER_NOT_AFTER.search(before):
                    continue
                run = _expand(m.group(1))
                if run and all(n in refs for n in run):
                    nums.extend(run)
    ays: list[str] = []
    taken: list[tuple[int, int]] = []
    for m in _MARK_AY.finditer(q):
        ays.append(m.group(1).strip())
        taken.append(m.span())
    for m in _MARK_NARR.finditer(q):
        # Skip a narrative match inside a parenthesised one already captured, or one source is counted
        # twice under two identities.
        if any(s <= m.start() and m.end() <= e for s, e in taken):
            continue
        # A year in parens ("Liu et al. (2025)") is four digits and does not match, so it still counts.
        if re.match(r"\s*[\(\[]\s*\d{1,3}\s*[,–—\-\)\]]", q[m.end():]):
            continue
        name = (m.group(1) or m.group(3) or "").strip()
        yr = m.group(2) or m.group(4)
        if name:
            ays.append(f"{name} {yr}".strip() if yr else name)
    return list(dict.fromkeys(nums)), list(dict.fromkeys(ays))

def _ay_key(marker: str) -> str:
    """'Berger et al., 2005' -> 'AY:berger2005'. Stable across papers so two authors citing the same work
    collide. Without a year it stays name-only, which is weaker."""
    name = re.split(r"\s+(?:et\s+al|and|&)", marker.strip(), maxsplit=1)[0]
    name = re.sub(r"[^A-Za-zÀ-ɏ]", "", name).lower()
    y = _YEAR_SUFFIXED.search(marker)
    return f"AY:{name}{y.group(1) if y else ''}"


# ---------------------------------------------------------------------------------------------------
# Layer 3: the paper's own reference list, parsed once per paper
# ---------------------------------------------------------------------------------------------------
_HEAD = re.compile(r"(?m)^[^\S\n]*(references|bibliography|literature cited|works cited)\b[^\S\n]*:?[^\S\n]*$",
                   re.I)
_ENTRY = re.compile(r"(?m)^[^\S\n]*[\[(]?(\d{1,3})[\].)]\s+(?=\S)")


def parse_references(text: str, min_entries: int = 5) -> dict[str, str]:
    """Numbered reference list -> {'11': 'Berger et al. Nature 2005 ... doi:10.1038/...'}.

    Returns {} when there is no list, which is common and normal; callers fall back to the local tier.
    `min_entries` guards against a stray numbered list (a protocol, a figure legend) being mistaken for a
    bibliography. Parsed once per paper, never per claim.
    """
    if not text:
        return {}
    # An explicit heading wins wherever it sits; the last such line is taken because supplementary
    # sections can repeat it.
    heads = list(_HEAD.finditer(text))
    region = text[heads[-1].end():] if heads else text[int(len(text) * 0.5):]

    hits = list(_ENTRY.finditer(region))
    if len(hits) < min_entries:
        # Second chance: a run-on list, where PMC glued the whole bibliography into one line and no entry
        # starts a line. Candidates are kept only by walking the numbering sequentially from near 1, since
        # a real bibliography is consecutive; junk matches are stepped over, every viable start is tried,
        # the longest chain wins and a tie goes to the latest start. Three boundary shapes are tried, strict
        # before gap-tolerant, and the span and dated-majority checks below still apply.
        best: list[re.Match] = []
        for tolerance in (1, 15):
            for boundary in (r"(\d{1,3})\.(?=[A-ZÀ-ɏ])",
                             r"(?:(?<=[.;\]])|(?<=\n))\s*(\d{1,3})\s+(?=[A-ZÀ-ɏ])",
                             r"\[(\d{1,3})\]\s*(?=[A-ZÀ-ɏ])"):
                cands = list(re.finditer(boundary, region))
                for i, first in enumerate(cands):
                    if int(first.group(1)) > 3:
                        continue
                    seq = [first]
                    for m in cands[i + 1:]:
                        last = int(seq[-1].group(1))
                        if last < int(m.group(1)) <= last + tolerance:
                            seq.append(m)
                    if len(seq) >= len(best):        # >= : the later start wins ties
                        best = seq
            if len(best) >= min_entries:
                break
        if len(best) >= min_entries:
            hits = best
        else:
            return {}
    out: dict[str, str] = {}
    for i, m in enumerate(hits):
        # +2000 bounds the last entry only: enough for any real entry, small enough not to swallow the
        # page furniture after the list.
        end = hits[i + 1].start() if i + 1 < len(hits) else min(len(region), m.end() + 2000)
        body = " ".join(region[m.end():end].split())
        if body:
            out.setdefault(m.group(1), body)         # first wins: a re-used number is a parse artefact
    # A real bibliography is mostly consecutive. A scattered set of numbered lines is not one.
    nums = sorted(int(k) for k in out)
    if len(nums) < min_entries or nums[0] > 3 or (nums[-1] - nums[0] + 1) > 3 * len(nums):
        return {}
    # And it is mostly dated: numbered equations are consecutive and numerous but carry no year.
    dated = sum(1 for v in out.values() if _YEAR.search(v))
    if dated * 2 < len(out):
        return {}
    return _with_author_year_keys(out)


# An author-year bibliography entry begins "Surname, I."; the comma is required because journal
# abbreviations ("Sci. World J. 2") mimic the comma-less form. Splits unnumbered lists.
_AY_ENTRY_START = re.compile(r"([A-Z][A-Za-zà-ÿ'\-]+),\s+(?=[A-Z]\.)")


def _first_author_year_key(body: str) -> str | None:
    """The bibliography entry's author-year key, the same normalisation `_ay_key` applies to in-text
    markers. The first capitalised token is the surname, which skips lowercase particles on both sides.
    """
    m = re.search(r"([A-Z][A-Za-zà-ÿ'\-]+)", body or "")
    y = _YEAR.search(body or "")
    if not (m and y):
        return None
    return re.sub(r"[^a-zà-ÿ]", "", m.group(1).lower()) + y.group(0)


def _with_author_year_keys(out: dict[str, str]) -> dict[str, str]:
    """Add 'smith1994'-style keys beside the numeric ones, so a narrative citation can resolve through
    the bibliography in a numbered paper. A name+year that maps to two entries is ambiguous and gets no key.
    """
    ay: dict[str, str | None] = {}
    for body in out.values():
        k = _first_author_year_key(body)
        if k:
            ay[k] = None if k in ay and ay[k] != body else body
    for k, body in ay.items():
        if body and k not in out:
            out[k] = body
    return out


def parse_references_author_year(text: str, min_entries: int = 5) -> dict[str, str]:
    """An unnumbered (author-year) reference list -> {'smith1994': '<entry>'}.

    Two splitting strategies: PMC pages separate entries with '[ Google Scholar ]', used when frequent;
    otherwise the text splits at every 'Surname, I.' start and fragments merge forward until one contains a
    year, so co-author fragments fold into their entry. Same safety rails as the numbered parser: enough
    entries, mostly dated, ambiguous name+year keys dropped.
    """
    if not text:
        return {}
    heads = list(_HEAD.finditer(text))
    region = text[heads[-1].end():] if heads else text[int(len(text) * 0.5):]

    parts: list[str]
    if region.count("[ Google Scholar ]") >= min_entries:
        parts = region.split("[ Google Scholar ]")
    else:
        # Comma form first, then the Springer form where initials follow the surname without a comma.
        # The no-comma anchor is looser, so it is consulted second.
        parts = []
        for anchor in (_AY_ENTRY_START, re.compile(r"([A-Z][a-zà-ÿ'\-]+)\s+(?=[A-Z]{1,3}\b[,\s])")):
            starts = [m.start() for m in anchor.finditer(region)]
            if len(starts) < min_entries:
                continue
            raw_parts = [region[a:b] for a, b in
                         zip(starts, starts[1:] + [min(len(region), starts[-1] + 2000)])]
            merged, acc = [], ""
            for p in raw_parts:
                acc += p
                if _YEAR.search(p):
                    merged.append(acc)
                    acc = ""
            if len(merged) >= min_entries:
                parts = merged
                break
        if not parts:
            return {}
    out: dict[str, str | None] = {}
    for p in parts:
        body = " ".join(p.split())[:2000]   # junk bound, not a format: whole entries fit
        k = _first_author_year_key(body)
        if k:
            out[k] = None if k in out and out[k] != body else body
    # min_entries counts parsed entries, including ambiguous ones that then get no key.
    if len(out) < min_entries:
        return {}
    return {k: v for k, v in out.items() if v}


def resolve_marker(marker: str, refs: dict[str, str], source_ref: int) -> CitedSource:
    """One numbered marker -> the strongest identity available for it. Never returns None: an unresolved
    marker still identifies a source locally, which clusters echoes inside one paper."""
    raw = (refs or {}).get(marker, "")
    if raw:
        d = _DOI.search(raw)
        if d:
            return CitedSource(f"DOI:{_clean_doi(d.group(1))}", marker, "doi", raw)
        p = _PMID.search(raw)
        if p:
            return CitedSource(f"PMID:{p.group(1)}", marker, "pmid", raw)
        am = _MARK_NARR.search(raw) or re.match(r"\s*([A-Z][A-Za-zÀ-ɏ'\-]+)", raw)
        y = _YEAR.search(raw)
        if am and y:
            return CitedSource(_ay_key(f"{am.group(1)} {y.group(0)}"), marker, "author_year", raw)
    return CitedSource(f"SRC:{source_ref}.{marker}", marker, "local", raw)


def cited_sources(quote: str, refs: dict[str, str], source_ref: int,
                  superscript: bool = True, glued: bool = False) -> list[CitedSource]:
    """Every source a quote leans on, strongest identity first. Deterministic and order-stable.

    `superscript=False` closes the bare-number pass while keeping `refs` for resolving bracketed markers —
    pass `not uses_bracket_citations(text)` when the full paper is in hand, because in a bracket-citing paper
    a bare trailing number is a footnote. `glued=True` additionally opens the word-glued pattern — pass
    `uses_glued_superscripts(text, refs)`.
    """
    nums, ays = find_markers(quote, refs if superscript else None, glued=glued)
    out = [resolve_marker(n, refs, source_ref) for n in nums]
    for a in ays:
        # An author-year marker whose name+year keys a bibliography entry inherits that entry's strongest
        # identity.
        key = _ay_key(a)
        raw = (refs or {}).get(key[3:], "")
        if raw:
            d = _DOI.search(raw)
            p = _PMID.search(raw)
            if d:
                out.append(CitedSource(f"DOI:{_clean_doi(d.group(1))}", a, "doi", raw))
                continue
            if p:
                out.append(CitedSource(f"PMID:{p.group(1)}", a, "pmid", raw))
                continue
            out.append(CitedSource(key, a, "author_year", raw))
            continue
        out.append(CitedSource(key, a, "author_year"))
    seen, uniq = set(), []
    for c in out:
        if c.sid not in seen:
            seen.add(c.sid)
            uniq.append(c)
    return uniq


# ---------------------------------------------------------------------------------------------------
# Layer 1: attribution. Works on every paper, with or without citations.
# ---------------------------------------------------------------------------------------------------
def classify(model_says: str = "") -> AttributionVerdict:
    """Is this the authors' own finding, or someone else's restated? The model decides, as
    `evidence_type`, with the paper in context; this function maps that answer onto the attribution
    vocabulary. Citation markers are still extracted by `cited_sources` for provenance links.
    """
    value = _MODEL_ATTRIBUTION.get((model_says or "").strip().lower(), UNCLEAR)
    basis = [f"model_said_{model_says}"] if model_says else ["model_said_nothing"]
    return AttributionVerdict(value, basis, True, model_says)


# ---------------------------------------------------------------------------------------------------
# Hedged claims are kept, labelled, rather than deferred; storing them indistinguishably from a
# measurement is what must not happen. The model picks from a closed menu and `vocab.CERTAINTY` turns the
# label into a number, so belief resolves to a menu choice plus a table of constants.
def classify_certainty(model_says: str = "") -> AttributionVerdict:
    """How strongly does the paper assert this claim? The model decides from a closed menu.
    `demonstrated` is the default when the model offers nothing usable.
    """
    from dnhacksbio.litmap.vocab import CERTAINTY
    m = (model_says or "").strip().lower()
    if m in CERTAINTY:
        return AttributionVerdict(m, [f"model_said_{m}"], True, model_says)
    return AttributionVerdict("demonstrated", ["model_said_nothing_usable"], True, model_says)
