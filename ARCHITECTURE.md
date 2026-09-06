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

Opus reads each paper against the category, predicate, aspect and context menus, returning
claims and source quotes. A separate Sonnet session checks direction. Code then resolves
names within each category's owner vocabulary.

Unresolved claims and upfront reader omissions go to grouped parallel Sonnet repair,
which can correct the source name, category, species context, direction and representation.
It receives the source, reviewed vocabulary definitions and concrete validation errors.
Python checks source quote spans, owner identifiers and the existing claim models; a failed
correction gets a second attempt with retrieved alternatives. There are no model tools in
repair sessions. See [claim repair](docs/claim-repair.md) for the contract and replay controls.

Unresolved failures become **deferral** rows. Unsupported/nonclaim rejections and repair
history are saved separately in extraction audits; warnings on retained claims do not inflate
the failure queue. Lookup failure alone does not establish that an ontology lacks a concept.

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
| processes and cellular components | GO via OLS |
| pathological processes | MeSH via OLS |
| cellular outcomes absent from GO | reviewed LOCALPHENO registry |
| populations absent from CL | reviewed LOCALCELL registry |
| experimental reagents absent from ChEBI | reviewed LOCALREAGENT registry |
| specific disease subtypes absent from MONDO | reviewed LOCALDISEASE registry |

Downloaded lexicons live under `data/processed/`. A small versioned supplement in
`lexicon_supplement.py` stores verified aliases and explicitly local definitions with source
provenance. Local entries do not impersonate external ontology identifiers. Missing vocabulary
is recoverable when a reviewed entry exists; arbitrary IDs remain disallowed. Ontology lookup
requests contain entity strings; the extraction and repair models receive the paper text.

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
| `inhibitor` | skill-gated, experiment-scoped bounded preparation/docking, scene vision and canonical measurements; exploratory artifacts only |
| `spindle` | bounded provisional 3D filament jobs, collected numerical ensembles and separate scoped scene/capture/vision operations; requires spindle-interface guidance |
| `tissue` | skill-gated conditional PhysiCell/BioFVM jobs, exact source-cell/field queries, immutable scene actions and actual PNG review; simulation sensitivity only |
| `log` | record an idea, observation, dead end, open question or note with a promise score |
| `submit` | send a self-judged experiment to verification |
| `fork`, `checkpoint` | request parent allocation through a mandatory checkpoint report |
| `reflect`, `done` | record a synthesis; request completion through reporting |

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

### 4.4 Checkpoints and parent allocation

Each worker has at most 18 research actions per round, with a warning at three remaining. `checkpoint`,
`fork` and `done` pause research for the same child's mandatory report; `done` requests completion.
At the action ceiling a separate tool-disabled turn resumes that child's transcript, with a 4096-token,
90-second output allowance and at most two format repairs. Failure leaves `reporting_blocked` durable.
A valid report leaves `awaiting_parent`; neither state is completion or scientific failure.

The parent controller inspects the report and supporting work and explicitly continues, forks, finishes
or prunes. There is no top-two quota or experiment-count renewal. `run()` produces one checkpoint;
`run_investigation()` runs parent allocation, including the root controller. Concurrent children report
and receive decisions individually. Accepted splits transfer work to two or three specified descendants;
code executes the approved questions from the child's saved context. SQLite stores report versions,
idempotent decisions and atomic tree-wide slot reservations. An ambiguous interrupted launch is blocked,
never repeated speculatively. Pending reports/decisions survive restart. Reserved slots are retained on
ambiguous launch failure. A revised decision/operator recovery is needed for blocked work.

Operational limits remain depth 6, 72 total descendant slots, six continuation rounds and 96 research
actions per node. In addition, `explorer/budget.py` enforces a frozen shared action/operation-time
contract across descendants and continuations. Research grants reserve reporting first; fork grants,
consumption and refunds share the controller transaction. Restart never refreshes the endpoint or
refunds ambiguous operations. Async operation deadlines mark backend overrun/cancellation uncertainty
as operational violations; summed operation wall time is not an OS CPU/GPU quota or calibrated horizon.
Reported SDK tokens are retained separately. Submissions during research remain available and
pruning preserves all findings and pending verification. Statistical stopping is not enabled.

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
- `expression_experiment.py`: agent command that submits declared TPM inputs and returns a durable
  receipt only. `expression_scoring.py` runs the private queue and numerical worker separately;
  it has no result-reading HTTP endpoint or feedback callback. See `docs/expression-scoring.md`
  for operator setup and the required filesystem separation when agents run unrestricted code.
- `dependency_experiment.py`: receipt-only registered Chronos submission; `dependency_scoring.py`
  privately validates frozen operator protocols/cohort manifests and scores blocked label permutations
  through `dependency_evalue.py`. Unsupported exchangeability, overlap, development exposure and
  insufficient units yield private unavailable results. No confirmation cohort is bundled.
  Both adapters use `experiment_transport.py` for durable acceptance, canonical receipt aliases,
  worker ownership/restart recovery and output-suppressed subprocesses. See `docs/dependency-scoring.md`.
- `drug_response_experiment.py`: receipt-only submission of an operator-registered biomarker/AUC
  association. `drug_response_scoring.py` uses the shared private transport and frozen donor registry;
  `drug_response.py` computes observed log-dose inhibition area and stratified Spearman permutations.
  No synergy evidence or biological confirmation cohort is enabled. See `docs/drug-response-scoring.md`.

- `registered_expression_scoring.py`: shared-queue adapter for operator-frozen paired pathway protocols,
  hashed expression cohorts/resources and receipt aliases. `expression_design.py` validates donor pairs
  and prepares integer pseudobulk; `pathway_evalue.py` computes fixed weighted scores and assignment
  evidence. Optional `count_expression.py` records approximate paired PyDESeq2 effects privately.
  The `expression_experiment --dataset-id` route accepts identifiers only; legacy TPM uploads remain
  available. No confirmation cohort is bundled, and no statistical result enters discovery feedback.
- `pharmacotype_data.py`, `pharmacotype_encoder.py`, `pharmacotype.py`: declared donor/curve
  preparation, CPU separate-view encoders and development prediction/neighborhood/program tools.
  `pharmacotype_scoring.py` provides receipt-only operator-frozen association replay through the
  shared native ledger, with opt-in atomic past-block critic updates. Public PRISM/CCLE
  acquisition and real CPU/GPU training are reproducible via scripts; PCA remains selected
  after validation. No PDO confirmation is enabled. See [pharmacotype operations](docs/pharmacotype.md)
  and [real-development model card](docs/pharmacotype-training.md).
- `expr_encoder.py`: frozen PCA or masked-gene autoencoder encoders with recorded training provenance,
  trained by `scripts/train_expr_encoder.py`.
- `evalues.py`: p-to-e calibration, merging and e-BH helpers. Inputs must already be valid.
- `skills/expression-experiment`, `docs/learned-evalue-process.md`, `plans/PLAN-learned-evalue.md` and
  `research/` hold the guide, the process record, the plan and the paper.

### 7.1 Private branch-monitor infrastructure

`branch_monitoring/` provides operator-only episode enrollment, historical-prefix scoring, private
records, grouped fitting/calibration/evaluation, and private evidence review. Nothing in the explorer
starts this worker or receives its predictions. Its target is qualifying new subtree outcomes under a
frozen policy and budget. Learned values are monitor statistics, not automatically exact e-values.
Algorithm 1 calibration uses independent complete successful episodes and returns no threshold when
there are too few. No statistical stop is enforced.

`outcomes.py` prospectively binds the runtime budget and frozen final assessor, gathers pre-endpoint
submitted code/results, requires matching automated verification and privately applies the evidence
rubric. Pending verification has a fixed adjudication deadline; incomplete/unavailable continuations
are censored. Only workflow-qualified labels enter the operator training CLI. `--prepare-only` creates
the runtime identity/budget without research, allowing enrollment before the first action. Legacy
submission verification remains supported. `receipt_outcomes.py` also supports registered pathway,
Chronos dependency and biomarker/AUC receipts under `registered-receipts-v1`. The runner's
`private_experiment` action records exact public requests with owned run/experiment identities;
operator adapters reconcile these against frozen queue settings, scientific identities and immutable
completion snapshots. They never infer ownership from printed receipts or rescore an experiment.
Method-specific evidence and a prospective validity/family review feed the frozen rubric, without a
universal e-value success threshold. Completed evidence routes to private human review automatically through labeling or the separate
operator `route` worker, which permits inspection before the subtree endpoint without calling a model;
review decisions are not training labels. Unsupported/unbound receipt workflows are censored.
`experiment_transport.py` provides an opt-in immutable completion contract for these three registered
queues; it records terminal status/result/config/time atomically and prevents terminal result rewrites.
Other queue types retain their existing replay contracts. Existing completed jobs acquire no invented historical completion timestamp.

A separate authenticated operator console displays recorded child histories and distinct experimental
evidence; it adds no routes to the research API. Private review never writes ordinary agent feedback or
the master graph. Explicit boundary export is available. Actual separate-account deployment and real
corpus trajectory collection/training remain pending; the user deferred those runs until ingestion.
See [branch monitoring operations](docs/branch-monitoring.md) for commands, boundaries and limitations.

## 8. The model seam (`llm.py`)

All in-loop model calls go through one module: the Claude Agent SDK over the installed `claude` CLI login.
There is no API key anywhere. Two pinned models: one for scientific judgment (the explorer, the fork judge,
the assistant), one for bulk extraction. A resumable `Session` is what makes the explorer's working memory
and forking possible; a `UsageLedger` records tokens and cache hits per run.

### Measured protein discovery

`protein_design.py`, `protein_encoder.py` and `protein_tools.py` provide exploratory
protein profiles, coverage, module means, nearest development profiles, context
comparisons and localization-aware site tables. Frozen mask-aware PCA and optional
CPU/CUDA denoising artifacts use donor-disjoint non-PDAC training/validation cohorts;
confirmation data and cross-assay transforms are rejected by discovery operations.
The operator-only audit preserves grade eligibility and the 48-pair policy.
`protein_experiment.py` conditionally registers operator-reviewed independent-group
finite replay through `native_group_replay.py` and the shared canonical donor ledger.
The explicitly versioned frozen-linear route binds source-fitted witness coefficients
and feature order, preserves16 unscored pairs, and requires matching final-power review.
Real CPTAC development models are trained. A subsequent Fudan external benchmark
provides 60 grade pairs after coverage filtering and CUDA-fitted transfer comparisons;
independent confirmation review and model-specific power remain release gates. No native wealth
or verification verdict is exposed. See [protein signaling](docs/protein-signaling.md).

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

React and TypeScript, built with Vite and Tailwind, with Radix components, Motion and React Flow,
d3-force for the literature graph, Dagre for investigation trees, and 3Dmol for structures. It talks only
to the JSON and SSE API. A project selector in the header scopes every view. The views:

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
- **Knowledge.** The project's literature claim graph with entity-kind shapes, signed relationships,
  collection-wide database search and vocabulary filters, collection totals and a capped graph view.
  Claim inspection shows entity forms, exact quotations, source papers, biological context, reported
  experiments, related claims and engine-test outcomes. Review controls are not exposed in the frontend.
  Backend review endpoints and human-decision persistence remain available.

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
`geo_expression`, `expression-experiment`. `skills/README.md` states the trust boundary and the result contract;
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

## Native association core

`native_evidence.py` implements the shared bounded two-view association kernel
and private atomic frozen-critic donor ledger. Receipt aliases share one process;
identical replay does not add wealth, and consumed canonical donors cannot be
reused across processes in one shared store. This infrastructure does not itself
satisfy biological access, sampling or power gates and does not alter discovery
promotion. The opt-in `past-block-bilinear-sgd-v1` schedule scores each block
with the prior critic before a deterministic consumed-block update; scored and
next critic states commit atomically. The fully frozen baseline remains available.
See [native evidence](docs/native-evidence.md).

## Cellular ecosystem development tool

The `ecosystem` CLI validates sparse UMI count provenance and a canonical donor
crosswalk, trains separate compartment PCA or masked NB encoders, and exposes
donor-level development profiles, coupling/comparison and segmented-cell spatial
summaries. Counts are not passed to the TPM encoder. Fixed per-compartment
subsamples, frozen gene/assay/state references and explicit missing coverage
preserve measurement boundaries. The private receipt adapter uses the shared
native frozen process ledger and requires operator-reviewed identity, access,
sampling, transfer, selection, privacy, novelty and power artifacts. No biological
confirmatory capability is approved. Original Peng/Lin development counts and
donor partitions have been audited and separate count/PCA/set models actually
trained: held-out reconstruction favored cell PCA; learned set pooling did not
improve on donor-summary PCA. All-gene library offsets and a residual NB decoder
bin preserve selected-panel measurement semantics. The [training report](docs/ecosystem-training.md)
records coverage, source checksums and negative pilot results. The subsequent
[CUDA expansion](docs/ecosystem-expansion.md) acquired three more original cohorts
for 72 donor records and trained separate 64-dimensional denoising/NB encoders
across three seeds, a lineage classifier and donor-matching scorers. All fitting,
including exact PCA, runs on CUDA under the shared GPU lease. Fifty-five donors
meet the two-compartment 32-cell coverage rule; external reconstruction still
favors PCA. These separate development checkpoints are not private registrations. Reserved-cohort
audit, adequate power and deployment privacy remain confirmation gates.
No graph promotion or branch-success behavior changes.
See [cellular ecosystems](docs/cellular-ecosystems.md) for schemas, CLI and limits.

### Exploratory binder interfaces

`binder/` adds bounded coordinate inspection, exact residue maps, contact/SASA diagnostics and
portable `binder_bundle.v1` artifacts with optional rebuilt source-derived surface meshes.
Worker-parsed surfaces and labeled Cα traces remain visual representations of immutable coordinates. The existing collector and explorer enforce source/hash,
provenance and experiment-scope checks before publication. RuntimeDetail opens those collected
artifacts in a lazy-loaded Three.js/R3F Interface Foundry, within their owning experiment.
A persistent node workspace keeps one selected molecular/binder source beside the researcher activity
and findings; source availability follows the exact event cursor. Binder cameras transition smoothly
and yield immediately to manual orbit; reduced motion and saved captures remain deterministic.
Paired candidates use two scissored views with one actual camera, matching target coordinates and
metric protocol. Captures retain both source hashes; saved-pixel picks resolve the exact candidate
and residue, and the inspector follows that source. Availability remains bounded by the event cursor.
Receipt storage and an operator-side pinned BindCraft launch adapter are separate from statistical
verification. No live design pilot, biological efficacy or performance acceptance
is implied. Immutable scoped scene recipes and PNG captures support actual image observations,
recorded action replay and independent user exploration inside the owning experiment.
See [supported behavior and remaining acceptance](docs/binder-design.md).

The provisional native `binder` action is instruction-gated by `binder-interface` and restricted to
an existing experiment owned by the current researcher. It records target/epitope/protocol and
comparison/follow-up artifacts, real receipt milestones, collected candidates and scoped scene/image
reviews. Queuing requires a separate operator launch; no agent-provided executables or host paths
are accepted. Image-review usage is recorded in the research ledger. This adds no audited structural
method, statistical verdict or master-graph promotion path.


## Tumor–stroma instrument

`tissue/` and `native/tissue/` provide a conditional fixed-position PhysiCell 1.14.2/BioFVM
alanine exchange model, bounded CPU runs and simulation-sensitivity summaries. The model's
volume/damage law and parameters are assumed; computational seeds and cells are not biological
replicates. No result is an audited statistical test. The collector validates tissue arrays and
stores immutable cell JSON and float32 field chunks, served through the exact-run/cursor guard.
The selected experiment opens a Three.js tissue theater with cutaways, shared field scale,
cell inspection and paired conditions. Numerical sampling uses source coordinates and voxels;
CAF shape and membrane shading are illustrative. The skill-gated `tissue` research action shares
the CLI's scoped model/job/scene operations. Immutable agent revisions support separate scene-action
playback; rendered PNG bytes reach the model seam and unavailable vision cannot complete a review.
The sourced sensitivity study and actual-image reviews are recorded. Large scenes retain all source
cells through adaptive drawing and mobile aggregation; software-rendered motion measurements miss
the60/30fps targets, so hardware-accelerated throughput is not claimed.
See [tumor–stroma](docs/tumor-stroma.md).

### Spindle experiment adapter

`spindle/` validates source-linked numerical protocols and executes an operator-pinned
3D Cytosim CPU build with durable scoped receipts, cancellation, budgets and raw
archives. The registered `spindle` action publishes complete saved trajectories and
ensemble metrics into their owning experiment. New scientific hypotheses use new
experiment identities; scene revisions do not rerun mechanics. The inline spindle
observatory preserves source coordinates and physical samples, displays pole IDs
and comparison, and replays recorded scene actions separately from human exploration.
Immutable scene recipes, captures and actual image-bearing model observations use
the runtime journal and its playback visibility boundary. This is provisional,
uncalibrated mechanics; no p-values, biological sample counts or verification verdicts
are generated. See [spindle operations](docs/spindle-simulator.md).
