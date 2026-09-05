"""Launch the engine web UI.

    uv run python scripts/serve_ui.py [--port 8765] [--host 127.0.0.1]

Reads the engine's on-disk state under data/processed (reasoning traces + KG
DuckDB files) and serves a local dashboard: live run monitor, knowledge graph,
and the human-review queue. Read-mostly; the only writes are project records, job
launches and promotion decisions under data/projects/.
"""

import argparse

from dnhacksbio.webui.server import serve


def main() -> None:
    ap = argparse.ArgumentParser(description="Serve the discovery-engine web UI")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    serve(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
