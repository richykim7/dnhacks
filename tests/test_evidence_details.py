"""Real graph/schema checks for read-only, collection-scoped evidence inspection."""
import json
import os

import pytest
import duckdb

from dnhacksbio.explorer.fulltext import FullTextStore
from dnhacksbio.litmap.store import KGStore
from dnhacksbio.webui import data, evidence, server


@pytest.fixture
def collections(tmp_path, monkeypatch):
    paths = {}
    for name in ("alpha", "beta"):
        path = tmp_path / name / "kg.duckdb"
        store = KGStore(path)
        con = store.con
        con.execute("insert into claims (claim_id,subject_label,object_label,predicate,polarity) values ('same-id','SCN2A','excitability','regulates',1)")
        con.execute("insert into evidence (evidence_id,claim_id,source_ref,source_label,quote,section,attribution) values (1,'same-id',7,? ,?,'Results','own')", [f"{name} source", f"{name} quotation"])
        con.execute("insert into evidence_context (ctx_id,evidence_id,claim_id,source_ref,slot,value,label,provenance,quote) values (1,1,'same-id',7,'organism','human','Human','stated',?)", [f"{name} context"])
        FullTextStore(con=con).add_paper(source_ref=7, title=f"{name} paper", year=2020, doi=f"10.1234/{name}", text="Stored source body", resolve_identity=False)
        store.close()
        paths[name] = path
    monkeypatch.setattr(data, "kg_sources", lambda: paths)
    return paths


def test_graph_ids_open_exact_collection_evidence(collections):
    edge = data.kg_graph("alpha")["edges"][0]
    result = evidence.claim_detail("alpha", edge["claim_id"])
    assert edge["claim_id"] == "same-id"
    assert result["source"] == "alpha"
    assert result["evidence_total"] == 1
    row = result["evidence"][0]
    assert row["quote"] == "alpha quotation"
    assert row["attribution"] == "own"
    assert row["contexts"][0]["quote"] == "alpha context"
    assert row["papers"][0]["title"] == "alpha paper"
    assert row["papers"][0]["doi"] == "10.1234/alpha"
    assert "beta" not in json.dumps(result)
    assert evidence.claim_detail("beta", "same-id")["evidence"][0]["quote"] == "beta quotation"


@pytest.mark.parametrize("source,claim", [("missing", "same-id"), ("../alpha", "same-id"), ("alpha", "missing"), ("alpha", "' OR 1=1 --")])
def test_unknown_collection_or_claim_never_falls_back(collections, source, claim):
    with pytest.raises(KeyError):
        evidence.claim_detail(source, claim)


def test_optional_paper_metadata_and_empty_evidence_remain_explicit(collections):
    store = KGStore(collections["alpha"])
    store.con.execute("drop table papers")
    store.close()
    assert evidence.claim_detail("alpha", "same-id")["evidence"][0]["papers"] == []
    store = KGStore(collections["alpha"])
    store.con.execute("delete from evidence")
    store.close()
    result = evidence.claim_detail("alpha", "same-id")
    assert result["evidence"] == []
    assert result["evidence_total"] == 0


def test_claim_dispatch_requires_explicit_source(collections):
    handler = object.__new__(server.Handler)
    handler._error = lambda status, message: (status, message)
    handler._send_json = lambda payload: payload
    assert handler._kg({"claim": ["same-id"]})[0] == 400
    assert handler._kg({"claim": ["same-id"], "source": ["missing"]})[0] == 404
    assert handler._kg({"claim": ["same-id"], "source": ["alpha"]})["source"] == "alpha"


def test_locked_same_name_databases_cannot_reuse_another_collections_snapshot(collections, monkeypatch, tmp_path):
    for path in collections.values():
        os.utime(path, (1700000000, 1700000000))
    monkeypatch.setattr(data, "_CACHE", tmp_path / "snapshots")
    connect = duckdb.connect

    def locked(path, **kwargs):
        if kwargs.get("read_only"):
            raise duckdb.IOException("Database locked by writer")
        return connect(path, **kwargs)

    monkeypatch.setattr(data.duckdb, "connect", locked)
    assert evidence.claim_detail("alpha", "same-id")["evidence"][0]["quote"] == "alpha quotation"
    assert evidence.claim_detail("beta", "same-id")["evidence"][0]["quote"] == "beta quotation"
    assert evidence.claim_detail("alpha", "same-id")["evidence"][0]["quote"] == "alpha quotation"
    assert len(list(data._CACHE.glob("*.duckdb"))) == 2


def test_graph_preserves_distinct_measured_properties(collections):
    store = KGStore(collections["alpha"])
    store.con.execute("update claims set object_aspect='activity' where claim_id='same-id'")
    store.con.execute("insert into claims (claim_id,subject_label,object_label,predicate,polarity,object_aspect) values ('another-id','SCN2A','excitability','regulates',1,'abundance')")
    store.close()
    edges = {edge["claim_id"]: edge for edge in data.kg_graph("alpha")["edges"]}
    assert edges["same-id"]["object_function"] == "activity"
    assert edges["another-id"]["object_function"] == "abundance"
