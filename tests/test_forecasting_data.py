"""Temporal input isolation, cross-release identities, and derived-packet integrity."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from dnhacksbio.forecasting.snapshots import historical_snapshot, future_outcomes, load_scenario
from dnhacksbio.forecasting.sources.civic import normalize_row, therapy_members


def row(evidence_id, variant, drugs, date="2018-01-01", **changes):
    raw = dict(evidence_id=str(evidence_id), variant_id=str(variant), gene_id="1", gene="GENE",
        variant=f"V{variant}", drugs=drugs, evidence_type="Predictive", evidence_status="accepted",
        evidence_statement="An association was observed.", pubmed_id="123", citation="Author et al., 2017, Journal",
        disease="Example disease", evidence_direction="Supports", clinical_significance="Resistance")
    raw.update(changes)
    return normalize_row(raw, date)


def historical():
    return [row(1, 1, "Drug A"), row(2, 2, "Drug B"), row(3, 1, "Drug A,Drug C")]


def snapshot(rows=None):
    return historical_snapshot(rows or historical(), cutoff="2018-01-01", horizon="2022-03-01")


def test_treatment_groups_are_atomic_case_and_order_independent():
    a = row(1, 1, "Drug B,Drug A")
    b = row(2, 1, " drug a , DRUG B ")
    assert a["target"] == b["target"] != row(3, 1, "Drug A")["target"]
    assert therapy_members("A,A, b") == ("a", "b")
    assert a["context"]["drug_interaction_type"] is None
    assert a["context"]["clinical_significance"] == "Resistance"


def test_citation_schema_and_missing_dates():
    old = row(1, 1, "A")
    new = row(1, 1, "A", pubmed_id="", source_type="PubMed", citation_id="123")
    assert old["evidence"]["url"] == new["evidence"]["url"] == "https://pubmed.ncbi.nlm.nih.gov/123/"
    unknown = row(2, 1, "A", citation="No publication date", source_type="ASCO", citation_id="abc")
    assert unknown["evidence"]["publication_year"] is None
    assert "pubmed" not in unknown["evidence"]["url"]
    assert unknown["evidence"]["available_at"] == "2018-01-01"


def test_parenthesized_alias_commas_do_not_create_therapy_members():
    aliases = "BEZ235 (NVP-BEZ235, Dactolisib)"
    combined = row(1, 1, aliases + ",Drug B (alias (nested, name))")
    assert combined["context"]["therapies"] == [
        "bez235 (nvp-bez235, dactolisib)", "drug b (alias (nested, name))"]
    assert combined["therapy_label"] == aliases + ", Drug B (alias (nested, name))"
    assert row(2, 1, aliases)["context"]["therapies"] == [aliases.casefold()]
    assert combined["target"] == row(3, 1, "Drug B (alias (nested, name))," + aliases)["target"]


def test_historical_candidates_exclude_known_pairs_and_preserve_endpoint_eligibility():
    scenario = snapshot()
    known = {(r["source"], r["target"]) for r in historical()}
    nodes = {node["id"] for node in scenario["nodes"]}
    assert scenario["candidates"]
    assert all((c["source"], c["target"]) not in known for c in scenario["candidates"])
    assert all(c["source"] in nodes and c["target"] in nodes for c in scenario["candidates"])
    assert all(c["query_id"] == c["source"] for c in scenario["candidates"])
    assert scenario == snapshot(list(reversed(historical())))


def test_later_labels_cannot_change_historical_scene():
    scenario = snapshot()
    frozen = copy.deepcopy(scenario)
    future = [row(4, 1, "Drug B", "2022-03-01"), row(5, 999, "FUTURE DRUG", "2022-03-01")]
    results = future_outcomes(scenario, historical(), future)
    assert sum(outcome["observed"] for outcome in results["outcomes"]) == 1
    assert scenario == frozen
    assert "FUTURE DRUG" not in json.dumps(scenario)
    assert {ev["id"] for ev in results["evidence"]} == {"civic:evidence:4"}


def test_edits_to_old_ids_and_out_of_window_rows_are_not_new_evidence():
    scenario = snapshot()
    for future in [row(1, 1, "Drug B", "2022-03-01"), row(9, 1, "Drug B", "2023-01-01"),
                   row(10, 1, "Drug B", "2018-01-01"),
                   row(11, 1, "Drug B", "2022-03-01", evidence_status="submitted")]:
        result = future_outcomes(scenario, historical(), [future])
        assert not any(outcome["observed"] for outcome in result["outcomes"])


def test_historical_builder_and_loader_reject_later_evidence(tmp_path):
    with pytest.raises(ValueError, match="later evidence"):
        snapshot([row(4, 1, "A", "2022-03-01")])
    scenario = snapshot()
    scenario["evidence"][0]["available_at"] = "2022-03-01"
    path = tmp_path / "historical.json"
    path.write_text(json.dumps(scenario))
    with pytest.raises(ValueError, match="historical input"):
        load_scenario(path)


def test_snapshot_identity_changes_with_evidence_text():
    rows = historical()
    first = snapshot(rows)["manifest"]["snapshot_id"]
    rows[0]["evidence"]["text"] = "Changed historical evidence"
    assert snapshot(rows)["manifest"]["snapshot_id"] != first


def test_tracked_packet_hashes_references_and_temporal_separation():
    directory = Path(__file__).resolve().parents[1] / "demo/forecasting/scenarios/civic-2018-2022"
    manifest = json.loads((directory / "manifest.json").read_text())
    for filename, digest in manifest["files_sha256"].items():
        assert hashlib.sha256((directory / filename).read_bytes()).hexdigest() == digest
    scenario = load_scenario(directory / "historical.json")
    future = json.loads((directory / "outcomes.json").read_text())
    assert 40 <= len(scenario["nodes"]) <= 100
    assert "outcomes" not in scenario
    assert future["scenario_id"] == scenario["id"]
    assert future["manifest"]["snapshot_id"] == scenario["manifest"]["snapshot_id"]
    evidence = {ev["id"] for ev in scenario["evidence"]}
    later_ids = {ev["id"] for ev in future["evidence"]}
    assert evidence.isdisjoint(later_ids)
    assert all(ev["available_at"] <= scenario["cutoff"] for ev in scenario["evidence"])
    assert all(scenario["cutoff"] < ev["available_at"] <= scenario["horizon"] for ev in future["evidence"])
    nodes = {node["id"] for node in scenario["nodes"]}
    for claim in scenario["claims"]:
        assert claim["source"] in nodes and claim["target"] in nodes
        assert set(claim["evidence_ids"]) <= evidence
        assert {context["evidence_id"] for context in claim["contexts"]} == set(claim["evidence_ids"])
    candidate_ids = {candidate["id"] for candidate in scenario["candidates"]}
    assert candidate_ids == {outcome["candidate_id"] for outcome in future["outcomes"]}
    assert len(candidate_ids) == len(scenario["candidates"])
    assert any(outcome["observed"] for outcome in future["outcomes"])
    assert all(bool(outcome["evidence_ids"]) == outcome["observed"] for outcome in future["outcomes"])
    assert all(set(outcome["evidence_ids"]) <= later_ids for outcome in future["outcomes"])
