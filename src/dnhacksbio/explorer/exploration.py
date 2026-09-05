"""Exploration log: the explorer's structured episodic memory and the tree-search frontier.

Every move the explorer makes is a typed entry (idea / experiment / observation / dead-end / open-question /
note), a flat ordered set scoped by `run_id`. Search is driven by status and score: `frontier()` returns
the promising open nodes to expand next; a node that fizzles is marked `dead`; a promising result is marked
`promising` or `submitted`. Branching lives one level up, in the fork tree of agents keyed by the
path-encoded `run_id` (`explorer/lineage.py`), which also decides what a branch may read. Every entry
stores its provenance (papers, claims, entities, parent entries) beside the reasoning that produced it, and
is indexed by keyword and MiniLM embedding so a restarted or parallel explorer finds prior thinking. It
lives in the same DuckDB as the graph and the full text.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from dnhacksbio.explorer import embed as E
from dnhacksbio.litmap.store import DEFAULT_DB

KINDS = ("idea", "experiment", "observation", "dead-end", "open-question", "note")
STATUSES = ("open", "promising", "dead", "submitted", "needs-retry", "reframe", "validated")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ExplorationLog:
    def __init__(self, db_path: str | Path | None = None, con=None):
        # Share one connection across the memory layer (graph, papers, log and queue are one DB). Pass
        # `con` to attach to an existing store; else open our own.
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
        self.con.execute("CREATE SEQUENCE IF NOT EXISTS explore_seq START 1")
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS exploration (
                entry_id BIGINT PRIMARY KEY,
                run_id VARCHAR,
                kind VARCHAR,                -- idea|experiment|observation|dead-end|open-question|note
                title VARCHAR,
                body VARCHAR,                -- the reasoning / content
                status VARCHAR,              -- open|promising|dead|submitted|needs-retry|reframe|validated
                score DOUBLE,                -- agent's promise estimate 0..1 (tree-search ranking)
                provenance VARCHAR,          -- JSON {papers:[], claims:[], entities:[], parents:[]}
                code VARCHAR,                -- for experiments: the code that was run
                result VARCHAR,              -- for experiments: key numbers / stdout digest
                embedding FLOAT[],           -- of title+body (semantic search)
                created_at VARCHAR,
                updated_at VARCHAR
            )""")

    # --- write ------------------------------------------------------------------------------------
    def log(self, kind: str, title: str, body: str = "", *, run_id: str = "",
            status: str = "open", score: float | None = None, provenance: dict | None = None,
            code: str = "", result: str = "") -> int:
        kind = kind if kind in KINDS else "note"
        prov = provenance or {}
        vec = E.embed_one(f"{title}\n{body}")
        eid = int(self.con.execute("SELECT COALESCE(MAX(entry_id), 0) + 1 FROM exploration").fetchone()[0])
        self.con.execute(
            "INSERT INTO exploration (entry_id, run_id, kind, title, body, status, score, provenance, "
            "code, result, embedding, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [eid, run_id, kind, title, body, status, score,
             json.dumps(prov), code, result, vec, _now(), _now()])
        return eid

    def update(self, entry_id: int, **fields) -> None:
        """Update mutable fields (status, score, result, body). Re-embeds if title/body change."""
        allowed = {"status", "score", "result", "body", "title", "kind"}
        sets, params = [], []
        for k, v in fields.items():
            if k in allowed:
                sets.append(f"{k}=?"); params.append(v)
        if not sets:
            return
        if "body" in fields or "title" in fields:
            cur = self.get(entry_id) or {}
            vec = E.embed_one(f"{fields.get('title', cur.get('title', ''))}\n{fields.get('body', cur.get('body', ''))}")
            sets.append("embedding=?"); params.append(vec)
        sets.append("updated_at=?"); params.append(_now())
        params.append(int(entry_id))
        self.con.execute(f"UPDATE exploration SET {', '.join(sets)} WHERE entry_id=?", params)

    # --- read / tree ------------------------------------------------------------------------------
    _COLS = ("entry_id", "run_id", "kind", "title", "body", "status", "score",
             "provenance", "code", "result", "created_at", "updated_at")

    def _rows(self, where: str = "", params=None) -> list[dict]:
        cols = ",".join(self._COLS)
        out = []
        for r in self.con.execute(f"SELECT {cols} FROM exploration {where}", params or []).fetchall():
            d = dict(zip(self._COLS, r))
            d["provenance"] = json.loads(d["provenance"]) if d["provenance"] else {}
            out.append(d)
        return out

    def get(self, entry_id: int) -> dict | None:
        r = self._rows("WHERE entry_id=?", [int(entry_id)])
        return r[0] if r else None

    def submittable(self, run_id: str, limit: int = 12) -> list[dict]:
        """This branch's own experiments that carry a parsed result and have not been submitted yet: the
        exact set `submit` will accept. Used to answer a refused submit with the available ids."""
        out = []
        for e in self._rows("WHERE kind='experiment' AND run_id=? AND status<>'submitted' "
                            "ORDER BY entry_id DESC", [run_id]):
            try:
                if "p_null" in json.loads(e.get("result") or "{}"):
                    out.append(e)
            except Exception:
                continue
            if len(out) >= limit:
                break
        return out

    def _run_filter(self, scope) -> tuple[str, list]:
        """Normalize a run-scope spec into (sql_fragment_without_leading_AND, params):
          - None                 -> "" / []            : no filter (every run in the DB)
          - a str                -> "run_id=?" / [s]    : exact single-run match
          - a (frag, params) pair-> used verbatim        : the lineage predicate (explorer.lineage.scope_sql):
                                                           this lineage plus prior separate runs, minus
                                                           concurrent siblings.
        This is the one place run scoping is interpreted, so every read below scopes identically."""
        if scope is None:
            return "", []
        if isinstance(scope, tuple):
            return scope
        return "run_id=?", [scope]

    def frontier(self, scope=None, limit: int = 10) -> list[dict]:
        """The tree-search frontier: open/promising nodes worth expanding next, best score first. This is
        what the explorer reads to decide where to branch."""
        frag, params = self._run_filter(scope)
        w = "WHERE status IN ('open','promising')" + (f" AND {frag}" if frag else "")
        rows = self._rows(w, params)
        rows.sort(key=lambda d: (d.get("score") is not None, d.get("score") or 0.0), reverse=True)
        return rows[:limit]

    def open_questions(self, scope=None) -> list[dict]:
        frag, params = self._run_filter(scope)
        w = "WHERE kind='open-question' AND status='open'" + (f" AND {frag}" if frag else "")
        return self._rows(w, params)

    # --- feedback from the verification/human loop (so the explorer reacts) ------------------------
    def record_feedback(self, entry_id: int, *, source: str, verdict: str, reason: str = "",
                        note: str = "", new_status: str | None = None) -> None:
        """Fold a verifier or human verdict back onto the experiment entry it came from — appended to the
        body (so the reasoning trail shows what came back) and, if given, a new status that steers the
        tree search (needs-retry / reframe / dead / validated). This is how a killed branch stops being
        deepened and a methods-fixable one gets retried."""
        e = self.get(entry_id)
        if not e:
            return
        tag = f"[{source} verdict: {verdict}" + (f"/{reason}" if reason else "") + "]"
        if note:
            tag += f" {note}"
        body = (e.get("body", "") + "\n" + tag).strip()
        self.update(entry_id, body=body, **({"status": new_status} if new_status else {}))

    def feedback_entries(self, scope=None, limit: int = 8) -> list[dict]:
        """Recently-updated entries carrying a verdict — what came back for the explorer to react to
        (retry / reframe / abandon / build on a survivor), newest first."""
        frag, params = self._run_filter(scope)
        w = ("WHERE status IN ('needs-retry','reframe','dead','validated','promising')"
             + (f" AND {frag}" if frag else ""))
        return self._rows(w + " ORDER BY updated_at DESC", params)[:limit]

    def corrections(self, scope=None, limit: int = 5) -> list[dict]:
        """Human corrections (the explanation behind a rejection) the explorer follows; they reshape its
        model, not just one branch."""
        frag, params = self._run_filter(scope)
        w = "WHERE kind='note' AND title LIKE 'CORRECTION%'" + (f" AND {frag}" if frag else "")
        return self._rows(w + " ORDER BY entry_id DESC", params)[:limit]

    def search_keyword(self, query: str, limit: int = 10, scope=None) -> list[dict]:
        like = f"%{query.lower()}%"
        frag, params = self._run_filter(scope)
        w = "WHERE (lower(title) LIKE ? OR lower(body) LIKE ?)" + (f" AND {frag}" if frag else "")
        return self._rows(w + " ORDER BY entry_id DESC LIMIT ?", [like, like, *params, limit])

    def search_semantic(self, query: str, limit: int = 10, scope=None) -> list[dict]:
        qv = E.embed_one(query)
        if not qv:
            return self.search_keyword(query, limit, scope=scope)
        frag, params = self._run_filter(scope)
        w = "SELECT entry_id, embedding FROM exploration" + (f" WHERE {frag}" if frag else "")
        rows = self.con.execute(w, params).fetchall()
        ranked = E.rank(qv, rows, vec_key=lambda r: r[1], top_k=limit)
        ids = [r[0] for _, r in ranked]
        if not ids:
            return []
        by_id = {d["entry_id"]: d for d in self._rows(f"WHERE entry_id IN ({','.join('?' * len(ids))})", ids)}
        return [by_id[i] for i in ids if i in by_id]

    def counts(self) -> dict:
        rows = self.con.execute("SELECT kind, COUNT(*) FROM exploration GROUP BY kind").fetchall()
        return {"total": self.con.execute("SELECT COUNT(*) FROM exploration").fetchone()[0],
                "by_kind": dict(rows)}

    def close(self) -> None:
        if self._owns:
            self.con.close()
