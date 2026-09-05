"""Build the KG's semantic index: embed every claim edge once and persist it in the DB.

  uv run python scripts/embed_kg.py --db data/corpora/<name>/<name>_kg.duckdb

Run this at the end of a corpus build. The explorer's `search_kg` then reads the vectors straight out of DuckDB
instead of embedding at run time.

Why it belongs here and not in the explorer: the literature graph is static during a run, and embedding
every edge is blocking CPU work.

Idempotent and incremental — a vector is reused only while the edge's text is unchanged, so re-running
after ingesting new papers embeds just the new and changed edges.
"""
from __future__ import annotations

import argparse
import time

from dnhacksbio.litmap.store import DEFAULT_DB, KGStore


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DEFAULT_DB), help="KG DuckDB file to index")
    args = ap.parse_args()

    kg = KGStore(args.db)
    t0 = time.time()
    r = kg.embed_claims()
    kg.close()

    dt = time.time() - t0
    print(f"{args.db}: {r['n_claims']} claims — {r['n_embedded']} embedded, {r['n_cached']} already "
          f"current, {r['n_failed']} failed  ({dt:.1f}s)")
    if r["n_failed"]:
        raise SystemExit("embedding model unavailable — install sentence-transformers "
                         "(the explorer will fall back to keyword-only KG search)")


if __name__ == "__main__":
    main()
