"""Local web UI for watching the discovery engine run.

A read-mostly frontend over the engine's on-disk state: the append-only
reasoning traces (JSONL) and the DuckDB knowledge-graph / ledger files.
Serves a no-build vanilla-JS single-page app. See `server.py` for the HTTP
layer and `data.py` for the (dependency-light) data-access layer.
"""
