"""Read-only claim inspection for the existing literature graph.

One claim, everything the graph stores about it, in one round trip: the claim_edges row plus the
entity-form columns the view drops (state, variant, isoform, construct, feature), every evidence
record with its contexts, citations, source paper and the experiment it reports, the other claims
that answer the same question (`abstract_key` siblings, which is what a dispute is made of), and
every engine test that has touched the claim. Nothing here writes, resolves identifiers or calls a
model; a missing table simply yields an empty list so an older graph still opens.
"""
from . import data

_FORM_FIELDS = ("state", "variant", "isoform", "protein_construct", "feature_type", "feature_tier")

_PAPER_COLS_FULL = ("paper_id, source_ref, source_label, title, year, doi, pmid, pmcid, url, license, "
                    "is_full_text, n_chars, meta_method, meta_verified")
_PAPER_COLS_MIN = "paper_id, source_ref, title, year, doi, pmid, url, meta_verified"


def _entity_forms(con, claim_id: str) -> dict[str, dict]:
    cols = ", ".join(f"{side}_{f}" for side in ("subject", "object") for f in _FORM_FIELDS)
    try:
        rows = data._rows(con, f"select {cols} from claims where claim_id = ?", [claim_id])
    except data.duckdb.Error:
        return {}
    if not rows:
        return {}
    row = rows[0]
    return {
        f"{side}_form": {f: row.get(f"{side}_{f}") for f in _FORM_FIELDS if row.get(f"{side}_{f}")}
        for side in ("subject", "object")
    }


def _papers(con, claim_id: str, tables: set[str]) -> list[dict]:
    if "papers" not in tables:
        return []
    sql = ("from papers where source_ref in (select source_ref from evidence where claim_id = ?) "
           "order by paper_id")
    try:
        return data._rows(con, f"select {_PAPER_COLS_FULL} {sql}", [claim_id])
    except data.duckdb.Error:                       # a paper store written before these columns existed
        return data._rows(con, f"select {_PAPER_COLS_MIN} {sql}", [claim_id])


def claim_detail(source: str, claim_id: str) -> dict:
    sources = data.kg_sources()
    if source not in sources:
        raise KeyError("unknown kg source")
    con = data._connect_ro(sources[source])
    try:
        claims = data._rows(con, "select * from claim_edges where claim_id = ?", [claim_id])
        if not claims:
            raise KeyError("claim not found in this collection")
        claim = claims[0]
        claim.update(_entity_forms(con, claim_id))
        tables = data._tables(con)
        rows = data._rows(
            con, "select * from evidence where claim_id = ? order by source_ref, evidence_id limit 100", [claim_id])
        total = con.execute("select count(*) from evidence where claim_id = ?", [claim_id]).fetchone()[0]
        contexts = data._rows(
            con, "select * from evidence_context where claim_id = ? order by evidence_id, slot, ctx_id", [claim_id]
        ) if "evidence_context" in tables else []
        cites = data._rows(
            con, "select evidence_id, sid, marker, tier from evidence_cites where claim_id = ? order by evidence_id, sid",
            [claim_id],
        ) if "evidence_cites" in tables else []
        papers = _papers(con, claim_id, tables)
        experiment_ids = sorted({r["experiment_id"] for r in rows if r.get("experiment_id")})
        experiments: dict[str, dict] = {}
        if experiment_ids and "experiments" in tables:
            marks = ",".join("?" * len(experiment_ids))
            for e in data._rows(con, f"select * from experiments where experiment_id in ({marks})", experiment_ids):
                experiments[e["experiment_id"]] = e
        for row in rows:
            row["contexts"] = [c for c in contexts if c["evidence_id"] == row["evidence_id"]]
            row["cites"] = [c for c in cites if c["evidence_id"] == row["evidence_id"]]
            row["papers"] = [p for p in papers if p["source_ref"] == row["source_ref"]]
            row["experiment"] = experiments.get(row.get("experiment_id") or "")
        related = data._rows(
            con,
            "select claim_id, subject_label, predicate, object_label, object_function, relation_class, "
            "polarity, status, dispute_kind, n_sources, first_year from claim_edges "
            "where abstract_key = ? and claim_id <> ? order by n_sources desc, claim_id",
            [claim["abstract_key"], claim_id],
        ) if claim.get("abstract_key") else []
        tests = data._rows(
            con,
            "select test_id, run_id, method, hypothesis, expected_sign, observed_sign, effect, effect_size, "
            "p_null, status, kill_reason, verdict_note, human_review, review_note, novelty_verdict, created_at "
            "from engine_tests where kg_claim_id = ? order by test_id",
            [claim_id],
        ) if "engine_tests" in tables else []
        return {"source": source, "claim": claim, "evidence": rows, "evidence_total": total,
                "related": related, "tests": tests}
    finally:
        con.close()
