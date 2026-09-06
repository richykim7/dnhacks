"""Frozen suite coverage, failure parity, and outcome-read ordering."""
import asyncio
from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import pytest

from dnhacksbio.forecasting.reasoning import fixture_completion

spec = importlib.util.spec_from_file_location("forecast_suite", Path(__file__).resolve().parents[1] / "scripts/run_forecast_suite.py")
suite = importlib.util.module_from_spec(spec)
spec.loader.exec_module(suite)


@pytest.fixture
def scenario():
    queries = ["query-d", "query-b", "query-c", "query-a"]
    return {"id": "synthetic", "dataset": "synthetic", "cutoff": "2018-01-01", "horizon": "2022-03-01",
        "nodes": [{"id": n, "label": n, "type": "entity"} for n in [*queries, "target-a", "target-b", "bridge"]],
        "claims": [{"id": f"claim-{i}", "source": "bridge", "target": target,
                    "relation": "associated_with", "evidence_ids": [f"e{i}"], "contexts": []}
                   for i, target in enumerate([*queries, "target-a", "target-b"])],
        "evidence": [{"id": f"e{i}", "title": f"Source {i}", "text": "Historical evidence",
                      "available_at": "2017-01-01", "publication_year": 2016}
                     for i in range(6)],
        "candidates": [{"id": f"{q}/{t}", "source": q, "target": t, "query_id": q}
                       for q in queries for t in ("target-a", "target-b")]}


def outcomes(scenario, tmp_path):
    path = tmp_path / "outcomes.json"
    path.write_text(json.dumps({"scenario_id": scenario["id"], "horizon": scenario["horizon"], "evidence": [],
        "outcomes": [{"candidate_id": c["id"], "observed": c["target"] == "target-a", "evidence_ids": []}
                     for c in scenario["candidates"]]}))
    return path


def test_freezes_every_query_and_candidate(scenario):
    result = suite.prepare_suite(scenario, model="test", fixture=True)
    assert [q["query_id"] for q in result["queries"]] == sorted({c["query_id"] for c in scenario["candidates"]})
    assert result["candidate_count"] == len(scenario["candidates"])
    assert result["planned_model_calls"] == 24
    assert result["budget"]["output_tokens"] == 6000
    assert all(len({c["id"] for c in q["candidates"]}) == 2 for q in result["queries"])


def test_manifest_precedes_calls_and_concurrency_is_bounded(scenario, tmp_path):
    directory = tmp_path / "suite"
    active = peak = calls = 0
    async def complete(prompt, **kwargs):
        nonlocal active, peak, calls
        assert (directory / "manifest.json").exists()
        assert not (directory / "sealed.json").exists()
        assert kwargs["max_output_tokens"] == 6000
        assert kwargs["max_attempts"] == 1
        active += 1
        peak = max(peak, active)
        calls += 1
        await asyncio.sleep(0.005)
        response = await fixture_completion(prompt)
        active -= 1
        return response
    manifest, records = asyncio.run(suite.run_suite(scenario, directory, model="test", completion=complete))
    assert peak <= 9 and calls == 24
    assert len(records) == 4 and all(r["result"]["comparison_ready"] for r in records)
    assert (directory / "sealed.json").exists()
    with pytest.raises(ValueError, match="immutable"):
        asyncio.run(suite.run_suite(scenario, directory, model="test", fixture=True))


def test_evaluation_requires_seal_before_opening_outcomes(scenario, tmp_path):
    directory = tmp_path / "suite"
    directory.mkdir()
    suite.save_new(directory / "manifest.json", suite.prepare_suite(scenario, model="test", fixture=True))
    with pytest.raises(FileNotFoundError, match="sealed.json"):
        suite.evaluate_suite(scenario, directory, tmp_path / "NEVER-OPENED.json")


def test_common_complete_queries_and_same_evidence_popularity(scenario, tmp_path):
    directory = tmp_path / "suite"
    async def complete(prompt, **kwargs):
        packet = json.loads(prompt)
        response = await fixture_completion(prompt)
        if packet["candidates"][0]["query_id"] == "query-a" and packet["graph"] is None:
            response["forecasts"] = []
        return response
    asyncio.run(suite.run_suite(scenario, directory, model="test", completion=complete))
    report = suite.evaluate_suite(scenario, directory, outcomes(scenario, tmp_path))
    assert report["origin"] == "illustrative"
    assert report["coverage"]["complete_queries"] == 3
    assert report["coverage"]["evaluated_candidates"] == 6
    assert report["coverage"]["excluded_observed"] == 1
    assert report["failures"][0]["query_id"] == "query-a"
    for model in report["comparison"]["models"].values():
        assert set(model["queries"]) == {"query-b", "query-c", "query-d"}
    assert report["comparison"]["models"]["popularity"]["overall"]["average_precision"] == 0.5
    bootstrap = suite.paired_bootstrap(report["comparison"]["models"])
    assert bootstrap == report["bootstrap"]
    assert all(row["eligible_queries"] == 3 for row in bootstrap["comparisons"].values())


def test_modified_run_rejected_before_outcomes_are_opened(scenario, tmp_path):
    directory = tmp_path / "suite"
    manifest, _ = asyncio.run(suite.run_suite(scenario, directory, model="test", fixture=True))
    (directory / manifest["queries"][0]["file"]).write_text("{}")
    with pytest.raises(ValueError, match="changed after sealing"):
        suite.evaluate_suite(scenario, directory, tmp_path / "NEVER-OPENED.json")


def test_full_failure_stays_explicit(scenario, tmp_path):
    async def invalid(prompt, **kwargs):
        return {"invalid": True}
    directory = tmp_path / "suite"
    asyncio.run(suite.run_suite(scenario, directory, model="test", completion=invalid))
    report = suite.evaluate_suite(scenario, directory, outcomes(scenario, tmp_path))
    assert report["comparison"] is None and report["bootstrap"] is None
    assert report["coverage"]["complete_queries"] == 0
    assert len(report["failures"]) == 4


def test_no_positive_queries_have_explicit_metric_eligibility(scenario, tmp_path):
    directory = tmp_path / "suite"
    asyncio.run(suite.run_suite(scenario, directory, model="test", fixture=True))
    path = outcomes(scenario, tmp_path)
    packet = json.loads(path.read_text())
    for row in packet["outcomes"]:
        row["observed"] = False
    path.write_text(json.dumps(packet))
    report = suite.evaluate_suite(scenario, directory, path)
    assert report["coverage"]["evaluated_observed"] == 0
    for model in report["comparison"]["models"].values():
        assert model["macro"]["average_precision"] is None
        assert model["macro"]["average_precision_eligible_queries"] == 0
