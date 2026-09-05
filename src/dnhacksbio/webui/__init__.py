"""Local web UI for watching the discovery engine run.

A read-mostly frontend over the engine's on-disk state: the append-only
reasoning traces (JSONL) and the DuckDB knowledge-graph / ledger files.
Serves the React/Vite build from frontend/dist. See docs/frontend.md for setup,
`server.py` for HTTP and `data.py` for the dependency-light data-access layer.
"""
