"""Populate the full-text store from a local corpus directory (offline: no re-fetch, no tokens).

Loads the corpus via litmap.ingest and stores each paper's parsed text into the knowledge-graph DuckDB,
keyed by ref so it joins to the graph's evidence rows.

  uv run python scripts/build_fulltext_store.py
"""
from __future__ import annotations

from dnhacksbio.explorer.fulltext import FullTextStore
from dnhacksbio.litmap.ingest import load_corpus


def main() -> dict:
    docs = load_corpus()
    ft = FullTextStore()
    n = 0
    for d in docs:
        ft.add_paper(source_ref=d.ref, source_label=d.label,
                     doi=(d.source_id if d.source_id.startswith("10.") else ""),
                     pmid=(d.source_id if d.source_id.isdigit() else ""),
                     title=d.label, text=d.text, is_full_text=True)
        n += 1
    counts = ft.counts()
    ft.close()
    print(f"populated {n} papers -> {counts}")
    return counts


if __name__ == "__main__":
    main()
