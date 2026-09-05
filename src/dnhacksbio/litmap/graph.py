"""Claim graph persistence: the DuckDB store where extracted claims become a graph you can query.

A claim's primary key is `claim_id`, the hash of its identity (subject, object, aspect, relation class,
polarity, entity state), so two papers asserting the same thing write the same row and stack evidence
under it; nothing needs merging after the fact. Context is a table (`evidence_context`, one row per slot
per evidence), so "what happens in HeLa?" is a join rather than a scan. `evidence_cites` records what
each evidence row leans on, for telling echoes of one paper from independent findings. Re-extraction of a
paper is idempotent.
"""
from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

import duckdb

from dnhacksbio.litmap import refinement
from dnhacksbio.litmap.schema import Claim, Deferral, Experiment
from dnhacksbio.litmap.vocab import OPPOSITE_PREDICATES, quantifiers_conflict

# Pre-sorted "a|b" strings so the pair test is a list lookup in SQL rather than a Python round trip.
_OPPOSITE_SORTED = ["|".join(sorted(p)) for p in OPPOSITE_PREDICATES]

DEFAULT_DB = Path("data/processed/litmap_kg.duckdb")


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


class ClaimGraph:
    def __init__(self, db_path: str | Path | None = None, fresh: bool = False):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB
        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            if fresh and self.db_path.exists():
                self.db_path.unlink()
        self.con = duckdb.connect(str(self.db_path))
        self._schema()

    # --- schema -----------------------------------------------------------------------------------
    def _schema(self) -> None:
        c = self.con
        for s in ("ev_seq", "def_seq", "ctx_seq"):
            c.execute(f"CREATE SEQUENCE IF NOT EXISTS {s} START 1")
        # `abstract_key` is stored, not derived at query time: contradiction detection and the "has anyone
        # claimed this?" check both group by it, and a computed column would re-parse every row on every
        # query.
        c.execute("""
            CREATE TABLE IF NOT EXISTS claims (
                claim_id VARCHAR PRIMARY KEY,
                abstract_key VARCHAR,
                subject_curie VARCHAR, subject_label VARCHAR, subject_kind VARCHAR,
                subject_state VARCHAR, subject_variant VARCHAR, subject_isoform VARCHAR,
                subject_protein_construct VARCHAR,   -- a piece of the protein (DBD, delta283-595, full-length);
                                             -- splits identity but never narrows
                subject_feature_type VARCHAR, subject_feature_tier VARCHAR,
                object_curie VARCHAR, object_label VARCHAR, object_kind VARCHAR,
                object_state VARCHAR, object_variant VARCHAR, object_isoform VARCHAR,
                object_protein_construct VARCHAR,
                object_feature_type VARCHAR, object_feature_tier VARCHAR,
                object_aspect VARCHAR, relation_class VARCHAR, polarity INTEGER,
                predicate VARCHAR,          -- display only, not identity (synonyms merge)
                mechanism VARCHAR,
                created_at VARCHAR
            )""")
        c.execute("""
            CREATE TABLE IF NOT EXISTS evidence (
                evidence_id BIGINT PRIMARY KEY,
                claim_id VARCHAR,
                source_ref INTEGER, source_label VARCHAR,
                experiment_id VARCHAR,      -- NULL for a retelling
                quote VARCHAR, section VARCHAR,
                predicate VARCHAR,          -- the surface form this source used; the canonical
                                            -- form lives on the claim
                aspect_said VARCHAR,        -- "degradation" where the claim is stored on "abundance";
                mechanism_term VARCHAR,     -- the direction-free route that word named; on evidence
                                            -- because two sources can reach one claim by different routes
                quantifier VARCHAR,         -- all | most | some | '' (not a set claim / not stated);
                                            -- '' is never read as `all`
                evidence_type VARCHAR, study_type VARCHAR,
                attribution VARCHAR, attribution_basis VARCHAR, attribution_agreed BOOLEAN,
                certainty VARCHAR, certainty_basis VARCHAR, certainty_agreed BOOLEAN,
                extractor VARCHAR, prompt_version VARCHAR,
                created_at VARCHAR
            )""")
        # One row per slot per evidence; the table context queries join against.
        c.execute("""
            CREATE TABLE IF NOT EXISTS evidence_context (
                ctx_id BIGINT PRIMARY KEY,
                evidence_id BIGINT, claim_id VARCHAR, source_ref INTEGER,
                slot VARCHAR, value VARCHAR, label VARCHAR,
                provenance VARCHAR,         -- stated | inherited | unspecified
                quote VARCHAR, inherited_from VARCHAR
            )""")
        # What each evidence row leans on. Recorded at extraction time because it is unrecoverable later.
        c.execute("""
            CREATE TABLE IF NOT EXISTS evidence_cites (
                evidence_id BIGINT, claim_id VARCHAR, source_ref INTEGER,
                sid VARCHAR,                -- DOI:… | PMID:… | AY:… | SRC:<paper>.<n>
                marker VARCHAR, tier VARCHAR
            )""")
        c.execute("""
            CREATE TABLE IF NOT EXISTS experiments (
                experiment_id VARCHAR PRIMARY KEY, source_ref INTEGER,
                unit VARCHAR, intervention VARCHAR, control VARCHAR, readout VARCHAR,
                assay VARCHAR, timepoint VARCHAR,
                n INTEGER, effect VARCHAR, uncertainty VARCHAR, statistic VARCHAR,
                quote VARCHAR, created_at VARCHAR
            )""")
        c.execute("""
            CREATE TABLE IF NOT EXISTS deferrals (
                deferral_id BIGINT PRIMARY KEY,
                source_ref INTEGER, reason VARCHAR, quote VARCHAR,
                raw VARCHAR, candidates VARCHAR,
                extractor VARCHAR, prompt_version VARCHAR, created_at VARCHAR
            )""")

    # --- write path -------------------------------------------------------------------------------
    def write_paper(self, source_ref: int, claims: list[Claim], experiments: list[Experiment] = (),
                    deferrals: list[Deferral] = ()) -> dict:
        """Write one paper's extraction. Idempotent: everything for `source_ref` is deleted first, so a
        second run replaces the paper's contribution rather than doubling its apparent support."""
        self.forget_source(source_ref)
        now = _now()
        n_new = 0
        for cl in claims:
            s = cl.spine
            if not self._claim_exists(s.claim_id()):
                n_new += 1
                self.con.execute(
                    "INSERT INTO claims VALUES (" + ",".join(["?"] * 26) + ")",
                    [s.claim_id(), s.abstract_key(),
                     s.subject.curie, s.subject.label, s.subject.kind,
                     s.subject.state.functional, s.subject.state.variant, s.subject.state.isoform,
                     s.subject.state.protein_construct,
                     s.subject.feature_type, s.subject.feature_tier,
                     s.object.curie, s.object.label, s.object.kind,
                     s.object.state.functional, s.object.state.variant, s.object.state.isoform,
                     s.object.state.protein_construct,
                     s.object.feature_type, s.object.feature_tier,
                     s.object_aspect, s.relation_class, s.polarity, s.predicate, cl.mechanism, now])
            for ev in cl.evidence:
                eid = self.con.execute("SELECT nextval('ev_seq')").fetchone()[0]
                self.con.execute(
                    "INSERT INTO evidence VALUES (" + ",".join(["?"] * 22) + ")",
                    [eid, s.claim_id(), ev.source_ref, ev.source_label, ev.experiment_id,
                     ev.quote, ev.section, ev.predicate_said or s.predicate,
                     ev.aspect_said, ev.mechanism_term, ev.quantifier,
                     ev.evidence_type, ev.study_type,
                     ev.attribution, ";".join(ev.attribution_basis), ev.attribution_agreed,
                     ev.certainty, ";".join(ev.certainty_basis), ev.certainty_agreed,
                     ev.extractor, ev.prompt_version, now])
                for slot, cv in (ev.context.slots or {}).items():
                    self.con.execute(
                        "INSERT INTO evidence_context VALUES (nextval('ctx_seq'),?,?,?,?,?,?,?,?,?)",
                        [eid, s.claim_id(), ev.source_ref, slot, cv.value, cv.label,
                         cv.provenance, cv.quote, cv.inherited_from])
                for sid, marker in zip(ev.cites, ev.cite_markers + [""] * len(ev.cites)):
                    self.con.execute(
                        "INSERT INTO evidence_cites VALUES (?,?,?,?,?,?)",
                        [eid, s.claim_id(), ev.source_ref, sid, marker, sid.split(":")[0].lower()])
        for ex in experiments:
            self.con.execute(
                "INSERT OR REPLACE INTO experiments VALUES (" + ",".join(["?"] * 14) + ")",
                [ex.experiment_id, ex.source_ref, ex.unit, ex.intervention, ex.control, ex.readout,
                 ex.assay, ex.timepoint, ex.n, ex.effect, ex.uncertainty, ex.statistic, ex.quote, now])
        for d in deferrals:
            self.con.execute(
                "INSERT INTO deferrals VALUES (nextval('def_seq'),?,?,?,?,?,?,?,?)",
                [d.source_ref, d.reason, d.quote, json.dumps(d.raw),
                 ";".join(d.candidates), d.extractor, d.prompt_version, now])
        return {"claims_new": n_new, "claims_seen": len(claims),
                "evidence": sum(len(c.evidence) for c in claims),
                "experiments": len(experiments), "deferrals": len(deferrals)}

    def forget_source(self, source_ref: int) -> None:
        """Remove everything a source contributed, then drop any claim left with no evidence, since an
        unsupported edge must not remain in the graph."""
        c = self.con
        for t in ("evidence_context", "evidence_cites"):
            c.execute(f"DELETE FROM {t} WHERE source_ref = ?", [source_ref])
        c.execute("DELETE FROM evidence WHERE source_ref = ?", [source_ref])
        c.execute("DELETE FROM experiments WHERE source_ref = ?", [source_ref])
        c.execute("DELETE FROM deferrals WHERE source_ref = ?", [source_ref])
        c.execute("DELETE FROM claims WHERE claim_id NOT IN (SELECT DISTINCT claim_id FROM evidence)")

    def _claim_exists(self, claim_id: str) -> bool:
        return bool(self.con.execute("SELECT 1 FROM claims WHERE claim_id = ?", [claim_id]).fetchone())

    # --- read path ------------------------------------------------------------------------------
    def counts(self) -> dict:
        q = lambda t: self.con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]  # noqa: E731
        n_c, n_e = q("claims"), q("evidence")
        multi = self.con.execute(
            "SELECT count(*) FROM (SELECT claim_id FROM evidence GROUP BY 1 "
            "HAVING count(DISTINCT source_ref) > 1)").fetchone()[0]
        return {"claims": n_c, "evidence": n_e, "experiments": q("experiments"),
                "deferrals": q("deferrals"), "papers": q("(SELECT DISTINCT source_ref FROM evidence)"),
                "merge_ratio": round(n_e / n_c, 3) if n_c else 0.0,
                "multi_paper_claims": multi}

    def contradictions(self) -> list[dict]:
        """Claims on the same question that disagree. Not a verdict: a pair may be wild-type vs mutant
        or two different settings, which is why the state column is returned.

        Three kinds:
          `opposite_sign`       same relation class, opposite derived sign (the class test keeps a timing
                                claim from contradicting an amount claim).
          `opposite_predicate`  predicates that cannot both hold and carry no sign: present_in vs
                                absent_in, binds vs does_not_bind.
          `measured_null`       one paper tested it and found nothing, another found an effect.
        """
        rows = self.con.execute("""
            SELECT a.abstract_key, a.claim_id, a.polarity, a.subject_state, a.subject_label,
                   a.object_label, b.claim_id, b.polarity, b.subject_state, 'opposite_sign'
            FROM claims a JOIN claims b
              ON a.abstract_key = b.abstract_key
             AND a.relation_class = b.relation_class          -- a timing claim cannot contradict an
             AND a.polarity * b.polarity < 0                  -- amount claim
             AND a.claim_id < b.claim_id
            UNION ALL
            SELECT a.abstract_key, a.claim_id, a.polarity, a.subject_state, a.subject_label,
                   a.object_label, b.claim_id, b.polarity, b.subject_state, 'opposite_predicate'
            FROM claims a JOIN claims b
              ON a.abstract_key = b.abstract_key AND a.predicate < b.predicate
            WHERE list_contains(?, a.predicate || '|' || b.predicate)
            UNION ALL
            SELECT a.abstract_key, a.claim_id, a.polarity, a.subject_state, a.subject_label,
                   a.object_label, n.claim_id, n.polarity, n.subject_state, 'measured_null'
            FROM claims a JOIN claims n
              ON a.abstract_key = n.abstract_key
             -- keyed on the predicate: `no_effect_on` is the null result
             AND a.predicate <> 'no_effect_on' AND a.polarity <> 0
             AND n.predicate = 'no_effect_on'
        """, [_OPPOSITE_SORTED]).fetchall()
        # How much of the set each side covers: "most do" and "some don't" are both true of one group and
        # do not conflict.
        quant = {c: {v for (v,) in self.con.execute(
            "SELECT DISTINCT quantifier FROM evidence WHERE claim_id = ? AND quantifier <> ''",
            [c]).fetchall()} for c in {r[1] for r in rows} | {r[6] for r in rows}}

        rowmap = {r["claim_id"]: r for r in
                  (dict(zip([d[0] for d in self.con.description], x))
                   for x in self.con.execute("SELECT * FROM claims").fetchall())}

        def _is_exception(a: str, b: str) -> bool:
            """One side names a particular form of the other's subject: an exception, not a conflict.
            Only an `all` claim is refuted by a counterexample; `most`, `some` and unquantified are not."""
            ra, rb = rowmap.get(a), rowmap.get(b)
            if not ra or not rb:
                return False
            for spec, gen in ((ra, rb), (rb, ra)):
                if refinement.specialises(spec, gen) and "all" not in (quant.get(gen["claim_id"]) or set()):
                    return True
            return False

        def _still_conflicts(a: str, b: str) -> bool:
            if _is_exception(a, b):
                return False
            qa, qb = quant.get(a) or {""}, quant.get(b) or {""}
            # One source claiming a universal is enough to keep the flag, even if another source hedged.
            return any(quantifiers_conflict(x, y) for x in qa for y in qb)

        return [{"abstract_key": r[0], "pos_claim": r[1], "neg_claim": r[6],
                 "subject": r[4], "object": r[5],
                 "pos_state": r[3], "neg_state": r[8], "kind": r[9],
                 "state_separated": r[3] != r[8]} for r in rows if _still_conflicts(r[1], r[6])]

    # --- the refinement lattice ---------------------------------------------------
    def _rows_by_abstract_key(self, abstract_key: str | None = None) -> dict[str, list[dict]]:
        sql = "SELECT * FROM claims" + (" WHERE abstract_key = ?" if abstract_key else "")
        rows = self.con.execute(sql, [abstract_key] if abstract_key else []).fetchall()
        cols = [d[0] for d in self.con.description]
        out: dict[str, list[dict]] = {}
        for r in rows:
            d = dict(zip(cols, r))
            out.setdefault(d["abstract_key"], []).append(d)
        return out

    def evidence_for(self, claim_id: str, slot: str | None = None,
                     value: str | None = None) -> list[dict]:
        """Every source asserting a claim, optionally filtered by context slot and value."""
        sql = ["SELECT e.* FROM evidence e"]
        args: list = []
        if slot:
            sql.append("JOIN evidence_context x ON x.evidence_id = e.evidence_id AND x.slot = ?")
            args.append(slot)
            if value:
                sql[-1] += " AND x.value = ?"
                args.append(value)
        sql.append("WHERE e.claim_id = ?")
        args.append(claim_id)
        rows = self.con.execute(" ".join(sql), args).fetchall()
        cols = [d[0] for d in self.con.description]
        return [dict(zip(cols, r)) for r in rows]

    def context_profile(self, claim_id: str) -> dict[str, list[str]]:
        """Where has this been observed: a list of places, read as coverage rather than scope."""
        rows = self.con.execute(
            "SELECT slot, value, count(DISTINCT source_ref) FROM evidence_context "
            "WHERE claim_id = ? GROUP BY 1,2 ORDER BY 1, 3 DESC", [claim_id]).fetchall()
        out: dict[str, list[str]] = {}
        for slot, value, n in rows:
            out.setdefault(slot, []).append(f"{value}×{n}")
        return out

    def _inherited_support(self, claim_id: str) -> dict:
        """Evidence for claims that are special cases of this one, counted separately. Support flows
        specific -> general only.
        """
        row = self.con.execute("SELECT abstract_key FROM claims WHERE claim_id = ?", [claim_id]).fetchone()
        if not row:
            return {"claims": 0, "evidence_rows": 0, "distinct_papers": 0}
        rows = self._rows_by_abstract_key(row[0]).get(row[0], [])
        me = next((r for r in rows if r["claim_id"] == claim_id), None)
        kids = [r["claim_id"] for r in rows
                if r["claim_id"] != claim_id and me and refinement.refines(r, me)]
        if not kids:
            return {"claims": 0, "evidence_rows": 0, "distinct_papers": 0}
        n, papers = self.con.execute(
            "SELECT count(*), count(DISTINCT source_ref) FROM evidence "
            f"WHERE claim_id IN ({','.join('?' * len(kids))})", kids).fetchone()
        return {"claims": len(kids), "evidence_rows": n, "distinct_papers": papers}
