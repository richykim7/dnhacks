import asyncio
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCENARIO = ROOT / "demo/forecasting/scenarios/civic-2018-2022"
RUN = ROOT / "demo/forecasting/runs/civic-2018-2022-greedy.json"

spec = importlib.util.spec_from_file_location("memory_control", ROOT / "scripts/run_forecast_memory_control.py")
mc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mc)


@pytest.fixture(scope="module")
def scenario():
    return json.loads((SCENARIO / "historical.json").read_text())


def test_fixture_run_seals_before_evaluating_and_scores_identical_rows(tmp_path, scenario):
    out = tmp_path / "control"
    manifest = asyncio.run(mc.run(scenario, out, model=None, fixture=True, output_tokens=10, timeout=5))
    assert manifest["origin"] == "illustrative" and manifest["budget"]["evidence_records"] == 0
    assert all(q["prompt"]["evidence"] == [] for q in manifest["queries"])
    assert (out / "sealed.json").exists() and not (out / "evaluation.json").exists()
    report = mc.evaluate(scenario, out, RUN, SCENARIO / "outcomes.json")
    assert set(report["models"]) == {"no_retrieval", "structural_full_graph", "popularity"}
    cov = report["coverage"]
    assert cov["complete_queries"] == cov["planned_queries"] == 22
    assert cov["evaluated_candidates"] == cov["planned_candidates"] == 683
    assert cov["evaluated_observed"] == cov["planned_observed"] == 24
    counts = {name: m["overall"]["candidate_count"] for name, m in report["models"].items()}
    assert set(counts.values()) == {683}
    with pytest.raises(FileExistsError):
        mc.save_new(out / "evaluation.json", {})


def test_validation_rejects_incomplete_or_out_of_range_scores():
    ids = {"a", "b"}
    assert mc.validate({"forecasts": [{"candidate_id": "a", "score": 0.5}, {"candidate_id": "b", "score": 1}]}, ids) == []
    assert mc.validate({"forecasts": [{"candidate_id": "a", "score": 0.5}]}, ids)
    assert mc.validate({"forecasts": [{"candidate_id": "a", "score": 1.5}, {"candidate_id": "b", "score": 0}]}, ids)
    assert mc.validate({"forecasts": [{"candidate_id": "a", "score": 0, "note": "x"}, {"candidate_id": "b", "score": 0}]}, ids)
    assert mc.validate({"hypotheses": []}, ids)


def test_tampered_query_record_is_refused(tmp_path, scenario):
    out = tmp_path / "control"
    asyncio.run(mc.run(scenario, out, model=None, fixture=True, output_tokens=10, timeout=5))
    record = out / "query-01.json"
    record.write_text(record.read_text().replace('"score": 0.', '"score": 1.', 1))
    with pytest.raises(ValueError, match="changed after sealing"):
        mc.evaluate(scenario, out, RUN, SCENARIO / "outcomes.json")
