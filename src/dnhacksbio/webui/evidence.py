"""Read-only claim inspection for the existing literature graph."""
from . import data


def claim_detail(source: str, claim_id: str) -> dict:
    sources = data.kg_sources()
    if source not in sources:
        raise KeyError("unknown kg source")
    con = data._connect_ro(sources[source])
    try:
        claims = data._rows(con, "select * from claim_edges where claim_id = ?", [claim_id])
        if not claims:
            raise KeyError("claim not found in this collection")
        rows = data._rows(con, "select * from evidence where claim_id = ? order by source_ref, evidence_id limit 100", [claim_id])
        total = con.execute("select count(*) from evidence where claim_id = ?", [claim_id]).fetchone()[0]
        tables = data._tables(con)
        contexts = data._rows(con, "select * from evidence_context where claim_id = ? order by evidence_id, slot, ctx_id", [claim_id]) if "evidence_context" in tables else []
        papers = data._rows(con, "select paper_id, source_ref, title, year, doi, pmid, url, meta_verified from papers where source_ref in (select source_ref from evidence where claim_id = ?) order by paper_id", [claim_id]) if "papers" in tables else []
        for row in rows:
            row["contexts"] = [context for context in contexts if context["evidence_id"] == row["evidence_id"]]
            row["papers"] = [paper for paper in papers if paper["source_ref"] == row["source_ref"]]
        return {"source": source, "claim": claims[0], "evidence": rows, "evidence_total": total}
    finally:
        con.close()
