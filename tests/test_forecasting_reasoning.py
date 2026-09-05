import asyncio
from copy import deepcopy
import json

import pytest

from dnhacksbio.forecasting.reasoning import (
    CONDITIONS, fixture_completion, prepare_reasoning, run_reasoning_comparison,
)


@pytest.fixture
def historical():
    return {"id": "example", "dataset": "synthetic test", "cutoff": "2018-01-01",
        "horizon": "2022-01-01", "manifest": {"origin": "illustrative"},
        "nodes": [{"id": key, "label": key, "type": "entity"} for key in "abcdef"],
        "claims": [{"id": f"claim{i}", "source": "a", "target": target,
                    "relation": "associated_with", "evidence_ids": [f"e{i}"],
                    "contexts": [{"evidence_id": f"e{i}", "note": f"context{i}"}]}
                   for i, target in enumerate("ef", 1)] + [
            {"id": "claim3", "source": "e", "target": "b", "relation": "associated_with",
             "evidence_ids": ["e3"], "contexts": []},
            {"id": "claim4", "source": "f", "target": "c", "relation": "associated_with",
             "evidence_ids": ["e4"], "contexts": []}],
        "evidence": [{"id": f"e{i}", "title": f"Source {i}", "text": f"Historical source {i}",
                      "url": f"https://example.org/{i}", "available_at": "2017-01-01"}
                     for i in range(1, 5)],
        "candidates": [{"id": f"candidate-{target}", "source": "a", "target": target, "query_id": "a"}
                       for target in "bcd"]}


def test_fixture_is_deterministic_and_does_not_mutate_sources(historical):
    original = deepcopy(historical)
    first = run_reasoning_comparison(historical, fixture=True, evidence_limit=4)
    assert first == run_reasoning_comparison(historical, fixture=True, evidence_limit=4)
    assert historical == original
    assert first["origin"] == "illustrative"
    assert first["comparison_ready"]
    expected = {row["id"] for row in first["candidates"]}
    for run in first["conditions"].values():
        assert {row["candidate_id"] for row in run["forecasts"]} == expected
        assert len(run["events"]) == 2
        assert all(h["status"] == "unverified_model_hypothesis" for event in run["events"] for h in event["hypotheses"])


def test_information_parity_and_actual_graph_iteration(historical):
    result = run_reasoning_comparison(historical, fixture=True, evidence_limit=4)
    conditions = result["conditions"]
    for step in range(2):
        events = [conditions[name]["events"][step] for name in CONDITIONS]
        assert len({event["source_packet_sha256"] for event in events}) == 1
        assert all(event["visible_evidence_ids"] == events[0]["visible_evidence_ids"] for event in events)
        assert all(event["prompt"]["candidates"] == result["candidates"] for event in events)
    static = conditions["static_graph"]["events"]
    dynamic = conditions["evolving_graph"]["events"]
    assert static[0]["graph"] == static[1]["graph"]
    assert len(dynamic[1]["graph"]["source_claims"]) > len(dynamic[0]["graph"]["source_claims"])
    assert dynamic[1]["prompt"]["graph"]["hypotheses"] == dynamic[0]["hypotheses"]
    assert dynamic[1]["graph_revision"]["hypothesis_candidate_ids_removed"]
    static_log = json.dumps(static[1]["prompt"]["append_log"])
    assert all(row["text"] in static_log for row in historical["evidence"])
    assert all(row["id"] in static_log for row in historical["claims"])
    flat_prompt = conditions["flat_log"]["events"][1]["prompt"]
    assert flat_prompt["graph"] is None
    assert all(row["text"] in str(flat_prompt["append_log"]) for row in historical["evidence"])


@pytest.mark.parametrize("fault", ["extra_candidate", "duplicate", "missing", "future_citation",
                                  "fact_promotion", "nan", "empty_rationale", "unsupported_stance"])
def test_invalid_attempts_are_preserved_and_never_scored(historical, fault):
    async def invalid(prompt, **kwargs):
        response = await fixture_completion(prompt)
        if fault == "extra_candidate":
            response["forecasts"][0]["candidate_id"] = "not-eligible"
        elif fault == "duplicate":
            response["forecasts"].append(response["forecasts"][0])
        elif fault == "missing":
            response["forecasts"].pop()
        elif fault == "future_citation":
            response["hypotheses"][0]["evidence_ids"] = ["future-source"]
        elif fault == "fact_promotion":
            response["hypotheses"][0]["status"] = "verified"
        elif fault == "nan":
            response["forecasts"][0]["score"] = float("nan")
        elif fault == "empty_rationale":
            response["forecasts"][0]["rationale"] = ""
        else:
            response["hypotheses"][0]["stance"] = "proven"
        return response
    result = run_reasoning_comparison(historical, completion=invalid, evidence_limit=4)
    assert not result["comparison_ready"]
    for run in result["conditions"].values():
        assert run["status"] == "incomplete"
        assert run["forecasts"] == []
        assert run["diagnostics"]
        assert all(event["model_response"] is not None for event in run["events"])
        assert all(event["hypotheses"] == [] for event in run["events"])


def test_later_retrieval_cannot_be_cited_early(historical):
    plan = prepare_reasoning(historical, evidence_limit=4)
    future_to_step = plan["evidence_batches"][1][0]
    async def invalid(prompt, **kwargs):
        response = await fixture_completion(prompt)
        response["hypotheses"][0]["evidence_ids"] = [future_to_step]
        return response
    result = run_reasoning_comparison(historical, completion=invalid, evidence_limit=4)
    for run in result["conditions"].values():
        assert run["events"][0]["status"] == "invalid"
        assert run["events"][1]["status"] == "accepted"
        assert run["status"] == "incomplete"


@pytest.mark.parametrize("location", ["root", "candidate", "evidence"])
def test_outcomes_are_rejected_before_any_completion(historical, location):
    if location == "root":
        historical["outcomes"] = []
    else:
        historical["candidates" if location == "candidate" else "evidence"][0]["observed"] = True
    with pytest.raises(ValueError, match="historical inputs only"):
        run_reasoning_comparison(historical, fixture=True)


def test_later_dates_are_rejected_and_selection_ignores_input_order(historical):
    expected = prepare_reasoning(historical, candidate_limit=2, evidence_limit=4)
    for key in ("nodes", "claims", "evidence", "candidates"):
        historical[key].reverse()
    assert prepare_reasoning(historical, candidate_limit=2, evidence_limit=4) == expected
    historical["evidence"][0]["available_at"] = "2022-01-01"
    with pytest.raises(ValueError, match="after the cutoff"):
        prepare_reasoning(historical)


def test_same_per_call_limits_and_failed_calls_are_not_retried(historical):
    calls = []
    async def fail(prompt, **kwargs):
        calls.append(kwargs)
        raise RuntimeError("test unavailable")
    result = run_reasoning_comparison(historical, completion=fail, evidence_limit=4, output_tokens=321)
    assert len(calls) == 6
    assert all(call["tools_disabled"] and call["max_attempts"] == 1 and call["max_turns"] == 1
               and call["max_output_tokens"] == 321 for call in calls)
    assert not result["comparison_ready"]
    assert all(run["diagnostics"] for run in result["conditions"].values())


def test_live_seam_disables_tools_and_uses_per_call_limits(monkeypatch):
    pytest.importorskip("claude_agent_sdk")
    from dnhacksbio import llm
    options = llm._opts("test-model", "system", "low", 1, tools_disabled=True,
                        max_output_tokens=333, cwd="/tmp/empty-test")
    assert options.tools == []  # SDK sends --tools ''; allowed_tools=[] alone is insufficient.
    assert options.strict_mcp_config is True
    assert options.setting_sources == []
    assert options.cwd == "/tmp/empty-test"
    assert options.env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] == "333"
    assert llm._opts("test-model", None, "low", 1).tools is None
    from claude_agent_sdk._internal.transport.subprocess_cli import SubprocessCLITransport
    options.cli_path = "claude"  # Build argv only; do not start an authenticated process.
    command = SubprocessCLITransport(prompt="test", options=options)._build_command()
    assert command[command.index("--tools") + 1] == ""
    assert "--strict-mcp-config" in command
    assert "--setting-sources=" in command
    calls = []
    async def failed_query(**kwargs):
        calls.append(kwargs)
        raise RuntimeError("no retry")
        yield
    monkeypatch.setattr(llm, "query", failed_query)
    with pytest.raises(RuntimeError, match="no retry"):
        asyncio.run(llm.acomplete("test", max_attempts=1))
    assert len(calls) == 1


def test_invalid_numeric_response_remains_json_serializable(historical):
    async def invalid(prompt, **kwargs):
        response = await fixture_completion(prompt)
        response["forecasts"][0]["score"] = float("inf")
        return response
    result = run_reasoning_comparison(historical, completion=invalid, evidence_limit=4)
    text = json.dumps(result, allow_nan=False)
    assert "Infinity" in text  # Preserved as diagnostic text, not a JSON numeric value.


def test_live_adapter_uses_an_empty_cwd_and_does_not_read_outcomes(historical, monkeypatch, tmp_path):
    pytest.importorskip("claude_agent_sdk")
    from pathlib import Path
    from dnhacksbio import llm
    from dnhacksbio.forecasting.snapshots import load_scenario
    source = tmp_path / "historical.json"
    source.write_text(json.dumps(historical))
    (tmp_path / "outcomes.json").write_text("must never be parsed")
    seen = []
    async def fake_live(prompt, **kwargs):
        cwd = Path(kwargs.pop("cwd"))
        assert cwd.is_dir() and list(cwd.iterdir()) == []
        assert kwargs["tools_disabled"] and kwargs["max_attempts"] == 1
        assert "must never be parsed" not in prompt
        seen.append(cwd)
        return json.dumps(await fixture_completion(prompt))
    monkeypatch.setattr(llm, "acomplete", fake_live)
    result = run_reasoning_comparison(load_scenario(source), evidence_limit=4, model="test-model")
    assert result["comparison_ready"] and len(seen) == 6
    assert all(not cwd.exists() for cwd in seen)
