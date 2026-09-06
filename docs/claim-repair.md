# Claim extraction and repair

`extract_paper` reads with Opus, checks direction with Sonnet, and resolves names
against each category's owner. Unresolved claims and the reader's upfront omissions
then enter the shared repair queue in configured ingestion runs. The queue combines
pending records across papers into batches of ten and runs at most ten repair workers.
Every record retains its source owner; quotes are validated against that paper only.
A final partial batch is flushed only when producers are blocked and cannot supply
more work, rather than dispatching undersized batches on a timer. Per-record responses
are cached durably, so a resumed producer can reuse completed repair work.

Local repair grouping also caps each request at ten records; it does not cap a paper
at four total requests. Local concurrency controls submission, while the shared queue
controls model-worker concurrency across papers. The queue receives compact schema
instructions on both initial submissions and retries. Retry records contain only
pending corrections and their latest validation errors; original records remain in
the local audit rather than being duplicated in model input.

The full paper is not sent to repair. Missing source-supported quotations trigger a
bounded local passage lookup, with up to 4,000 characters of nearby source context per
record. Successful claims are not resubmitted merely because another record needs a retry.
These replace the old serial Opus choice menus.

Repair reads quotations and retrieved source passages and can correct names, categories, species context, direction
and representation. Its dedicated repair schema stays below 8,000 characters and includes
closed menus, the corrected-claim shape, scientific-scope constraints and inline-experiment
rules. It does not reuse the full extraction prompt or send the complete vocabulary
supplement; validation feedback supplies relevant canonical labels and definitions. Corrected quotes must occur in the source (whitespace changes and ordered
ellipsis-separated spans are allowed). Python resolves names and constructs the
existing EntityRef, ClaimSpine, Evidence and Experiment models. Concrete lookup or
schema errors go back for a second attempt, with retrieved alternative labels where
available. This structural check cannot by itself prove that a claim follows from its
quote; that remains the source-reading model's responsibility.

Ambiguous perturbation/treatment quotes and flagged direction errors also receive
bounded neighboring passages on the first attempt, so a naming repair does not
guess the intervention direction.

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

A mutation class is a `mutant` actor even when no individual variant is named;
`general` means the unqualified gene. A weaker rescue is not a measured null.
Repair retains these source qualifiers and returns an actionable error for the
unsupported plural per-claim `experiments` field instead of silently losing its assay.

## Frozen corpus ingestion

`scripts/ingest_frozen_corpus.py --corpus <frozen-directory> --run <durable-run-directory>
--lexicons <processed-lexicons-directory>` extracts the selected full texts without
search or retrieval. It keeps a rolling pool of ten concurrent papers and pins the
reader to `claude-opus-4-8`, with `claude-sonnet-5` direction checking and repair.
All model sessions disable tools, MCP, skills and hooks, and verify returned model
identifiers. Ontology lookups remain available to the application.

Each paper checkpoints its reader output and complete validated result. Restarting
the same command skips completed papers and reuses saved reader output for failed
papers. Workers retry once for ordinary failures. A model service/quota failure
stops queued launches immediately, drains active workers, and remains resumable.
The coordinator checks frozen file hashes, writes results through one transactional
store writer, then publishes a closed snapshot by atomic rename as papers finish.
An import ledger avoids rewriting unchanged paper contributions at each publication.
A pre-ingestion
database backup and per-paper model usage and repair audits stay in the run directory.
The frontend can display completed papers through the existing corpus source.
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
frontend work. Replay snapshots and actual database publication events are separate:
standard builds publish after extraction, while the rolling runner publishes completed
papers as they arrive.
