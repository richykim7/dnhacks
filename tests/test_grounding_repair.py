"""Regression cases observed in the extraction smoke, without network dependencies."""
from dnhacksbio.litmap import grounding as G


def test_chemical_spacing_alias_is_owner_scoped(monkeypatch):
    monkeypatch.setattr(G, "_lexcache", {"chebi": {
        "n-acetyl-l-cysteine": ["CHEBI:28939", "N-acetyl-L-cysteine"],
    }, "family": {}})
    assert G.owner_first(" N‑acetyl  cysteine ", ("CHEBI",))["curie"] == "CHEBI:28939"
    assert G.owner_first("N-acetyl cysteine", ("FPLX",)) is None
    assert G.chebi_lookup("N-acetyl-D-cysteine") is None


def test_owner_lexicon_cannot_return_foreign_namespace(monkeypatch):
    monkeypatch.setattr(G, "_lexcache", {"family": {"erk": ["HGNC:6877", "MAPK3"]}})
    assert G.owner_first("ERK", ("FPLX",)) is None


def test_invasion_alias_requires_explicit_pathological_category(monkeypatch):
    calls = []
    def exact(query, ontology):
        calls.append((query, ontology))
        return {"curie": "MESH:D009361", "label": "Neoplasm Invasiveness", "match": "label"} if query == "neoplasm invasiveness" else None
    monkeypatch.setattr(G, "_ols_exact", exact)
    monkeypatch.setattr(G, "_proc_cache", {})
    monkeypatch.setattr(G, "_mesh_ok", lambda _: True)
    monkeypatch.setattr(G, "mesh_kind", lambda _: "pathological_process")
    monkeypatch.setattr(G, "go_namespace", lambda _: "")
    assert G.resolve_process("invasion", ("MESH",))["curie"] == "MESH:D009361"
    calls.clear()
    assert G.resolve_process("invasion", ("GO",)) is None
    assert G.resolve_process("invasion") is None
    assert not any(query == "neoplasm invasiveness" for query, _ in calls)


def test_candidate_pool_is_filtered_before_menu_truncation(monkeypatch):
    calls = []
    class Response:
        def json(self):
            return {"response": {"docs": [
                *[{"obo_id": f"CL:{i}", "label": "imported cell"} for i in range(8)],
                {"obo_id": "GO:0000001", "label": "matching process"},
            ]}}
    def get(url, *, params, **kwargs):
        calls.append(params)
        return Response()
    monkeypatch.setattr(G.requests, "get", get)
    monkeypatch.setattr(G, "_cand_cache", {})
    result = G.process_candidates("matching process", namespaces=("GO",))
    assert calls[0]["rows"] >= 40
    assert [r["curie"] for r in result] == ["GO:0000001"]


def test_regulation_demotion_cannot_escape_owner(monkeypatch):
    monkeypatch.setattr(G, "_ols_exact", lambda *args: {"curie": "CL:0000001", "label": "cell"})
    original = {"curie": "GO:0040000", "label": "positive regulation of cell"}
    assert G.demote_regulation_term(original)["curie"] == "GO:0040000"


def test_exact_search_skips_imported_term_before_selecting(monkeypatch):
    class Response:
        def json(self):
            return {"response": {"docs": [
                {"obo_id": "CL:0000001", "label": "division"},
                {"obo_id": "GO:0000001", "label": "division"},
            ]}}
    monkeypatch.setattr(G.requests, "get", lambda *a, **k: Response())
    monkeypatch.setattr(G, "kind_from_curie", lambda _: "process")
    assert G._ols_exact("division", "go")["curie"] == "GO:0000001"


def test_repeat_owner_keeps_dfam_class_identifiers(monkeypatch):
    monkeypatch.setattr(G, "_lexcache", {"repeat": {"line": ["DFAMCLASS:LINE", "LINE"]}, "repeat_meta": {}})
    assert G.repeat_lookup("LINE")["curie"] == "DFAMCLASS:LINE"


def test_mouse_saa3_supplement_requires_species_and_preserves_human_veto(monkeypatch):
    import pytest
    monkeypatch.setattr(G, "_lexcache", {"nonhuman_gene": {}})
    monkeypatch.setattr(G, "_raw", lambda _: [])
    assert G.nonhuman_gene_lookup("SAA3", "mouse")["curie"] == "NCBIGene:20210"
    assert G.nonhuman_gene_lookup("serum amyloid A3", "mouse")["organism"] == "10090"
    for organism in ("", "human", "rat"):
        with pytest.raises(LookupError):
            G.nonhuman_gene_lookup("SAA3", organism)
    monkeypatch.setattr(G, "_raw", lambda _: [{"db": "HGNC", "organism": "9606", "score": 1., "entry_name": "SAA3P"}])
    with pytest.raises(LookupError, match="resolves in HGNC"):
        G.nonhuman_gene_lookup("SAA3", "mouse")


def test_trp53_uses_existing_ortholog_policy(monkeypatch):
    import pytest
    looked_up = []
    def raw(text):
        looked_up.append(text)
        return [{"db": "HGNC", "id": "11998", "organism": "9606", "score": 1., "entry_name": "TP53"}]
    monkeypatch.setattr(G, "_raw", raw)
    assert G.ground_curie("TRP53", namespaces=("HGNC",))["curie"] == "HGNC:11998"
    assert looked_up == ["TP53"]
    with pytest.raises(LookupError, match="tracked ortholog"):
        G.nonhuman_gene_lookup("TRP53", "mouse")


def test_exact_search_same_owner_homonyms_require_disambiguation(monkeypatch):
    class Response:
        def json(self):
            return {"response": {"docs": [
                {"obo_id": "GO:0000001", "label": "ambiguous process"},
                {"obo_id": "GO:0000002", "label": "ambiguous process"},
            ]}}
    monkeypatch.setattr(G.requests, "get", lambda *a, **k: Response())
    assert G._ols_exact("ambiguous process", "go") is None
