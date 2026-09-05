"""The explorer-facing store over one DuckDB file.

The literature claim graph itself (claims, evidence, evidence_context, evidence_cites, experiments,
deferrals) is owned by `litmap.graph.ClaimGraph`; this module opens the same file and adds the
engine's layer on top: the tested-edge table the explorer writes back to (`engine_tests`), the
promotion copy into a master store, the `claim_edges` view the explorer and the console read
(claim rows with source counts, first-mention year, status and confidence), structural graph reads
(neighbours, subgraph, shortest path, digest), and the persisted semantic index over claim edges.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import duckdb

from dnhacksbio.falsifier import kind_of_kill
from dnhacksbio.litmap.graph import ClaimGraph

DEFAULT_DB = Path("data/processed/litmap_kg.duckdb")

# column-named inserts
_ET_COLS = ["run_id", "kg_claim_id", "atom_id", "source", "subject", "object", "method",
            "expected_sign", "observed_sign", "effect", "effect_size", "p_null", "status",
            "kill_reason", "verdict_note", "hypothesis", "human_review", "novelty_verdict",
            "novelty_detail", "review_note", "explore_entry", "created_at"]

# per-source reliability prior behind the confidence column: 1 - (1 - r)^n_sources
SOURCE_PRIOR = 0.7
DISPUTED_PENALTY = 0.55


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _f(x):
    """float-or-NULL: keep NaN/None out of the DOUBLE columns."""
    import math
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) else v


def _i(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


class KGStore:
    def __init__(self, db_path: str | Path | None = None, fresh: bool = False):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB
        self.graph = ClaimGraph(self.db_path, fresh=fresh)
        self.con = self.graph.con
        self._edge_cache: list[dict] | None = None
        self._schema()

    def _schema(self) -> None:
        # a float32 BLOB per claim; `text_hash` is of the edge's text when it was embedded
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS claim_vectors (
                claim_id VARCHAR PRIMARY KEY,
                text_hash VARCHAR,
                embedding BLOB,
                created_at VARCHAR
            )""")
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS claim_status (
                claim_id VARCHAR PRIMARY KEY,
                status VARCHAR,
                dispute_kind VARCHAR
            )""")
        self.con.execute("CREATE SEQUENCE IF NOT EXISTS test_seq START 1")
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS engine_tests (
                test_id BIGINT PRIMARY KEY,
                run_id VARCHAR, kg_claim_id VARCHAR, atom_id VARCHAR, source VARCHAR,
                subject VARCHAR, object VARCHAR, method VARCHAR,
                expected_sign INTEGER, observed_sign INTEGER,
                effect DOUBLE, effect_size DOUBLE, p_null DOUBLE,
                status VARCHAR, kill_reason VARCHAR, verdict_note VARCHAR, hypothesis VARCHAR,
                human_review VARCHAR, novelty_verdict VARCHAR, novelty_detail VARCHAR,
                review_note VARCHAR, explore_entry INTEGER, created_at VARCHAR
            )""")
        # The one row shape every reader uses: a claim plus its evidence roll-up and status.
        self.con.execute(f"""
            CREATE OR REPLACE VIEW claim_edges AS
            SELECT c.claim_id,
                   COALESCE(NULLIF(c.subject_curie, ''), c.subject_label) AS subject_id,
                   c.subject_label, c.subject_curie, c.subject_kind,
                   c.predicate,
                   COALESCE(NULLIF(c.object_curie, ''), c.object_label) AS object_id,
                   c.object_label, c.object_curie, c.object_kind,
                   c.object_aspect AS object_function, c.relation_class, c.polarity,
                   c.mechanism, c.abstract_key,
                   COALESCE(s.n_sources, 0) AS n_sources, s.first_year,
                   COALESCE(st.status, CASE WHEN COALESCE(s.n_sources, 0) >= 2
                                            THEN 'established' ELSE 'reported' END) AS status,
                   COALESCE(st.dispute_kind, '') AS dispute_kind,
                   ROUND((1 - POWER({1 - SOURCE_PRIOR}, GREATEST(COALESCE(s.n_sources, 1), 1)))
                         * CASE WHEN st.status = 'disputed' THEN {DISPUTED_PENALTY} ELSE 1 END, 4)
                       AS confidence,
                   c.created_at
            FROM claims c
            LEFT JOIN (SELECT claim_id, COUNT(DISTINCT source_ref) AS n_sources,
                              MIN(TRY_CAST(regexp_extract(source_label, '(19|20)[0-9]{{2}}')
                                           AS INTEGER)) AS first_year
                       FROM evidence GROUP BY claim_id) s USING (claim_id)
            LEFT JOIN claim_status st USING (claim_id)""")

    # --- literature graph writes (delegated) ------------------------------------------------------
    def write_paper(self, source_ref: int, claims, experiments=(), deferrals=()) -> dict:
        """Write one paper's extraction into the claim graph (idempotent per source)."""
        self._edge_cache = None
        return self.graph.write_paper(source_ref, claims, experiments, deferrals)

    def refresh_status(self) -> dict:
        """Recompute claim status from the graph's contradiction check. Disputed claims are written to
        `claim_status`; every other status derives from the source count in the view."""
        self._edge_cache = None
        self.con.execute("DELETE FROM claim_status")
        n = 0
        for c in self.graph.contradictions():
            for cid in (c.get("pos_claim"), c.get("neg_claim")):
                if cid:
                    self.con.execute("INSERT OR REPLACE INTO claim_status VALUES (?, 'disputed', ?)",
                                     [cid, str(c.get("kind") or "direct")])
                    n += 1
        return {**self.counts(), "disputed_claims": n}

    # --- engine verdict -> working graph as a tested edge -----------------------------------------
    def record_engine_verdict(self, v: dict, run_id: str) -> int | None:
        """Write one engine experiment's outcome onto the working graph as a tested edge. `status` is
        'candidate' when it survived the falsifier, else the kill kind ('invalid' | 'underpowered' |
        'inconclusive' | 'refuted', or 'killed' when the kind cannot be recovered). 'candidate' is the
        only non-kill status, so readers ask `status != 'candidate'`. Idempotent per (run_id, subject,
        object, method, expected_sign). Returns the new test_id, or None if skipped as a duplicate."""
        subject, obj = str(v.get("subject") or ""), str(v.get("object") or "")
        method, exp = str(v.get("method") or ""), _i(v.get("expected_sign")) or 0
        # a result may name the branch that produced it; otherwise the family's run_id
        run_id = str(v.get("run_id") or run_id)
        if self._test_exists(run_id, subject, obj, method, exp):
            return None
        reason = str(v.get("reason") or "")
        status = ("candidate" if v.get("status") == "CANDIDATE" else kind_of_kill(reason))
        return self._insert_engine_row({
            "run_id": run_id, "kg_claim_id": str(v.get("kg_claim_id") or ""),
            "atom_id": str(v.get("claim_id") or ""), "source": str(v.get("source") or ""),
            "subject": subject, "object": obj, "method": method,
            "expected_sign": exp, "observed_sign": _i(v.get("observed_sign")),
            "effect": _f(v.get("effect")), "effect_size": _f(v.get("effect_size")),
            "p_null": _f(v.get("p_null")), "status": status,
            "kill_reason": "" if status == "candidate" else reason,
            "verdict_note": str(v.get("verdict_note") or v.get("note") or ""),
            "hypothesis": str(v.get("hypothesis") or ""),
            "human_review": "", "novelty_verdict": "", "novelty_detail": "", "review_note": "",
            "explore_entry": _i(v.get("explore_entry")), "created_at": _now()})

    def _test_exists(self, run_id, subject, obj, method, exp) -> bool:
        return self.con.execute(
            "SELECT 1 FROM engine_tests WHERE run_id=? AND subject=? AND object=? AND method=? "
            "AND expected_sign=?", [run_id, subject, obj, method, exp]).fetchone() is not None

    def _insert_engine_row(self, d: dict) -> int:
        """Column-named INSERT of one engine_tests row from a full dict. Returns the new test_id."""
        ph = ",".join("?" for _ in _ET_COLS)
        self.con.execute(
            f"INSERT INTO engine_tests (test_id,{','.join(_ET_COLS)}) VALUES (nextval('test_seq'),{ph})",
            [d.get(c) for c in _ET_COLS])
        return int(self.con.execute("SELECT currval('test_seq')").fetchone()[0])

    # --- promotion gate -------------------------------------------------------------------------
    def set_human_review(self, test_id: int, decision: str, note: str = "") -> None:
        """Record the human verdict (validated | rejected) and its note on a tested edge."""
        self.con.execute("UPDATE engine_tests SET human_review=?, review_note=? WHERE test_id=?",
                         [decision, (note or "")[:400], int(test_id)])

    def get_engine_test(self, test_id: int) -> dict | None:
        cols = [c[0] for c in self.con.execute("SELECT * FROM engine_tests LIMIT 0").description]
        r = self.con.execute("SELECT * FROM engine_tests WHERE test_id=?", [int(test_id)]).fetchone()
        return dict(zip(cols, r)) if r else None

    def insert_promoted(self, test_row: dict, claim_row: dict | None = None,
                        evidence_rows: list[dict] | None = None, note: str = "") -> int | None:
        """Copy a human-validated tested edge into this (master) store, plus the literature claim and
        evidence it originated from, so the edge keeps its provenance. Idempotent. Only the human-gated
        promote step calls this."""
        if self._test_exists(test_row.get("run_id"), test_row.get("subject"), test_row.get("object"),
                             test_row.get("method"), test_row.get("expected_sign")):
            return None
        if claim_row and claim_row.get("claim_id"):
            self._import_claim_row(claim_row, evidence_rows or [])
        row = {c: test_row.get(c) for c in _ET_COLS}
        row.update(human_review="validated", review_note=(note or ""), created_at=_now())
        return self._insert_engine_row(row)

    def _import_claim_row(self, claim_row: dict, evidence_rows: list[dict]) -> None:
        """Insert a literature claim and its evidence into this store if absent."""
        cid = claim_row.get("claim_id")
        if not cid or self.con.execute("SELECT 1 FROM claims WHERE claim_id=?", [cid]).fetchone():
            return
        self._edge_cache = None
        cols = [c[0] for c in self.con.execute("SELECT * FROM claims LIMIT 0").description]
        self.con.execute(f"INSERT INTO claims ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                         [claim_row.get(c) for c in cols])
        ev_cols = [c[0] for c in self.con.execute("SELECT * FROM evidence LIMIT 0").description
                   if c[0] != "evidence_id"]
        next_id = (self.con.execute("SELECT COALESCE(MAX(evidence_id), 0) FROM evidence").fetchone()[0]
                   or 0) + 1
        for ev in evidence_rows:
            self.con.execute(
                f"INSERT INTO evidence (evidence_id,{','.join(ev_cols)}) "
                f"VALUES (?,{','.join('?' * len(ev_cols))})",
                [next_id] + [cid if c == "claim_id" else ev.get(c) for c in ev_cols])
            next_id += 1

    def write_back(self, results: list[dict], run_id: str) -> dict:
        """Record every result of an engine family. Returns a summary: written, duplicates, candidates,
        killed, by_kind, and the nodes the engine introduced."""
        written = 0
        for v in results:
            if self.record_engine_verdict(v, run_id) is not None:
                written += 1
        et = self.engine_tests(run_id=run_id)
        from collections import Counter
        killed = [r for r in et if r["status"] != "candidate"]
        return {"written": written, "duplicates": len(results) - written,
                "candidates": sum(1 for r in et if r["status"] == "candidate"),
                "killed": len(killed), "by_kind": dict(Counter(r["status"] for r in killed)),
                "new_nodes": self.new_engine_nodes()}

    def set_novelty(self, test_id: int, verdict: str, detail: str = "") -> None:
        """Attach an external-novelty verdict (known|contradicts|distant-field|open) to a tested edge."""
        self.con.execute("UPDATE engine_tests SET novelty_verdict=?, novelty_detail=? WHERE test_id=?",
                         [verdict, (detail or "")[:600], int(test_id)])

    # --- read path --------------------------------------------------------------------------------
    def counts(self) -> dict:
        return {
            "claims": self.con.execute("SELECT COUNT(*) FROM claims").fetchone()[0],
            "evidence": self.con.execute("SELECT COUNT(*) FROM evidence").fetchone()[0],
            "entities": self.con.execute(
                "SELECT COUNT(*) FROM (SELECT subject_id FROM claim_edges UNION "
                "SELECT object_id FROM claim_edges)").fetchone()[0],
            "disputed": self.con.execute(
                "SELECT COUNT(*) FROM claim_edges WHERE status='disputed'").fetchone()[0],
            "engine_tests": self.con.execute("SELECT COUNT(*) FROM engine_tests").fetchone()[0],
            "engine_candidates": self.con.execute(
                "SELECT COUNT(*) FROM engine_tests WHERE status='candidate'").fetchone()[0],
            "engine_killed": self.con.execute(
                "SELECT COUNT(*) FROM engine_tests WHERE status<>'candidate'").fetchone()[0],
            "engine_new_nodes": len(self.new_engine_nodes()),
        }

    def edges(self) -> list[dict]:
        """Every claim as one row of the `claim_edges` view. Cached until the next write."""
        if self._edge_cache is None:
            cols = [c[0] for c in self.con.execute("SELECT * FROM claim_edges LIMIT 0").description]
            self._edge_cache = [dict(zip(cols, r)) for r in
                                self.con.execute("SELECT * FROM claim_edges ORDER BY claim_id").fetchall()]
        return list(self._edge_cache)

    def get_claim(self, claim_id: str) -> dict | None:
        cols = [c[0] for c in self.con.execute("SELECT * FROM claim_edges LIMIT 0").description]
        r = self.con.execute("SELECT * FROM claim_edges WHERE claim_id=?", [claim_id]).fetchone()
        return dict(zip(cols, r)) if r else None

    def evidence_for(self, claim_id: str) -> list[dict]:
        cols = [c[0] for c in self.con.execute("SELECT * FROM evidence LIMIT 0").description]
        return [dict(zip(cols, r)) for r in
                self.con.execute("SELECT * FROM evidence WHERE claim_id=?", [claim_id]).fetchall()]

    def engine_tests(self, status: str | None = None, run_id: str | None = None,
                     human_review: str | None = None, scope=None) -> list[dict]:
        """Read tested edges, filtered by status (candidate or a kill kind), run_id or human_review.
        `engine_tests(status='candidate', human_review='')` is the promotion queue. `scope` is a
        (sql_fragment, params) pair from explorer.lineage.scope_sql restricting to a branch's lineage; when
        both `run_id` and `scope` are given, `scope` wins."""
        cols = [c[0] for c in self.con.execute("SELECT * FROM engine_tests LIMIT 0").description]
        q, params = "SELECT * FROM engine_tests", []
        conds = []
        if status is not None:
            conds.append("status=?"); params.append(status)
        if scope is not None:
            frag, sp = scope
            conds.append(frag); params.extend(sp)
        elif run_id is not None:
            conds.append("run_id=?"); params.append(run_id)
        if human_review is not None:
            conds.append("human_review=?"); params.append(human_review)
        if conds:
            q += " WHERE " + " AND ".join(conds)
        return [dict(zip(cols, r)) for r in
                self.con.execute(q + " ORDER BY test_id", params).fetchall()]

    def new_engine_nodes(self) -> list[str]:
        """Entities that entered the working graph via an engine test but appear in no literature claim:
        the nodes the engine introduced beyond the corpus."""
        rows = self.con.execute("""
            SELECT DISTINCT e FROM (
                SELECT subject AS e FROM engine_tests UNION ALL SELECT object FROM engine_tests) t
            WHERE e <> '' AND e NOT IN (
                SELECT subject_id FROM claim_edges UNION SELECT object_id FROM claim_edges UNION
                SELECT subject_label FROM claim_edges UNION SELECT object_label FROM claim_edges)
            ORDER BY e""").fetchall()
        return [r[0] for r in rows]

    # --- structural graph reads ---------------------------------------------------------------------
    def _node_ids(self) -> list[str]:
        return [r[0] for r in self.con.execute(
            "SELECT DISTINCT subject_id FROM claim_edges UNION SELECT DISTINCT object_id FROM claim_edges"
        ).fetchall() if r[0]]

    def resolve_node(self, entity: str) -> str | None:
        """Map a free-text entity to a node id: case-insensitive exact match on an id or label, then a
        substring fallback. None if nothing matches."""
        e = (entity or "").strip().lower()
        if not e:
            return None
        ids = self._node_ids()
        for i in ids:
            if i.lower() == e:
                return i
        row = self.con.execute(
            "SELECT subject_id FROM claim_edges WHERE lower(subject_label)=? UNION "
            "SELECT object_id FROM claim_edges WHERE lower(object_label)=? LIMIT 1", [e, e]).fetchone()
        if row:
            return row[0]
        for i in ids:
            if e in i.lower():
                return i
        return None

    def _adjacency(self):
        """Undirected adjacency and per-node incident edges over the claim graph."""
        from collections import defaultdict
        adj: dict[str, set] = defaultdict(set)
        inc: dict[str, list] = defaultdict(list)
        for e in self.edges():
            s, o = e.get("subject_id"), e.get("object_id")
            if s and o and s != o:
                adj[s].add(o); adj[o].add(s)
                inc[s].append(e); inc[o].append(e)
        return adj, inc

    def neighbors(self, entity: str, limit: int | None = None) -> list[dict]:
        """The 1-hop neighbourhood: claim edges incident to `entity`, deduped. `limit=None` returns the
        whole neighbourhood; the caller truncates, since it knows its own budget."""
        node = self.resolve_node(entity)
        if not node:
            return []
        _, inc = self._adjacency()
        seen, out = set(), []
        for e in inc.get(node, []):
            if e["claim_id"] not in seen:
                seen.add(e["claim_id"]); out.append(e)
        return out[:limit] if limit else out

    def subgraph_around(self, entity: str, hops: int = 1, max_edges: int | None = None) -> list[dict]:
        """BFS out to `hops` from `entity`; the edges of the induced neighbourhood, deduped."""
        node = self.resolve_node(entity)
        if not node:
            return []
        adj, inc = self._adjacency()
        frontier, visited, edges = {node}, {node}, {}
        for _ in range(max(1, hops)):
            nxt = set()
            for n in frontier:
                for e in inc.get(n, []):
                    edges[e["claim_id"]] = e
                for m in adj.get(n, ()):
                    if m not in visited:
                        visited.add(m); nxt.add(m)
            frontier = nxt
            if not frontier:
                break
        out = list(edges.values())
        return out[:max_edges] if max_edges else out

    def path_between(self, a: str, b: str, max_hops: int = 4) -> list[dict] | None:
        """Shortest claim-edge path between two entities (BFS over the undirected edge graph), as the list of
        edges along it. [] if a==b; None if unreachable within `max_hops` or either endpoint is unknown."""
        na, nb = self.resolve_node(a), self.resolve_node(b)
        if not na or not nb:
            return None
        if na == nb:
            return []
        from collections import deque
        adj, inc = self._adjacency()
        prev, depth, q = {na: None}, {na: 0}, deque([na])
        while q:
            n = q.popleft()
            if n == nb:
                break
            if depth[n] >= max_hops:
                continue
            for m in adj.get(n, ()):
                if m not in prev:
                    prev[m] = n; depth[m] = depth[n] + 1; q.append(m)
        if nb not in prev:
            return None
        chain, cur = [], nb
        while cur is not None:
            chain.append(cur); cur = prev[cur]
        chain.reverse()
        out = []
        for x, y in zip(chain, chain[1:]):
            edge = next((e for e in inc.get(x, [])
                         if {e.get("subject_id"), e.get("object_id")} == {x, y}), None)
            if edge:
                out.append(edge)
        return out

    def digest(self, top_hubs: int = 12) -> dict:
        """A compact map summary: counts, highest-degree hubs and contested edges, for the explorer's state."""
        c = self.counts()
        deg = self.con.execute(
            "SELECT e, COUNT(*) d FROM (SELECT subject_id e FROM claim_edges UNION ALL "
            "SELECT object_id FROM claim_edges) WHERE e <> '' GROUP BY e ORDER BY d DESC, e LIMIT ?",
            [top_hubs]).fetchall()
        disp = self.con.execute(
            "SELECT subject_label, predicate, object_label, object_function FROM claim_edges "
            "WHERE status='disputed' ORDER BY n_sources DESC LIMIT 12").fetchall()
        return {"n_claims": c["claims"], "n_entities": c["entities"], "n_disputed": c["disputed"],
                "engine_tests": c["engine_tests"], "engine_candidates": c["engine_candidates"],
                "top_hubs": [(e, int(d)) for e, d in deg],
                "disputed": [(s, p, o, f) for s, p, o, f in disp]}

    # --- semantic index over the claim edges ---------------------------------------------------------
    @staticmethod
    def edge_text(e: dict) -> str:
        """The text a claim edge is embedded from: labels plus mechanism, so search matches on meaning.
        One definition shared by the build step and every reader."""
        return (f"{e.get('subject_label') or e.get('subject_id')} {e.get('predicate')} "
                f"{e.get('object_label') or e.get('object_id')} {e.get('object_function') or ''} "
                f"{(e.get('mechanism') or '')[:200]}").strip()

    @staticmethod
    def _text_hash(text: str) -> str:
        import hashlib
        return hashlib.blake2b(text.encode("utf-8"), digest_size=8).hexdigest()

    def _embed_and_store(self, edges: list[dict]) -> dict:
        """Embed these edges in one batched call and persist them. Returns {claim_id: float32 vector},
        or {} if no embedding model is available (callers degrade to keyword search)."""
        import numpy as np
        import pandas as pd

        from dnhacksbio.explorer import embed as E
        vecs = E.embed([self.edge_text(e) for e in edges])
        if not vecs:
            return {}
        mat = np.asarray(vecs, dtype=np.float32)
        df = pd.DataFrame({"claim_id": [e["claim_id"] for e in edges],
                           "text_hash": [self._text_hash(self.edge_text(e)) for e in edges],
                           "embedding": [v.tobytes() for v in mat],
                           "created_at": [_now()] * len(edges)})
        self.con.execute("DELETE FROM claim_vectors WHERE claim_id IN (SELECT claim_id FROM df)")
        self.con.execute("INSERT INTO claim_vectors SELECT * FROM df")
        return {e["claim_id"]: v for e, v in zip(edges, mat)}

    def claim_vectors(self, edges: list[dict] | None = None, *, embed_missing: bool = False) -> dict:
        """{claim_id: float32 vector} for `edges` (default: every claim) from the persisted index. A
        stored vector is used only if its `text_hash` still matches the edge's current text.
        `embed_missing=True` embeds and persists whatever is absent."""
        import numpy as np
        edges = self.edges() if edges is None else edges
        if not edges:
            return {}
        have = {cid: (h, b) for cid, h, b in
                self.con.execute("SELECT claim_id, text_hash, embedding FROM claim_vectors").fetchall()}
        out, missing = {}, []
        for e in edges:
            got = have.get(e["claim_id"])
            if got and got[1] and got[0] == self._text_hash(self.edge_text(e)):
                out[e["claim_id"]] = np.frombuffer(got[1], dtype=np.float32)
            else:
                missing.append(e)
        if missing and embed_missing:
            out.update(self._embed_and_store(missing))
        return out

    def embed_claims(self) -> dict:
        """Give every claim a current vector (`scripts/embed_kg.py`). Incremental: only new or changed
        claims are re-embedded. Returns {n_claims, n_cached, n_embedded, n_failed}."""
        edges = self.edges()
        cached = self.claim_vectors(edges)
        missing = [e for e in edges if e["claim_id"] not in cached]
        added = self._embed_and_store(missing) if missing else {}
        return {"n_claims": len(edges), "n_cached": len(cached), "n_embedded": len(added),
                "n_failed": len(missing) - len(added)}

    def snapshot(self) -> duckdb.DuckDBPyConnection:
        """A read-consistent cursor, for readers that need a stable graph while writes append."""
        return self.con.cursor()

    def close(self) -> None:
        self.con.close()
