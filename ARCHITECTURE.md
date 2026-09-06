# ARCHITECTURE.md

The anchoring document for this repository. It describes what is here and how the pieces fit, written from
the code. Read this before changing anything. If code and this document disagree, fix one of them in the
same commit.

## 1. What this is

An engine that turns a body of scientific literature into a knowledge graph, lets a reasoning agent roam
that graph and the papers behind it, has the agent write and run its own analysis code against public data,
checks the statistics of every result it wants to keep, and puts a person at the gate before
anything is recorded as accepted. The engine is domain-agnostic in its code; the data sources, vocabularies
and method guides wired in today are computational biology.

The loop, end to end:

```
project spec ──► corpus build ──► knowledge graph (DuckDB) ──┐
                                                            │
        ┌───────────────────────────────────────────────────┘
        ▼
   explorer agent  (reason → one action → observe, repeat)
        │  roams graph, reads papers, logs ideas, forks branches
        │  writes Python, runs experiments, reads the printed RESULT
        ▼
   verification queue ──► falsifier (soundness only) ──► engine_tests table
        │                                                    │
        │  kills fed back to the agent as retry / reframe / dead
        ▼
   promotion gate (human, written note required) ──► master graph
```

The design never treats "survived verification" as "true". Survival means the numbers were sound. Truth is the
person's call at the gate.

## 2. Repository layout

```
src/dnhacksbio/           the Python package
  litmap/                 literature → knowledge graph
  explorer/               the reasoning agent, its memory, experiment execution, the verification queue
  falsifier.py            the soundness gate
  methods.py              the ToolResult contract the falsifier judges
  llm.py                  the one place model calls happen
  evalues.py              e-value arithmetic helpers (standalone, not wired to the falsifier)
  learned_evalue.py       standalone two-sample betting diagnostic (standalone, not a verdict)
  expr_encoder.py         frozen expression encoders used by learned_evalue
  depmap_harmonize.py     DepMap data preparation
  webui/                  the local HTTP API the frontend talks to
frontend/                 the React workspace (Vite, TypeScript)
skills/                   method guides the agent reads before writing code
scripts/                  launchers, data builders, the coordination board
tests/                    pytest suite
docs/                     operational docs (frontend, learned e-value process)
plans/                    proposed work, explicitly not authorised until asked for
research/                 papers and validation records for the learned e-value work
data/                     corpora, raw pulls, interim tables, project records (gitignored except .gitkeep)
AGENTS.md BOARD.md COORDINATION.md   how people and coding agents coordinate on this repo
```

## 3. Literature to knowledge graph (`litmap/`)

### 3.1 A project is a corpus definition, not a question

A project (`webui/projects.py`) is one investigation: its own corpus, uploaded documents, runs and review
queue. Its record is a JSON file under `data/projects/<id>/`. The spec has these fields and no goal:

| field | meaning |
|---|---|
| `scope` | what the collection covers and leaves out, descriptive only |
| `theme` | one paragraph; relevance triage ranks candidates against its embedding |
| `queries` | Europe PMC query strings, one discovery channel each |
| `seed_dois` | anchors triage may not drop |
| `n_papers` | target size (default 120) |
| `year_min`, `year_max` | publication window |
| `exclude_terms` | drop candidates whose title or abstract matches |
| `full_text_only`, `concurrency` | fetch and extraction settings |

A goal is a question, and a question belongs to a run. The corpus outlives any number of runs.

### 3.2 The build pipeline (`corpus_build.py`)

One fixed pipeline, run as a detached job so the console can watch it:

1. **discover**: each query is searched on Europe PMC as an independent channel; seed DOIs are force-included.
2. **dedup and completeness**: candidates are merged across channels; overlap between channels gives a
   capture-recapture estimate of how complete the search is.
3. **filter**: year window and excluded terms.
4. **triage**: rank against the theme with MiniLM embeddings; keep the top `n_papers`.
5. **fetch**: open-access full text only (Europe PMC, PMC, Unpaywall), licence recorded per article, a
   title-overlap check so a mis-resolved identifier cannot bring in the wrong paper.
6. **documents**: the project's uploaded attachments are folded in as first-class documents.
7. **extract**: the LLM reads every paper (see 3.3).
8. **store**: claims go into the graph; claim status is recomputed from contradictions.
9. **papers**: full text is stored next to the graph so the agent can read it later.
10. **corpus card**: `corpus_card.md` is written from the spec; the explorer reads it as run context.

`--dry` runs discovery and triage only, with no model tokens, to check that the spec finds the right papers.

### 3.3 Claim extraction (`extract.py`)

Three reads of each paper, all against closed menus, with deferral instead of guessing:

- **Pass 1** returns every claim as menu choices plus a verbatim quote. Menus cover the entity category,
  the predicate, the object aspect, and the context slots.
- **Pass 2**, in a separate session that sees only the claim and its quote, checks the direction.
- **Pass 3** resolves the process and entity names that did not match deterministically by showing
  retrieved candidate terms and letting the model pick one while the paper is still in context.

The model only ever picks a letter or a menu word. It never types an identifier. Grounding to identifiers is
deterministic and happens in code. Anything that cannot be grounded becomes a **deferral** row rather than a
guessed claim. Context (cell line, tissue, organism, condition and so on) is captured from the same sentence
as the claim, not in a separate pass.

### 3.4 Grounding (`grounding.py`)

Surface strings become identifiers with one owner vocabulary per category. Genes and proteins resolve
through Gilda to HGNC. Every other category is answered first by its owner lexicon, then by Gilda within the
permitted namespaces, then by last-resort gap fillers:

| category | owner |
|---|---|
| chemicals | ChEBI |
| diseases | MONDO (DOID and EFO route to it) |
| phenotypes | HP |
| anatomy | UBERON |
| cell types | CL |
| cell lines | Cellosaurus |
| chromatin marks | SO |
| protein families and complexes | FamPlex |
| repeat families | Dfam |
| non-human genes | NCBI Gene, per species |
| processes | OLS exact match over GO and related ontologies |
| gap fillers | PRO, NCIt (consulted only when everything else failed) |

The lexicon files live under `data/processed/` and are not committed. Without them, extraction defers
ungrounded entities instead of guessing. Only the entity string is ever sent over the network.

### 3.5 The claim atom (`schema.py`, `vocab.py`)

A claim is a **spine** plus **evidence**. The spine is subject, predicate, object and object aspect, where
subject and object are resolved identifiers with an entity state (wild-type, mutant, variant, isoform, a
protein construct, a genomic feature). The identity key may contain only closed vocabulary or resolved
identifiers, never free text, so two papers asserting the same thing land on one row.

Two levels of identity: `abstract_key` (subject, object, aspect) is the question being asked;
`claim_id` adds relation class, polarity and entity states and names one distinct assertion.

Predicates carry their direction in the word itself (`increases`, `decreases`, `regulates`,
`depends_on`, `associated_with`, and the rest of the closed set in `vocab.PREDICATES`); synonyms collapse
through `CANONICAL_PREDICATES`. Relation classes exist so that two claims may only contradict on opposite
sign when they measure the same dimension.

Four objects: Paper → Experiment → Evidence → Claim, with the Experiment shared across the claims it
grounds.

### 3.6 The graph on disk (`graph.py`, `store.py`)

Everything for one corpus is one DuckDB file. `ClaimGraph` owns the literature tables:

| table | one row per |
|---|---|
| `claims` | distinct assertion (primary key `claim_id`) |
| `evidence` | one source supporting one claim: quote, section, surface predicate, evidence type, study type, attribution, certainty |
| `evidence_context` | one context slot on one evidence row (cell line, tissue, organism…), with provenance stated / inherited / unspecified |
| `evidence_cites` | what an evidence row leans on (a resolved citation), so echoes of one paper can be told from independent findings |
| `experiments` | the experiment a paper reports: unit, intervention, control, readout, assay, n, effect |
| `deferrals` | an entity or claim the extractor refused to guess |

Writing a paper is idempotent: everything for that source is deleted first, then rewritten.
`ClaimGraph.contradictions()` finds claim pairs with opposite polarity on the same dimension.

`KGStore` opens the same file and adds the engine's layer:

- `engine_tests`: every verified experiment as a tested edge (subject, object, method, expected and
  observed sign, effect, `p_null`, status, kill reason, verdict note, human review, notes).
- `claim_status`: claims marked `disputed` by the contradiction check.
- `claim_vectors`: one MiniLM vector per claim edge, built once after a corpus build (`scripts/embed_kg.py`).
- The view `claim_edges`: the one row shape every reader uses. A claim plus its source count, first-mention
  year, status (`disputed`, else `established` with two or more sources, else `reported`) and a confidence
  derived from the source count with a penalty when disputed.
- Structural reads: neighbours, induced subgraph, shortest path, and a digest (hubs, disputed edges,
  counts).

### 3.7 Supporting modules

- `refinement.py`: is one claim a special case of another? Computed on demand within an `abstract_key`
  group using field-by-field rules; nothing is stored.
- `attribution.py`: whose finding is a quote reporting, own work or a citation, and which reference a
  marker like "(11)" points at. Deterministic and offline. Ten echoes of one experiment are one experiment.
- `metadata.py`: resolve DOI, PMID, title and year for a paper through Crossref and NCBI, and verify the
  answer against the paper's own text. Never guesses.
- `find.py`: discovery and full-text fetch. `ingest.py`: local files to clean text with provenance.
- `promote.py`: the human gate (section 6).

## 4. The explorer (`explorer/`)

### 4.1 The loop (`explorer.py`)

One resumable model session is the agent's working memory. Each step the agent receives what is new (the
last observation plus any verification or human feedback), answers with exactly one JSON object
`{"intent", "action", "args"}`, the code executes the action and returns an observation. Turn one sends the
full standing context: the goal, the corpus card, a digest of the graph, the frontier of its own memory,
open questions, feedback, the skill menu and the protocol. Every step is appended to a reasoning trace
(`data/processed/reasoning_<run_id>.jsonl`) with recorded model output, its stated intent, the action, the
observation and timing. The raw SDK message stream is written alongside it. New attempts also write ordered execution events,
lifecycle and worker identity into the runtime journal. `intent` is a concise user-facing progress update,
not private reasoning. The runner records what actually executed.

The actions:

| action | what it does |
|---|---|
| `search_kg` | keyword plus semantic search over claim edges, with what is already tested |
| `neighbors`, `subgraph`, `path` | structural reads of the graph; a missing path is a candidate untested bridge |
| `recall` | search the agent's own memory across every run on this corpus |
| `search_papers`, `read_paper` | semantic search over stored full text, then read one (paged; a truncated read never supports an absence claim) |
| `fetch_papers` | pull new open-access papers into the store for reading (never adds claims) |
| `find_datasets` | search GEO and ArrayExpress for real datasets |
| `search_skills`, `get_skill` | find and read a method guide |
| `run_experiments` | run several pieces of Python in parallel |
| `log` | record an idea, observation, dead end, open question or note with a promise score |
| `submit` | send a self-judged experiment to verification |
| `fork` | one generation of beam search over forked sessions |
| `reflect`, `done` | record a synthesis; stop |

The system prompt makes the agent a curious, rigorous computational biologist looking for something new,
and carries the **absence rule**: a capped or truncated retrieval is evidence of presence only, so nothing
may be called novel on the strength of a partial search.

The **rigor contract** every experiment must satisfy is stated in the protocol and enforced downstream:
permute at the truly independent unit, report a Phipson-Smyth permutation p that is never exactly zero,
match the predicted direction, hold up under leave-one-group-out, have at least 8 units per group, decide
the analysis before seeing the result, include a negative control where possible.

### 4.2 Memory (`exploration.py`)

The exploration log is the agent's episodic memory and the search frontier, in the same DuckDB file as the
graph. Every entry has a kind (`idea`, `experiment`, `observation`, `dead-end`, `open-question`, `note`), a
status (`open`, `promising`, `dead`, `submitted`, `needs-retry`, `reframe`, `validated`), a promise score,
provenance (papers, claims, entities, parent entries), the code and result for experiments, and a MiniLM
embedding. `frontier()` returns the promising open nodes to expand next. Verification and human feedback
are written onto the entry they concern, so the agent sees them on its next turn.

### 4.3 Branch identity (`lineage.py`)

A run id is a path: `root`, `root~1`, `root~1~0`. Depth, parent, ancestors and tree membership are string
operations on the id, with no lineage table. A branch may read its own lineage's entries and the shared
graph. The map from run id to model session id is written to disk so a stopped run can be resumed.

### 4.4 Fork and beam search

`fork` takes up to 3 branches, each with a distinct angle, and the engine adds one adversarial branch whose
only job is to falsify the current leading hypothesis. Each branch forks the parent's session, so it
inherits the full context, runs to completion as a leaf with forking disabled, and its findings are
digested. A judge call ranks the digests by how much more compute they deserve (a search heuristic, never a
soundness verdict). The top 2 are resumed with forking enabled and may fork again; the rest are pruned.
Pruning only stops further exploration: every branch's submissions were already verified.

Budgets, all disclosed to the agent: maximum depth 6, a tree-wide budget of 72 branches, 18 steps per
leaf generation, up to 6 continuation rounds per survivor, 96 steps per branch in total. A node forks once.

### 4.5 Experiment execution

Product decision: remove Docker from experiment execution. Docker-only execution and mandatory
container sandboxing are not architectural requirements. The replacement execution environment and
its permissions have not yet been specified; this decision does not by itself define them.

Implementation status: `sandbox.py`, `sandbox.Dockerfile` and `sandbox_lib/` still implement the
existing Docker runner. The backend migration has not happened yet. Its container-specific mounts,
dependencies and restrictions describe that existing implementation, not the intended architecture.

Experiment code must print one line, `RESULT: {json}`, with `effect`, `p_null`, `null_model`, `n_units`
and `robust`. A malformed result is rejected and the experiment records no result. Required fields are strictly typed: positive integer `n_units`, nonempty `null_model`, explicit boolean
`robust`, finite numeric `effect`, and `p_null` in (0,1]. An incomplete queued result receives a
`malformed-result` verdict; a missing robustness check never defaults to a pass. Everything else printed
is handed back to the agent as its debugging channel.

### 4.6 Other inputs

- `datasets.py`: GEO and ArrayExpress search through their documented APIs; returns candidates and a
  download hint, downloads nothing itself.
- `fulltext.py`: the paper store, keyword and semantic search, paged reads.
- `skills.py`: lists, searches and reads `skills/<name>/SKILL.md`.
- `embed.py`: the one MiniLM loader, lazy, thread-capped, degrades to keyword search if unavailable.

## 5. Verification (`verifyqueue.py`, `falsifier.py`, `methods.py`)

`submit` writes a row to `verification_queue` with the hypothesis, subject, object, method, expected sign,
the printed result and the code that produced it. The run script drains the queue on a timer while the
agent keeps exploring, and once more at the end.

`drain` wraps each row as a `ToolResult` (the audited-statistic contract in `methods.py`) and applies the
falsifier's soundness floor, in this order:

| check | kill slug | kind |
|---|---|---|
| required result fields missing or invalid (before the floor) | `malformed-result` | invalid |
| effect is not a finite number | `no-effect` | invalid |
| fewer than 8 units | `too-few-units` | underpowered |
| `p_null` is not in (0,1] | `malformed-p` | invalid |
| direction disagrees with the predicted sign | `direction-wrong` | refuted |
| `p_null` above 0.05 | `not-significant` | inconclusive |
| robustness check failed | `not-robust` | refuted |

A pass is `CANDIDATE`; anything else is `KILL` with its slug. There is no minimum-effect gate, because the
effect size is filled by the agent and validated by nothing. The falsifier judges only whether the numbers
can be trusted. Whether a result matters is decided at the gate.

Verdicts are written to `engine_tests` and folded back onto the agent's experiment entry:
`needs-retry` for fixable kills (`malformed-result`, `no-effect`, `malformed-p`, `too-few-units`, `not-robust`), `reframe` for a
wrong direction, `promising` for a candidate. The agent sees these in its next turn.

## 6. The human gate (`promote.py`, `webui/data.py`)

Every `engine_tests` row with status `candidate` and no human review becomes a discovery card, with the
claim edge it tests, its literature quotes and its numbers. A person records `validated` or `rejected`,
and every decision requires a written note; an unexplained verdict is skipped. These controls are currently
hidden in the frontend; the backend routes remain available. Applying decisions copies
validated cards, with their literature provenance and the note, into a separate **master graph**. A
rejection stays local, and the note is pushed to the explorer as a correction it must not repeat. Nothing
reaches the master graph without a person.

## 7. Standalone statistical diagnostics

These are in the package and tested, and deliberately not connected to the falsifier or any verdict:

- `learned_evalue.py`: a two-sample test for whether two groups of expression vectors have the same
  distribution, implemented as a neural bettor trained on earlier independent units and scored on fresh
  batches (deep anytime-valid testing). It requires declared donor identifiers, a frozen encoder trained on a
  separate cohort, and a sampling contract; it rejects shared donors and undeclared aggregation. It cannot
  establish a gene effect, a direction or a mechanism. Torch is an optional extra (`uv sync --extra evalue`).
- `expr_encoder.py`: frozen PCA or masked-gene autoencoder encoders with recorded training provenance,
  trained by `scripts/train_expr_encoder.py`.
- `evalues.py`: p-to-e calibration, merging and e-BH helpers. Inputs must already be valid.
- `skills/learned-evalue`, `docs/learned-evalue-process.md`, `plans/PLAN-learned-evalue.md` and
  `research/` hold the guide, the process record, the plan and the paper.

## 8. The model seam (`llm.py`)

All in-loop model calls go through one module: the Claude Agent SDK over the installed `claude` CLI login.
There is no API key anywhere. Two pinned models: one for scientific judgment (the explorer, the fork judge,
the assistant), one for bulk extraction. A resumable `Session` is what makes the explorer's working memory
and forking possible; a `UsageLedger` records tokens and cache hits per run.

## 9. The console

### 9.1 Python side (`webui/`)

A stdlib HTTP server bound to localhost, serving the built frontend and a JSON plus SSE API. It reads the
engine's on-disk state: inspection tails reasoning traces and opens DuckDB read-only, using a snapshot
copy when a run holds the writer lock. Applying human decisions is an explicit write operation (section 6).

- `projects.py`: the project record and its directory (`project.json`, `kg.duckdb`, `attachments/`,
  `jobs/`, `corpus_card.md`). Corpora built by scripts under `data/corpora/` are surfaced read-only.
- `jobs.py`: a build or run is a detached subprocess plus a record file, an append-only JSONL progress
  stream and a stderr log. Liveness is checked against the pid, never trusted from the record.
- `attachments.py`: the scientist's own documents, parsed at upload time so an unreadable PDF is caught
  immediately.
- `assistant.py`: the onboarding conversation. Each turn the model sees the project and its spec and
  returns a reply plus a proposed spec patch; the person accepts or edits the patch.
- `data.py`: everything the frontend shows, derived from traces and DuckDB: run summaries, investigations
  grouped into fork trees, the parsed run, the live step stream, the search tree, the graph for a project,
  the review queue, promotion decisions.
- `architecture.py`: the engine's shape as nodes whose facts (action names, thresholds, budgets) are read
  from source by AST, so the description fails loudly if the code drifts.

- `runtime.py`: scoped snapshots, ordered events/SSE, immutable result/artifact blobs and opt-in terminal
  capture. Node live/replay state includes verifier assessments and separately recorded human decisions.
  Applied human decisions are queued durably and published idempotently; replay reveals them only after
  their event is available. A publication failure keeps saved decisions available for retry.

Main routes: `/api/projects` and its sub-routes for build, run, jobs, chat and attachments; `/api/runs`,
`/api/runs/<id>`, `/api/runs/<id>/stream`; `/api/investigations`, `/api/tree/<id>`, `/api/events/<id>`;
`/api/runtime/<id>/snapshot`, `/events`, `/stream`, `/blob/<hash>`, `/terminal`;
`/api/kg`; `/api/review`, `/api/review/promotion`, `/api/review/promotion/apply`; `/api/architecture`.

### 9.2 Frontend (`frontend/`)

React and TypeScript, built with Vite and Tailwind, with Radix components, Motion, React Flow and Dagre for
graphs, and 3Dmol for structures. It talks only to the JSON and SSE API. A project selector in the header
scopes every view. The views:

- **Investigations.** The project's runs grouped into fork trees. The selected investigation shows its
  search tree as a spatial graph of agents, a live activity feed streamed step by step, and each experiment
  with its code, result and provenance. Historical runs play back recorded activity. A disclosure explains
  how the research process works, drawn from the architecture endpoint.
  Molecular PDB/mmCIF geometry appears inside the selected researcher's experiment only when that
  experiment produced a validated, collected artifact. Ribbon, atomic and surface views use its actual
  coordinates and provenance; there is no standalone Structures tab, remote lookup or local file picker.
- **Library.** Create a project; edit every collection field; run a dry preview or a full build; upload
  and remove documents; talk to the assistant and accept its proposed settings; see build and run history
  with progress, logs and cancellation.
- **Knowledge.** The project's literature claim graph with status filters, entity detail, relationship
  search over the loaded subset, exact quotations, source papers and biological context. Review controls
  are not exposed in the frontend. Backend review endpoints and human-decision persistence remain available.

## 10. Data on disk

```
data/projects/<id>/        project record, its graph, attachments, jobs, corpus card
data/corpora/<name>/       corpora built by scripts: <name>_kg.duckdb and corpus_card.md
data/processed/            lexicons, reasoning traces, session maps, master graph
<trace_dir>/runtime/       journal.sqlite3 (manifests/events), immutable content-addressed blobs
data/raw/, data/interim/   raw pulls and analysis-ready tables (DepMap)
```

Everything under `data/` is gitignored except placeholders. Publisher full text is copyrighted and stays
local. Legacy traces are append-only JSONL, one file per run. New runtime manifests preserve original questions
and branch objectives across restarts. Ordered journal events drive live views and deterministic playback;
legacy histories are labelled partial. See `docs/runtime.md` for the artifact and API contracts.

## 11. Scripts

| script | purpose |
|---|---|
| `run_explorer.py` | run the agent: `--goal`, `--steps`, `--db`, `--corpus-card`, `--resume`, `--network none|bridge`, `--freeze-year` |
| `serve_ui.py` | serve the console on localhost |
| `embed_kg.py` | build the semantic index over claim edges after a corpus build |
| `build_fulltext_store.py` | store a local corpus's parsed text next to the graph |
| `build_explorer_data.py`, `build_frozen_depmap_tables.py`, `build_coessentiality_table.py` | analysis-ready DepMap tables for experiments |
| `gen_capability_index.py` | render `docs/CAPABILITIES.md` from live vocabularies; a test keeps it current |
| `evalue_harness.py`, `train_expr_encoder.py` | the standalone diagnostics |
| `board.py`, `board_mirror.py`, `board_nudge.py`, `pr_digest.py` | team coordination (see `BOARD.md`) |

## 12. Skills

A skill is `skills/<name>/SKILL.md`: what a method is, when to use it, the statistical invariants the code
must honour, and a worked example. The agent reads a skill before writing experiment code. The mandatory `agent-runtime` skill links
common rigor, progress and artifact instructions. Method execution requires a registered `method_id`
and complete, version-pinned instruction delivery; this enforces delivery, not scientific correctness.
Custom exploratory methods cannot be submitted as audited results. Method guides present: `experimental-rigor`, `permutation-testing`, `multiple-testing-fdr`,
`effect-sizes-and-floors`, `bootstrap-confidence-intervals`, `confounding-and-causal-inference`,
`mixed-models-pseudoreplication`, `regression-glm`, `batch-correction-combat-sva`,
`rnaseq-qc-normalization`, `pydeseq2`, `gsea-enrichment`, `depmap_dependency`, `co_essentiality`,
`geo_expression`, `learned-evalue`. `skills/README.md` states the trust boundary and the result contract;
`TEMPLATE.md` is the layout.

## 13. Running it

```
uv sync --extra dev --extra llm          # add --extra evalue for the learned diagnostic
npm --prefix frontend ci && npm --prefix frontend run build
uv run python scripts/serve_ui.py --port 8765
uv run python scripts/run_explorer.py --db data/corpora/<name>/<name>_kg.duckdb --steps 30
uv run pytest tests
```

Needs Python 3.12, uv, Node 22, a logged-in `claude` CLI, and the lexicon files under
`data/processed/`. The MiniLM embedding model downloads on first use.

The current experiment runner still requires its Docker image until the migration in section 4.5
is implemented. These commands do not yet provide a Docker-free experiment runtime.

## 14. Invariants worth knowing before you edit

- Identity keys never contain free text. If you add a field to the claim spine, it must be closed
  vocabulary or a resolved identifier.
- The model picks from menus; code grounds. Never let a prompt ask the model to write an identifier.
- The falsifier has no answer key and no notion of importance. Do not add a gate keyed on gene identity or
  effect magnitude there; that belongs at the promotion gate.
- Every verdict and every human decision is written back onto the agent's memory entry. Feedback that
  does not reach the agent's next turn is a bug.
- Writing a paper into the graph replaces that paper's previous contribution. Refs are the join key
  between a document and its claims and are never reused.
- Console inspection is read-only. Applying human review is an explicit write exception: it updates
  the working database and exports accepted results to master. It currently waits until the working
  database is not held by an active run. Builds and runs are subprocesses.
- `docs/CAPABILITIES.md` and `webui/architecture.py` are generated from or checked against source. Rename
  a constant and the test tells you.
