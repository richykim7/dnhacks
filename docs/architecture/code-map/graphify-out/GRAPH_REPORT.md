# Graph Report - latest  (2026-09-06)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 1860 nodes · 3727 edges · 109 communities (92 shown, 14 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 206 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- ForecastReasoning.tsx
- metadata.py
- experiments.py
- test_forecasting_evaluation.py
- extract.py
- board.py
- FullTextStore
- geoharmonize.py
- run_scenario
- Handler
- llm.py
- projects.py
- attribution.py
- explorer.py
- ClaimGraph
- Journal
- ExplorationLog
- DepMap
- Path
- jobs.py
- corpus_build.py
- sandbox.py
- schema.py
- KGStore
- webui/__init__.py
- RuntimeDetail.tsx
- verifyqueue.py
- DeferralError
- snapshots.py
- evalue_real_data.py
- _entity
- grounding.py
- FrozenEncoder
- run_reasoning_comparison
- test_runtime.py
- VerifyQueue
- Explorer
- test_learned_evalue.py
- architecture.py
- fixtures.ts
- App.tsx
- store.py
- data.py
- _trace_path
- pr_digest.py
- learned_evalue.py
- reasoning.py
- refinement.py
- types.ts
- lineage.py
- resolve_process
- runtime.ts
- ValueError
- ._act_fork
- .run
- assistant.py
- Library.tsx
- datasets.py
- skills.py
- _raw
- forecasting.py
- test_forecasting_data.py
- gen_capability_index.py
- _kind_for
- attachments.py
- test_frontend_server.py
- board_mirror.py
- run_forecast_suite.py
- ._scope
- EntityState
- ._adjacency
- .write_back
- test_evidence_details.py
- Evidence.tsx
- Investigation.tsx
- main
- _ncit_norm
- update
- test_forecasting_presentation.py
- test_runtime_api.py
- collect
- run_tree
- ._act_run_experiments
- records.py
- _Model
- ForkBudget
- promote.py
- test_forecasting_memory_control.py
- mesh_kind
- resolve_repeat
- probe.py
- trace_audit.py
- build_frozen_depmap_tables.py
- ._turn_message
- ._judge_promise
- ncit_lookup
- .scope_key
- present.py
- build_coessentiality_table.py
- evalue_report.py
- ._act_submit
- .snapshot
- 21st.mjs
- render_report.py
- forecasting/__init__.py
- sources/__init__.py

## God Nodes (most connected - your core abstractions)
1. `KGStore` - 52 edges
2. `Explorer` - 51 edges
3. `Journal` - 34 edges
4. `DeferralError` - 32 edges
5. `extract_paper()` - 27 edges
6. `ExplorationLog` - 26 edges
7. `ground_curie()` - 24 edges
8. `Handler` - 22 edges
9. `load()` - 21 edges
10. `build()` - 20 edges

## Surprising Connections (you probably didn't know these)
- `test_concurrent_serialization_idempotency_and_resume()` --uses--> `Journal`  [INFERRED]
  tests/test_runtime.py → src/dnhacksbio/explorer/runtime.py
- `test_sqlite_rolls_back_incomplete_event_transaction()` --uses--> `Journal`  [INFERRED]
  tests/test_runtime.py → src/dnhacksbio/explorer/runtime.py
- `main()` --uses--> `KGStore`  [INFERRED]
  scripts/embed_kg.py → src/dnhacksbio/litmap/store.py
- `test_graph_preserves_distinct_measured_properties()` --uses--> `KGStore`  [INFERRED]
  tests/test_evidence_details.py → src/dnhacksbio/litmap/store.py
- `test_optional_paper_metadata_and_empty_evidence_remain_explicit()` --uses--> `KGStore`  [INFERRED]
  tests/test_evidence_details.py → src/dnhacksbio/litmap/store.py

## Import Cycles
- None detected.

## Communities (109 total, 14 thin omitted)

### Community 0 - "ForecastReasoning.tsx"
Cohesion: 0.06
Nodes (43): download(), Forecasting(), short(), stages, typeLabels, year(), ConditionId, Evaluation (+35 more)

### Community 1 - "metadata.py"
Cohesion: 0.07
Nodes (49): _cand_key(), Candidate, dedup_candidates(), estimate_completeness(), europepmc_search(), fetch_fulltext(), _jats_license(), _jats_to_text() (+41 more)

### Community 2 - "experiments.py"
Cohesion: 0.11
Nodes (39): biological(), finite_audit(), hidden_box_oracle(), main(), matched(), Reproducible finite audits and matched-budget mechanisms (stdlib only). Run:…, Exact adaptive Bellman oracle: pay to reveal, then pay to execute child. The…, Exact same-information Bellman oracle under a uniform one-prize prior. A query… (+31 more)

### Community 3 - "test_forecasting_evaluation.py"
Cohesion: 0.09
Nodes (42): main(), Evaluate complete forecasting runs against a separate outcome file. uv run…, digest(), evaluate(), fixture_completion(), main(), prepare(), No-retrieval memory control: the model scores every sealed candidate with zero… (+34 more)

### Community 4 - "extract.py"
Cohesion: 0.08
Nodes (43): ApiUnavailable, build_prompt(), _category_menu(), _claim_organism(), _context(), _corpus_organism(), _experiment(), _experiment_for() (+35 more)

### Community 5 - "board.py"
Cohesion: 0.14
Nodes (41): datetime, active_state(), agent_name(), cache_dir(), cmd_check(), cmd_init(), cmd_post(), cmd_show() (+33 more)

### Community 6 - "FullTextStore"
Cohesion: 0.07
Nodes (28): main(), Populate the full-text store from a local corpus directory (offline: no re-…, _cap_threads(), embed(), embed_one(), _get(), max_similarity(), rank() (+20 more)

### Community 7 - "geoharmonize.py"
Cohesion: 0.08
Nodes (31): _build_symbol_index(), compare_scales(), Dataset, _explode_symbols(), load(), _looks_normalized_unit(), _meta_from_gsms(), _needs_log2() (+23 more)

### Community 8 - "run_scenario"
Cohesion: 0.09
Nodes (33): main(), Build a computed replay from a historical scenario; never opens outcome files., _branches(), _canonical(), _date(), Path, Deterministic historical-evidence acquisition and forecast replay. No outcome…, Serialize committed predictions without overwriting an existing run. (+25 more)

### Community 9 - "Handler"
Cohesion: 0.12
Nodes (16): BaseHTTPRequestHandler, main(), Launch the engine web UI. uv run python scripts/serve_ui.py [--port 8765]…, Handler, _json_safe(), HTTP server for the engine web UI. stdlib only. ThreadingHTTPServer so a long-…, The active project, if the client scoped the request to one. `project=all` is…, Raw-body upload: the filename rides in X-Filename, the bytes are the body. Not… (+8 more)

### Community 10 - "llm.py"
Cohesion: 0.07
Nodes (25): ClaudeAgentOptions, live_completion(), _live_completion(), acomplete(), _block_to_dict(), _msg_to_dict(), _opts(), parse_json() (+17 more)

### Community 11 - "projects.py"
Cohesion: 0.13
Nodes (36): remove(), _adopted(), attachments_dir(), _blank(), built_manifest(), claim_count(), corpus_card_path(), create() (+28 more)

### Community 12 - "attribution.py"
Cohesion: 0.08
Nodes (33): AttributionVerdict, _ay_key(), cited_sources(), CitedSource, classify(), classify_certainty(), _clean_doi(), _expand() (+25 more)

### Community 13 - "explorer.py"
Cohesion: 0.09
Nodes (27): _fail(), main(), Run the explorer — one curious agent that roams the graph + reads papers,…, Write a terminal `fail` event if this run was launched with a progress stream., Find the corpus card for this run: an explicit --corpus-card path wins; else…, _resolve_card(), _run(), _finite() (+19 more)

### Community 14 - "ClaimGraph"
Cohesion: 0.08
Nodes (18): ClaimGraph, _now(), Path, Claim graph persistence: the DuckDB store where extracted claims become a graph…, Write one paper's extraction. Idempotent: everything for `source_ref` is…, Remove everything a source contributed, then drop any claim left with no…, Claims on the same question that disagree. Not a verdict: a pair may be wild-…, Every source asserting a claim, optionally filtered by context slot and value. (+10 more)

### Community 15 - "Journal"
Cohesion: 0.14
Nodes (19): Journal, process_identity(), process_namespace(), Path, Durable runner-owned execution journal. SQLite commits serialize every branch.…, Canonical backend snapshot, mirrored by the frontend reducer and parity…, Best-effort common secret redaction, NOT a general secret detector., redact() (+11 more)

### Community 16 - "ExplorationLog"
Cohesion: 0.12
Nodes (11): ExplorationLog, _now(), Path, Exploration log: the explorer's structured episodic memory and the tree-search…, This branch's own experiments that carry a parsed result and have not been…, Normalize a run-scope spec into (sql_fragment_without_leading_AND, params): -…, The tree-search frontier: open/promising nodes worth expanding next, best score…, Fold a verifier or human verdict back onto the experiment entry it came from —… (+3 more)

### Community 17 - "DepMap"
Cohesion: 0.13
Nodes (17): main(), Materialize analysis-ready DepMap tables for the explorer sandbox. The clean…, _assert_harmonized(), _clean_symbol_cols(), DepMap, harmonize(), _load_matrix(), DataFrame (+9 more)

### Community 18 - "Path"
Cohesion: 0.12
Nodes (27): _count_lines(), _declared_project(), _fork_index(), _iter_fork_records(), kg_graph(), kg_sources(), list_runs(), _load_run_index() (+19 more)

### Community 19 - "jobs.py"
Cohesion: 0.14
Nodes (26): kg_lane(), The Workflow view's Knowledge-graph lane, lit up. Two sources, in priority…, active_job(), _alive(), cancel(), events(), get_job(), _job_paths() (+18 more)

### Community 20 - "corpus_build.py"
Cohesion: 0.13
Nodes (19): Candidate, _attachment_documents(), build(), BuildError, _extract_with_progress(), _finish_project(), _main(), _matches_any() (+11 more)

### Community 21 - "sandbox.py"
Cohesion: 0.14
Nodes (25): build_image(), _build_run_argv(), _detect_native(), _docker_argv(), docker_ok(), ensure_image(), image_exists(), _is_native() (+17 more)

### Community 22 - "schema.py"
Cohesion: 0.10
Nodes (17): ClaimSpine, The claim atom: the typed model every extracted assertion must satisfy before…, The machine-comparable core: every component is a resolved identifier, a closed…, Keep direction in one place, at construction. Some aspect words carry direction…, What kind of statement this is, read off the canonical predicate., The direction, read off the canonical predicate., The question: does subject affect this property of object? Context-free,…, One distinct assertion: subject, object, aspect, relation class, canonical… (+9 more)

### Community 23 - "KGStore"
Cohesion: 0.11
Nodes (10): KGStore, Path, Write one paper's extraction into the claim graph (idempotent per source)., Record the human verdict (validated | rejected) and its note on a tested edge., Attach an external-novelty verdict (known|contradicts|distant-field|open) to a…, Every claim as one row of the `claim_edges` view. Cached until the next write., The text a claim edge is embedded from: labels plus mechanism, so search…, Embed these edges in one batched call and persist them. Returns {claim_id:… (+2 more)

### Community 24 - "webui/__init__.py"
Cohesion: 0.14
Nodes (22): _connect_ro(), _count_where(), _db_for_run(), _iso_to_unix(), promotion_cards(), DuckDBPyConnection, Queue + tested-layer + human-gate events for the whole tree, from the DB where…, Every run in the investigation tree `run_id` belongs to, so opening any run in… (+14 more)

### Community 25 - "RuntimeDetail.tsx"
Cohesion: 0.16
Nodes (13): Disclosure(), ErrorNotice(), Loading(), Modal(), Status(), descriptions, ResearchProcess(), Structures (+5 more)

### Community 26 - "verifyqueue.py"
Cohesion: 0.13
Nodes (16): Async verification handoff between exploration (fast, self-judged) and…, Falsifier, _finite(), kill_kind(), kind_of_kill(), The falsifier: the engine's soundness gate. It judges statistical and design…, The kind of a KILL from its reason slug, or None if the slug is unknown., The kind of a kill, always: one of KILL_KINDS, or UNKNOWN_KILL when the slug is… (+8 more)

### Community 27 - "DeferralError"
Cohesion: 0.17
Nodes (8): field_validator, model_validator, DeferralError, Evidence, Raised when a claim cannot be built under the schema rules. Callers catch it…, The attestation: this source, in these exact words, asserts this claim. A null…, Closed here as well as on the spine., A restatement cannot carry an experiment: the authors did not run one.

### Community 28 - "snapshots.py"
Cohesion: 0.17
Nodes (19): main(), Build a reproducible historical packet from two locally cached CIViC releases., OutcomePacket, Scenario, build_civic_scenario(), future_outcomes(), historical_snapshot(), Path (+11 more)

### Community 29 - "evalue_real_data.py"
Cohesion: 0.17
Nodes (20): interval(), Wilson 95% binomial interval; uncertainty for simulation rejection rates., benchmark(), evaluate(), load(), main(), metadata(), permutation() (+12 more)

### Community 30 - "_entity"
Cohesion: 0.13
Nodes (19): _category_of(), _entity(), _entity_surfaces(), _feature(), _norm(), _path_for(), _process_surfaces(), Surface string -> resolved EntityRef, or DeferralError. Grounding is… (+11 more)

### Community 31 - "grounding.py"
Cohesion: 0.19
Nodes (21): _ambiguous_tie(), anatomy_lookup(), cell_line_lookup(), cell_type_lookup(), chebi_lookup(), family_lookup(), ground_curie(), _lex() (+13 more)

### Community 32 - "FrozenEncoder"
Cohesion: 0.19
Nodes (15): main(), Train a frozen encoder from a separate, one-row-per-unit TPM NPZ cohort., execution(), fit_autoencoder(), fit_pca(), FrozenEncoder, gene_names(), ndarray (+7 more)

### Community 33 - "run_reasoning_comparison"
Cohesion: 0.14
Nodes (17): main(), Save a three-condition reasoning run without opening any outcome packet., Synchronous entry point for scripts; async callers use…, run_reasoning_comparison(), load_scenario(), Load historical input only; never opens sibling outcome files., test_tracked_packet_hashes_references_and_temporal_separation(), historical() (+9 more)

### Community 34 - "test_runtime.py"
Cohesion: 0.17
Nodes (17): The explorer faculty — curious agents that roam the knowledge graph + read…, action(), make_explorer(), parametrize, skipif, test_artifacts_reject_invalid_and_escaped_files(), test_audit_storage_failure_blocks_execution(), test_concurrent_serialization_idempotency_and_resume() (+9 more)

### Community 35 - "VerifyQueue"
Cohesion: 0.13
Nodes (10): _feedback_status(), _now(), Path, Every adjudicated result in this investigation tree, most recent first: the…, Recoverable publication from the durable queue; event IDs make retries…, Process every queued submission for a run: local soundness (direction, null,…, Map a verifier verdict to the tree-search action the explorer takes on that…, The explorer drops a self-judged experiment. `result` carries the standardized… (+2 more)

### Community 36 - "Explorer"
Cohesion: 0.15
Nodes (6): Explorer, One claim edge as the model reads it: labels first, resolved ids in brackets., {claim_id: vector} for the KG edges, read once per investigation from the index…, Rank KG edges by meaning (cosine to the query) rather than substring, so…, Declare a read-side cap to the agent; an unannounced cap reads as completeness…, _shown()

### Community 37 - "test_learned_evalue.py"
Cohesion: 0.26
Nodes (18): data(), parametrize, skipif, Contract, leakage, exact-null, artifact and replay tests for diagnostics., run(), test_adaptive_wealth_is_fair_over_all_pair_orientations(), test_cuda_training_replay_rng_and_portable_encoder(), test_exact_null_swap_average_of_product_is_one() (+10 more)

### Community 38 - "architecture.py"
Cohesion: 0.22
Nodes (17): AST, ArchitectureDrift, build(), const(), counted_dir(), default_arg(), dispatch_actions(), _find_def() (+9 more)

### Community 39 - "fixtures.ts"
Cohesion: 0.18
Nodes (14): evidenceApi(), events, experiments, ids, investigation, mockApi(), project, runs (+6 more)

### Community 40 - "App.tsx"
Cohesion: 0.18
Nodes (11): App(), readRoute(), View, useResource(), actionLabel(), human(), id, number() (+3 more)

### Community 41 - "store.py"
Cohesion: 0.14
Nodes (11): main(), Build the KG's semantic index: embed every claim edge once and persist it in…, _f(), _i(), _now(), The explorer-facing store over one DuckDB file. The literature claim graph…, Write one engine experiment's outcome onto the working graph as a tested edge.…, Column-named INSERT of one engine_tests row from a full dict. Returns the new… (+3 more)

### Community 42 - "data.py"
Cohesion: 0.18
Nodes (17): apply_promotions(), _kg_db_for_project(), kg_stats(), promotion_decisions_path(), Data-access layer for the engine web UI. Everything the frontend shows is…, Everything the console needs to describe one project's graph in numbers, in one…, Where a project's pending verdicts are collected before they are applied. Per-…, UI-written promotion decisions: {test_id: {decision, note}}. (+9 more)

### Community 43 - "_trace_path"
Cohesion: 0.12
Nodes (18): _beam_badge(), _count_complete_lines(), investigations(), _job_for_run(), _normalize_step(), parse_run(), phase_for(), The beam badge for one branch, read from its parent's trace only (cheaper than… (+10 more)

### Community 44 - "pr_digest.py"
Cohesion: 0.24
Nodes (16): arrange_diff(), build_prompt(), drain_stdin(), _file_rank(), format_message(), gh(), log(), main() (+8 more)

### Community 45 - "learned_evalue.py"
Cohesion: 0.18
Nodes (13): Explicit numerical execution settings shared by e-value training tools., identifiers(), Reject missing identifiers rather than turning None/NaN into donor names., _fit(), learned_two_sample_e(), LearnedE, _log_payoffs(), _network() (+5 more)

### Community 46 - "reasoning.py"
Cohesion: 0.19
Nodes (16): arun_reasoning_comparison(), _digest(), fixture_completion(), _index(), prepare_reasoning(), Controlled, historical-only graph reasoning; outcome evaluation is a separate…, Illustrative provider. It demonstrates plumbing and makes no empirical claim., Execute equally allocated calls; actual token usage and failures remain… (+8 more)

### Community 47 - "refinement.py"
Cohesion: 0.20
Nodes (16): fields(), pairs(), _predicate_refines(), Any, Is one claim a special case of another? Claim identity is an exact hash, so…, Why `specific` is a special case of `general`, or None if it is not., Every (specific, general, why) among a set of claims sharing one abstract_key.…, Is `specific`'s subject a narrower form of `general`'s subject, regardless of… (+8 more)

### Community 48 - "types.ts"
Cohesion: 0.13
Nodes (13): ClaimDetail, ClaimEdge, EvidenceGraph, Paper, Beam, Experiment, Graph, Investigation (+5 more)

### Community 49 - "lineage.py"
Cohesion: 0.15
Nodes (15): ancestors(), child(), depth(), parent(), Path-encoded run_id: the branch's self-describing lineage key. A run_id is a…, The investigation id — everything before the first separator (the whole id for…, How far down the fork tree this branch is; 0 = the root run., The parent branch's run_id (lop the last segment), or None if this is the root. (+7 more)

### Community 50 - "resolve_process"
Cohesion: 0.15
Nodes (16): canonical_curie(), demote_regulation_term(), may_mint(), _mesh_ok(), _ols_exact(), process_candidates(), _process_ontologies(), May this identifier become a node of this kind? False means route or refuse,… (+8 more)

### Community 51 - "runtime.ts"
Cohesion: 0.20
Nodes (11): post(), request(), useAgent(), emptyRuntime(), reduceRuntime(), RuntimeEvent, RuntimeState, runtimeUrl() (+3 more)

### Community 52 - "ValueError"
Cohesion: 0.28
Nodes (14): _e(), e_bh(), e_to_p(), from_log(), mean_merge(), p_to_e(), product_merge(), Evidence utilities. Inputs must already be valid for the declared null/family.… (+6 more)

### Community 53 - "._act_fork"
Cohesion: 0.14
Nodes (9): _adversarial_brief(), _leaf_brief(), The turn-1 message a freshly forked leaf child receives instead of the full…, Build a child leaf branch that shares this branch's DB and fork budget…, Collect a branch's own findings into a structured digest the orchestrator…, Write the promise judge's ranking to the exploration log the moment it is…, One generation of recursive beam search. The orchestrator for this fork: 1.…, The turn-1 message for the adversarial leaf the engine adds to every fork.… (+1 more)

### Community 54 - ".run"
Cohesion: 0.21
Nodes (5): One think→act→observe cycle on the persistent session. `message` is turn 1's…, Autonomous loop on one persistent resumable session (the agent's working…, Record run_id -> sdk_session_id on disk, so a stopped run can be resumed. The…, Get the model's next-action text for this turn, capturing its thinking blocks…, One action for this turn. An unparseable reply retries the turn with the…

### Community 55 - "assistant.py"
Cohesion: 0.23
Nodes (13): _ask(), AssistantUnavailable, chat(), _context(), RuntimeError, The onboarding assistant — natural language in, a corpus spec out. Designing a…, The LLM seam is not reachable. The manual path still works, so say that., Separate the prose reply from the proposed spec patch. (+5 more)

### Community 56 - "Library.tsx"
Cohesion: 0.17
Nodes (5): CreateProject(), Documents(), LaunchInvestigation(), Library(), AnimatedTabs()

### Community 57 - "datasets.py"
Cohesion: 0.23
Nodes (12): _geo_ids(), _norm(), Dataset discovery: the analog of litmap.find for data rather than papers.…, Search the ArrayExpress collection in BioStudies (functional-genomics…, Fan out across repositories; return a merged, de-duplicated candidate list.…, The common candidate shape every repo search returns., Rank a query's terms for GEO: gene-symbol-like tokens first (the specific…, Search GEO DataSets/Series. Returns curated GDS + user GSE records with sample… (+4 more)

### Community 58 - "skills.py"
Cohesion: 0.22
Nodes (12): get_skill(), list_skills(), _parse_header(), Path, Skill library loader — the explorer's menu of methods. A skill is a…, Rank skills by relevance to a free-text question (keyword over name+one-…, Every skill's header (name + one-liner + category + library/license). Cheap to…, The full SKILL.md text — what the explorer reads before writing code for that… (+4 more)

### Community 59 - "_raw"
Cohesion: 0.15
Nodes (13): ground_entity(), ground_gene(), Resolve one context slot's surface string, using the slot to constrain the…, Surface string -> a non-gene grounding via Gilda (chemical, drug, disease,…, A foreign id in an owned category -> the owner's id, or '' when no equivalence…, Prefer a local gilda install; fall back to the REST service. Force REST with…, Gilda matches as normalized dicts [{db,id,entry_name,organism,score}], best…, Surface string -> canonical HGNC symbol when Gilda maps it confidently to a… (+5 more)

### Community 60 - "forecasting.py"
Cohesion: 0.33
Nodes (12): demo_packet(), _digest(), _forecasts(), _paths(), Path, Read-only presentation of saved forecasting artifacts; never used as scorer…, The separate outcome evaluation is added only to completed model replays., Show saved progress independently of the sealed outcome evaluation. (+4 more)

### Community 61 - "test_forecasting_data.py"
Cohesion: 0.37
Nodes (12): historical(), Temporal input isolation, cross-release identities, and derived-packet…, row(), snapshot(), test_citation_schema_and_missing_dates(), test_edits_to_old_ids_and_out_of_window_rows_are_not_new_evidence(), test_historical_builder_and_loader_reject_later_evidence(), test_historical_candidates_exclude_known_pairs_and_preserve_endpoint_eligibility() (+4 more)

### Community 62 - "gen_capability_index.py"
Cohesion: 0.26
Nodes (11): _claim_layer(), _explorer_layer(), Render `docs/CAPABILITIES.md` FROM the live code. Everything here is read out…, The predicate vocabulary a literature claim may carry., The falsifier's verdicts and thresholds: the numbers that decide whether a…, The reasoning agent's own closed vocabularies., The knowledge-graph tables, introspected from a freshly created database., render() (+3 more)

### Community 63 - "_kind_for"
Cohesion: 0.18
Nodes (12): entity_candidates(), _go_meta(), go_namespace(), go_obsolete(), _kind_for(), kind_from_curie(), (branch, is_obsolete) for a GO term, from one cached OLS fetch. The obsolete…, Which GO branch a term belongs to: biological_process | molecular_function |… (+4 more)

### Community 64 - "attachments.py"
Cohesion: 0.26
Nodes (11): add(), listing(), next_ref(), _parse(), Path, Attachments — the scientist's own documents, parsed at upload time. A…, The next never-used corpus ref. Monotonic over the project's whole history: it…, Store one uploaded document, parse it to text, and register it on the project. (+3 more)

### Community 65 - "test_frontend_server.py"
Cohesion: 0.23
Nodes (11): get(), http(), fixture, parametrize, Frontend integration contracts. No model calls or live project mutations., test_built_frontend_and_assets(), test_experiment_evidence_and_query_errors_are_exposed(), test_missing_build_is_actionable() (+3 more)

### Community 66 - "board_mirror.py"
Cohesion: 0.38
Nodes (10): drain_stdin(), format_tg(), live_sessions(), log(), main(), nudge(), board_mirror.py — mirror the GitHub Board into a Telegram group chat, and back.…, sanitize() (+2 more)

### Community 67 - "run_forecast_suite.py"
Cohesion: 0.33
Nodes (10): digest(), evaluate_suite(), main(), paired_bootstrap(), prepare_suite(), Run a frozen all-query graph-representation comparison, then evaluate sealed…, Verify every saved run before the first outcome-file read., Never overwrite a protocol, run, or evaluation from an earlier attempt. (+2 more)

### Community 68 - "._scope"
Cohesion: 0.18
Nodes (7): _continue_brief(), _depth_nudge(), The turn-1 message a promoted branch receives when it is resumed: it was judged…, The durable-memory read scope for this branch (see exploration._run_filter /…, After the opening message (which already shows the current feedback and…, Depth-scaled fork guidance. A promoted survivor is exactly the branch whose…, Search the explorer's own episodic memory across all runs on this corpus…

### Community 69 - "EntityState"
Cohesion: 0.18
Nodes (6): EntityState, A mutant form is a different actor from the wild-type form., Route a construct out of the isoform slot at construction, via…, `variant`, `isoform` and `construct` are normalised and included: an L858R…, Does this state pin the actor down to a particular form?, Is this an explicit claim about the gene as a whole? Only a `general` state may…

### Community 70 - "._adjacency"
Cohesion: 0.22
Nodes (5): Map a free-text entity to a node id: case-insensitive exact match on an id or…, Undirected adjacency and per-node incident edges over the claim graph., The 1-hop neighbourhood: claim edges incident to `entity`, deduped.…, BFS out to `hops` from `entity`; the edges of the induced neighbourhood,…, Shortest claim-edge path between two entities (BFS over the undirected edge…

### Community 71 - ".write_back"
Cohesion: 0.18
Nodes (5): Recompute claim status from the graph's contradiction check. Disputed claims…, Record every result of an engine family. Returns a summary: written,…, Read tested edges, filtered by status (candidate or a kill kind), run_id or…, Entities that entered the working graph via an engine test but appear in no…, A compact map summary: counts, highest-degree hubs and contested edges, for the…

### Community 72 - "test_evidence_details.py"
Cohesion: 0.18
Nodes (8): collections(), fixture, parametrize, Real graph/schema checks for read-only, collection-scoped evidence inspection., test_graph_preserves_distinct_measured_properties(), test_locked_same_name_databases_cannot_reuse_another_collections_snapshot(), test_optional_paper_metadata_and_empty_evidence_remain_explicit(), test_unknown_collection_or_claim_never_falls_back()

### Community 73 - "Evidence.tsx"
Cohesion: 0.20
Nodes (4): Empty(), Evidence(), nodeTypes, Review()

### Community 74 - "Investigation.tsx"
Cohesion: 0.22
Nodes (5): AgentData, Investigation(), investigationTitle(), nodeTypes, RuntimeDetail()

### Community 75 - "main"
Cohesion: 0.27
Nodes (9): leaked_wealth(), main(), merge_reports(), permutation_p(), Reproducible synthetic DAVT diagnostics. Simulation is not a validity proof., Fixed, multivariate mean-distance statistic and plus-one randomization p., INVALID negative control: fit a lookup judge to the same labels it scores. On…, Pool rejection counts from compatible shards, never average quantiles. (+1 more)

### Community 76 - "_ncit_norm"
Cohesion: 0.22
Nodes (10): disease_lookup(), _ncit_norm(), nonhuman_gene_lookup(), _pro_lex(), pro_lookup(), Raw organism context ('C. elegans', 'worm', or 'NCBITaxon:6239') -> NCBITaxon…, A species-specific gene symbol -> its NCBI Gene id, within one non-human…, MONDO, the disease owner. (+2 more)

### Community 77 - "update"
Cohesion: 0.24
Nodes (10): apply_patch(), The human's accept action: merge an approved proposal into the stored spec., Launch a corpus build for a project. Refuses if one is already running.…, start_build(), _as_str_list(), _as_year(), Normalize + bound a spec. `for_build=True` additionally demands the fields a…, Merge a partial update. Only whitelisted fields — a client cannot invent record… (+2 more)

### Community 78 - "test_forecasting_presentation.py"
Cohesion: 0.20
Nodes (3): artifacts(), fixture, Saved replay presentation preserves analytical commitments and provenance.

### Community 79 - "test_runtime_api.py"
Cohesion: 0.20
Nodes (4): api(), fixture, test_new_run_discovery_before_first_legacy_trace(), test_reconciliation_requires_process_identity_and_ignores_heartbeat_delay()

### Community 80 - "collect"
Cohesion: 0.36
Nodes (8): collect(), Path, Collect only declared, bounded molecular files from a sandbox output directory., No symlink components; O_NOFOLLOW and fstat guard the final file, too., read_regular(), validate_structure(), test_collected_structure_is_durable_and_integrity_checked(), test_mmcif_parsing_and_quota()

### Community 81 - "run_tree"
Cohesion: 0.25
Nodes (9): _as_dict(), _fans(), _fork_index_for(), A JSON column as a dict, whether the caller handed us the raw string or an…, Which `run_experiments` step produced which entries: the FAN, one of the view's…, The investigation as a tree of experiments, as opposed to `run_events`, the…, Every fork generation in the tree, with the judge's ranking. Deduped on…, run_tree() (+1 more)

### Community 82 - "._act_run_experiments"
Cohesion: 0.25
Nodes (4): _diagnostics(), The supporting context for a successful experiment: the design fields that make…, Find new papers on the web, fetch their open-access full text, and store the…, Discover public datasets (GEO, ArrayExpress) matching a query: candidates with…

### Community 83 - "records.py"
Cohesion: 0.39
Nodes (7): Candidate, Claim, Evidence, Node, Outcome, Small JSON contracts; observed claims and candidate forecasts stay distinct., TypedDict

### Community 84 - "_Model"
Cohesion: 0.29
Nodes (5): BaseModel, ContextValue, _Model, One context slot, with how it was obtained. Most papers state the system once…, Base that surfaces one exception type (`DeferralError`) to callers, unwrapping…

### Community 85 - "ForkBudget"
Cohesion: 0.29
Nodes (4): ForkBudget, One tree-wide fork allowance the whole investigation draws down, shared by…, Consume up to k branches; return how many were actually granted (0 if the pool…, Return an unused grant (e.g. a branch that failed to fork) to the pool.

### Community 86 - "promote.py"
Cohesion: 0.33
Nodes (5): apply_decisions(), Promotion gate: the human seat at the back of the loop. The engine writes…, A suggestion only; the human decides. Keyed on the external novelty verdict., Apply human verdicts. A decision without a note is skipped. `validated` stamps…, _recommend()

### Community 88 - "mesh_kind"
Cohesion: 0.40
Nodes (5): mesh_kind(), _mesh_kinds(), _mesh_tree_kinds(), Kinds implied by a MeSH record's tree numbers. A supplementary concept record…, Which kind a MeSH descriptor denotes, from its tree numbers; '' when it should…

### Community 89 - "resolve_repeat"
Cohesion: 0.40
Nodes (5): The longest prefix every one of these family names shares., Repeat/TE family name -> a stable identifier, or None. Three tiers, strongest…, _repeat_query(), resolve_repeat(), _shared_prefix()

### Community 91 - "trace_audit.py"
Cohesion: 0.67
Nodes (3): audit(), main(), Read only frozen historical inputs and saved forecast runs, never outcomes.…

### Community 92 - "build_frozen_depmap_tables.py"
Cohesion: 0.67
Nodes (3): main(), Build analysis-ready tables from a chosen DepMap release directly from the…, _sym()

### Community 95 - "ncit_lookup"
Cohesion: 0.50
Nodes (4): _ncit_lex(), ncit_lookup(), Lazy singleton for the NCIt surface-form table., Exact normalised match into NCIt, the last resort for things no other…

## Knowledge Gaps
- **43 isolated node(s):** `ConditionId`, `Evaluation`, `Hypothesis`, `QueryMetrics`, `StudyBootstrap` (+38 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 689 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **14 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DeferralError` connect `DeferralError` to `extract.py`, `EntityState`, `ValueError`, `_Model`, `schema.py`, `_entity`?**
  _High betweenness centrality (0.080) - this node is a cross-community bridge._
- **Why does `KGStore` connect `KGStore` to `VerifyQueue`, `Explorer`, `.snapshot`, `._adjacency`, `.write_back`, `test_evidence_details.py`, `store.py`, `data.py`, `explorer.py`, `ClaimGraph`, `corpus_build.py`, `promote.py`, `verifyqueue.py`, `gen_capability_index.py`?**
  _High betweenness centrality (0.077) - this node is a cross-community bridge._
- **Why does `Explorer` connect `Explorer` to `test_runtime.py`, `VerifyQueue`, `._scope`, `._act_submit`, `FullTextStore`, `explorer.py`, `Journal`, `ExplorationLog`, `._act_run_experiments`, `._act_fork`, `.run`, `KGStore`, `._turn_message`, `._judge_promise`?**
  _High betweenness centrality (0.063) - this node is a cross-community bridge._
- **Are the 90 inferred relationships involving `ValueError` (e.g. with `biological()` and `.__post_init__()`) actually correct?**
  _`ValueError` has 90 INFERRED edges - model-reasoned connections that need verification._
- **Are the 9 inferred relationships involving `KGStore` (e.g. with `main()` and `_store_layer()`) actually correct?**
  _`KGStore` has 9 INFERRED edges - model-reasoned connections that need verification._
- **Are the 8 inferred relationships involving `Explorer` (e.g. with `_run()` and `ExplorationLog`) actually correct?**
  _`Explorer` has 8 INFERRED edges - model-reasoned connections that need verification._
- **Are the 12 inferred relationships involving `Journal` (e.g. with `collect()` and `Explorer`) actually correct?**
  _`Journal` has 12 INFERRED edges - model-reasoned connections that need verification._