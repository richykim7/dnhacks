# Research workspace

The frontend is a new React + TypeScript application in `frontend/`, built with Vite, Tailwind v4, local shadcn-style components, Radix, Motion, React Flow/Dagre, and 3Dmol.js. It uses the existing Python JSON and SSE APIs. The old DOM-rendering JavaScript is retired.

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

- Investigations: project-scoped roster and spatial agent tree. New runs use ordered runtime events for lifecycle, actual model/tool execution, concise agent intent, worker heartbeat, streaming experiment output and deterministic playback. Select a node for its experiments and artifacts; Show terminal is opt-in and reports unavailable for SDK branches without a dedicated pane. Streams reconnect by cursor and close on navigation. Legacy trace-only runs are explicitly partial. See [runtime contract](runtime.md).
- Library: create a project; edit all collection fields; preview/build; upload/remove documents; assistant conversation and proposed settings; build/run history, progress, logs, and cancellation. Imported collections remain read-only where the API requires it.
- Evidence: scoped literature graph with directed relationships, claim status filters, and a searchable relationship list. Selecting an edge or list result focuses its endpoints and opens stored quotations, paper metadata/links, attribution and per-source biological context. Search covers the loaded graph subset; it does not imply a full-corpus search. Missing quotations or source metadata remain explicit. Existing finding-review decisions still use the promotion gate.
- Molecular structures: only a selected node's collected experiment artifacts, inline in that experiment. No standalone Structures route, remote demo lookup or unrelated file picker. PDB/mmCIF coordinates are validated before durable collection; ribbon/atomic/surface modes, ambient occlusion, chain/residue controls, camera preservation and optional rotation use the public 3Dmol API without a fork. Artifact provenance distinguishes reference, prediction, derived geometry and illustration. No invented docking, confidence, mutation or binding scores.

Invalid/oversized/missing artifacts have explicit errors. A browser-side malformed PDB guard remains in addition to backend parsing; no renderable artifact means no viewer. Geometry is fetched only when inspecting its owning experiment, with run/project scope and immutable hash checks at the backend.

Research IDs live behind disclosures. New manifest questions survive job cleanup and resume; legacy job questions remain a fallback. A quiet trace is not labeled complete. Candidates remain unconfirmed until reviewed. Missing measurements say “Not measured.” New live/replayed node detail uses one reducer, so results, feedback, child branches and artifacts appear only at their recorded cursor. Legacy playback hides full present-day experiment detail. Full new observations are immutable referenced text, with explicit output-cap markers rather than silent summary truncation.

## Backend/UI audit fixes

- `run_tree` now includes the body, code, full structured result, raw output and provenance it previously fetched but discarded.
- Tree query errors are returned as `db_unreadable`, not swallowed into apparently empty results.
- SSE uses the same non-finite-to-null JSON sanitizer as snapshot responses.
- Static containment uses path ancestry, preventing sibling directories with a shared string prefix from passing the check.
- Investigation responses expose the question recorded by a launch job. Collection scope is never substituted for a research question.
- Frontend preserves project scope for evidence and promotion writes, displays build/spec drift, and exposes required review rationale.
- Graph edges preserve `claim_id`. `GET /api/kg?source=<collection>&claim=<claim_id>` reads the exact collection's claim and up to 100 evidence records, with `evidence_total`, source-paper metadata and context. Claim inspection requires an explicit source; unknown sources/claims return 404. It does not extract papers, run models or change the graph. Older graph responses without IDs retain relationship browsing but cannot open source details.
- Lock-safe DuckDB snapshots include a hash of the resolved source path, preventing separate projects with the same `kg.duckdb` filename and modification time from sharing a cached snapshot.

## Validation

```sh
npm --prefix frontend run build
npm --prefix frontend run test
npm --prefix frontend run e2e
uv run pytest tests/test_frontend_server.py
```

Playwright starts Vite if needed. The real empty-state check needs a Python server on 8766 with no recorded investigations. If your development data is populated, stop that development server and launch an isolated one from an empty working directory:

```sh
frontend_test_repo="$PWD" # run from the repository root
frontend_test_data=$(mktemp -d)
(cd "$frontend_test_data" && PYTHONPATH="$frontend_test_repo/src" "$frontend_test_repo/.venv/bin/python" "$frontend_test_repo/scripts/serve_ui.py" --port 8766)
```

Install the browser once if needed: `cd frontend && npx playwright install chromium`.
Browser fixtures are isolated under `frontend/e2e` and never imported by the application. The suite exercises live selection, evidence inspection, project edits, assistant proposals, review scope, playback, accessibility and mobile layout. Screenshots are written under `/tmp/dn-*.png`. Inspect dark, light and mobile captures after visual changes. The 3D viewer is code-split; 3Dmol's upstream bundle contains an `eval` that Vite reports at build time.

## Prepared forecasting demo

Open `/#forecast` for the checked-in historical replay, graph revisions, source-linked
recommendations and explicit later-evidence reveal. Recorded model memory has a separate
flat/static/evolving comparison. The illustrative provider supports a deterministic fallback
without measured claims. [Demo guide](forecasting-demo.md) documents the artifacts, API
boundaries, date semantics, and presentation script.
