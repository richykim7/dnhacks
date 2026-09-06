"""Deterministic entity grounding: surface strings to resolved identifiers, with one owner vocabulary per
category.

Gene and protein strings resolve through Gilda (BSD-2, INDRA) to HGNC; every other category is answered
first by its owner lexicon (ChEBI, MONDO, HP, UBERON, CL, Cellosaurus, SO, FamPlex, Dfam, NCBI Gene for
non-human genes), then by Gilda within the permitted namespaces, then by a last-resort chain of gap-fillers
(PRO, NCIt). Processes resolve through OLS exact matching. Gilda runs locally when installed and falls back
to the public REST service; any failure returns None so grounding degrades rather than crashing. Only the
entity surface string is ever sent over the network.
"""
from __future__ import annotations

import json
import os
import re

from pathlib import Path

import requests

_REST_URL = "https://grounding.indra.bio/ground"
_UA = {"User-Agent": "research-tool/1.0"}
_HUMAN = "9606"                      # NCBI taxon id — restrict to human genes
_backend: str | None = None         # resolved lazily: 'local' | 'rest'
_cache: dict[str, str | None] = {}
_raw_cache: dict[str, list[dict]] = {}   # memoize Gilda matches per string (gene + non-gene share it)

# Gilda namespace -> coarse entity type for non-gene entities. Genes, proteins and families are handled
# by `ground_gene` and excluded here. MESH is ambiguous across disease, chemical and anatomy, so it stays
# type 'other'.
_DB_TYPE: dict[str, str] = {
    "CHEBI": "drug", "DRUGBANK": "drug", "CHEMBL": "drug", "PUBCHEM": "drug",
    "DOID": "disease", "MONDO": "disease", "EFO": "disease",
    "GO": "process",
    "HP": "phenotype", "MP": "phenotype",
    "CL": "cell_type", "CLO": "cell_line",
    "MESH": "other", "UBERON": "other", "NCBITAXON": "other", "TAXONOMY": "other",
}


def _resolve_backend() -> str:
    """Prefer a local gilda install; fall back to the REST service. Force REST with LITMAP_GILDA_REST=1."""
    global _backend
    if _backend is None:
        if os.environ.get("LITMAP_GILDA_REST") == "1":
            _backend = "rest"
        else:
            try:
                import gilda  # noqa: F401
                _backend = "local"
            except Exception:
                _backend = "rest"
    return _backend


def _raw(text: str, timeout: float = 15.0) -> list[dict]:
    """Gilda matches as normalized dicts [{db,id,entry_name,organism,score}], best first. Returns [] on any
    failure and is memoized per string."""
    key = (text or "").strip()
    if key in _raw_cache:
        return _raw_cache[key]
    out = _raw_uncached(text, timeout)
    _raw_cache[key] = out
    return out


def _raw_uncached(text: str, timeout: float = 15.0) -> list[dict]:
    try:
        if _resolve_backend() == "local":
            import gilda
            return [{"db": m.term.db, "id": m.term.id, "entry_name": m.term.entry_name,
                     "organism": str(getattr(m.term, "organism", _HUMAN) or _HUMAN),
                     "score": float(m.score)}
                    for m in gilda.ground(text)]
        r = requests.post(_REST_URL, json={"text": text}, headers=_UA, timeout=timeout)
        out = []
        for m in (r.json() or []):
            t = m.get("term", {})
            out.append({"db": t.get("db"), "id": t.get("id"), "entry_name": t.get("entry_name"),
                        "organism": str(t.get("organism", _HUMAN) or _HUMAN),
                        "score": float(m.get("score", 0))})
        return out
    except Exception:
        return []


def ground_gene(text: str, min_score: float = 0.7) -> str | None:
    """Surface string -> canonical HGNC symbol when Gilda maps it confidently to a single human HGNC gene
    (db=HGNC, organism 9606, score >= min_score), else None. HGNC specifically, never a FamPlex family, so
    a gene is not collapsed into a family. Cached per string.
    """
    if not text or not text.strip():
        return None
    key = text.strip()
    if key in _cache:
        return _cache[key]
    sym = None
    matches = _raw(key)
    if matches:
        top = matches[0]
        if top["score"] >= min_score and top["db"] == "HGNC" and top["organism"] == _HUMAN:
            sym = top["entry_name"]
    _cache[key] = sym
    return sym


def ground_entity(text: str, min_score: float = 0.7) -> dict | None:
    """Surface string -> a non-gene grounding via Gilda (chemical, drug, disease, phenotype, process, cell
    line). Returns {id, type, grounder, db, db_id} for the best match in a `_DB_TYPE` namespace at or above
    `min_score`, else None. `id` is the ontology entry name; `db`/`db_id` keep the stable xref.
    """
    if not text or not text.strip():
        return None
    text = _ORTHOLOG_SYMBOL.get(text.strip().lower(), text)
    for m in _raw(text.strip()):                 # best-first; stop once below threshold
        if m.get("score", 0) < min_score:
            break
        t = _DB_TYPE.get(m.get("db"))
        name = m.get("entry_name") or ""
        if t and name:
            return {"id": name, "type": t, "grounder": "gilda", "db": m["db"], "db_id": m.get("id")}
    return None


# --- resolved CURIEs -----------------------------------------------------------------------
# The identity key admits only resolved identifiers: no CURIE, no claim (it becomes a deferral).

# Which namespace may mint a node, and for which kind. An allowlist: a prefix absent from here can never
# become a node, so an unconsidered vocabulary fails closed. `_DB_CURIE` below only says what a prefix
# means; this table says whether it is allowed to answer. Gap-fillers (NCIt, PRO) are reached only after the
# owner has failed.
_MINTABLE: dict[str, set[str]] = {
    "HGNC": {"entity"},                      # genes / proteins
    "CHEBI": {"entity"},                     # chemicals
    "FPLX": {"entity"},                      # families / complexes
    "GO": {"process", "entity"},             # processes; its cellular_component branch holds THINGS
    "MESH": {"pathological_process"},        # the one category GO excludes by design
    "MONDO": {"disease"},
    "HP": {"phenotype"},
    "UBERON": {"anatomy"}, "CL": {"cell_type"}, "CVCL": {"cell_line"},
    "NCBITaxon": {"organism"},
    # Non-human genes: NCBI Gene owns them as their own category. The id can only arrive through
    # `nonhuman_gene_lookup`, so a human gene cannot acquire one.
    "NCBIGene": {"entity"},
    "SO": {"mark"},
    "DFAM": {"repeat_family"}, "DFAMCLASS": {"repeat_family"},
    "FEATURE": {"feature"}, "ENDPOINT": {"endpoint"}, "PHENOTYPE": {"endpoint"},
}


# Specific ids that must route whatever their prefix says: ChEBI carries four chromatin marks that SO owns,
# and Gilda's index returns them, so they are routed by equivalence wherever ownership is decided.
_NOT_OWNED_IDS: dict[str, str] = {
    "CHEBI:85042": "SO:0001705",     # H3K4Me1
    "CHEBI:85043": "SO:0001706",     # H3K4Me3
    "CHEBI:85044": "SO:0002049",     # H3K27Ac
    "CHEBI:85045": "SO:0001709",     # H3K27Me3
}


def may_mint(curie: str, kind: str) -> bool:
    """May this identifier become a node of this kind? False means route or refuse, never mint; an unknown
    prefix fails closed."""
    if canonical_curie(curie) in _NOT_OWNED_IDS:
        return False                    # a real id in the wrong vocabulary: route it, never mint it
    prefix = (curie or "").partition(":")[0]
    allowed = _MINTABLE.get(prefix) or _MINTABLE.get(_CANONICAL_PREFIX.get(prefix.upper(), prefix))
    return bool(allowed) and kind in allowed


_DB_CURIE: dict[str, tuple[str, str]] = {
    "HGNC": ("HGNC", "entity"), "UP": ("UniProt", "entity"), "FPLX": ("FPLX", "entity"),
    "CHEBI": ("CHEBI", "entity"), "DRUGBANK": ("DRUGBANK", "entity"), "CHEMBL": ("CHEMBL", "entity"),
    # GO's cellular_component branch holds things (nucleosome, chromatin), not processes; this default is
    # corrected per term by `_kind_for` at every return site.
    "GO": ("GO", "process"),
    "MONDO": ("MONDO", "disease"), "DOID": ("DOID", "disease"), "EFO": ("EFO", "disease"),
    "HP": ("HP", "phenotype"), "MP": ("MP", "phenotype"),
    "CL": ("CL", "cell_type"), "UBERON": ("UBERON", "anatomy"),
    "SO": ("SO", "mark"), "CVCL": ("CVCL", "cell_line"),
    "DFAM": ("DFAM", "repeat_family"), "DFAMCLASS": ("DFAMCLASS", "repeat_family"),
    "NCBITAXON": ("NCBITaxon", "organism"), "TAXONOMY": ("NCBITaxon", "organism"),
    # Typing only: Gilda never returns NCBIGene; this row lets `kind_from_curie` type ids minted by
    # `nonhuman_gene_lookup`.
    "NCBIGENE": ("NCBIGene", "entity"),
}


# The canonical spelling of each namespace prefix. Sources disagree on case (OLS `mesh:`, Gilda `MESH:`),
# so every id passes through `canonical_curie` before it can become a node.
_CANONICAL_PREFIX: dict[str, str] = {
    "MESH": "MESH", "GO": "GO", "HP": "HP", "MP": "MP", "MONDO": "MONDO", "DOID": "DOID", "EFO": "EFO",
    "NCIT": "NCIT", "CHEBI": "CHEBI", "HGNC": "HGNC", "UBERON": "UBERON", "CL": "CL", "CLO": "CLO",
    "CVCL": "CVCL", "FPLX": "FPLX", "UP": "UniProt", "UNIPROT": "UniProt", "PR": "PR", "PATO": "PATO",
    "NCBITAXON": "NCBITaxon", "TAXONOMY": "NCBITaxon", "OBI": "OBI", "BAO": "BAO", "SO": "SO",
    "NCBIGENE": "NCBIGene",
}


# Model-organism orthologs whose symbol differs from the human one (most mouse symbols differ only in case
# and Gilda matches them). A mouse claim and a human claim land on the same node; organism is a veto
# context slot, so the species still disqualifies a cross-organism comparison. Worm and fly genes are too
# diverged for this and defer instead.
_ORTHOLOG_SYMBOL: dict[str, str] = {
    "cdkn2a-arf": "CDKN2A", "p19arf": "CDKN2A", "p14arf": "CDKN2A",
    "trp53": "TP53",  # mouse ortholog; https://www.ncbi.nlm.nih.gov/gene/22059
}



# --- the owner lexicons ------------------------------------
# One file per owner, loaded on first use, so a run that never touches cell lines never loads Cellosaurus.
LEXDIR = "data/processed/lexicons"
_lexcache: dict[str, dict] = {}


def _lex(name: str) -> dict:
    if name not in _lexcache:
        try:
            _lexcache[name] = json.loads((Path(LEXDIR) / f"{name}.json").read_text())
        except FileNotFoundError:
            _lexcache[name] = {}          # an unbuilt owner is a gap, never a crash
    return _lexcache[name]


def _owner_hit(lexname: str, text: str, kind: str, db: str) -> dict | None:
    """Look a surface up in one owner's lexicon, hyphen-insensitively (papers write `HERV-K`, Dfam files
    `HERVK`)."""
    lex = _lex(lexname)
    if not lex:
        return None
    t = _ncit_norm(text)
    for k in (t, _ncit_norm(t.replace("-", "")), _ncit_norm(t.replace("-", " "))):
        hit = lex.get(k)
        if hit and canonical_curie(hit[0]).partition(":")[0] in ({"DFAM", "DFAMCLASS"} if db == "DFAM" else {db}):
            return {"curie": canonical_curie(hit[0]), "label": hit[1], "kind": kind, "db": db, "score": 1.0}
    # ChEBI:28939 is N-acetyl-L-cysteine. These are verified spelling variants,
    # not a general rule deleting chemical punctuation (which can change identity).
    if lexname == "chebi" and t in {"n-acetyl cysteine", "n acetyl cysteine", "n-acetylcysteine"}:
        for name in ("n-acetyl-l-cysteine", "n-acetylcysteine"):
            hit = lex.get(name)
            if hit and canonical_curie(hit[0]) == "CHEBI:28939":
                return {"curie": "CHEBI:28939", "label": hit[1], "kind": kind, "db": db, "score": 1.0}
    return None


def anatomy_lookup(text: str) -> dict | None:
    return _owner_hit("anatomy", text, "anatomy", "UBERON")


def cell_type_lookup(text: str) -> dict | None:
    return _owner_hit("cell_type", text, "cell_type", "CL")


def cell_line_lookup(text: str) -> dict | None:
    return _owner_hit("cell_line", text, "cell_line", "CVCL")


def phenotype_lookup(text: str) -> dict | None:
    return _owner_hit("phenotype", text, "phenotype", "HP")


def mark_lookup(text: str) -> dict | None:
    return _owner_hit("mark", text, "mark", "SO")


def family_lookup(text: str) -> dict | None:
    """FamPlex. `kind` stays `entity`: a family is a molecular actor and takes aspects; the family/complex
    distinction rides on the record."""
    hit = _owner_hit("family", text, "entity", "FPLX")
    if hit:
        hit["family_kind"] = _lex("family_kind").get(hit["curie"], "family")
    return hit


def repeat_lookup(text: str) -> dict | None:
    """Dfam, at both levels it supports. The path is kept on the record so prefix-matching gives `parent_of`."""
    hit = _owner_hit("repeat", text, "repeat_family", "DFAM")
    if hit:
        meta = _lex("repeat_meta").get(hit["curie"]) or {}
        hit["repeat_level"] = meta.get("kind", "family")
        hit["path"] = meta.get("path", "")
    return hit


# --- non-human genes -> NCBI Gene, keyed by organism -----------------
# Reached only when the reader names the `non_human_gene` category; HGNC keeps `gene` (human) and Gilda is
# not consulted for this category. The lexicon is nested by NCBITaxon id because gene symbols collide across
# species: the claim's organism context picks the species table, and there is no human table. Three vetoes,
# in order: a tracked ortholog (which lands on the human node), any HGNC human match at Gilda's acceptance
# bar, and a missing, unresolvable or human organism. Refusals raise LookupError with the reason so the
# deferral queue can show it.
_HGNC_VETO_SCORE = 0.7          # ground_curie's own acceptance bar, applied in both directions

# Verified owner records absent from the locally built species tables. Kept taxon-scoped;
# these are NCBI identifiers, not an orthology assertion or a species inference.
_NONHUMAN_SUPPLEMENT = {
    "10090": {
        "saa3": ("NCBIGene:20210", "Saa3"),
        "saa-3": ("NCBIGene:20210", "Saa3"),
        "serum amyloid a 3": ("NCBIGene:20210", "Saa3"),
        "serum amyloid a3": ("NCBIGene:20210", "Saa3"),
    },
}
_NONHUMAN_SUPPLEMENT_SOURCES = {"NCBIGene:20210": "https://www.ncbi.nlm.nih.gov/gene/20210"}


def _taxon_curie(organism: str) -> str:
    """Raw organism context ('C. elegans', 'worm', or 'NCBITaxon:6239') -> NCBITaxon CURIE, from the same
    table the context resolver uses. '' when unknown; no fuzzy lookup, since organism is a veto-grade fact.
    """
    t = (organism or "").strip()
    if t.startswith("NCBITaxon:"):
        return t
    from .vocab import CONTEXT_SLOTS
    return CONTEXT_SLOTS["organism"]["map"].get(_ncit_norm(t), "")


def species_gene_collision(surface: str, organism: str) -> dict | None:
    """Verified species/symbol collisions where human string matching changes gene identity.

    H2-Ab1 is mouse MHC class II beta (NCBI Gene 14961), while the punctuation-stripped
    human H2AB1 is a histone. Preserve the hyphen and require explicit mouse context;
    this is not a general exception to ortholog normalization or the human-name veto.
    Sources: https://www.ncbi.nlm.nih.gov/gene/14961
    https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/HGNC:22516
    """
    if (surface or "").strip().lower() != "h2-ab1" or _taxon_curie(organism) != "NCBITaxon:10090":
        return None
    return {"curie": "NCBIGene:14961", "label": "H2-Ab1", "kind": "entity", "db": "NCBIGene",
            "score": 1.0, "organism": "10090"}


def nonhuman_gene_lookup(text: str, organism: str) -> dict | None:
    """A species-specific gene symbol -> its NCBI Gene id, within one non-human species' table. Returns a
    hit dict, None on a plain miss, and raises LookupError with the reason whenever answering could put a
    human gene here."""
    t = (text or "").strip()
    if not t:
        return None
    collision = species_gene_collision(t, organism)
    if collision:
        return collision
    human = _ORTHOLOG_SYMBOL.get(t.lower())
    if human:
        raise LookupError(f"{text!r} is a tracked ortholog written onto the human node "
                          f"(HGNC {human}); category `gene` owns it, organism rides in context")
    for m in _raw(t):
        if m.get("db") == "HGNC" and m.get("organism") == _HUMAN \
                and m.get("score", 0) >= _HGNC_VETO_SCORE:
            raise LookupError(f"{text!r} resolves in HGNC ({m.get('entry_name')}, "
                              f"score {m.get('score', 0):.2f}); a human-resolvable symbol never "
                              "enters non_human_gene; category `gene` owns it")
    taxon = _taxon_curie(organism)
    if not taxon:
        if (organism or "").strip():
            raise LookupError(f"organism {organism!r} is not in the deterministic taxon table "
                              "(vocab.CONTEXT_SLOTS); cannot pick a species table")
        raise LookupError("non_human_gene needs an organism context to pick a species table, "
                          "and this claim carries none")
    if taxon == "NCBITaxon:9606":
        raise LookupError(f"{text!r} claimed as non_human_gene with organism=human; refused")
    taxon_id = taxon.partition(":")[2]
    species = {**_NONHUMAN_SUPPLEMENT.get(taxon_id, {}),
               **((_lex("nonhuman_gene") or {}).get(taxon_id) or {})}
    if not species:
        raise LookupError(f"no non-human gene table for {taxon}")
    for k in (_ncit_norm(t), _ncit_norm(t.replace("-", "")), _ncit_norm(t.replace("-", " "))):
        hit = species.get(k)
        if hit:
            return {"curie": hit[0], "label": hit[1], "kind": "entity", "db": "NCBIGene",
                    "score": 1.0, "organism": taxon.partition(":")[2]}
    return None


# Namespace prefix -> the owner lexicon that answers for it, so the owner can be asked before any general
# matcher. `NCBIGene` is absent: its lookup needs an organism and is only reached via `nonhuman_gene_lookup`.
_OWNER_LOOKUP: dict[str, str] = {
    "CHEBI": "chebi", "MONDO": "disease", "HP": "phenotype", "UBERON": "anatomy",
    "CL": "cell_type", "CVCL": "cell_line", "SO": "mark", "FPLX": "family", "DFAM": "repeat",
}


def owner_first(text: str, namespaces) -> dict | None:
    """Ask the category's owner before anything else, then fall through to a general matcher. With no
    category the fallback-last order applies.
    """
    for ns in (namespaces or ()):
        lexname = _OWNER_LOOKUP.get(ns)
        if not lexname:
            continue                          # HGNC has no lexicon here: Gilda is its resolver
        hit = _owner_hit(lexname, text, _LEX_KIND[lexname], ns)
        if hit:
            if lexname == "family":
                hit["family_kind"] = _lex("family_kind").get(hit["curie"], "family")
            elif lexname == "repeat":
                meta = _lex("repeat_meta").get(hit["curie"]) or {}
                hit["repeat_level"] = meta.get("kind", "family")
                hit["path"] = meta.get("path", "")
            return hit
    return None


_LEX_KIND: dict[str, str] = {
    "chebi": "entity", "disease": "disease", "phenotype": "phenotype", "anatomy": "anatomy",
    "cell_type": "cell_type", "cell_line": "cell_line", "mark": "mark", "family": "entity",
    "repeat": "repeat_family",
}


def route_to_owner(curie: str) -> str:
    """A foreign id in an owned category -> the owner's id, or '' when no equivalence is recorded."""
    return _NOT_OWNED_IDS.get(canonical_curie(curie), "")


def chebi_lookup(text: str) -> dict | None:
    """Current ChEBI, which is newer than Gilda's shipped index. Consulted before any gap-filler, since ChEBI
    owns chemicals."""
    return _owner_hit("chebi", text, "entity", "CHEBI")


def disease_lookup(text: str) -> dict | None:
    """MONDO, the disease owner."""
    hit = _lex("disease").get(_ncit_norm(text))
    if not hit:
        return None
    return {"curie": hit[0], "label": hit[1], "kind": "disease", "db": "MONDO", "score": 1.0}


_pro: dict | None = None
PRO_LEXICON = "data/processed/pro_lexicon.json"


def _pro_lex() -> dict:
    global _pro
    if _pro is None:
        try:
            _pro = json.loads(Path(PRO_LEXICON).read_text())
        except FileNotFoundError:
            _pro = {"surface": {}, "terms": {}, "version": ""}
    return _pro


def pro_lookup(text: str) -> dict | None:
    """A specific protein form (an isoform or a modified form) rather than the gene it comes from. PRO
    records `PR:P10275-3` as `is_a PR:P10275`, so AR-V7 is a form of the androgen receptor rather than an
    unrelated node; `form_of` is returned for the refinement lattice. Consulted after every other resolver
    and before NCIt. Keys claimed by two PRO terms, or owned by another vocabulary, were dropped at build
    time.
    """
    hit = (_pro_lex().get("surface") or {}).get(_ncit_norm(text))
    if not hit:
        return None
    curie, label, cat, taxon = hit
    info = (_pro_lex().get("terms") or {}).get(curie) or {}
    parents = info.get("parents") or []
    return {"curie": curie, "label": label, "kind": "entity", "db": "PR", "score": 1.0,
            "form_of": parents[0] if parents else "", "pro_category": cat, "organism": taxon}


_ncit: dict | None = None
NCIT_LEXICON = "data/processed/ncit_lexicon.json"


def _ncit_lex() -> dict:
    """Lazy singleton for the NCIt surface-form table."""
    global _ncit
    if _ncit is None:
        try:
            _ncit = json.loads(Path(NCIT_LEXICON).read_text())
        except FileNotFoundError:
            # A missing lexicon degrades to "no NCIt".
            _ncit = {}
    return _ncit


def ncit_lookup(text: str) -> dict | None:
    """Exact normalised match into NCIt, the last resort for things no other vocabulary contains. NCIt
    holds its own gene, process and disease terms, so it is asked last and can only fill a hole. The match
    is string equality after mild normalisation, never fuzzy; surface forms claimed by two NCIt concepts
    were dropped at build time.
    """
    hit = _ncit_lex().get(_ncit_norm(text))
    if not hit:
        return None
    curie, label, kind = hit
    return {"curie": curie, "label": label, "kind": kind, "db": "NCIT", "score": 1.0}


def _ncit_norm(s: str) -> str:
    # Typography only: preserve ASCII chemical punctuation and gene-symbol content.
    text = (s or "").translate(str.maketrans({"‐": "-", "‑": "-", "–": "-", "−": "-"}))
    return re.sub(r"\s+", " ", text.strip().lower()).strip(" .,;:")


def _ambiguous_tie(matches: list[dict], namespaces=None) -> bool:
    """True when the best score is shared by two different namespaces: an ambiguity, not a winner. Fires
    only when the category has not already narrowed the search. Only cross-namespace ties count; ties
    within one vocabulary are refused by the lexicon's contested-key rule at build time.
    """
    live = [m for m in matches if not namespaces or (m.get("db") or "") in namespaces]
    if len(live) < 2:
        return False
    top = live[0].get("score", 0)
    tied = [m for m in live if abs(m.get("score", 0) - top) < 1e-9]
    return len({m.get("db") for m in tied}) > 1


def ground_curie(text: str, min_score: float = 0.7, namespaces=None) -> dict | None:
    """Surface string -> {curie, label, kind, db, score}, or None when nothing resolves confidently.
    Owner lexicon first, then Gilda within the permitted namespaces, then the last-resort chain."""
    if not text or not text.strip():
        return None
    from .lexicon_supplement import supplement_lookup
    supplemented = supplement_lookup(text, namespaces=namespaces)
    if supplemented and (not namespaces or supplemented["curie"].partition(":")[0] in namespaces):
        return supplemented
    text = _ORTHOLOG_SYMBOL.get(text.strip().lower(), text)
    owned = owner_first(text, namespaces)
    if owned:
        return owned
    raw = _raw(text.strip())
    if _ambiguous_tie([m for m in raw if m.get("score", 0) >= min_score], namespaces):
        return None                    # two namespaces, one score: send it to the reader
    for m in raw:                                      # best-first; stop once below threshold
        if m.get("score", 0) < min_score:
            break
        # The category narrows the search: a wrong candidate is removed, not out-ranked.
        if namespaces and (m.get("db") or "") not in namespaces:
            continue
        if m.get("db") == "MESH" and m.get("id"):
            # ChEBI owns chemicals: a MeSH hit defers to ChEBI whenever ChEBI has the string and the
            # category admits ChEBI.
            owned = chebi_lookup(text) if (not namespaces or "CHEBI" in namespaces) else None
            if owned:
                return owned
            # typed per term, never per prefix; '' means refuse
            cur = str(m["id"])
            cur = cur if cur.startswith("MESH:") else f"MESH:{cur}"
            mk = mesh_kind(cur)
            if not mk:
                continue
            # and the owned-subtree bound the process path applies
            if namespaces and "MESH" in namespaces and not _mesh_ok(cur):
                continue
            return {"curie": cur, "label": m.get("entry_name") or text.strip(), "kind": mk,
                    "db": "MESH", "score": float(m.get("score", 0))}
        pair = _DB_CURIE.get(m.get("db"))
        if not pair or not m.get("id"):
            continue
        prefix, kind = pair
        if kind == "entity" and m["db"] == "HGNC" and m.get("organism") != _HUMAN:
            continue                                   # human genes only, as ground_gene
        cid = str(m["id"])
        curie = cid if cid.startswith(prefix + ":") else f"{prefix}:{cid}"
        if prefix == "GO":
            if go_obsolete(curie):
                continue                               # a dead id is not an answer; try the next match
            kind = _kind_for({"curie": curie})         # the branch decides, not the prefix
        # The ownership gate, applied where a match becomes a node.
        if not may_mint(curie, kind):
            routed = route_to_owner(curie)
            if routed and namespaces and routed.partition(":")[0] not in namespaces:
                continue         # routing must not deliver a namespace this category does not own
            if routed:
                # The kind comes from the id we end up with, not the one we started from.
                return {"curie": routed, "label": m.get("entry_name") or text.strip(),
                        "kind": kind_from_curie(routed, default=kind),
                        "db": canonical_curie(routed).partition(":")[0],
                        "score": float(m.get("score", 0)), "routed_from": prefix}
            continue                                   # not an owner and no route: refuse, try the next
        return {"curie": curie,
                "label": m.get("entry_name") or text.strip(), "kind": kind,
                "db": m["db"], "score": float(m.get("score", 0))}
    # Last-resort chain, owners before gap-fillers, consulted only when everything above left a hole. It
    # obeys `namespaces` like the two paths above it.
    chain = (("CHEBI", chebi_lookup), ("MONDO", disease_lookup), ("HP", phenotype_lookup),
             ("FPLX", family_lookup), ("SO", mark_lookup), ("DFAM", repeat_lookup),
             ("CVCL", cell_line_lookup), ("CL", cell_type_lookup), ("UBERON", anatomy_lookup),
             ("PR", pro_lookup), ("NCIT", ncit_lookup))
    for ns, fn in chain:
        if namespaces and ns not in namespaces:
            continue
        hit = fn(text)
        if hit:
            return hit
    return None


# --- processes and phenotypes as objects ------------------------------------------------------------
# Processes are first-class objects ("EGFR increases apoptosis"). Gilda resolves few of them, so OLS4 is
# the resolver, with exact label/synonym matching only.
_OLS = "https://www.ebi.ac.uk/ols4/api/search"
_proc_cache: dict[tuple[str, tuple[str, ...]], dict | None] = {}

# Bare nouns that GO stores under a longer canonical label, tried in order after the literal string.
_PROCESS_EXPANSIONS: tuple[str, ...] = ("cell {}", "cellular {}", "{} process", "cell population {}")

# The two owners of the two process-path categories: GO owns `process` and MeSH owns
# `pathological_process` (GO excludes disease processes). `_process_ontologies` narrows the pair to the one
# owner of the category asked for.
_PROCESS_ONTOLOGIES: tuple[str, ...] = ("go", "mesh")


def _mesh_ok(curie: str) -> bool:
    """True unless this is a MeSH id outside the subtrees MeSH owns on the process path (`process` or
    `pathological_process` by tree number). Non-MeSH ids pass untouched."""
    if not curie.startswith("MESH:"):
        return True
    return mesh_kind(curie) in ("process", "pathological_process")


def _process_ontologies(namespaces: tuple[str, ...] | None) -> tuple[str, ...]:
    """OLS ontology slugs for the requested category's namespaces: the owner and nothing else.
    `namespaces=None` keeps the union of both owners."""
    if not namespaces:
        return _PROCESS_ONTOLOGIES
    want = {n.strip().lower() for n in namespaces}
    return tuple(o for o in _PROCESS_ONTOLOGIES if o in want)


# GO stores direction in the term ("positive regulation of apoptotic process") as well as offering the bare
# process. Claims carry their own polarity, so a regulation term would encode direction twice and two
# opposite claims would resolve to different object CURIEs; the bare process is used instead (GO-CAM's
# convention). Only the directional forms are demoted: bare `regulation of X` carries no direction.
_REGULATION_PREFIX = re.compile(r"^(positive|negative)\s+regulation of\s+", re.I)


# GO has three branches and only two are processes; a cellular component is a thing that can be bound. The
# branch is not in the search response, so it costs one cached lookup against the terms endpoint.
_ns_cache: dict[str, tuple[str, bool]] = {}
_GO_COMPONENT = "cellular_component"


def _go_meta(curie: str) -> tuple[str, bool]:
    """(branch, is_obsolete) for a GO term, from one cached OLS fetch. The obsolete flag arrives in the
    same response and keeps dead identifiers (GO retires whole term families) out of the graph."""
    if not curie.startswith("GO:"):
        return "", False
    if curie in _ns_cache:
        return _ns_cache[curie]
    meta = ("", False)
    try:
        r = requests.get("https://www.ebi.ac.uk/ols4/api/ontologies/go/terms",
                         params={"obo_id": curie}, headers=_UA, timeout=10.0)
        terms = (r.json().get("_embedded") or {}).get("terms") or []
        got = ((terms[0].get("annotation") or {}).get("has_obo_namespace") or []) if terms else []
        ns = (got[0] if isinstance(got, list) and got else got) or ""
        meta = (ns, bool(terms and terms[0].get("is_obsolete")))
    except Exception:
        meta = ("", False)                 # a network failure must not look like an obsoletion
    _ns_cache[curie] = meta
    return meta


def go_namespace(curie: str) -> str:
    """Which GO branch a term belongs to: biological_process | molecular_function | cellular_component."""
    return _go_meta(curie)[0]


def go_obsolete(curie: str) -> bool:
    """True only when GO itself says the term is obsolete; False on any network failure."""
    return _go_meta(curie)[1]


_mesh_cache: dict[str, str] = {}

# MeSH tree roots we accept and what they mean. The lookup breaks on its first prefix match, so specific
# prefixes precede general ones. No `C` (diseases belong to MONDO) except the two process subtrees, and no
# `D12` (proteins belong to HGNC).
_MESH_ROOTS: tuple[tuple[str, str], ...] = (
    ("D12", ""),        # proteins/peptides: HGNC's job; listed first so it wins as a prefix match
    # A11 is cells, not anatomy: A11.251 is "Cells, Cultured", where cell lines live.
    ("A11.251", "cell_line"), ("A11", "cell_type"),
    ("A", "anatomy"), ("B", "organism"), ("D", "entity"),
    # G = Phenomena and Processes. GO excludes disease processes, so MeSH answers for those; ordering
    # still protects the overlap, since `apoptosis` matches GO first.
    ("G", "process"),
    # Two subtrees that are processes despite living under C (Diseases): "Neoplastic Processes" and
    # "Pathologic Processes". These make `pathological_process` a category with MeSH as its one owner.
    ("C04.697", "pathological_process"), ("C23.550", "pathological_process"),
)


def _mesh_tree_kinds(codes) -> set:
    kinds = set()
    for tn in codes:
        code = str(tn).rsplit("/", 1)[-1]
        for root, k in _MESH_ROOTS:                   # D12 first: a protein match short-circuits to ''
            if code.startswith(root):
                kinds.add(k)
                break
    return kinds


def _mesh_kinds(ident: str, _depth: int = 0) -> set:
    """Kinds implied by a MeSH record's tree numbers. A supplementary concept record carries no tree
    numbers, only `preferredMappedTo` descriptors for its class, which are followed one hop to decide the
    kind; the record keeps its own identifier.
    """
    r = requests.get(f"https://id.nlm.nih.gov/mesh/{ident}.json", headers=_UA, timeout=10.0)
    j = r.json()
    tns = j.get("treeNumber") or []
    if isinstance(tns, str):
        tns = [tns]
    if tns:
        return _mesh_tree_kinds(tns)
    if _depth:                                        # one hop only; an SCR maps to descriptors, not SCRs
        return set()
    mapped = j.get("preferredMappedTo") or []
    if isinstance(mapped, str):
        mapped = [mapped]
    kinds = set()
    for m in mapped[:4]:
        kinds |= _mesh_kinds(str(m).rsplit("/", 1)[-1], _depth + 1)
    return kinds


def mesh_kind(curie: str) -> str:
    """Which kind a MeSH descriptor denotes, from its tree numbers; '' when it should not be accepted. A
    descriptor whose tree numbers straddle two kinds is refused rather than guessed."""
    if not curie.startswith("MESH:"):
        return ""
    if curie in _mesh_cache:
        return _mesh_cache[curie]
    kind = ""
    try:
        # A term in both `G` (process) and `C23.550`/`C04.697` (pathological_process) is a hierarchy, not a
        # straddle: the second is the more specific statement.
        kinds = _mesh_kinds(curie.split(":", 1)[1])
        if kinds == {"process", "pathological_process"}:
            kinds = {"pathological_process"}
        # one unambiguous kind, and not the empty (refused) one
        kind = kinds.pop() if len(kinds) == 1 else ""
    except Exception:
        kind = ""
    _mesh_cache[curie] = kind
    return kind


def _kind_for(hit: dict) -> str:
    """A cellular component is an entity, a thing that can be bound; the other branches are processes."""
    return "entity" if go_namespace(hit.get("curie", "")) == _GO_COMPONENT else "process"


def kind_from_curie(curie: str, default: str = "process") -> str:
    """What kind an identifier denotes, from its namespace, never from the pass that retrieved it."""
    prefix = (curie or "").split(":")[0].upper()
    if prefix == "GO":
        return _kind_for({"curie": curie})             # branch decides: component is an entity
    pair = _DB_CURIE.get(prefix)
    return pair[1] if pair else default


def canonical_curie(curie: str) -> str:
    """One spelling per namespace (OLS returns `mesh:D063646`, Gilda `MESH:D063646`, and two spellings
    would be two nodes). Unknown prefixes are uppercased rather than dropped."""
    prefix, sep, local = (curie or "").partition(":")
    if not sep:
        return curie or ""
    up = prefix.upper()
    canon = _CANONICAL_PREFIX.get(up, up)
    return f"{canon}:{local}"


def _ols_exact(query: str, ontology: str, timeout: float = 15.0) -> dict | None:
    """Exact label/synonym match, preferring an exact label hit over a synonym hit (a synonym match can
    generalise a specific outcome into its regulator)."""
    try:
        r = requests.get(_OLS, params={"q": query, "ontology": ontology, "rows": 40, "exact": "true",
                                       "queryFields": "label,synonym",
                                       "fieldList": "obo_id,label"},
                         headers=_UA, timeout=timeout)
        docs = [d for d in ((r.json().get("response") or {}).get("docs") or [])
                if d.get("obo_id") and canonical_curie(d["obo_id"]).partition(":")[0] == ontology.upper()
                and _mesh_ok(canonical_curie(d["obo_id"]))]
    except Exception:
        return None
    q = query.strip().lower()
    labels = {canonical_curie(d["obo_id"]): d for d in docs
              if (d.get("label") or "").strip().lower() == q}
    matches = labels or {canonical_curie(d["obo_id"]): d for d in docs}
    if len(matches) != 1:
        return None                         # homonyms require a source-reading choice
    curie, d = next(iter(matches.items()))
    return {"curie": curie, "label": d.get("label") or query,
            "kind": kind_from_curie(curie), "db": ontology.upper(), "matched": query,
            "match": "label" if labels else "synonym"}


def resolve_process(text: str, namespaces: tuple[str, ...] | None = None) -> dict | None:
    """Surface string -> a CURIE for a process used as an object, or None when nothing matches exactly,
    which routes the claim to the deferral queue rather than attaching a near-miss."""
    key = _ncit_norm(text)
    if not key:
        return None
    ontologies = _process_ontologies(namespaces)
    allowed = {o.upper() for o in ontologies}
    from .lexicon_supplement import supplement_lookup
    supplemented = supplement_lookup(text, namespaces=tuple(allowed)) if allowed else None
    if supplemented and supplemented["curie"].partition(":")[0] in allowed:
        return {**supplemented, "matched": text, "match": "label"}
    ck = (key, ontologies)
    if ck in _proc_cache:
        return _proc_cache[ck]
    out = None
    for onto in ontologies:
        # Only a caller explicitly selecting pathological processes supplies enough
        # context to interpret bare "invasion" as neoplasm invasiveness (MeSH D009361).
        alias = "neoplasm invasiveness" if (
            ontologies == ("mesh",) and key in {"invasion", "cell invasion", "cellular invasion", "tumor invasion", "tumour invasion"}
        ) else ""
        queries = tuple(dict.fromkeys((key, *((alias,) if alias else ()), *(p.format(key) for p in _PROCESS_EXPANSIONS))))
        for cand in queries:
            out = _ols_exact(cand, onto)
            # OLS's `go` ontology includes the terms GO imports from UBERON, CL, ChEBI and PATO, so the
            # answer's namespace is checked as well as the query's.
            if out and out["curie"].split(":")[0].upper() not in allowed:
                out = None
                continue
            # MeSH also indexes anatomy, cells and organisms, so its answer is bounded to the subtrees
            # the category owns.
            if out and not _mesh_ok(out["curie"]):
                out = None
                continue
            if out:
                break
        if out:
            break
    if out:
        out = demote_regulation_term(out)
        out["kind"] = mesh_kind(out["curie"]) if out["curie"].startswith("MESH:") else _kind_for(out)
        out["go_namespace"] = go_namespace(out.get("curie", ""))
    _proc_cache[ck] = out
    return out


_cand_cache: dict[tuple[str, int, tuple[str, ...]], list[dict]] = {}


def entity_candidates(text: str, organism: str = "", lo: float = 0.40, hi: float = 0.70,
                      limit: int = 6, namespaces=None) -> list[dict]:
    """Menu of real identifiers for an entity Gilda could not resolve confidently. `organism` is an
    NCBITaxon CURIE from the claim's context; absent one, the human-only stance of `ground_curie` is
    unchanged.
    """
    out: list[dict] = []
    taxon = (organism or "").split(":")[-1] if organism else ""
    allowed = {n.upper() for n in (namespaces or ())} or None
    try:
        import gilda
        kw = {"organisms": [taxon]} if taxon.isdigit() else {}
        matches = gilda.ground(text, **kw)
    except Exception:
        return out
    for m in matches:
        score = float(getattr(m, "score", 0) or 0)
        if not (lo <= score < hi):
            continue
        db, ident = m.term.db, m.term.id
        pair = _DB_CURIE.get(db)
        if not pair or not ident:
            continue
        prefix, kind = pair
        cid = str(ident)
        curie = cid if cid.startswith(prefix + ":") else f"{prefix}:{cid}"
        # The owner rule applies to the menu too, filtered on the CURIE prefix (the alphabet `CATEGORY_NS`
        # uses), not on Gilda's `db` name.
        if allowed and prefix.upper() not in allowed:
            continue
        if prefix == "GO":
            if go_obsolete(curie):
                continue                               # never offer a dead id on a menu either
            kind = _kind_for({"curie": curie})
        out.append({"curie": curie, "label": m.term.entry_name or text, "kind": kind,
                    "db": db, "score": round(score, 3),
                    "organism": getattr(m.term, "organism", "") or ""})
        if len(out) >= limit:
            break
    return out


def process_candidates(text: str, limit: int = 8,
                       namespaces: tuple[str, ...] | None = None) -> list[dict]:
    """Top candidate terms for a process object: the menu for retrieve-then-choose. Relevance ranking is
    acceptable here because the reader makes the final call. Candidates are interleaved across ontologies
    so one ontology cannot fill the menu before another gets a seat.
    """
    key = _ncit_norm(text)
    if not key or limit <= 0:
        return []
    ontologies = _process_ontologies(namespaces)
    allowed = {o.upper() for o in ontologies}
    ck = (key.lower(), limit, ontologies)
    if ck in _cand_cache:
        return _cand_cache[ck]

    per_onto: list[list[dict]] = []
    for onto in ontologies:
        try:
            r = requests.get(_OLS, params={"q": key, "ontology": onto, "rows": max(40, limit * 5),
                                           "queryFields": "label,synonym",
                                           "fieldList": "obo_id,label,description"},
                             headers=_UA, timeout=15.0)
            docs = (r.json().get("response") or {}).get("docs") or []
        except Exception:
            docs = []
        rows = []
        for d in docs:
            if not d.get("obo_id"):
                continue
            # `ontology=go` serves GO's imported UBERON, CL and ChEBI terms too.
            if str(d["obo_id"]).split(":")[0].upper() not in allowed:
                continue
            # The menu needs the same subtree bound as the exact path.
            if not _mesh_ok(canonical_curie(d["obo_id"])):
                continue
            desc = d.get("description")
            # Canonicalised here as on the exact path, so a term chosen from a menu is the same node.
            rows.append({"curie": canonical_curie(d["obo_id"]), "label": d.get("label") or "",
                         "db": onto.upper(),
                         "definition": (desc[0] if isinstance(desc, list) and desc else "") or ""})
        # Directional regulation terms sink to the bottom of each ontology's list.
        rows.sort(key=lambda r: bool(_REGULATION_PREFIX.match(r["label"])))
        per_onto.append(rows)

    out: list[dict] = []
    seen: set[str] = set()
    for rank in range(limit):                          # round-robin: every ontology gets a seat
        for rows in per_onto:
            if rank < len(rows) and rows[rank]["curie"] not in seen:
                seen.add(rows[rank]["curie"])
                out.append(rows[rank])
    out = out[:limit]
    _cand_cache[ck] = out
    return out


def demote_regulation_term(hit: dict) -> dict:
    """Re-target `[positive|negative] regulation of X` to the bare process X, since direction belongs to
    the claim's polarity field. Applied to menu choices as well as exact matches, so the rule does not rest
    on the prompt. If the bare process does not resolve, the regulation term is kept and flagged.
    """
    label = (hit.get("label") or "")
    if not _REGULATION_PREFIX.match(label):
        return hit
    base = _REGULATION_PREFIX.sub("", label).strip()
    owner = canonical_curie(hit.get("curie", "")).partition(":")[0]
    for onto in _process_ontologies((owner,)):
        got = _ols_exact(base, onto)
        if (got and canonical_curie(got.get("curie", "")).partition(":")[0] == owner
                and _mesh_ok(got["curie"]) and not _REGULATION_PREFIX.match(got.get("label") or "")):
            got["demoted_from"] = hit["curie"]
            return got
    hit["regulation_term_kept"] = True
    return hit


# --- repeat / transposable-element families ------------
# Dfam is the open TE database. Each tier below yields a stable identifier from Dfam's own vocabulary,
# never from the paper's prose.
_DFAM = "https://dfam.org/api/families"
_repeat_cache: dict[str, dict | None] = {}

# Words a paper attaches to a family name that are not part of it. `element(s)`, `family`, `repeat(s)`.
_REPEAT_NOISE = re.compile(
    r"\b(elements?|famil(?:y|ies)|repeats?|retrotransposons?|transposons?|sequences?|"
    r"subfamil(?:y|ies)|insertions?|copies|copy)\b", re.I)
# Names biologists use that Dfam spells differently.
_REPEAT_ALIAS = {"line-1": "L1", "line1": "L1", "l1": "L1", "alu": "Alu", "mir": "MIR",
                 "sva": "SVA", "herv": "HERV", "line": "L1", "sine": "SINE"}


# Ordinary words are never asked about as family names: Dfam has families called THE1A/THE1B and DNA2-1_AP,
# so the definite article and "DNA" would otherwise match a shared prefix.
_TE_STOPWORDS: frozenset[str] = frozenset({
    "the", "a", "an", "of", "in", "at", "on", "to", "and", "or", "for", "with", "its", "this", "these",
    "dna", "rna", "cdna", "mrna", "gene", "genes", "protein", "proteins", "sequence", "sequences",
    "region", "regions", "domain", "domains", "element", "elements", "site", "sites", "locus", "loci",
    "repeat", "repeats", "family", "families", "motif", "motifs", "strand", "chain", "complex",
    "promoter", "enhancer", "exon", "intron", "cell", "cells", "human", "mouse", "nucleosome",
})


def _repeat_query(text: str) -> str:
    s = _REPEAT_NOISE.sub(" ", (text or "")).strip(" -_")
    s = re.sub(r"\s+", " ", s)
    return _REPEAT_ALIAS.get(s.lower(), s)


def _shared_prefix(names: set[str]) -> str:
    """The longest prefix every one of these family names shares."""
    if not names:
        return ""
    first, *rest = sorted(names)
    n = len(first)
    for other in rest:
        n = min(n, len(other))
        while n and first[:n].lower() != other[:n].lower():
            n -= 1
    return first[:n]


def resolve_repeat(text: str, timeout: float = 20.0) -> dict | None:
    """Repeat/TE family name -> a stable identifier, or None. Three tiers, strongest first, with `tier`
    recorded: `family` (an exact Dfam family name), `classification` (a component of Dfam's lineage),
    `name_group` (two or more Dfam families share the prefix). Classification outranks name_group because
    the lineage is curated while a shared prefix is a naming convention.
    """
    q = _repeat_query(text)
    if not q or len(q) < 2:
        return None
    key = q.lower()
    if key in _TE_STOPWORDS:
        return None                                     # an ordinary word is never a family name
    if key in _repeat_cache:
        return _repeat_cache[key]
    try:
        r = requests.get(_DFAM, params={"name_prefix": q, "limit": 20},
                         headers={**_UA, "accept": "application/json"}, timeout=timeout)
        hits = (r.json() or {}).get("results") or []
    except Exception:
        return None                                     # transient: do not cache a network failure
    out = None
    for h in hits:                                      # tier 1: exact family name
        if (h.get("name") or "").lower() == key and h.get("accession"):
            out = {"curie": f"DFAM:{h['accession']}", "label": h["name"], "kind": "repeat_family",
                   "tier": "family", "db": "Dfam"}
            break
    if out is None:                                     # tier 2: a component of the curated lineage
        for h in hits:
            parts = [p.strip().lower() for p in (h.get("classification") or "").split(";")]
            if key in parts:
                out = {"curie": f"REPEATCLASS:{re.sub(r'[^a-z0-9]+', '-', key).strip('-')}",
                       "label": q, "kind": "repeat_family", "tier": "classification", "db": "Dfam"}
                break
    # Tier 3: the key must be the whole shared prefix, not a fragment of one. Families sharing a longer
    # prefix than the key mean the key is a fragment.
    _members = {h.get("name") for h in hits if (h.get("name") or "").lower().startswith(key)}
    if out is None and len(_members) >= 2 and _shared_prefix(_members).lower() == key:
        out = {"curie": f"DFAMGRP:{re.sub(r'[^a-z0-9]+', '-', key).strip('-')}", "label": q,
               "kind": "repeat_family", "tier": "name_group", "db": "Dfam",
               "members": sorted({h["name"] for h in hits
                                  if (h.get("name") or "").lower().startswith(key)})[:8]}
    # Head-word fallback only for a short phrase: a TE name is one or two tokens, a clause is not a name.
    if out is None and 1 < len(q.split()) <= 2:
        head = q.split()[0]
        if head.lower() not in _TE_STOPWORDS:
            out = resolve_repeat(head, timeout=timeout)
    _repeat_cache[key] = out
    return out


# Namespaces usable for context slots. MESH is admitted here because a context slot declares its own type,
# so MESH's cross-type ambiguity cannot mis-type the answer.
_CONTEXT_PREFIX: dict[str, str] = {
    "MESH": "MESH", "UBERON": "UBERON", "CL": "CL", "CLO": "CLO", "MONDO": "MONDO", "DOID": "DOID",
    "EFO": "EFO", "NCBITAXON": "NCBITaxon", "TAXONOMY": "NCBITaxon", "OBI": "OBI", "BAO": "BAO",
    "CVCL": "CVCL", "HP": "HP", "GO": "GO",
}


# Context slots whose category has an owner: slot -> (owner prefix, the lexicon that answers for it).
_OWNED_CONTEXT: dict[str, tuple[str, str]] = {
    "disease": ("MONDO", "disease"),
    "tissue": ("UBERON", "anatomy"),
    "cell_type": ("CL", "cell_type"),
    "cell_line": ("CVCL", "cell_line"),
}


def resolve_context_value(slot: str, text: str, min_score: float = 0.50) -> dict | None:
    """Resolve one context slot's surface string, using the slot to constrain the namespace. Returns
    {value, label, db} where `value` is a CURIE or a closed-vocabulary token, else None. The threshold is
    lower than `ground_curie`'s because context terms are common nouns that score lower, and a mis-resolved
    context narrows or widens a scope rather than changing what the claim is about.
    """
    from dnhacksbio.litmap.vocab import CONTEXT_SLOTS

    spec = CONTEXT_SLOTS.get(slot)
    if spec is None or not text or not text.strip():
        return None
    raw = text.strip()

    explicit = spec.get("map")
    if explicit is not None:                             # deterministic table wins over similarity
        hit = explicit.get(raw.lower())
        if hit:
            return {"value": hit, "label": raw, "db": "map"}

    closed = spec.get("closed")
    if closed is not None:
        tok = raw.lower().replace(" ", "_").replace("-", "_")
        if tok in closed:
            return {"value": tok, "label": raw, "db": "closed"}
        # Keyword fallback for slots whose surface form is a phrase rather than a token ("luciferase
        # reporter assay"). Longest key first.
        kw = spec.get("keywords")
        if kw:
            low = raw.lower()
            for k in sorted(kw, key=len, reverse=True):
                if k in low:
                    return {"value": kw[k], "label": raw, "db": "keyword"}
        return None

    # An owned category is owned here too, so a context disease lands on the same MONDO node the actor
    # path mints.
    if slot in _OWNED_CONTEXT:
        prefix, lexname = _OWNED_CONTEXT[slot]
        owned = _owner_hit(lexname, raw, _LEX_KIND[lexname], prefix)   # the owner's own lexicon, first
        if owned:
            return {"value": owned["curie"], "label": owned["label"], "db": prefix}
    prefer = [p.upper() for p in spec.get("ontology", [])]
    matches = [m for m in _raw(raw) if m.get("score", 0) >= min_score and m.get("id")]
    for want in prefer:                                  # slot's preference order first
        for m in matches:
            if (m.get("db") or "").upper() == want and want in _CONTEXT_PREFIX:
                cid = str(m["id"])
                prefix = _CONTEXT_PREFIX[want]
                curie = cid if cid.startswith(prefix + ":") else f"{prefix}:{cid}"
                if slot in _OWNED_CONTEXT and prefix != _OWNED_CONTEXT[slot][0]:
                    # A non-owner answered: route it, and refuse rather than mint a second node.
                    routed = route_to_owner(curie)
                    if not routed:
                        continue
                    return {"value": routed, "label": m.get("entry_name") or raw, "db": "MONDO",
                            "routed_from": prefix}
                return {"value": curie, "label": m.get("entry_name") or raw, "db": m["db"]}
    return None
