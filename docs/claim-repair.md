# Claim extraction and repair

`extract_paper` reads with Opus, checks direction with Sonnet, and resolves names
against each category's owner. Unresolved claims and the reader's upfront omissions
then go to independent Sonnet repair sessions (at most four per paper), grouped by
failed term, category and species. These replace the old serial Opus choice menus.

Repair reads the source and can correct names, categories, species context, direction
and representation. It receives the same claim menus and a reviewed vocabulary
supplement. Corrected quotes must occur in the source (whitespace changes and ordered
ellipsis-separated spans are allowed). Python resolves names and constructs the
existing EntityRef, ClaimSpine, Evidence and Experiment models. Concrete lookup or
schema errors go back for a second attempt, with retrieved alternative labels where
available. This structural check cannot by itself prove that a claim follows from its
quote; that remains the source-reading model's responsibility.

Repair sessions have no filesystem, shell, web or MCP tools. The application performs
ontology lookups. They cannot create arbitrary ontology identifiers or edit the
lexicon. `lexicon_supplement.py` holds reviewed, versioned definitions and provenance:
external identifiers retain their owners; LOCALPHENO, LOCALCELL, LOCALREAGENT and LOCALDISEASE
explicitly identify local cellular outcomes, populations and experimental reagents
and specific disease subtypes missing from those owners. New local concepts require source and vocabulary checks,
not a failed search alone. Cell populations are not collapsed into generic fibroblasts.

Outputs distinguish `deferrals` (unresolved claims), `warnings` (issues on retained
claims), and `repair_audit` (originals, corrections, explicit unsupported/nonclaim
rejections and remaining limitations). Resolver diagnostics no longer create duplicate
claim deferrals. Corpus builds save audits under `extraction_audits/<run>/<ref>.json` beside
the corpus outputs as each paper completes, using atomic file replacement. Separate run
directories preserve interrupted runs and avoid stale-paper confusion. The original paper text and frozen source manifest are unchanged.
Model or service failures remain visible as unresolved work; they are never counted as
unsupported science.

For reproducible repair comparisons, `raw_extraction` accepts a saved first-reader JSON
object; it bypasses only the initial paid read. Direction checking and grounding still
run. `repair=False` disables repair; also set `direction_pass=False` for a lookup-only replay. `repair_model` defaults to
`llm.SONNET`. A repair run can recover upfront omissions, so retained counts can exceed
the original reader's `claims` count. Compare source claim records and explicit outcomes,
not just a deferral-list length. Successful lookup decisions are scoped by category and
species; contextual model choices are not reused across papers in the new flow.

Repair feedback includes exact-search synonym candidates ahead of broad search results,
starting with the first attempt. A related synonym remains a contextual choice, not an
automatic identifier equivalence (for example, hyaluronan versus hyaluronic acid).
Known species/name collisions are checked before human grounding: mouse `H2-Ab1` is
MHC class II `NCBIGene:14961`, whereas human `H2AB1` is an unrelated histone. The exact
mouse symbol requires the non-human category and mouse context; ordinary human H2AB1
and the existing verified ortholog conventions are preserved.

Candidate lists are suggestions, not exhaustive entity-name menus. Repair may propose a
source-faithful canonical name outside a shortlist for code to resolve; closed category,
predicate and aspect fields still use their schema menus.
