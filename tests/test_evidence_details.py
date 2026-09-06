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


def _rich_collection(path):
    """A graph with two answers to one question, an experiment, a citation, and engine tests."""
    store = KGStore(path)
    con = store.con
    con.execute(
        "insert into claims (claim_id, abstract_key, subject_curie, subject_label, subject_kind, subject_state, "
        "subject_variant, object_curie, object_label, object_kind, object_aspect, relation_class, polarity, "
        "predicate, mechanism) values "
        "('up', 'q1', 'HGNC:1100', 'BRCA1', 'entity', 'mutant', 'p.Cys61Gly', 'GO:0006281', 'DNA repair', 'process', "
        "'', 'causal', 1, 'increases', 'via RAD51 loading'), "
        "('down', 'q1', 'HGNC:1100', 'BRCA1', 'entity', 'wild-type', '', 'GO:0006281', 'DNA repair', 'process', "
        "'', 'causal', -1, 'decreases', ''), "
        "('assoc', 'q2', 'HGNC:1100', 'BRCA1', 'entity', 'unknown', '', 'MONDO:0007254', 'breast cancer', 'disease', "
        "'', 'correlational', 0, 'associated_with', '')"
    )
    con.execute("insert into claim_status values ('up', 'disputed', 'opposite_sign'), ('down', 'disputed', 'opposite_sign')")
    con.execute(
        "insert into evidence (evidence_id, claim_id, source_ref, source_label, experiment_id, quote, section, "
        "predicate, quantifier, evidence_type, study_type, attribution, certainty) values "
        "(1, 'up', 1, 'Alpha 2019', 'exp-1', 'BRCA1 promotes repair.', 'Results', 'promotes', 'most', "
        "'experimental_own', 'molecular_experiment', 'own', 'demonstrated'), "
        "(2, 'up', 2, 'Beta 2021', null, 'As shown before, BRCA1 promotes repair.', 'Introduction', 'promotes', '', "
        "'author_statement_prior', 'review_statement', 'prior', 'suggested'), "
        "(3, 'down', 3, 'Gamma 2020', null, 'Loss of BRCA1 raised repair rates.', 'Results', 'reduces', '', "
        "'experimental_own', 'genomic_assay', 'own', 'suggested'), "
        "(4, 'assoc', 1, 'Alpha 2019', null, 'BRCA1 carriers develop breast cancer.', 'Discussion', 'associated with', "
        "'some', 'curator_inference', 'cohort_association', 'own', 'predicted')"
    )
    con.execute(
        "insert into evidence_context (ctx_id, evidence_id, claim_id, source_ref, slot, value, label, provenance, "
        "quote, inherited_from) values (1, 1, 'up', 1, 'cell_line', 'CVCL_0031', 'MCF-7', 'inherited', '', 'methods')"
    )
    con.execute("insert into evidence_cites values (2, 'up', 2, 'DOI:10.1/alpha', '(3)', 'doi')")
    con.execute(
        "insert into experiments (experiment_id, source_ref, unit, intervention, control, readout, assay, n, effect, "
        "uncertainty, statistic, quote) values ('exp-1', 1, 'cells', 'BRCA1 knockdown', 'scrambled siRNA', "
        "'RAD51 foci', 'immunofluorescence', 24, '-1.4 log2FC', '95% CI 1.2-2.7', 'p<0.01', 'n=24 cells, -1.4 log2FC')"
    )
    con.execute(
        "insert into engine_tests (test_id, run_id, kg_claim_id, subject, object, method, expected_sign, observed_sign, "
        "effect, p_null, status, kill_reason, human_review, review_note) values "
        "(1, 'root', 'up', 'BRCA1', 'DNA repair', 'depmap_dependency', 1, 1, 0.4, 0.01, 'candidate', '', '', ''), "
        "(2, 'root~1', 'up', 'BRCA1', 'DNA repair', 'geo_expression', 1, -1, -0.2, 0.3, 'refuted', 'direction-wrong', '', ''), "
        "(3, 'root~2', 'up', 'BRCA1', 'DNA repair', 'co_essentiality', 1, 1, 0.5, 0.001, 'candidate', '', 'validated', 'Replicates.')"
    )
    FullTextStore(con=con).add_paper(source_ref=1, title="Alpha paper", year=2019, doi="10.1/alpha",
                                     text="body", is_full_text=True, license="cc-by", resolve_identity=False)
    store.close()


@pytest.fixture
def rich(tmp_path, monkeypatch):
    path = tmp_path / "rich" / "kg.duckdb"
    _rich_collection(path)
    monkeypatch.setattr(data, "kg_sources", lambda: {"rich": path})
    return path


def test_graph_carries_identity_kind_polarity_and_engine_overlay(rich):
    g = data.kg_graph("rich")
    nodes = {n["id"]: n for n in g["nodes"]}
    assert nodes["HGNC:1100"]["kind"] == "entity" and nodes["HGNC:1100"]["curie"] == "HGNC:1100"
    assert nodes["HGNC:1100"]["n_out"] == 3 and nodes["GO:0006281"]["n_in"] == 2
    edges = {e["claim_id"]: e for e in g["edges"]}
    assert edges["up"]["polarity"] == 1 and edges["down"]["polarity"] == -1 and edges["assoc"]["polarity"] == 0
    assert edges["up"]["relation_class"] == "causal" and edges["up"]["abstract_key"] == "q1"
    assert edges["up"]["mechanism"] == "via RAD51 loading" and edges["up"]["first_year"] == 2019
    assert edges["up"]["status"] == "disputed" and edges["up"]["dispute_kind"] == "opposite_sign"
    assert edges["up"]["tested"] == {"n": 3, "candidate": 1, "validated": 1, "rejected": 0, "killed": 1}
    assert edges["assoc"]["tested"] is None
    assert g["matched"] == g["total_claims"] == 3
    assert g["summary"]["papers"] == 1 and g["summary"]["experiments"] == 1 and g["summary"]["tests"] == 3
    assert {f["value"]: f["n"] for f in g["facets"]["kind"]} == {"entity": 1, "process": 1, "disease": 1}
    assert {f["value"]: f["n"] for f in g["facets"]["polarity"]} == {1: 1, -1: 1, 0: 1}
    assert g["as_of"] is not None


def test_graph_filters_are_closed_vocabulary_and_search_is_collection_wide(rich):
    assert {e["claim_id"] for e in data.kg_graph("rich", polarity="-1")["edges"]} == {"down"}
    assert {e["claim_id"] for e in data.kg_graph("rich", kind="disease")["edges"]} == {"assoc"}
    assert {e["claim_id"] for e in data.kg_graph("rich", relation_class="correlational")["edges"]} == {"assoc"}
    assert {e["claim_id"] for e in data.kg_graph("rich", predicate="decreases")["edges"]} == {"down"}
    assert data.kg_graph("rich", relation_class="nonsense")["matched"] == 3      # ignored, never guessed
    found = data.kg_graph("rich", q="rad51")
    assert {e["claim_id"] for e in found["edges"]} == {"up"} and found["matched"] == 1
    assert {e["claim_id"] for e in data.kg_graph("rich", q="mondo:0007254")["edges"]} == {"assoc"}
    assert data.kg_graph("rich", q="' or 1=1 --")["matched"] == 0


def test_claim_detail_carries_forms_experiment_cites_siblings_and_tests(rich):
    d = evidence.claim_detail("rich", "up")
    assert d["claim"]["subject_form"] == {"state": "mutant", "variant": "p.Cys61Gly"}
    assert d["claim"]["object_form"] == {}
    by_id = {e["evidence_id"]: e for e in d["evidence"]}
    assert by_id[1]["experiment"]["intervention"] == "BRCA1 knockdown" and by_id[1]["experiment"]["n"] == 24
    assert by_id[2]["experiment"] is None
    assert by_id[2]["cites"] == [{"evidence_id": 2, "sid": "DOI:10.1/alpha", "marker": "(3)", "tier": "doi"}]
    assert by_id[1]["contexts"][0]["inherited_from"] == "methods"
    assert by_id[1]["papers"][0]["is_full_text"] is True and by_id[1]["papers"][0]["license"] == "cc-by"
    assert by_id[2]["papers"] == []
    assert [r["claim_id"] for r in d["related"]] == ["down"]
    assert d["related"][0]["polarity"] == -1
    assert [t["test_id"] for t in d["tests"]] == [1, 2, 3]
    assert d["tests"][1]["kill_reason"] == "direction-wrong"
    assert d["tests"][2]["human_review"] == "validated" and d["tests"][2]["review_note"] == "Replicates."
    assert evidence.claim_detail("rich", "assoc")["related"] == []
