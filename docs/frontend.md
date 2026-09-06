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

- Investigations: project-scoped live roster; spatial agent tree; selected agent SSE activity; experiment details including code, result and provenance; recorded activity playback; explicit errors and unresolved links. Streams close on navigation and reconnect using event IDs. Snapshot polling discovers newly forked agents every five seconds. UI activity means recorded engine steps, not token-by-token model output.
- Library: create a project; edit all collection fields; preview/build; upload/remove documents; assistant conversation and proposed settings; build/run history, progress, logs, and cancellation. Imported collections remain read-only where the API requires it.
- Evidence: scoped literature graph and claim status filters; entity detail; required rationale for accept/reject; saved decisions applied through the existing promotion gate.
- Structures: real user-selected PDB/mmCIF geometry, remote PDB lookup or local files, ribbon/atomic/surface representations, residue selection, camera reset and optional rotation. This is a reference viewer. There are no invented docking, confidence, mutation or binding scores. Local files stay in the browser and are not persisted to a project. Future engine structure artifacts need an explicit association and provenance contract.

PDB files with no `ATOM  ` or `HETATM` coordinate records show the existing “No atoms could be read” error before loading 3Dmol. Selecting such a file clears previous geometry and retains the selected filename. PDB files containing coordinate records and mmCIF files continue through the viewer's full parsing and validation.

Research IDs live behind disclosures. Job questions title investigations when available. A quiet trace is not labeled complete. Candidates remain unconfirmed until reviewed. Missing measurements say “Not measured.” Historical playback hides present-day experiment detail to avoid showing future results. History events are bounded summaries from the existing API; full observations remain in latest agent detail.

## Backend/UI audit fixes

- `run_tree` now includes the body, code, full structured result, raw output and provenance it previously fetched but discarded.
- Tree query errors are returned as `db_unreadable`, not swallowed into apparently empty results.
- SSE uses the same non-finite-to-null JSON sanitizer as snapshot responses.
- Static containment uses path ancestry, preventing sibling directories with a shared string prefix from passing the check.
- Investigation responses expose the question recorded by a launch job. Collection scope is never substituted for a research question.
- Frontend preserves project scope for evidence and promotion writes, displays build/spec drift, and exposes required review rationale.

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
