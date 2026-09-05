from copy import deepcopy
import json
from pathlib import Path

import pytest

from dnhacksbio.forecasting.runner import run_scenario, save_run
from dnhacksbio.forecasting.scoring import active_claims, score_candidates


@pytest.fixture
def scenario():
    nodes = [{"id": node_id, "label": node_id, "type": kind}
             for node_id, kind in [("v1", "variant"), ("v2", "variant"), ("g", "gene"),
                                   ("t1", "therapy"), ("t2", "therapy"), ("t3", "therapy")]]
    claims = [{"id": str(i), "source": a, "target": b, "relation": relation,
               "evidence_ids": [f"e{i}"], "contexts": []}
              for i, (a, b, relation) in enumerate([
                  ("v1", "g", "variant_of"), ("v2", "g", "variant_of"),
                  ("v2", "t2", "associated_with"), ("v1", "t1", "associated_with"),
                  ("v2", "t1", "associated_with")], 1)]
    return {
        "id": "synthetic-path-test", "title": "Synthetic path test", "cutoff": "2018-01-01",
        "dataset": "unit-test-fixture", "horizon": "2022-01-01", "manifest": {}, "nodes": nodes,
        "claims": claims,
        "evidence": [{"id": f"e{i}", "title": f"Synthetic evidence {i}", "text": "Fixture",
                      "url": "", "available_at": "2017-01-01"} for i in range(1, 6)],
        "candidates": [{"id": "a-decoy", "source": "v1", "target": "t3", "query_id": "v1"},
                       {"id": "z-path", "source": "v1", "target": "t2", "query_id": "v1"}],
    }


def test_acquisition_changes_graph_and_ranking_with_inspectable_path(scenario):
    packet = run_scenario(scenario, initial_evidence_ids=["e1", "e2"], batch_size=1, rounds=1)
    assert packet["revisions"][0]["forecasts"][0]["candidate_id"] == "a-decoy"
    top = packet["forecasts"][0]
    assert top["candidate_id"] == "z-path"
    assert top["rank_change"] == 1
    assert top["evidence_ids"] == ["e1", "e2", "e3"]
    assert top["paths"][0]["types"] == ["variant", "gene", "variant", "therapy"]
    assert packet["costs"]["llm_calls"] == 0
    assert [event["seq"] for event in packet["events"]] == list(range(1, 6))
    assert [event["type"] for event in packet["events"]] == [
        "graph_updated", "forecast_recorded", "branches_selected", "graph_updated", "forecast_recorded"]
    assert packet["events"][2]["payload"]["selected_ids"] == ["e3"]


def test_graph_only_runner_never_opens_an_outcome_file(scenario, monkeypatch):
    def no_open(*args, **kwargs):
        raise AssertionError("pure runner must not open any files")
    monkeypatch.setattr(Path, "open", no_open)
    packet = run_scenario(scenario)
    assert packet["metrics"] == {}
    assert all("observed" not in row for row in packet["forecasts"])


def test_run_is_reproducible_does_not_mutate_input_and_snapshots_are_isolated(scenario):
    before = deepcopy(scenario)
    packet = run_scenario(scenario, initial_evidence_ids=["e1"], rounds=2, batch_size=2)
    assert scenario == before
    assert packet == run_scenario(scenario, initial_evidence_ids=["e1"], rounds=2, batch_size=2)
    assert packet["revisions"][0]["evidence_ids"] == ["e1"]
    assert len(packet["revisions"][-1]["evidence_ids"]) == 5
    assert [row["score"] for row in packet["forecasts"]] == [
        row["score"] for row in packet["comparisons"]["full_historical_graph"]]


def test_rejects_future_evidence_and_combined_presenter_packet(scenario):
    scenario["evidence"][0]["available_at"] = "2020-01-01"
    with pytest.raises(ValueError, match="cutoff"):
        run_scenario(scenario)
    scenario["outcomes"] = []
    with pytest.raises(ValueError, match="combined"):
        run_scenario(scenario)


def test_popularity_uses_same_visible_graph_and_claims_hide_unacquired_evidence(scenario):
    scenario["claims"][2]["evidence_ids"].append("e4")
    scenario["claims"][2]["contexts"] = [{"evidence_id": "e3", "disease": "known"},
                                          {"evidence_id": "e4", "disease": "unacquired"}]
    claims = active_claims(scenario, {"e1", "e2", "e3"})
    assert claims[-1]["evidence_ids"] == ["e3"]
    assert claims[-1]["contexts"] == [{"evidence_id": "e3", "disease": "known"}]
    assert score_candidates(scenario, evidence_ids={"e1", "e2"}, method="popularity")[0]["score"] == 0
    assert score_candidates(scenario, evidence_ids={"e3"}, method="popularity")[0]["score"] == 1
    with pytest.raises(ValueError, match="historical"):
        score_candidates(scenario, evidence_ids={"unknown"})


def test_save_is_exclusive_and_round_trips_committed_predictions(scenario, tmp_path):
    packet = run_scenario(scenario)
    path = save_run(packet, tmp_path / "run.json")
    assert json.loads(path.read_text()) == packet
    with pytest.raises(FileExistsError):
        save_run({**packet, "forecasts": []}, path)
    assert json.loads(path.read_text())["forecasts"] == packet["forecasts"]
