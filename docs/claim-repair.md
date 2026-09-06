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

## Frozen corpus ingestion

`scripts/ingest_frozen_corpus.py --corpus <frozen-directory> --run <durable-run-directory>
--lexicons <processed-lexicons-directory>` extracts the selected full texts without
search or retrieval. It runs strict batches of ten concurrent papers and pins the
reader to `claude-opus-4-8`, with `claude-sonnet-5` direction checking and repair.
All model sessions disable tools, MCP, skills and hooks, and verify returned model
identifiers. Ontology lookups remain available to the application.

Each paper checkpoints its reader output and complete validated result. Restarting
the same command skips completed papers and reuses saved reader output for failed
papers. Workers retry once; a batch with remaining failures halts further batches.
The coordinator checks frozen file hashes, writes results through one transactional
store writer, then publishes a closed snapshot by atomic rename. A pre-ingestion
database backup and per-paper model usage and repair audits stay in the run directory.
The frontend can display each completed batch through the existing corpus source.
Scientific deferrals remain in the graph review queue and are distinct from service
failures. Graph counts are deduplicated relationships, not extraction proposal counts.

Both standard corpus builds and the frozen ingestion runner automatically record
graph-construction timelines. Each completed paper immediately produces a cumulative
replay snapshot; recording does not wait for the batch to publish. The reusable
`litmap.timeline.TimelineRecorder` writes `timeline/events.jsonl` and self-contained
graph snapshots under the extraction run directory. Claim IDs and content-derived evidence replay
IDs let a player distinguish new relationships from additional supporting evidence.
Snapshots include nodes, edges, sources, quotations, contexts and experiments, so
later replay does not require rerunning extraction. Recording deduplicates events
across restarts and skips published databases with an active WAL.

For a run started before automatic recording was installed, the compatibility command
`scripts/record_ingestion_timeline.py --run <run-directory> --db <corpus-kg.duckdb>
--watch` observes completed artifacts every 1.5 seconds. Events distinguish observation
time from artifact modification time. Earlier events recovered when the observer
starts are not presented as precisely observed live events.
This records replay data only; timeline controls, playback speed and animation remain
frontend work. Actual graph publication happens per batch, while paper completions can
be animated individually using their recorded completion artifacts.
