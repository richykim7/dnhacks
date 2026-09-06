# Research workspace

The frontend is a new React + TypeScript application in `frontend/`, built with Vite, Tailwind v4, local shadcn-style components, Radix, Motion, React Flow (Dagre for the investigation tree, d3-force for the knowledge graph), and 3Dmol.js. It uses the existing Python JSON and SSE APIs. The old DOM-rendering JavaScript is retired.

## Run

Use Node 22.12+ and the repository's Python environment.

```sh
uv sync --extra dev
cd frontend
npm ci
npm run build
cd ..
uv run python scripts/serve_ui.py --port 8765
```

Open http://127.0.0.1:8765. The Python server serves `frontend/dist`; if it is missing, the server returns an actionable 503. `DNHACKS_FRONTEND_DIST` can point to a separately built artifact. This is a localhost research tool; this rewrite does not add public-hosting authentication.

Development uses two processes:

```sh
uv run python scripts/serve_ui.py --port 8766
npm --prefix frontend run dev
```

Open http://127.0.0.1:5174. Vite proxies `/api` to port 8766; override `API_PROXY_TARGET` for a different backend. No Node process is required for serving the production build. A Python wheel alone does not include the external frontend directory: deploy the build alongside it or set `DNHACKS_FRONTEND_DIST`.

## 21st.dev

The user-supplied key is stored only in the gitignored root `.env`, with owner-only file permissions, as `TWENTY_FIRST_API_KEY`. Never prefix it with `VITE_`, copy it into frontend source, put it into URLs, or commit it. Vite's default environment directory is `frontend/`, not the repository root. The app never needs this key at runtime.

```sh
cd frontend
npm run 21st -- search '{"query":"research toolbar","type":"component","limit":3}'
```

The development helper calls the official 21st HTTP MCP endpoint using an authentication header. `get_component` uses the account's retrieval quota; inspect the response for a paywall rather than treating it as source. `components.json`, Tailwind tokens, Radix and the `@/` alias support further component imports. Component provenance is in `frontend/THIRD_PARTY.md`.

## User-facing behavior

- Investigations: project-scoped roster and a full-viewport vertical researcher tree. Both left navigation panels have accessible collapse controls. Selecting a researcher expands it inline with smooth layout transitions; polling preserves the viewport. Experiments appear above bounded major steps, with raw diagnostics collapsed. The Candidates queue and producing-node badges open the owning experiment for explicit human review. New runs use ordered runtime events for lifecycle, actual model/tool execution, concise agent intent, worker heartbeat, streaming experiment output and deterministic playback. Select a node for its experiments and artifacts; Show terminal is opt-in and reports unavailable for SDK branches without a dedicated pane. Streams reconnect by cursor and close on navigation. Legacy trace-only runs are explicitly partial. See [runtime contract](runtime.md).
- Library: populated collections open to a scrollable paper browser with title, stored authors, publication year, local text/figure availability, title/author/DOI search, year/topic/availability filters and sorting. Selecting a paper opens a reading pane with stored text, section navigation and local figures; missing text, metadata and images are explicit. The reader can expand, and mobile returns to the list with Back to papers. The accent New collection action is visible with or without existing collections. Add papers is directly in the paper toolbar; each row has Read paper and Remove actions. Manage collection contains settings, supplemental documents, assistant and history; New collection is separate from the scoped New investigation action. Settings use chips for anchor DOIs/exclusions and progressive disclosure for advanced fields. Editing membership of a script-built source creates a separate collection; the source and its investigations are preserved. Busy or externally linked graphs reject membership writes.
- Knowledge: a full-height graph workspace with a compact toolbar and no permanent side panel. The initial overview shows up to 36 claims, ordered by the backend (disputed first, then source count); density controls expand to 160 or 800, the API cap. Counts state the displayed subset honestly, and database search/filters reach the whole collection. The 24 highest-degree entities retain labels at overview scale; zoom reveals the rest, and selecting an entity highlights its neighbors. Labels compensate for zoom for readability. The source inspector opens on entity/claim selection or explicit Browse, scrolls independently, and closes with Escape, its close button or the canvas. No review, combining or approval controls are mounted. The literature graph as stored, with nothing invented on the way to the screen, laid out as a force-directed graph (d3-force, deterministic, run to rest before first paint) rather than layered ranks. Each entity is a shape for its kind, sized by how many claims touch it in view, with its label beneath and its ontology identifier (linked through Bioregistry) in the inspector and on the selected node; edges carry the claim's sign in biological notation (arrowhead enables, bar represses, open dot for an unsigned predicate), line weight by distinct source count, and a dashed amber stroke for corpus-disputed claims. Claims between the same two entities fan apart so a dispute is visible as two edges. Search runs in the database over the whole collection; status, sign, entity kind and relation class filters are closed-vocabulary and show real counts. A summary strip states claims, entities, evidence records, papers (full text), reported experiments and engine tests with the graph file's modification time. Selecting a claim shows its status with what the word may mean (a source count, never approval or proof), the subject → predicate → object spine with entity state and variant, aspect, sources, first mention, mechanism and dispute kind, the other claims answering the same question, every engine test on the claim (predicted versus observed sign, effect, p, verifier outcome, reviewer decision and note, novelty), then each evidence record: paper with DOI/PubMed/PMC links, full-text and licence status, section, quotation, evidence type, study type, attribution and certainty with checker agreement, the source's own wording, what it cites, the experiment it reports, and biological context with provenance. Identifiers and extraction metadata sit in disclosures. Missing values say so. Review controls are not shown; backend decision and promotion APIs remain available.
- Molecular structures: only a selected node's collected experiment artifacts, inline in that experiment. No standalone Structures route, remote demo lookup or unrelated file picker. PDB/mmCIF coordinates are validated before durable collection; ribbon/atomic/surface modes, ambient occlusion, chain/residue controls, camera preservation and optional rotation use the public 3Dmol API without a fork. Artifact provenance distinguishes reference, prediction, derived geometry and illustration. No invented docking, confidence, mutation or binding scores.

Invalid/oversized/missing artifacts have explicit errors. A browser-side malformed PDB guard remains in addition to backend parsing; no renderable artifact means no viewer. Geometry is fetched only when inspecting its owning experiment, with run/project scope and immutable hash checks at the backend.

Research IDs live behind disclosures. New manifest questions survive job cleanup and resume; legacy job questions remain a fallback. A quiet trace is not labeled complete. Candidates remain unconfirmed until reviewed. Missing measurements say “Not measured.” New live/replayed node detail uses one reducer, so results, feedback, child branches and artifacts appear only at their recorded cursor. Legacy playback hides full present-day experiment detail. Full new observations are immutable referenced text, with explicit output-cap markers rather than silent summary truncation.

## Backend/UI audit fixes

- `run_tree` now includes the body, code, full structured result, raw output and provenance it previously fetched but discarded.
- Tree query errors are returned as `db_unreadable`, not swallowed into apparently empty results.
- SSE uses the same non-finite-to-null JSON sanitizer as snapshot responses.
- Static containment uses path ancestry, preventing sibling directories with a shared string prefix from passing the check.
- Investigation responses expose the question recorded by a launch job. Collection scope is never substituted for a research question.
- Frontend preserves project scope for knowledge inspection and displays build/spec drift. Legacy Evidence/Review links open Knowledge without exposing review controls.
- `GET /api/kg?source=&limit=&status=&polarity=&kind=&relation_class=&predicate=&q=` returns nodes with `kind` and `curie`, edges with `claim_id`, `abstract_key`, `polarity`, `relation_class`, `mechanism`, `first_year`, `n_sources`, `status`, `dispute_kind` and a `tested` overlay counted from `engine_tests`, plus `matched`, `total_claims`, `status_counts`, `facets`, `summary` and `as_of`. Filters are equality tests on closed vocabularies (unknown values are ignored); `q` is a case-insensitive substring match run in the database over labels, identifiers, predicate, aspect and mechanism. `GET /api/kg?source=<collection>&claim=<claim_id>` reads the exact collection's claim (with the entity-form columns the view drops), up to 100 evidence records each with contexts, citations, source paper and reported experiment, `evidence_total`, the other claims sharing its `abstract_key`, and its engine tests. Claim inspection requires an explicit source; unknown sources/claims return 404. Nothing here extracts papers, runs models or changes the graph. Older graph responses without IDs retain relationship browsing but cannot open source details.
- Lock-safe DuckDB snapshots include a hash of the resolved source path, preventing separate projects with the same `kg.duckdb` filename and modification time from sharing a cached snapshot.

## Validation

Choose checks for the changed behavior; the policy is in `AGENTS.md`. Documentation-only and
backend/coordination-only edits do not require unrelated UI or 3D suites.

| UI area | Browser selection after `npm --prefix frontend run e2e --` |
| --- | --- |
| Library, navigation, investigation tree, accessibility | `e2e/workspace.spec.ts` (use `--grep` for a specific flow) |
| Knowledge graph/evidence inspection | `e2e/evidence.spec.ts` |
| Runtime, experiment navigation, human review, molecular/inhibitor views | `e2e/runtime.spec.ts` (use `--grep` to select the affected flow) |
| Private branch-monitoring display | `e2e/monitor.spec.ts` |
| Binder viewer/camera/export | `e2e/binder.spec.ts` |
| Spindle viewer | `e2e/spindle.spec.ts` |
| Tissue viewer, exact-frame inspection and agent replay | `e2e/tissue.spec.ts` |

Local tests are optional by default (see `AGENTS.md`). For frontend changes, select a build,
focused unit/browser cases or manual visual inspection according to the affected behavior and risk.
Shared UI, API and dependency edits do not automatically require the full frontend suite.
Broaden only for a concrete integration risk or an explicit request.
New viewers should add their own spec to this table.

```sh
npm --prefix frontend run build
npm --prefix frontend run test -- src/lib/runtime.test.ts # substitute the affected unit test
npm --prefix frontend run e2e -- e2e/workspace.spec.ts --grep 'empty real backend'
# Full browser suite when its scope is relevant:
npm --prefix frontend run e2e
```

Install dependencies with `uv sync --extra dev` and `npm --prefix frontend ci`; install Chromium
once with `cd frontend && npx playwright install chromium`. The runner uses `.venv/bin/python`;
set `E2E_PYTHON=/absolute/path/to/python` to reuse another prepared development environment.
No manually launched Python or Vite server is needed.

### Concurrent agent sessions

`npm run e2e` uses `scripts/browser_tests.py`. One browser invocation per host/user runs at a time;
others print a waiting message and queue on a shared OS file lock. The lock covers all worktrees,
and releases on exit. This also limits contention from expensive software-rendered 3D tests.
Already-running older harnesses and other users' processes do not participate in this queue.

Each invocation starts its own backend from an empty temporary data directory and its own Vite
server from the requested checkout. Both bind OS-assigned ports. No existing development server
is reused, and no developer data is read or overwritten. Each run has a separate Vite cache,
Playwright artifacts and review screenshots under `frontend/test-results/run-*/`; its printed
path contains `run.json` with checkout/URLs, server logs and per-test artifacts. Artifacts persist
for review; the temporary backend data and owned process groups are cleaned up on normal exit,
failure or interruption. Do not kill another agent's servers or delete their run directories.
Use the npm wrapper, including for filtered runs; direct `playwright test` is rejected by config.
Separate worktrees are still required for concurrent edits/builds. The queue is not a machine-wide
CPU/GPU scheduler and cannot prevent load from unrelated jobs.

Browser fixtures under `frontend/e2e` are never imported by the application. Inspect relevant dark,
light and mobile captures after visual changes. The 3D viewer is code-split; 3Dmol's upstream bundle
contains an `eval` that Vite reports at build time. Playwright documents why [reusing an existing
server](https://playwright.dev/docs/test-webserver) can attach a run to an already-listening URL;
this harness instead owns the servers for the entire run.

### Binder candidate artifacts

Collected `binder_bundle.v1` artifacts open the lazy-loaded Interface Foundry inside their owning
experiment. The stage offers partner/contact colors, exact residue picking, opposing contact-only
cutaways, exploded presentation and camera/coordinate export. Accessible tables retain physical
atom-pair distances. Artifact hash checks precede rendering and historical availability uses the
existing event cursor. See [binder interface workbench](binder-design.md) for supported metrics,
provenance, visual-review records and incomplete live-design acceptance.

The comparison selector resolves another available binder in the same experiment. Exact target
coordinates, residue mapping and metric protocol must agree. One canvas and camera drive equal-size
views; picks return the candidate identity and its own contact metrics. Captures retain both source
hashes and viewport metadata, and historical playback removes unavailable comparison sources.

### Spindle trajectory development

Selected experiments can display validated `filament_trajectory` JSON artifacts
in the spindle observatory, using saved physical frames, persistent pole IDs,
condition switching, camera controls and local PNG export. This is an in-progress
exploratory viewer, not a calibrated spindle model or runtime vision pipeline.
See [spindle operations](spindle-simulator.md) for the contract and remaining work.

Binder scene history supports following the agent, action replay at 0.25–4× and independent
local exploration. Replay uses only recipes visible at the current runtime cursor. The production
workbench element provides a bounded controller for the local capture worker; only its convenient
window alias requires `?sceneReview=1`. Scene replay is not physical simulation time.

The selected experiment supports `tissue_simulation` artifacts through the Living tissue theater.
Exterior, Core and Neighborhood use instanced cell geometry and an optional bounded 3D field pass.
A section plane, exact simulation frame, shared comparison range and source-ID selection are
keyboard accessible. Dark/light styles and mobile single-condition exploration share the same
numerical data. Frame payloads load on demand with a three-frame cache; field textures are disposed
on replacement. The viewport scale is in micrometers at the focal plane. Membrane shading and
elongated CAF glyphs are illustration layers, never sampled measurements. Fixtures live only in
`frontend/e2e/tissue/`. See `docs/tumor-stroma.md` for implementation status and scientific boundaries.

For headless hosts without a usable graphics driver, set `PLAYWRIGHT_SOFTWARE_RENDERING=1` to
explicitly use Chromium SwiftShader. This keeps the same assertions and timeouts. Record this renderer
when reporting performance; browser screenshot success is not evidence of hardware GPU throughput.
The browser backend explicitly rebinds application journal, project, corpus, KG and
cache paths to its temporary data directory. Changing only the process cwd would
leave source-rooted application state visible; the runner regression checks that
a pre-existing journal cannot leak into the empty-backend test.

Binder bundles may include precomputed source-mapped surfaces. A browser worker performs parsing,
hash checks and normal preparation before the stage becomes ready. The representation selector
retains atomic envelopes and a labeled Cα trace; analytical close/reverse remain atomic cutaways.
See the binder guide for mesh approximation and exact source-picking semantics.

### Persistent researcher scenes

A researcher with an available binder or molecular structure opens a persistent inline workspace:
one selected collected source above its experiment records and major research steps.
The scene remains mounted while browsing the researcher’s records. The scene selector is restricted
to that researcher's available artifacts at the current cursor; rewinding removes later sources.
The selected experiment's binder is preferred, then its reference structure. Choosing another
source is a local viewing action and does not rewrite recorded agent activity. Mobile stacks the
scene above the research panel with an independently reachable close control.

Binder scene camera changes interpolate position, orbit target and FOV over700ms from the current
visible pose. A new target rebases that transition; OrbitControls interaction cancels it immediately.
Reduced motion disables transitions. Capture readiness waits for the transition and rendered frames,
and exported scene recipes retain the actual camera after manual navigation. Inspection action time
remains separate from physical simulation time. The projection selector also offers orthographic
constant-scale comparison; its height/zoom travel with the saved camera and captures.

The reference viewer's Open inhibitor workbench action replaces that viewer inline in the same
inline scene. Research activity remains in the same expanded node, and Return to reference restores the original
viewer. Only one molecular viewer is mounted. Embedded inhibitor controls open as an overlay;
its recorded-action Follow/Replay behavior is unchanged.

### Library paper reading

`GET /api/projects/<id>/papers` lists every stored graph paper without retrieval or extraction.
`GET /api/projects/<id>/papers/<paper_id>` returns its stored text and figure metadata;
`GET /api/projects/<id>/papers/<paper_id>/figures/<index>` serves a locally stored image.
The existing lock-safe read-only connection is used. Optional corpus `MANIFEST.json` and
local citation metadata supply categories, authors and figures; absent metadata is not inferred.
Figure paths are bounded to that corpus's paper directory. Nothing downloads publisher content.
The reader renders extracted text safely, preserves publication front matter in a disclosure
when an Abstract heading exists, and keeps original-source links for missing local content.

For real-data visual review, `frontend/e2e/library.spec.ts` accepts
`LIBRARY_REVIEW_SNAPSHOT=/tmp/library-review.json` containing a read-only exported project,
list, per-paper details and local figure-URL mappings. Use the normal browser harness;
it intercepts only GETs against the snapshot and never writes to the source corpus.
Without the local snapshot these optional review cases explicitly skip. No paper text
or image fixtures are committed.

For real Knowledge visual review, `frontend/e2e/knowledge-review.spec.ts` accepts
`KNOWLEDGE_REVIEW_SNAPSHOT=/tmp/knowledge-review.json`: a read-only `/api/kg?limit=800`
response with an additional `_details` map keyed by the first edge's claim ID, holding
its exact claim-detail response. The normal browser harness serves this local snapshot,
checks the full workspace, density control and source scrolling, and captures desktop,
light and mobile views. Without a snapshot the optional case explicitly skips.
No corpus records or quoted paper text are committed.

### Adding and removing Library papers

The Add papers dialog accepts DOI/DOI links (up to 50 per request) or one PDF, text,
Markdown or XML upload. Submission explicitly starts a detached `membership` job;
opening Library, opening the dialog and creating an empty collection start no model work.
The existing document conversion preserves available local figures, and the configured
reader/grounding/claim-repair path writes only new papers to the graph/full-text store.
Paper vectors and new/changed claim vectors are indexed through the existing embedding
modules. DOI/text hashes avoid duplicate extraction. The optional `litmap` dependencies
are required for PDF conversion (`uv sync --extra litmap`).

Library polls durable job stages and exposes actionable errors and Retry processing.
Source, reader and extraction checkpoints are saved per new source ref; retry reuses
completed stages instead of sending existing papers through extraction again. Truncated
reader output and unavailable repair/indexing fail explicitly. An index failure may leave
the added full text and graph visible while the job remains failed; retry completes indexing.

Routes: `POST /api/projects/<id>/papers/add` with `{dois: [...]}`, raw-body
`POST /api/projects/<id>/papers/upload` with `X-Filename`,
`POST /api/projects/<id>/papers/<paper_id>/remove`, and
`POST /api/projects/<id>/jobs/<job_id>/retry`. Responses include `project_id` and
`copied`; the frontend selects the separate editable collection when one is created.

A membership write refuses a busy project, a database held by another writer, or a
project graph linked outside its own directory. Script-built corpora are copied only
while an original read lock can be held and no pending WAL exists. Their graph, paper
assets and original corpus card remain intact. Build/run/membership launchers share an
inherited project lease. Workers receive the exact projects root explicitly, including
when a private preview uses isolated data; they never fall back to live data.

Removal is collection-scoped and transactional: it deletes the paper, its evidence,
contexts, citations, experiments and deferrals, removes now-unsupported affected claims
and orphan claim vectors, and recomputes support/disputes. Other papers' support and
unrelated engine claims remain. Original assets and historical records are retained;
manifest/count/card updates describe current membership. A durable removed-source marker
prevents an older failed addition retry from resurrecting a removed paper.

### Investigation candidate review

Automated candidate emissions are deduplicated by recorded experiment/submission and retry identities.
Candidate badges never mean human acceptance. Fresh heartbeats permit restrained activity animation;
stale workers, idle researchers and historical playback do not animate progress. Replay derives counts,
experiments, human decisions and artifact access from the same event cursor.

`GET /api/review/candidate?run=<run>&experiment=<experiment>&project=<project>` resolves the exact
runtime provenance association to the collection's candidate test. It exposes the submitted claim,
result/code, recorded verification, linked literature quotations and existing decision. Missing or
ambiguous associations remain unavailable instead of guessing. The review view loads only in Latest state.
`POST /api/review/candidate` accepts `run`, `experiment`, optional `project`, `decision` (`validated` or
`rejected`) and a required note of at most 400 characters. It saves the decision and applies only that card
through the established promotion gate. Acceptance copies supported source records into master; rejection
records a correction. Writer locks or publication failures leave a visible saved decision with an explicit
Apply saved decision retry. Identical retries are idempotent, conflicting decisions are rejected, and
applied decisions publish cursor-scoped human-review events. Existing bulk promotion endpoints remain
available and share the same decision lock. Graph application also holds the Library/build/run collection
lease; busy collections retain saved decisions. No decisions are submitted automatically by opening a view.

Focused coverage: `npm --prefix frontend run e2e -- e2e/investigation.spec.ts` and
`uv run pytest tests/test_candidate_review.py`. The latter uses a temporary project, master graph and
runtime journal to exercise real persistence; it never submits decisions to a live investigation.
