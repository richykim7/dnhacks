"""Full-text extraction, owner-scoped grounding and parallel source-backed Sonnet repair.

Ordinary validation checks typed claims and resolved owners; model repair reads the source,
corrects the proposal and receives concrete errors for another attempt. Rejected claims,
unresolved failures and warnings on retained claims are reported separately.
"""
from __future__ import annotations

import asyncio
from dataclasses import asdict
import hashlib
import json
import re
import string
from pathlib import Path

from dnhacksbio import llm
from dnhacksbio.litmap import attribution as A
from dnhacksbio.litmap import grounding as G
from dnhacksbio.litmap.schema import (
    Claim, ClaimSpine, Context, ContextValue, Deferral, DeferralError, EntityRef, EntityState,
    Evidence, Experiment, inheritance_allowed,
)
from dnhacksbio.litmap.vocab import (
    ASPECT_INPUTS, ASPECT_REWRITES, CATEGORIES, CATEGORY_NS, CATEGORY_PATH, CLINICAL_ENDPOINTS,
    CONTEXT_SLOTS,
    EVIDENCE_TYPES, EXPERIMENTAL_PHENOTYPES, FUNCTIONAL_STATES,
    PREDICATES, PREDICATE_WHEN, SO_FEATURE_TYPES, STUDY_TYPES, canonical_predicate,
    invert_predicate,
)

# The strong model does extraction: nothing downstream catches a collapsed subject, whereas an invented
# predicate is caught by the deferral gate.
EXTRACT_MODEL = llm.OPUS
PROMPT_VERSION = "1.1"

_JSON = re.compile(r"\{.*\}", re.S)

# Set `PROGRESS` to a callable `(source_ref, stage)` to see pass boundaries during a long run; the
# default is silence so library callers are unaffected.
PROGRESS = None


def _tick(ref: int, stage: str) -> None:
    if PROGRESS:
        PROGRESS(ref, stage)


# Reasoning trace, off by default. Set to a callable `(source_ref, pass_name, thinking, answer)` and
# pass 1 runs with extended thinking so the model's deliberation is captured.
TRACE = None


def _traced(ref: int, name: str, cap: dict, answer: str) -> None:
    if TRACE:
        TRACE(ref, name, (cap or {}).get("thinking", ""), answer)


class ApiUnavailable(RuntimeError):
    """The API refused (quota, rate limit, overload). A refusal says nothing about the paper, so it is a
    run-level fault that stops the run, not a DeferralError recorded against the paper.
    """


# Substrings that mean "the service refused".
_API_ERRORS = ("session limit", "rate limit", "quota", "overloaded", "api error", "usage limit",
               "weekly limit", "hit your", "limit · resets", "limit reached", "upgrade to",
               "insufficient credit", "service unavailable", "too many requests", "try again later")


def _refusal(txt: str) -> str | None:
    s = (txt or "").strip()
    if len(s) > 600:
        return None
    low = s.lower()
    return next((e for e in _API_ERRORS if e in low), None)


def _menu(items) -> str:
    return ", ".join(sorted(items))


def _category_menu() -> str:
    """The category list, rendered from the owner table so no category is offered that no vocabulary owns.
    One line each, since this sits in every pass-1 prompt."""
    return "\n".join(f"  {name:22s} {spec['when']}" for name, spec in CATEGORIES.items())


def _predicate_menu() -> str:
    """Every predicate with when to use it, rendered from `PREDICATES` and `PREDICATE_WHEN`."""
    signed = [p for p, (_, sg) in PREDICATES.items() if sg]
    out = []
    for p in list(PREDICATES):
        mark = "  " if p in signed else "  "
        out.append(f"{mark}{p:26s} {PREDICATE_WHEN[p]}")
    return "\n".join(out)


def _slot_menu() -> str:
    out = []
    for name, spec in CONTEXT_SLOTS.items():
        if "closed" in spec:
            out.append(f"  {name}: one of [{_menu(spec['closed'])}]")
        else:
            out.append(f"  {name}: a free-text surface term (we resolve it) — e.g. tissue 'liver', "
                       f"cell_line 'MCF-7'")
    return "\n".join(out)


SYSTEM = (
    "You extract structured scientific claims from full-text papers. You choose from fixed menus. "
    "You never invent a value that is not on a menu, and you never fill a field the paper does not "
    "support. Returning fewer, correct claims is strictly better than returning more."
)


def build_prompt(field: str, doc_type: str, text: str) -> str:
    inherit = ("You may inherit context from the Methods or a figure legend when the paper's own claim "
               "sentence omits it; mark provenance 'inherited' and quote the Methods sentence it came "
               "from." if inheritance_allowed(doc_type) else
               "This is a review. Do not inherit context from anywhere in this paper: a review restating "
               "someone else's finding has no experimental system of its own. Use 'stated' only when the "
               "claim's own sentence says it; otherwise omit the slot.")
    return f"""Purpose. You are building a knowledge graph that a researcher will reason over. Claims from
different papers land on the same node and are compared, so two papers disagreeing about the same thing
must collide rather than sit side by side as separate facts. Identity matters more than volume.

A claim is a relation the sentence asserts between two named things. It is not a judgement about whether
the finding is important, strong or likely true: record what the paper says, including weak, preliminary
and negative results, and let `certainty` and `evidence_type` carry the strength. A pair of names that
merely appear near each other with nothing asserted between them is not a claim. In particular, a list of
genes in prose ("such as CDK4, STAT3, AKT1") is not a set of claims; only extract a pair when the
sentence says something holds between them.

FIELD: {field}
DOCUMENT TYPE: {doc_type}

Extract every distinct scientific claim this paper makes or reports.

Rules for keeping the output small:
  1. Omit any field you cannot fill. Do not write "" or null as a placeholder; a missing key means "the
     paper did not say". Only `subject`, `predicate`, `object` and `quote` are always required.
  2. Write each experiment once. One experiment usually grounds several claims: put it once in the
     top-level `experiments` array and have every claim that rests on it reference its position
     (`"experiment": 0`).
  3. Do not repeat a quote. A claim's `quote` is its own; do not copy it into the experiment or into a
     context slot. A context slot needs its own quote only when it comes from a different sentence
     (typically the Methods), which is the `inherited` case.
  4. One sentence may carry several claims, and usually does when it names several things. Split it:
     "spleen, thymus and ovary expressed very high levels of EGFR"
        -> EGFR present_in spleen; EGFR present_in thymus; EGFR present_in ovary   (three claims)
     "Oct1 silencing reduced CCND1 levels, while Sp1 silencing did not"
        -> one claim per factor
     Reusing the same quote on each is expected and is not a duplicate.
  5. Do not emit the same claim twice. If two sentences support one claim, that is one claim; pick the
     better quote. Two claims are different only if subject, predicate, object or aspect differ.

The menus are a mapping, not a filter. The paper will not use these words and does not need to:
"abrogated", "rescued", "no longer detectable" and "restored to baseline" are real findings that map onto
menu terms whose letters appear nowhere in the sentence. Never reject a claim because the paper's wording
differs from the menu, and never pick a menu term merely because its letters appear in the text (a sentence
about "the promoters of EGFR target genes" is not about promoting anything).

PREDICATE. Choose exactly one. Most of these are not causal: a location, a co-occurrence, a presence or a
correlation is a first-class claim here.
{_predicate_menu()}
  `depends_on` means the subject needs the object.
  `co_occurs_with` is two things observed together in the same samples ("both G719S and S768I were
  detected in 4 patients"), unlike `co_occupies`, which is two proteins at one place on the DNA.
  `no_effect_on` is for a measured null: the authors tested it and found nothing. It is evidence.
  If no predicate fits, put the claim in "deferred" with the wording you would have wanted. Do not fall
  back to `associated_with`; that is reserved for genuine correlation.

SUBJECT. A named entity, process, cellular phenotype or cell population from a supported category.
A process or cell population can be the subject when the paper asserts a relation about it. It does not have to act (a histone mark is enriched at a place, a gene is conserved in a lineage).
  Yes   "EGFR", "GRB2", "arsenic trioxide", "EGFR exon 19", "EGFR T790M"
        (write the gene with its variant; the gene grounds and the variant becomes state)
  No    "EGFR mutation frequency", "EGFR mutation heterogeneity", "EGFR-SHC1 complex stabilization",
        "EGFR expression levels", "the pathway"
  The "no" cases put a measurement or a property where an actor belongs. Frequency, heterogeneity,
  stabilization and levels are measured about something: they are the aspect or the readout. If your
  subject is a noun phrase describing a quantity, the real subject is the thing the quantity is about.

CATEGORY. Say what the subject is (`subject_category`) and what the object is (`object_category`). Each
name is looked up in a different reference work depending on its kind, so the category decides where to
look. You have the paper; a dictionary does not.
{_category_menu()}

  Pick by what the paper means, not by how the word looks. A
  wrong category costs the claim rather than producing a wrong answer, so choose the accurate category
  rather than the commonest one.
  `gene` vs `family`: one gene product is `gene`; a group with members (NCORs, AKT, NF-kappaB) is
  `family`. Preserve the name in the source: ERK1/2 is a family, not a guessed MAPK3;
  NADPH oxidases are a family, not a guessed NOX1. ROS names chemical species, not a process.
  Do not resolve a family down to a guessed member. Preserve stated species in context; never
  invent a human ortholog for a species-specific gene with no human equivalent.
  `process` vs `pathological_process`: ordinary cell biology vs a disease process. Apoptosis and
  proliferation are `process` even in a cancer paper; tumorigenesis and metastasis are
  `pathological_process` even in a healthy tissue.

  Two categories are closed lists; use the exact token:
  endpoint (clinical, only with `predicts`/`stratifies`): {_menu(CLINICAL_ENDPOINTS)}
    "poor prognosis" is not an endpoint: use `predicts_worse` with overall_survival.
  endpoint (experimental phenotype; a treatment can cause these, so they also take
    increases/decreases): {_menu(EXPERIMENTAL_PHENOTYPES)}
    "fulvestrant reduced xenograft growth" -> decreases tumour_burden.

  Aspects: only an entity-like object (gene, chemical, family, mark, repeat, feature) may take an aspect.
  A process, pathological_process, disease, phenotype or endpoint is the object and takes none:
  "EGFR increases apoptosis" -> object=apoptosis, object_category=process, no aspect.

OBJECT ASPECT. Which property of an entity object changed. Empty for process/endpoint objects.
{_menu(ASPECT_INPUTS)}
  Write the word the paper uses. `degradation` is recorded as `abundance` with the sign adjusted in
  code, so say "increases degradation" if that is what the paper says rather than converting it yourself.

  "Stability" covers two different measurements, and you must say which. Does the claim say the protein
  folds better or worse, or that it lasts longer or shorter inside a cell?
    conformational_stability: how firmly it folds. ΔΔG, FoldX, Tm, melting/thermal/thermostability,
      "predicted to stabilize the protein", free energy of unfolding.
    conformational_dynamics: how much it moves. ΔΔSvib, ENCoM, normal-mode or molecular-dynamics
      analysis, "flexibilizing", RMSF. More dynamics means more flexible; write "rigidity" if the paper
      frames it that way and it is inverted in code.
    half_life: how long it lasts in a cell. cycloheximide chase, ubiquitination, proteasome inhibition
      (MG132), "stabilized EGFR and prevented its degradation", protein turnover.
  The first two are both structural and both in silico, and still different measurements from different
  tools: a variant can fold less well and move less. An entropy or a flexibility is dynamics, not
  stability. The listed words are examples of each concept, not strings that must appear. If the paper
  does not say which, use `half_life` only when it discusses amount or degradation; otherwise defer.

A tissue, organ or cell type is a setting, not an object. Never put one in the object slot of an
expression/abundance/activity claim; use the `tissue` or `cell_type` context slot instead.
  "EGFR induces apoptosis in spermatogenic cells" -> object=apoptosis, context.cell_type=spermatogenic cell
If the paper says only that something is expressed or present in a tissue, that is a claim: use
`present_in` with the tissue as the object and no aspect.
  "spleen, thymus and ovary expressed very high levels of EGFR" -> EGFR present_in spleen (+ thymus, ovary)
Same for a tumour type: "90% of SPNs harbor CTNNB1 mutations" -> CTNNB1 present_in solid-pseudopapillary
neoplasm. A tissue as the object never takes an aspect.

GENOMIC FEATURES. Write `<gene symbol> <feature type>` and nothing else: "EGFR intron 1", "MYC
promoter", "PIM1 enhancer". Keep the feature; which part of the gene is the claim. Do not pass the paper's
shorthand through:
  - use the gene symbol, not a protein alias ("MYC promoter", not "the p21 promoter"; "KLK3 promoter",
    not "the PSA promoter")
  - drop the article and surrounding prose, but keep the paper's own name for the region and put it last,
    after the feature type: "CCND1 enhancer enh2", "CCND1 promoter distal", "PIM1 enhancer E1". That
    trailing name is what separates one enhancer of a gene from another.
  - if the paper names a region with a private abbreviation and you cannot say which gene and which
    feature type it is (ERGE, TRE, a lab's internal label), defer it rather than inventing one.

CATEGORY BOUNDARIES. These four pairs are where the category is most often wrong:
  - a named tumour or illness is `disease` ("prostate adenocarcinoma", "Li-Fraumeni syndrome"); the
    process of becoming one is `pathological_process` ("tumorigenesis", "carcinogenesis").
  - a normal biological process is `process`; a process that is itself pathology is
    `pathological_process` ("genomic instability", "oxidative stress").
  - a specific named gene or protein is `gene`, even when the paper discusses its pathway or complex
    ("the mTOR pathway" is still about the gene mTOR). `family` is only for a group named as a group
    ("SMAD", "HDAC", "AP-1").
  - `feature` is a region of DNA belonging to a gene. Chromatin, nucleosomes and euchromatin are things,
    not regions, and belong in `entity`.

ENTITY STATE. Which form of the gene/protein is this claim about? Mutant and wild-type are different
actors and must not be conflated.
  functional, choose one:
    wild-type      the normal form
    mutant         a mutated form (give `variant` if the paper names one)
    null_loss      knocked out, deleted, lost
    overexpressed  present at forced/elevated levels
    general        the paper means the gene as a whole, or "EGFR mutations" as a class
    unknown        the paper is about some particular form and you cannot tell which

  State is the actor the claim is about, not the experiment that revealed it. When you invert a
  loss-of-function sentence, the claim is about the gene's normal form, so its state is `wild-type` or
  `general`, and the knockout goes in `context.perturbation`. Writing `null_loss` there records the
  perturbation a second time and a reader honouring both fields inverts the claim twice.
    "CCND1-null mice show defective mammary development" -> CCND1 [general] increases proliferation,
    context.perturbation = knockout.   Not CCND1 [null_loss].
  Use `null_loss` only when the claim is about the absent form and no inversion was applied. Entity
  state is part of a claim's identity: the same finding from a knockout paper and from an overexpression
  paper must land on one claim with two pieces of evidence.

  `general` and `unknown` are not interchangeable:
    "EGFR mutations shorten survival"        -> general   (a claim about the class)
    "EGFR activated MYC in these cells"    -> unknown   (some specific EGFR, unstated)
  `general` says the paper is generalising; `unknown` says you cannot tell. Never use `general` to mean
  "not stated", and do not reach for `general` because you cannot name the variant: "exon 19 mutations
  were predominantly destabilizing" is about a subset of mutants, so it is `mutant` with no variant, or a
  deferral.

  A claim whose subject and object are the same entity in the same state says nothing. If a variant
  affects the protein, the subject is the variant (state=mutant, with the variant named) and the object
  is the protein.

  Look before you answer. The form is often given once in the Methods or in a cell-line name (EGFR-null
  MEFs, an EGFR-null line, a knock-in mutant line) and never repeated. Use `inherited` provenance.
  variant: HGVS if the paper names one (e.g. p.Leu858Arg), else ""
  isoform: a naturally occurring form of the protein, e.g. isoform-alpha, AR-V7. Else "".
  protein_construct: a lab construct, a piece of the protein or the intact protein named to contrast with
           a piece: "DBD", "CTD", "AF-2", "delta283-595", "residues 294-393", "full-length". Else "".
  An isoform is a kind of the protein and inherits its biology; a construct is a part of it and does not.
  "The isolated kinase domain binds nucleosomes" is not evidence that EGFR binds nucleosomes.

QUANTIFIER. Only when the subject is a group ("EGFR mutations", "exon 19 variants", "these patients").
Omit it for a claim about one thing.
  all    every member: "all", "every", "invariably", "without exception"
  most   a majority or a tendency: "predominantly", "most", "generally", "the majority"
  some   a subset: "some", "a subset", "two variants", "in certain cases"
"Exon 19 mutations were predominantly destabilizing" is `most`; "two exon 19 variants were stabilizing" is
`some`. Both are true, and without the quantifier they would be stored as a direct contradiction. An
omitted quantifier means "not a group claim" and is never read as "all".

CERTAINTY. How strongly the paper asserts this claim. One of:
  demonstrated  the authors show it
  suggested     the data are consistent with it and the authors hedge ("suggests", "may")
  predicted     a computational or structural prediction, not a measurement
  hypothesized  proposed and untested
  Keep hedged claims; label them rather than dropping or upgrading them.

STUDY TYPE: {_menu(STUDY_TYPES)}
EVIDENCE TYPE: {_menu(EVIDENCE_TYPES)}
  Use `author_statement_prior` when the authors are restating someone else's result.

CONTEXT. Include a slot only if the paper supports it. An omitted slot means "the paper did not say",
not that the finding holds everywhere.
{_slot_menu()}

  Organism is required on a phenotype claim. Phenotypes resolve into a human-curated vocabulary, so
  "insulin resistance" in a mouse study is filed under the same identifier as the human phenotype; that
  makes mouse and human evidence comparable only if the species travels with the claim. If the paper
  states the species anywhere (the model system, the strain, the cell source), put it in.
{inherit}

EXPERIMENTS. A top-level array, each entry describing one run; claims point at them by index.
Quantitative values (n, effect, uncertainty, statistic) must appear verbatim inside that experiment's
`quote`. If you cannot quote the number, omit the field. Give an experiment its own `quote` only when the
numbers live in a different sentence from the claim's quote. A review restating someone else's finding has
no experiment; omit the reference.

QUOTE. Copy the supporting passage verbatim from the paper. The quote must let a later reader, without
the paper, tell which way the effect goes: extend it until it does. Quoting only "and L858R, T790M,
G719S and S768I in these tumours" from "Four activating variants were also detected..." leaves the claim
unverifiable because the word that proved it sits outside the quote. The quote need not contain the
predicate's word: "depletion of SOS1 protein led to increased EGFR binding" is the evidence for "SOS1
protein decreases EGFR binding". Quote the whole experiment, not a fragment. If the direction is only in
a number (a ΔΔG value, a fold-change), extend the quote to the sentence that says which way the number
goes. If the claim is the authors reporting someone else's result, the quote must include the citation
exactly as printed ("(11)", "[13-15]", "(Berger et al., 2005)", "Liu et al. (2025)"); that is how a
finding is told from a retelling. Do not add a citation that is not in the text; every marker is checked
against this quote.

Return JSON only. The shape below shows which keys exist, not which to emit; omit every key you cannot
fill from the paper.

{{"experiments": [{{"unit": "", "intervention": "", "control": "", "readout": "", "assay": "",
                   "timepoint": "", "n": null, "effect": "", "uncertainty": "", "statistic": "",
                   "quote": ""}}],
 "claims": [{{"subject": "", "predicate": "", "object": "",
   "subject_category": "", "object_category": "", "object_aspect": "",
   "subject_state": {{"functional": "", "variant": "", "isoform": "", "protein_construct": ""}},
   "object_state": {{"functional": ""}},
   "quote": "", "section": "", "study_type": "", "evidence_type": "", "quantifier": "",
   "certainty": "demonstrated|suggested|predicted|hypothesized",
   "context": {{"<slot>": {{"value": "", "provenance": "stated|inherited", "quote": ""}}}},
   "experiment": 0}}],
 "deferred": [{{"reason": "", "wanted": "", "quote": ""}}]}}

A minimal claim is legitimate and preferred where the paper supports no more:
{{"subject": "GRB2", "predicate": "increases", "object": "EGFR", "object_aspect": "degradation",
  "quote": "GRB2 overexpression accelerated EGFR degradation in these cells"}}

PAPER:
{text}
"""


# The direction auditor sees only a claim and the quote it came from, never the paper or the extractor's
# reasoning, so its judgement is independent.
DIRECTION_SYSTEM = (
    "You audit extracted scientific claims for one thing: direction. You are given a claim and the "
    "verbatim sentence it was drawn from, and nothing else. You did not extract these claims and you owe "
    "them no deference. Judge only what the quoted sentence says. When the sentence does not settle which "
    "entity acts on which, say so rather than guessing."
)

DIRECTION_PROMPT = """Check direction. Each claim below is shown with the verbatim sentence it was drawn
from. Judge only against that sentence. Two things can be wrong, and they are different:

  swapped: the subject and object are the wrong way round. "GRB2 degrades EGFR" written as
           "EGFR degrades GRB2". The effect goes the right way; the actors are reversed.

  wrong sign: the actors are right but the effect points the wrong way. "L861Q increases stability"
           where the sentence says L861Q is destabilizing. Nothing is swapped; the direction is inverted.

A claim can be fine on one and wrong on the other, so decide each separately.

Signs are most often wrong when the quoted sentence does not itself state the direction, so the test is
strict: does this sentence say which way it goes? If it does not, the claim belongs in "unsure". Do not
reason from what you know about the biology or from elsewhere in the paper; you cannot see the paper.

{rows}

Return JSON only: {{"swapped": [<index>, ...], "wrong_sign": [<index>, ...], "unsure": [<index>, ...]}}
An index may appear in at most one list. "unsure" is the right answer whenever the sentence does not
settle it; guessing is worse than abstaining."""


PROCESS_MENU_PROMPT = """One last question, about the process/phenotype terms you used as objects.

Each term below did not match an ontology term exactly, so here are the real candidate terms. For each
numbered term, choose the candidate that means the same thing as this paper uses it.

  - Answer with the candidate's letter, or "none".
  - "none" is the right answer whenever no candidate means the same thing. A near-miss is worse than no
    match: it silently files this claim under a different process.
  - Prefer the plain process over a "positive regulation of ..." or "negative regulation of ..." variant.
    Direction is recorded separately, so a regulation term would record it twice.
  - A closer label is not a better answer. Candidates come from several ontologies and NCIT has a
    near-verbatim label for almost everything. For an ordinary cell-biological process (proliferation,
    apoptosis, migration, cell cycle, metabolism, differentiation) the GO term is the right answer even
    when its label is worded differently, because GO is where every other such claim in this graph is
    filed: choose GO:0008283 ("cell population proliferation") over NCIT:C18081 for `cell proliferation`.
  - For a disease process (`tumorigenesis`, `carcinogenesis`, `metastasis`, `genomic instability`) the
    MESH candidate is the right answer; GO excludes disease processes. Prefer MESH over NCIT here.
  - Choose a MONDO or HP candidate only when the term is a named disease or a clinical phenotype rather
    than a process.

{rows}

Return JSON only: {{"choices": {{"0": "a", "1": "none", ...}}}}"""


ENTITY_MENU_PROMPT = """One more question, about entity names I could not resolve confidently.

Each name below matched something only weakly, usually because the paper uses an alias or an older
symbol. Here are the real candidates. For each numbered term, choose the one that is the thing this paper
means.

  - Answer with the candidate's letter, or "none".
  - "none" is often the right answer and is never penalised. Three traps:
      * a different organism's gene with the same symbol as a human gene
      * a near-miss molecule: the propionate ester of a hormone is not the hormone
      * a drug named after the thing: a "PROTAC AR-V7 degrader" is not AR-V7
  - You have the paper. The organism, the assay and the surrounding sentence decide this; a
    string-similarity score cannot.

{rows}

Return JSON only: {{"choices": {{"0": "a", "1": "none", ...}}}}"""


def _parse(txt: str, *, whole_paper: bool = True) -> dict:
    """Lenient JSON extraction. A failure raises with the response attached so the caller can defer it
    with evidence."""
    if not (txt or "").strip():
        raise DeferralError("model returned an empty response")
    hit = _refusal(txt)
    if hit:
        raise ApiUnavailable(f"the API refused ({hit!r}): {(txt or '').strip()[:200]}")
    m = _JSON.search(txt)
    if not m:
        if whole_paper and len((txt or "").strip()) <= 600:
            raise ApiUnavailable(
                f"the API returned a short non-JSON response, which is a service message rather than an "
                f"answer; the paper was not read: {(txt or '').strip()[:200]!r}")
        raise DeferralError(f"no JSON object in model response (first 300 chars): {txt[:300]!r}"
                            + _log_bad(txt, "nojson"))
    body = m.group(0)
    try:
        # strict=False permits raw control characters inside strings: quotes are copied verbatim from
        # papers, which contain hard line breaks and tabs, and asking the model to escape them would risk a
        # silently altered quote.
        return json.loads(body, strict=False)
    except Exception as e:
        rescued = _salvage_claims(body)
        if rescued is not None:
            rescued["_salvaged"] = f"{e}"
            return rescued
        raise DeferralError(
            f"model response is not valid JSON ({e}); len={len(txt)}, "
            f"salvage saw {_SALVAGE_SEEN[0]} decodable objects and kept none "
            f"(keys on the first: {_SALVAGE_KEYS[0]}); "
            f"head={body[:200]!r}, tail={body[-200:]!r}" + _log_bad(txt, "badjson")) from e


# Filled by `_salvage_claims` so a total failure can report what it saw.
_SALVAGE_SEEN: list[int] = [0]
_SALVAGE_KEYS: list = [[]]


def _salvage_claims(body: str) -> dict | None:
    """Recover the claim objects that did parse from a response whose JSON is broken as a whole, so one
    malformed claim does not cost the paper.

    Objects are decoded one at a time from the `claims` array. Only objects carrying a `subject` or
    `predicate` are kept, because a failed decode resumes at the next `{`, which may be a claim's nested
    `subject_state` or `context` block.
    """
    _SALVAGE_SEEN[0], _SALVAGE_KEYS[0] = 0, []
    i = body.find('"claims"')
    if i < 0 or (i := body.find("[", i)) < 0:
        return None
    dec = json.JSONDecoder(strict=False)
    out: list[dict] = []
    pos, n = i + 1, len(body)
    while pos < n:
        while pos < n and body[pos] in ", \t\r\n":
            pos += 1
        if pos < n and body[pos] == "]":         # end of the claims array; anything after is not a claim
            break
        j = body.find("{", pos)
        if j < 0:
            break
        try:
            obj, pos = dec.raw_decode(body, j)
        except ValueError:
            pos = j + 1
            continue
        if isinstance(obj, dict):
            _SALVAGE_SEEN[0] += 1
            if not _SALVAGE_KEYS[0]:
                _SALVAGE_KEYS[0] = sorted(obj)[:12]
            if "subject" in obj or "predicate" in obj:
                out.append(obj)
    if not out:
        # Fallback: scan the whole body for claim-shaped objects, ignoring array structure. Reached when the
        # damage is in the array scaffolding rather than in one element.
        pos = 0
        while (j := body.find("{", pos)) >= 0:
            try:
                obj, pos = dec.raw_decode(body, j)
            except ValueError:
                pos = j + 1
                continue
            if isinstance(obj, dict) and "subject" in obj and "predicate" in obj:
                out.append(obj)
    return {"claims": out, "deferred": []} if out else None


# Where to write a response that would otherwise be discarded. Off unless a path is set.
LOG_BAD_RESPONSES: str | None = None

# --- sticky menu decisions --------------------------------------------------------------------------
# A menu choice is a model judgement. So a surface term is decided once and every later paper reuses the
# decision. Only menu choices are recorded; exact label matches stay live so a better
# resolver is not overridden by a stale decision. The store is also the audit list of every identity
# judgement the model made.
PROCESS_DECISIONS: str | None = None
_DECISIONS: dict[str, dict] = {}


def load_decisions(path: str | None = None) -> int:
    """Load the sticky decision store. Idempotent; safe when the file does not exist yet."""
    global PROCESS_DECISIONS
    PROCESS_DECISIONS = path or PROCESS_DECISIONS
    if not PROCESS_DECISIONS or not Path(PROCESS_DECISIONS).exists():
        return 0
    for line in Path(PROCESS_DECISIONS).read_text().splitlines():
        if line.strip():
            try:
                d = json.loads(line)
                _DECISIONS[d["surface"]] = d["hit"]
            except Exception:
                continue                      # a corrupt line must not cost the whole store
    return len(_DECISIONS)


def _record_decision(surface: str, hit: dict) -> None:
    _DECISIONS[surface] = hit
    if not PROCESS_DECISIONS:
        return
    try:
        p = Path(PROCESS_DECISIONS)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a") as fh:
            fh.write(json.dumps({"surface": surface, "hit": hit}) + "\n")
    except Exception:
        pass                                  # an unwritable store degrades to in-memory, never fatal


def _log_bad(txt: str, tag: str) -> str:
    if not LOG_BAD_RESPONSES:
        return ""
    try:
        p = Path(LOG_BAD_RESPONSES) / f"badresponse_{tag}.txt"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(txt)
        return f" [full response saved to {p}]"
    except Exception:
        return ""


def _entity(surface: str, state: dict | None, category: str,
            process_map: dict[str, dict | None] | None = None,
            entity_map: dict[str, dict | None] | None = None,
            organism: str = "") -> EntityRef:
    """Surface string -> resolved EntityRef, or DeferralError. Grounding is deterministic; the state
    modifier is stripped first.

    A `process` object is resolved only through `process_map`, the result of the retrieve-then-choose
    pass: the general grounder misses most processes and types its hits as disease/phenotype/anatomy,
    which would slip past the spine's "a process takes no aspect" check.
    """
    st = EntityState(**{k: (state or {}).get(k, "") or ("unspecified" if k == "functional" else "")
                        for k in ("functional", "variant", "isoform", "protein_construct")})
    # The category decides both which resolver handles this and which namespaces may answer.
    category = (category or "").strip().lower()
    if category not in CATEGORIES:
        raise DeferralError(f"unknown or missing category {category!r}; choose a supported category")
    if category == "gene" and G.species_gene_collision(surface, organism):
        raise DeferralError(f"gene {surface!r} is a verified species-specific symbol that collides "
                            "with an unrelated human gene; use non_human_gene and preserve organism context")
    kind_hint = _path_for(category)
    ns = CATEGORY_NS[category] or None
    def checked(hit):
        if hit and ns and hit.get("curie", "").split(":", 1)[0] not in ns:
            raise DeferralError(f"identifier {hit.get('curie')!r} is outside owner for {category}")
        return hit
    # A closed-vocabulary token is an endpoint whichever category it arrived under; there is nothing to
    # ground.
    if kind_hint == "endpoint" or _norm(surface) in EXPERIMENTAL_PHENOTYPES \
            or _norm(surface) in CLINICAL_ENDPOINTS:
        return EntityRef.endpoint(surface)
    if kind_hint == "process":
        hit = checked((process_map or {}).get(_resolution_key(surface, category, organism))
                      or (process_map or {}).get(_norm(surface)))
        if not hit:
            raise DeferralError(f"process {surface!r} matched no ontology term (and no candidate was "
                                "accepted)")
        # The kind comes from the resolver, not the slot: GO's cellular_component branch holds things
        # (`nucleosome` is GO:0000786), and those may take an aspect.
        return EntityRef(curie=hit["curie"], label=surface.strip(),
                         kind=hit.get("kind") or "process", state=st)
    if kind_hint == "nonhuman_gene":
        # Species-table lookup only: it vetoes any human-resolvable symbol and requires a non-human organism,
        # so a human gene cannot arrive at an NCBIGene id. Every refusal defers with its reason.
        try:
            hit = G.nonhuman_gene_lookup(_strip_state(surface), organism)
        except LookupError as e:
            raise DeferralError(f"non-human gene {surface!r}: {e}")
        if not hit:
            raise DeferralError(f"non-human gene {surface!r} is not in the {organism or '?'} table "
                                "(symbol miss, not a veto)")
        return EntityRef(curie=hit["curie"], label=surface.strip(), kind="entity", state=st)
    feat = _feature(surface, state) if category == "feature" else None
    if feat:
        return feat.model_copy(update={"state": st})
    bare = _strip_state(surface)
    hit = G.ground_curie(bare, namespaces=ns) or G.ground_curie(surface or "", namespaces=ns)
    if not hit:
        # Repeat/TE families last.
        rep = (G.resolve_repeat(surface) or G.resolve_repeat(bare)) if category == "repeat" else None
        if rep:
            return EntityRef(curie=rep["curie"], label=surface.strip(), kind="repeat_family",
                             feature_tier=rep["tier"], state=st)
        # The reader's verdict on a weak (0.40-0.70) match, decided in pass 3 with the paper in view.
        # Consulted only after every deterministic route has failed, so a menu choice never overrides a
        # confident grounding. Keys are normalised on both sides (`_entity_surfaces` uses `_norm`).
        chosen = (entity_map or {}).get(_norm(bare)) or (entity_map or {}).get(_norm(surface))
        if chosen:
            checked(chosen)
            return EntityRef(curie=chosen["curie"], label=surface.strip(),
                             kind=chosen.get("kind") or "entity", state=st)
        raise DeferralError(f"entity {surface!r} did not ground to any identifier")
    checked(hit)
    return EntityRef(curie=hit["curie"], label=surface.strip(), kind=hit["kind"], state=st)


def _resolution_key(surface: str, category: str, organism: str = "") -> str:
    return json.dumps([_norm(surface), category, organism], separators=(",", ":"))


def _norm(s: str) -> str:
    return (s or "").strip().lower()


# The state itself is kept in the claim's `state` block. Modifiers appear on either side of the noun.
_STATE_WORDS = (r"wild[- ]?type|wt|mutant[s]?|mut|mutation[s]?|mutated|null|knockout|ko|"
                r"over[- ]?expressed|over[- ]?expression|temperature[- ]sensitive|ts|"
                r"variant[s]?|allele[s]?|deficient|deleted|truncated|hotspot|"
                r"missense|nonsense|frameshift|somatic|germline|"
                # sequence-variant nouns
                r"m?SNV[s]?|SNP[s]?|polymorphism[s]?|substitution[s]?|indel[s]?")
_STATE_PREFIX = re.compile(rf"^(?:{_STATE_WORDS})\s+", re.I)
_STATE_SUFFIX = re.compile(rf"\s+(?:{_STATE_WORDS})$", re.I)

# A named variant is state, not part of the entity's name, so the variant token is removed before the
# string reaches a gene resolver. Shapes stripped, all anchored to the end so a gene whose symbol merely
# looks variant-like is untouched: G719S / T790M (one-letter AA + position + one-letter AA), Arg521Lys /
# Leu858Arg (three-letter form), p.Leu858Arg / c.375G>A (HGVS with prefix), E746* / L747fs / E746-A750del
# (nonsense, frameshift, deletion), (rs2227983) (a dbSNP id in parentheses).
_AA3 = r"Ala|Arg|Asn|Asp|Cys|Gln|Glu|Gly|His|Ile|Leu|Lys|Met|Phe|Pro|Ser|Thr|Trp|Tyr|Val|Ter"
_PAREN_TAIL = re.compile(r"\s*\([^()]{1,40}\)\s*$")
_VARIANT_TAIL = re.compile(
    rf"""(?:\s+|\s*\()\s*(?:          # a boundary is required, or the pattern would consume the tail of
                                       # a gene symbol that looks like a variant token
          (?:p\.|c\.)\S+                                   # explicit HGVS
        | rs\d+                                             # dbSNP
        | (?:{_AA3})\d+(?:{_AA3}|fs|Ter|\*)?                # Arg521Lys, Glu746Ter
        | [A-Z]\d{{1,4}}(?:[A-Z]|fs|\*|del|dup|ins)?          # G719S, E746*, L747fs
        | [A-Z]?\d{{1,4}}[-–]\d{{1,4}}(?:del|dup|ins)          # R265-71del
    )\s*\)?\s*$""", re.I | re.X)


def _strip_state(surface: str) -> str:
    """Peel state modifiers off both ends, repeatedly, since they stack ("EGFR temperature-sensitive
    mutant" -> "EGFR"). Never strips to nothing: a surface that is all modifier ("mutant") is returned
    unchanged so grounding fails on the original string.
    """
    s = (surface or "").strip()
    for _ in range(4):
        # A trailing parenthetical is a gloss, not part of the name: "CDKN2A (p16)", "EGFR Arg521Lys
        # (rs2227983)". Bounded in length so a parenthesised clause is left alone.
        nxt = _PAREN_TAIL.sub("", s).strip()
        nxt = _VARIANT_TAIL.sub("", _STATE_SUFFIX.sub("", _STATE_PREFIX.sub("", nxt))).strip()
        if nxt == s or not nxt:
            break
        s = nxt
    return s or (surface or "").strip()


# Longest first, so "androgen response element" is tried before "response element".
_FEATURE_WORDS = sorted(SO_FEATURE_TYPES, key=len, reverse=True)
_GENERIC_MARK = re.compile(r"\b(sequences?|regions?|elements?)\b$", re.I)


def _feature(surface: str, state: dict | None) -> EntityRef | None:
    """`EGFR intron 1` -> a feature node; `EGFR intronic sequences` -> EGFR qualified by SO:0000188.

    Returns None when the string names no feature type, so the caller falls through to ordinary grounding.
    Tried before the general grounder, which would fuzzy-match the gene and drop the feature. A designator
    earns a node; without one ("the MYC promoter", "MYC intronic sequences") the gene carries an SO
    qualifier, which is Biolink's convention.
    """
    s = (surface or "").strip()
    if not s:
        return None
    low = s.lower()
    for word in _FEATURE_WORDS:
        # `s` for plurals, `ic` for adjectival forms ("intronic sequences"); both mean the type generically.
        m = re.search(rf"(?<![a-z]){re.escape(word)}(?:s|ic)?(?![a-z])", low)
        if not m:
            continue
        before, after = s[:m.start()].strip(" '\"-,"), s[m.end():].strip(" '\"-,")
        plural = low[m.start():m.end()].endswith("s") and not word.endswith("s")
        if " of " in f" {after} ":                       # "intron 1 of EGFR", "promoter of MYC"
            desig, _, gene = after.partition(" of ")
            gene = gene.strip() or before
        else:
            gene, desig = before, after
        gene = re.sub(r"^(the|human|murine|mouse)\s+", "", gene.strip(), flags=re.I)
        gene = re.sub(r"\b(gene|locus|promoter|intronic|genomic)\b", "", gene, flags=re.I).strip()
        if not gene:
            return None                  # no parent named: not a sub-genic feature of anything
        hit = G.ground_curie(gene)
        if not hit:
            raise DeferralError(
                f"{surface!r} names a {word} of {gene!r}, but {gene!r} did not ground; a feature's "
                "identity is anchored to its parent, so there is nothing to attach it to")
        desig = _GENERIC_MARK.sub("", desig).strip(" '\"-,")
        generic = plural or not desig or len(desig) > 40
        return EntityRef.feature(hit["curie"], SO_FEATURE_TYPES[word], designator="" if generic else desig,
                                 tier="generic" if generic else "designator", label=s)
    return None



def _category_of(rc: dict, side: str) -> str:
    """The pass-1 category for one side of a claim. `*_category` is what the reader says the thing is and
    only chooses which reference work is opened; `kind` is derived from the identifier found there and is
    the only one that reaches the graph."""
    return (rc.get(f"{side}_category") or "").strip().lower()


def _path_for(category: str) -> str:
    """Which resolver handles a pass-1 category: 'process' | 'endpoint' | 'entity' | 'nonhuman_gene'.

    Categories pick an owner vocabulary; paths pick a resolver mechanism, so there are more categories than
    paths. Unknown or absent -> 'entity', so a model that ignores the field still resolves.
    """
    return CATEGORY_PATH.get((category or "").strip().lower(), "entity")


def _process_surfaces(raw_claims: list[dict], skip: set[int]) -> list[tuple[str, str]]:
    """Distinct (surface, category) pairs worth resolving as processes, in first-seen order, from both
    sides of every claim.

    The category travels with the surface because `process` (GO) and `pathological_process` (MeSH) have
    different owners, and `_entity` resolves a process only through `process_map`, so a process surface
    missing here could not resolve at all.
    """
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for i, rc in enumerate(raw_claims):
        if i in skip:
            continue
        for key, side in (("subject", "subject"), ("object", "object")):
            category = _category_of(rc, side)
            if _path_for(category) != "process":
                continue
            s = _norm(rc.get(key, ""))
            if s and s not in seen:
                seen.add(s)
                out.append((s, category))
    return out


def _entity_surfaces(raw_claims: list[dict], skip: set[int]) -> list[tuple[str, str]]:
    """Distinct entity surfaces deterministic grounding could not resolve, as (surface, category) pairs.

    Resolvability is asked through `_entity` under the surface's own category, so pass 3 never re-decides
    a confident match and the menu stays short.
    """
    out: list[str] = []
    seen: set[str] = set()
    for i, rc in enumerate(raw_claims):
        if i in skip:
            continue
        for key, side in (("subject", "subject"), ("object", "object")):
            category = _category_of(rc, side)
            if _path_for(category) != "entity":
                continue
            surface = _norm(_strip_state(rc.get(key, "")))
            if not surface or surface in seen:
                continue
            try:
                _entity(surface, None, category)
            except DeferralError:
                seen.add(surface)
                out.append((surface, category))         # genuinely unresolved -> it earns a menu
            except Exception:
                continue
    return out


def _claim_organism(rc: dict, paper_organism: str = "") -> str:
    """This CLAIM's organism context, raw ('C. elegans' or 'NCBITaxon:6239'), falling back to the paper-level
    organism. Feeds the non_human_gene species-table pick; the lookup itself resolves the text through the
    same deterministic table the context resolver uses, so no second parser here.
    """
    v = ((rc.get("context") or {}).get("organism") or "")
    v = v.get("value") if isinstance(v, dict) else v
    return (str(v or "").strip()) or paper_organism


def _corpus_organism(raw_claims: list[dict]) -> str:
    """The organism this paper's claims are about, as an NCBITaxon CURIE, or '' when it does not say.

    A hint to the candidate generator, never defaulted to human: an absent organism leaves the grounder's
    human-only stance as it is rather than asserting a species the paper never named.
    """
    seen: dict[str, int] = {}
    for rc in raw_claims:
        v = ((rc.get("context") or {}).get("organism") or "")
        v = v.get("value") if isinstance(v, dict) else v
        if isinstance(v, str) and v.startswith("NCBITaxon:"):
            seen[v] = seen.get(v, 0) + 1
    if len(seen) != 1:              # no organism, or a mixed-organism paper -> no hint, not a guess
        return ""
    return next(iter(seen))


def _render_menu(menus: list[tuple[str, list[dict]]]) -> str:
    rows = []
    for i, (surface, cands) in enumerate(menus):
        rows.append(f'TERM {i}: "{surface}"')
        for letter, c in zip(string.ascii_lowercase, cands):
            defn = (c.get("definition") or "").replace("\n", " ")[:180]
            rows.append(f"   {letter}) {c['curie']}  {c['label']}" + (f" — {defn}" if defn else ""))
    return "\n".join(rows)


async def _resolve_entities(session, surfaces: list[tuple[str, str]] | list[str],
                            organism: str = "") -> tuple[dict, list[str]]:
    """Retrieve-then-choose for entities, on the same session as the process menu in pass 3.

    Only surfaces that failed `ground_curie` reach here, the candidates are the grounder's 0.40-0.70 band
    (see `grounding.entity_candidates`), and the menu is owner-filtered like every other path that can
    return an identifier. A rejected menu defers. Accepts (surface, category) pairs; bare strings ask
    across every namespace, which is only correct when no category is known.
    """
    resolved: dict[str, dict | None] = {}
    notes: list[str] = []
    if not surfaces:
        return resolved, notes
    pairs = [(s, "") if isinstance(s, str) else (s[0], s[1]) for s in surfaces]
    menus = []
    for surface, category in pairs:
        prior = _DECISIONS.get("entity::" + _resolution_key(surface, category, organism))
        if prior:
            resolved[surface] = dict(prior, chosen_by="sticky")
            notes.append(f"entity {surface!r}: reused earlier decision {prior['curie']}")
            continue
        ns = CATEGORY_NS.get((category or "").strip().lower()) or None
        cands = await asyncio.to_thread(G.entity_candidates, surface, organism, namespaces=ns)
        if cands:
            menus.append((surface, cands))
        else:
            notes.append(f"entity {surface!r}: no candidates in the 0.40-0.70 band")
    if not menus:
        return resolved, notes
    try:
        got = _parse(await session.ask(ENTITY_MENU_PROMPT.format(rows=_render_menu(menus))),
                     whole_paper=False)
    except DeferralError as e:
        for surface, _ in menus:
            notes.append(f"entity {surface!r}: menu pass failed ({e})")
        return resolved, notes
    choices = got.get("choices") or {}
    for i, (surface, cand_list) in enumerate(menus):
        pick = str(choices.get(str(i), choices.get(i, "none"))).strip().lower()
        idx = string.ascii_lowercase.find(pick) if len(pick) == 1 else -1
        if idx < 0 or idx >= len(cand_list):
            notes.append(f"entity {surface!r}: reader rejected all {len(cand_list)} candidates "
                         f"(answered {pick!r})")
            continue
        hit = dict(cand_list[idx], chosen_by="menu")
        resolved[surface] = hit
        _record_decision("entity::" + _resolution_key(surface, next(cat for surf, cat in pairs if surf == surface), organism), hit)
        notes.append(f"entity {surface!r}: reader chose {hit['curie']} ({hit['label']})")
    return resolved, notes


async def _resolve_processes(session, surfaces: list[tuple[str, str]] | list[str],
                             ) -> tuple[dict[str, dict | None], list[str]]:
    """Two-step resolution of process objects: an exact ontology match is taken without asking; anything
    else gets a menu of retrieved CURIEs decided by the model with the paper in context. The model picks a
    letter, never types an identifier, and "none" routes to deferral.
    """
    resolved: dict[str, dict | None] = {}
    notes: list[str] = []
    if not surfaces:
        return resolved, notes

    # A bare string means "no category stated", so both process owners stay reachable.
    pairs: list[tuple[str, str]] = [(s, "") if isinstance(s, str) else (s[0], s[1]) for s in surfaces]
    ns_of: dict[str, tuple[str, ...] | None] = {
        s: (CATEGORY_NS.get(cat) or None) if cat else None for s, cat in pairs}
    surfaces = [s for s, _ in pairs]

    # An exact label match is taken silently; a synonym match goes to the menu. A term already decided is
    # not re-decided, checked before any lookup.
    pending = []
    for s in surfaces:
        prior = _DECISIONS.get("process::" + _resolution_key(s, ",".join(ns_of.get(s) or ())))
        if prior:
            resolved[s] = dict(prior, chosen_by="sticky")
            notes.append(f"process {s!r}: reused earlier decision {prior['curie']}")
        else:
            pending.append(s)
    if not pending:
        return resolved, notes

    exact = await asyncio.gather(*(asyncio.to_thread(G.resolve_process, s, ns_of.get(s))
                                   for s in pending))
    todo: list[tuple[str, dict | None]] = []
    for s, hit in zip(pending, exact):
        if hit and hit.get("match") == "label" and not hit.get("regulation_term_kept"):
            resolved[s] = dict(hit, chosen_by="exact_label")
        else:
            todo.append((s, hit))
    if not todo:
        return resolved, notes

    cands = await asyncio.gather(*(asyncio.to_thread(G.process_candidates, s, 8, ns_of.get(s))
                                   for s, _ in todo))
    menus: list[tuple[str, list[dict]]] = []
    for (s, hit), c in zip(todo, cands):
        # The synonym hit leads its own menu.
        if hit:
            c = [dict(hit, definition=hit.get("definition", ""))] + \
                [x for x in c if x["curie"] != hit["curie"]]
        if c:
            menus.append((s, c))
        else:
            resolved[s] = None
            notes.append(f"process {s!r}: no exact match and no candidates retrieved — the ontologies "
                         "lookup did not establish whether an appropriate term exists")
    if not menus:
        return resolved, notes

    try:
        got = _parse(await session.ask(PROCESS_MENU_PROMPT.format(rows=_render_menu(menus))),
                     whole_paper=False)
    except DeferralError as e:
        for s, _ in menus:
            resolved[s] = None
            notes.append(f"process {s!r}: menu pass failed ({e})")
        return resolved, notes

    choices = got.get("choices") or {}
    for i, (surface, cand_list) in enumerate(menus):
        pick = str(choices.get(str(i), choices.get(i, "none"))).strip().lower()
        idx = string.ascii_lowercase.find(pick) if len(pick) == 1 else -1
        if idx < 0 or idx >= len(cand_list):
            resolved[surface] = None
            notes.append(f"process {surface!r}: reader rejected all {len(cand_list)} candidates "
                         f"(answered {pick!r})")
            continue
        # Enforced here, not only asked for in the prompt: a chosen `positive/negative regulation of X`
        # would encode direction twice. The kind comes from the CURIE, since the menu interleaves GO, HP,
        # MONDO and NCIT and a reader may pick a MONDO disease for `mammary carcinoma`.
        chosen = cand_list[idx]
        hit = await asyncio.to_thread(
            G.demote_regulation_term,
            dict(chosen, kind=G.kind_from_curie(chosen.get("curie", ""), default="process"),
                 chosen_by="menu"))
        resolved[surface] = hit
        _record_decision("process::" + _resolution_key(surface, ",".join(ns_of.get(surface) or ())), hit)
        notes.append(f"process {surface!r}: chose {hit['curie']} ({hit.get('label')}) from a menu of "
                     f"{len(cand_list)}")
    return resolved, notes


def _context(raw: dict, doc_type: str, *, phenotype: bool = False,
             paper_organism: str = "") -> tuple[Context, list[str]]:
    """Resolve each declared slot. Unresolvable slots are dropped and recorded as notes, never guessed; a
    dropped slot means 'the paper did not say'.

    Organism is backfilled on a phenotype claim only, as a backstop for the prompt's requirement: a
    phenotype resolves into HP, a human-curated vocabulary, so the species must travel with the claim. The
    backfill fires only when the whole paper names one organism, is recorded as `inherited`, and obeys
    `inheritance_allowed`, so a review never inherits.
    """
    slots, notes = {}, []
    allow_inherit = inheritance_allowed(doc_type)
    for name, spec in (raw or {}).items():
        if name not in CONTEXT_SLOTS:
            notes.append(f"unknown context slot {name!r}")
            continue
        val = (spec or {}).get("value", "")
        prov = ((spec or {}).get("provenance") or "stated").strip().lower()
        if prov == "inherited" and not allow_inherit:
            notes.append(f"{name}: inherited context refused for doc_type={doc_type}")
            continue
        hit = G.resolve_context_value(name, val)
        if not hit:
            notes.append(f"{name}: {val!r} did not resolve")
            continue
        slots[name] = ContextValue(value=hit["value"], label=hit.get("label", val), provenance=prov,
                                   quote=(spec or {}).get("quote", ""))
    if phenotype and "organism" not in slots and paper_organism and allow_inherit:
        slots["organism"] = ContextValue(value=paper_organism, label=paper_organism,
                                         provenance="inherited", quote="")
        notes.append(f"organism: backfilled {paper_organism} from the paper (phenotype claim)")
    return Context(slots=slots), notes


def _experiment_for(rc: dict, got: dict) -> dict | None:
    """Resolve a claim's experiment, whether it points at the shared array or carries one inline."""
    ref = rc.get("experiment")
    if isinstance(ref, dict):
        return ref
    if isinstance(ref, bool) or ref is None:
        return None
    try:
        idx = int(ref)
    except (TypeError, ValueError):
        return None
    shared = got.get("experiments")
    if not isinstance(shared, list) or not (0 <= idx < len(shared)):
        return None                      # an index pointing nowhere is a deferral's worth of nothing
    return shared[idx] if isinstance(shared[idx], dict) else None


def _experiment(raw: dict, source_ref: int) -> Experiment | None:
    """Build an Experiment under the quotable-or-null rule: a value that is not in the quote is dropped."""
    if not raw or not any((raw.get(k) or "") for k in ("unit", "intervention", "assay", "readout")):
        return None
    q = raw.get("quote") or ""
    kw = {k: (raw.get(k) or "") for k in
          ("unit", "intervention", "control", "readout", "assay", "timepoint",
           "effect", "uncertainty", "statistic")}
    for f in ("effect", "uncertainty", "statistic"):
        if kw[f] and kw[f] not in q:
            kw[f] = ""
    n = raw.get("n")
    if n is not None and str(n) not in q:
        n = None
    # The id is derived from the content, never asked of the model.
    ident = hashlib.sha256(json.dumps({"q": q, "n": n, **kw}, sort_keys=True).encode()).hexdigest()[:10]
    return Experiment(experiment_id=f"E{source_ref}.{ident}", source_ref=source_ref, quote=q, n=n, **kw)


async def extract_paper(text: str, *, source_ref: int, source_label: str = "", field: str,
                        doc_type: str = "primary_research", model: str = EXTRACT_MODEL,
                        direction_pass: bool = True, repair: bool = True,
                        repair_model: str = llm.SONNET,
                        raw_extraction: dict | None = None) -> dict:
    """Read, ground and repair a paper. raw_extraction replays a saved reader output for audits.

    Replayed input still undergoes the same direction, grounding, evidence and repair checks.
    The returned repair audit preserves original claims, corrections and explicit outcomes.
    """
    from dnhacksbio.litmap.repair import repair_claims, quote_supported
    from dnhacksbio.litmap.lexicon_supplement import SUPPLEMENT, VERSION as LEXICON_VERSION, supplement_lookup, supplement_candidates

    def supplement_category(term):
        prefix = term.curie.split(":", 1)[0]
        if prefix == "GO":
            return "cellular_component" if term.kind == "entity" else "process"
        return next(category for category, spec in CATEGORIES.items() if prefix in spec["ns"])

    supplement_menu = [{**asdict(term), "category": supplement_category(term)} for term in SUPPLEMENT]
    claims, deferrals, experiments, warnings = [], [], [], []
    process_map, emap, pnotes = {}, {}, []
    failures = []
    seen_experiments = set()

    def defer(reason, raw, quote=""):
        deferrals.append(Deferral(source_ref=source_ref, reason=str(reason)[:2000],
            raw=raw if isinstance(raw, dict) else {"value": str(raw)}, quote=str(quote or ""),
            extractor=model, prompt_version=PROMPT_VERSION))

    if raw_extraction is None:
        _tick(source_ref, f"pass 1 START ({len(text):,} chars)")
        async with llm.Session(system=SYSTEM, model=model, effort="medium", max_turns=6,
                               thinking=bool(TRACE)) as session:
            answer = ""
            for attempt in range(3):
                cap = {}
                answer = await (session.ask(build_prompt(field, doc_type, text), capture=cap)
                                if TRACE else session.ask(build_prompt(field, doc_type, text)))
                _traced(source_ref, "pass1", cap, answer)
                if (answer or "").strip():
                    break
                await asyncio.sleep(2 + 3 * attempt)
            if not (answer or "").strip():
                raise ApiUnavailable(f"three empty reader responses for ref {source_ref}")
            try:
                got = _parse(answer)
            except DeferralError as exc:
                defer(f"pass 1 failed: {exc}", {})
                return {"claims": [], "experiments": [], "deferrals": deferrals,
                        "processes": {}, "process_notes": [], "warnings": [], "repair_audit": {},
                        "stats": {"raw": 0, "kept": 0, "deferred": 1, "pass1_failed": True}}
            if session.truncated:
                defer("pass 1 truncated; paper extraction is incomplete", {})
    else:
        got = raw_extraction
    if got.get("_salvaged"):
        defer("pass 1 partially recovered from invalid JSON; paper extraction is incomplete", {})
    raw_claims = [r for r in (got.get("claims") or []) if isinstance(r, dict)]
    paper_org = _corpus_organism(raw_claims)
    refs = A.parse_references(text) or A.parse_references_author_year(text) or {}
    superscript_ok = not A.uses_bracket_citations(text)
    glued_ok = superscript_ok and A.uses_glued_superscripts(text, refs)

    # Group identical lookups by owner and species, but never share a model's contextual judgment
    # across papers. Failed terms remain eligible for a corrected name/category in repair.
    lookup_tasks = {}
    candidate_tasks = {}
    async def resolve(rc):
        org = _claim_organism(rc, paper_org)
        for side in ("subject", "object"):
            surface, category = rc.get(side, ""), _category_of(rc, side)
            key = _resolution_key(surface, category, org)
            if _path_for(category) == "process":
                if key not in lookup_tasks:
                    lookup_tasks[key] = asyncio.create_task(asyncio.to_thread(
                        G.resolve_process, surface, CATEGORY_NS.get(category)))
                hit = await lookup_tasks[key]
                # Exact labels and reviewed supplemental aliases resolve immediately. Other
                # ontology synonyms can generalize a finding: repair chooses their canonical label.
                if hit and hit.get("match") == "label" and not hit.get("regulation_term_kept"):
                    process_map[key] = hit

    def build(rc, reader):
        if not quote_supported(rc.get("quote", ""), text):
            raise DeferralError("quote does not match the source text; restore the verbatim passage")
        rc_org = _claim_organism(rc, paper_org)
        subj = _entity(rc.get("subject", ""), rc.get("subject_state"),
                       _category_of(rc, "subject"), process_map, entity_map=emap,
                       organism=rc_org)
        obj = _entity(rc.get("object", ""), rc.get("object_state"),
                      _category_of(rc, "object"), process_map, entity_map=emap,
                      organism=rc_org)
        is_phen = "HP:" in (subj.curie or "") or "HP:" in (obj.curie or "")
        ctx, notes = _context(rc.get("context"), doc_type, phenotype=is_phen,
                              paper_organism=paper_org)
        pred = (rc.get("predicate") or "").strip().lower()
        # `relation_class` and `polarity` are derived from the predicate.
        spine = ClaimSpine(subject=subj, predicate=pred, object=obj,
                            object_aspect=rc.get("object_aspect") or "")
        exp = _experiment(_experiment_for(rc, got), source_ref)
        if exp and (rc.get("study_type") == "review_statement"):
            exp = None                      # a restatement has no experiment of its own
        quote = rc.get("quote") or ""

        # Whose finding is this: the model's call, made with the paper in context.
        cites = A.cited_sources(quote, refs, source_ref, superscript=superscript_ok, glued=glued_ok)
        verdict = A.classify(rc.get("evidence_type") or "")
        cert = A.classify_certainty(rc.get("certainty") or "")
        if verdict.value == A.PRIOR and exp:
            # A restated result is not this paper's experiment to report; drop it and record why.
            notes.append("experiment dropped: a restated finding has no experiment of its own")
            exp = None
        if exp and not quote_supported(exp.quote, text):
            raise DeferralError("experiment quote does not occur in source; restore its source passage")
        ev = Evidence(claim_id=spine.claim_id(), source_ref=source_ref,
                       source_label=source_label,
                       experiment_id=exp.experiment_id if exp else None,
                       quote=quote, section=rc.get("section") or "",
                       predicate_said=pred,
                       evidence_type=(rc.get("evidence_type") or "unspecified"),
                       study_type=(rc.get("study_type") or "unspecified"),
                       attribution=verdict.value, attribution_basis=verdict.basis,
                       attribution_agreed=verdict.agreed_with_model,
                       quantifier=(rc.get("quantifier") or ""),
                       certainty=cert.value, certainty_basis=cert.basis,
                       certainty_agreed=cert.agreed_with_model,
                       cites=[c.sid for c in cites], cite_markers=[c.marker for c in cites],
                       context=ctx, extractor=reader, prompt_version=PROMPT_VERSION)
        return Claim(spine=spine, mechanism=rc.get("mechanism") or "", evidence=[ev]), exp, notes

    async def validate(rc):
        if rc.get("experiment") is not None and not isinstance(rc["experiment"], dict):
            return "repair must provide an inline source-supported experiment or omit it; numeric experiment pointers are not accepted"
        if not quote_supported(rc.get("quote", ""), text):
            return "quote must be actual source text (ordered ellipsis-separated spans are allowed)"
        await resolve(rc)
        try:
            build(rc, repair_model)
        except (DeferralError, ValueError, TypeError, KeyError) as exc:
            suggestions = []
            for side in ("subject", "object"):
                category, surface = _category_of(rc, side), rc.get(side, "")
                if category == "gene" and _claim_organism(rc, paper_org):
                    try:
                        nonhuman = await asyncio.to_thread(G.nonhuman_gene_lookup, surface,
                                                            _claim_organism(rc, paper_org))
                    except LookupError:
                        nonhuman = None
                    if nonhuman:
                        suggestions.append({"side": side, "label": surface,
                                            "category": "non_human_gene",
                                            "definition": "Verified gene in the stated species table; preserve organism context"})
                if category in CATEGORIES:
                    suggestions.extend({"side": side, "label": candidate["label"],
                                        "category": candidate["category"], "definition": candidate["definition"],
                                        "match": candidate["match"]}
                                       for candidate in supplement_candidates(surface, CATEGORY_NS[category]))
                reviewed = supplement_lookup(surface)
                if reviewed:
                    entry = next(t for t in supplement_menu if t["curie"] == reviewed["curie"])
                    suggestions.append({"side": side, "label": entry["label"],
                                        "category": entry["category"], "definition": entry["definition"]})
                if category not in CATEGORIES:
                    continue
                key = _resolution_key(surface, category, _claim_organism(rc, paper_org))
                # An exact-search synonym can be the best contextual option even when it must
                # not be accepted automatically. Keep it ahead of broad search alternatives.
                if key in lookup_tasks:
                    exact_candidate = await lookup_tasks[key]
                    if exact_candidate:
                        suggestions.append({"side": side, "label": exact_candidate["label"],
                                            "category": category,
                                            "definition": exact_candidate.get("definition", ""),
                                            "match": exact_candidate.get("match", "")})
                if key not in candidate_tasks:
                    if _path_for(category) == "process":
                        candidate_tasks[key] = asyncio.create_task(asyncio.to_thread(
                            G.process_candidates, surface, 8, CATEGORY_NS[category]))
                    elif _path_for(category) == "entity":
                        candidate_tasks[key] = asyncio.create_task(asyncio.to_thread(
                            G.entity_candidates, surface, _claim_organism(rc, paper_org),
                            namespaces=CATEGORY_NS[category]))
                if key in candidate_tasks:
                    candidates = await candidate_tasks[key]
                    suggestions.extend({"side": side, "label": c["label"], "definition": c.get("definition", "")}
                                       for c in candidates)
            return str(exc) + ("; retrieved candidate names (choose only if source meaning matches): "
                               + json.dumps(suggestions) if suggestions else "")
        return None

    def keep(rc, reader):
        claim, exp, notes = build(rc, reader)
        claims.append(claim)
        if exp and exp.experiment_id not in seen_experiments:
            seen_experiments.add(exp.experiment_id)
            experiments.append(exp)
        warnings.extend({"reason": n, "raw": rc, "claim_id": claim.spine.claim_id()} for n in notes)

    _tick(source_ref, f"pass 1 done — {len(raw_claims)} raw claims")
    direction = {}
    if direction_pass and raw_claims:
        rows = []
        for i, c in enumerate(raw_claims):
            asp = str(c.get("object_aspect") or "").strip().lower().replace(" ", "_")
            pred = str(c.get("predicate") or "")
            rule = ASPECT_REWRITES.get(asp)
            if rule:
                asp, _, flip = rule
                canon = canonical_predicate(pred)
                if flip and canon:
                    pred = invert_predicate(canon) or canon
            rows.append(f"[{i}] subject={c.get('subject')!r} predicate={pred!r} object={c.get('object')!r}"
                        f" [{asp}]\nquote: {c.get('quote', '')}")
        _tick(source_ref, "direction audit START (Sonnet)")
        async with llm.Session(system=DIRECTION_SYSTEM, model=repair_model, effort="medium") as audit_s:
            try:
                audit = _parse(await audit_s.ask(DIRECTION_PROMPT.format(rows="\n".join(rows))),
                               whole_paper=False)
                for key in ("swapped", "wrong_sign", "unsure"):
                    for i in audit.get(key) or []:
                        if str(i).isdigit():
                            direction[int(i)] = "direction audit: " + key
            except DeferralError as exc:
                direction = {i: f"direction audit failed: {exc}" for i in range(len(raw_claims))}

    _tick(source_ref, "grounding START")
    await asyncio.gather(*(resolve(rc) for rc in raw_claims))
    for i, rc in enumerate(raw_claims):
        reason = direction.get(i)
        if not reason:
            try:
                keep(rc, model)
            except (DeferralError, ValueError, TypeError, KeyError) as exc:
                reason = str(exc)
        if reason:
            failures.append({"id": f"claim:{i}", "raw": rc, "reason": reason})
    for i, d in enumerate(got.get("deferred") or []):
        d = d if isinstance(d, dict) else {"reason": str(d)}
        failures.append({"id": f"reader:{i}", "raw": d,
                         "reason": "reader deferred: " + str(d.get("reason", ""))})

    repaired = {"accepted": [], "rejected": [], "unresolved": [], "audit": []}
    if repair and failures:
        _tick(source_ref, f"Sonnet repair START ({len(failures)} unique failed claim records)")
        # Expand the original reader's experiment reference so repair never guesses what an index
        # means. Original fields remain in the audit; corrected experiments must be inline.
        for failure in failures:
            original_raw = failure["raw"]
            failure["original_raw"] = original_raw
            failure["raw"] = dict(original_raw)
            if "experiment" in original_raw:
                experiment = _experiment_for(original_raw, got)
                if experiment:
                    failure["raw"]["experiment"] = experiment
                else:
                    failure["raw"].pop("experiment", None)
        # Give the first repair attempt the same concrete alternatives as a retry. This avoids
        # spending an entire round proposing the original failed surface again.
        async def enrich_failure(failure):
            feedback = await validate(failure["raw"])
            if feedback:
                failure["reason"] += "; validation feedback: " + str(feedback)
        await asyncio.gather(*(enrich_failure(failure) for failure in failures))
        instructions = build_prompt(field, doc_type, "[Source is supplied separately below]")
        instructions += ("\nREPAIR EXPERIMENT OVERRIDE: Never output numeric experiment references. "
                         "Use an inline experiment with its actual source passage only when it supports "
                         "this specific finding, readout and experimental system; otherwise omit it. "
                         "An intervention assay cannot support an unrelated expression or cell-line "
                         "correlation claim merely because it is in the same paper. "
                         "Check all copied experiment metadata against the corrected claim. "
                         "Original reader experiment table for reference: " + json.dumps(got.get("experiments", [])))
        instructions += "\nVerified vocabulary supplement (local IDs are explicitly local definitions):\n" + json.dumps(supplement_menu)
        repaired = await repair_claims(text, failures, model=repair_model, validate=validate,
                                      instructions=instructions, max_concurrency=4)
        for row in repaired["accepted"]:
            keep(row["raw"], repair_model)
        for row in repaired["unresolved"]:
            unresolved_raw = row.get("last_raw") or row["original"].get("raw", {})
            defer(row["reason"], unresolved_raw, unresolved_raw.get("quote", ""))
    else:
        for failure in failures:
            defer(failure["reason"], failure["raw"], failure["raw"].get("quote", ""))
    return {"claims": claims, "deferrals": deferrals, "experiments": experiments,
            "processes": process_map, "process_notes": pnotes, "warnings": warnings,
            "repair_audit": repaired, "raw_extraction": got,
            "extraction_metadata": {"source_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "reader_model": model, "repair_model": repair_model, "prompt_version": PROMPT_VERSION,
                "lexicon_version": LEXICON_VERSION, "replayed": raw_extraction is not None},
            "stats": {"raw": len(raw_claims), "kept": len(claims), "deferred": len(deferrals),
                      "repair_attempted": len(failures) if repair else 0,
                      "repaired": len(repaired["accepted"]), "rejected": len(repaired["rejected"]),
                      "warnings": len(warnings), "flipped": sum(v == "direction audit: swapped" for v in direction.values()),
                      "direction_flagged": len(direction),
                      "experiments": len(experiments), "proc_seen": len(lookup_tasks),
                      "proc_resolved": len(process_map), "proc_by_menu": 0}}
