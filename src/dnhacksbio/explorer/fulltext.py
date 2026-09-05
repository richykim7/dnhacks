"""Full-text store: every paper in the corpus, parsed and stored locally so the explorer reads it without
re-fetching. Lives in the same DuckDB as the knowledge graph, so a node's papers are a join away. Indexed
by keyword (LIKE over title+text) and by MiniLM embedding. The explorer uses `search_semantic` to roam by
meaning and `read` to read one.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from dnhacksbio.explorer import embed as E
from dnhacksbio.litmap.store import DEFAULT_DB


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _paper_id(doi: str, pmid: str, ref) -> str:
    if doi:
        return doi.lower().strip()
    if pmid:
        return f"PMID:{pmid}"
    return f"ref:{ref}"


class FullTextStore:
    def __init__(self, db_path: str | Path | None = None, con=None):
        # Share one connection across the memory layer (graph, papers, log and queue are one DB).
        self._owns = con is None
        if con is not None:
            self.con, self.db_path = con, None
        else:
            self.db_path = Path(db_path) if db_path else DEFAULT_DB
            if str(self.db_path) != ":memory:":
                self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self.con = duckdb.connect(str(self.db_path))
        self._schema()

    def _schema(self) -> None:
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS papers (
                paper_id VARCHAR PRIMARY KEY,
                source_ref INTEGER,          -- corpus ref number (joins to evidence.source_ref)
                source_label VARCHAR,
                doi VARCHAR, pmid VARCHAR, pmcid VARCHAR,
                title VARCHAR, year INTEGER,
                text VARCHAR,                -- parsed full text (or abstract if no OA full text)
                sections VARCHAR,            -- JSON {section: text}, optional
                license VARCHAR, url VARCHAR,
                is_full_text BOOLEAN, n_chars INTEGER,
                embedding FLOAT[],           -- of title + head-of-text (semantic search)
                fetched_at VARCHAR,
                -- identity provenance: how this paper's doi/title were obtained and how they were checked
                meta_method VARCHAR,         -- doi-front-matter | title-search | author-year-search | ...
                meta_overlap DOUBLE,         -- title-token overlap against the paper's own text
                meta_verified BOOLEAN,       -- cleared the verification gate
                meta_checked_at VARCHAR
            )""")

    # --- write ------------------------------------------------------------------------------------
    def add_paper(self, *, source_ref=None, source_label="", doi="", pmid="", pmcid="", title="",
                  year=None, text="", sections=None, license="", url="", is_full_text=False,
                  resolve_identity: bool = True) -> str:
        """Write one paper. This is the single path every paper takes, whether from a literature sweep or
        a user upload, and it is where identity is resolved: if the caller supplies no DOI and no PMID, one
        is resolved from the paper's own text and verified against it (litmap.metadata). An unresolvable
        paper is still stored, flagged `meta_verified = FALSE`, keyed on `ref:<n>`, and will not dedup.
        Pass `resolve_identity=False` for offline/test paths."""
        meta_method = meta_overlap = meta_verified = None
        if resolve_identity and not (doi or pmid) and len(text or "") > 500:
            try:
                from dnhacksbio.litmap import metadata as _M     # lazy: keeps import graph + network optional
                ident = _M.resolve(text=text, title_hint=title or source_label, year_hint=year)
                meta_method, meta_overlap, meta_verified = ident.method, ident.overlap, ident.verified
                if ident.verified:
                    doi, pmid = ident.doi or doi, ident.pmid or pmid
                    pmcid = pmcid or ident.pmcid
                    title = ident.title or title
                    year = year or ident.year
                else:
                    print(f"  unverified identity: {source_label or title or 'paper'!r} stored without a "
                          f"resolvable DOI/PMID (best overlap {ident.overlap}). It will not dedup.",
                          flush=True)
            except Exception as e:      # never let a metadata lookup block the write
                meta_method, meta_verified = f"error:{type(e).__name__}", False
        elif doi or pmid:
            meta_method, meta_verified = "caller-supplied", None

        pid = _paper_id(doi, pmid, source_ref)
        vec = E.embed_one(f"{title}\n\n{(text or '')[:1500]}")
        row = [pid, source_ref, source_label, doi, pmid, pmcid, title, year, text or "",
               json.dumps(sections) if sections else None, license, url, bool(is_full_text),
               len(text or ""), vec, _now(), meta_method, meta_overlap, meta_verified, _now()]
        self.con.execute("DELETE FROM papers WHERE paper_id=?", [pid])   # idempotent upsert
        self.con.execute(f"INSERT INTO papers VALUES ({','.join('?' * len(row))})", row)
        return pid

    # --- read / search ----------------------------------------------------------------------------
    def _rows(self, where="", params=None, cols="paper_id,source_ref,source_label,title,year,doi,pmid,"
                                              "is_full_text,n_chars,url"):
        q = f"SELECT {cols} FROM papers {where}"
        names = [c.strip() for c in cols.split(",")]
        return [dict(zip(names, r)) for r in self.con.execute(q, params or []).fetchall()]

    def get(self, paper_id: str) -> dict | None:
        r = self._rows("WHERE paper_id=?", [paper_id])
        return r[0] if r else None

    def read(self, paper_id: str, max_chars: int | None = None, max_year: int | None = None) -> dict | None:
        """Return a paper with its full text and sections. `max_year` is a freeze guard: a post-freeze paper
        is invisible even if its id is requested."""
        row = self.con.execute(
            "SELECT paper_id,source_label,title,year,doi,text,sections,is_full_text FROM papers "
            "WHERE paper_id=?", [paper_id]).fetchone()
        if not row:
            return None
        if max_year and row[3] and row[3] > max_year:
            return None            # frozen out
        text = row[5] or ""
        return {"paper_id": row[0], "source_label": row[1], "title": row[2], "year": row[3],
                "doi": row[4], "is_full_text": row[7],
                "sections": json.loads(row[6]) if row[6] else None,
                "text": text[:max_chars] if max_chars else text}

    def search_keyword(self, query: str, limit: int = 10, max_year: int | None = None) -> list[dict]:
        like = f"%{query.lower()}%"
        w, params = "WHERE (lower(title) LIKE ? OR lower(text) LIKE ?)", [like, like]
        if max_year:
            w += " AND year IS NOT NULL AND year<=?"; params.append(max_year)   # freeze filter
        return self._rows(w + " LIMIT ?", params + [limit])

    def search_semantic(self, query: str, limit: int = 10, max_year: int | None = None) -> list[dict]:
        qv = E.embed_one(query)
        if not qv:
            return self.search_keyword(query, limit, max_year)      # graceful fallback
        q, params = "SELECT paper_id, title, year, source_label, embedding FROM papers", []
        if max_year:
            q += " WHERE year IS NOT NULL AND year<=?"; params = [max_year]      # freeze filter
        rows = self.con.execute(q, params).fetchall()
        ranked = E.rank(qv, rows, vec_key=lambda r: r[4], top_k=limit)
        return [{"paper_id": r[0], "title": r[1], "year": r[2], "source_label": r[3],
                 "score": round(s, 3)} for s, r in ranked]

    def counts(self) -> dict:
        n, full = self.con.execute(
            "SELECT COUNT(*), COALESCE(SUM(CASE WHEN is_full_text THEN 1 ELSE 0 END),0) FROM papers"
        ).fetchone()
        return {"papers": n, "full_text": full}

    def close(self) -> None:
        if self._owns:
            self.con.close()
