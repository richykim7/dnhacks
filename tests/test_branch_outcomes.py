import asyncio
import json
import time

import pytest

from dnhacksbio.branch_monitoring.store import MonitorStore
from dnhacksbio.branch_monitoring.outcomes import prepare, adjudicate, workflow
from dnhacksbio.explorer.control import ControlStore
from dnhacksbio.explorer.runtime import Journal
from test_branch_monitoring import protocol


def setup(tmp_path, *, rid="r", eid="e", terminal=True, baseline=None):
    trace = tmp_path / "public"
    j = Journal(trace); j.register("r", "Question")
    s = ControlStore(trace)
    s.freeze_budget(rid, {"policy_id": "pilot-v1", "actions": 80})
    p = protocol()
    spec = dict(episode_id=eid, run_id=rid, root_id="r", group_id="g", objective="Check mechanism",
        initial_evidence=[b["finding_id"] for b in baseline or []], protocol=p, start_sequence=0, calibration_unit=True,
        outcome_policy=dict(assessor_model="fake-model-v1", prompt_version="subtree-outcome-v1",
            verification_policy="legacy-submission-v1", adjudication_seconds=60, assessment_timeout=2,
            max_candidates=10, initial_snapshot=baseline or []))
    m = MonitorStore(tmp_path / "private")
    prepare(m, j, trace, **spec)
    return m, j, s, trace, spec


def finding(j, rid="r~1", eid="new", *, verdict="CANDIDATE", title="Mechanism supported", submitted=True):
    j.register(rid, "Question")
    j.append(rid, "a", "experiment.queued", {"title": title, "method_id": "audited-method", "code": j.blob("print('measured result')")}, experiment_id=eid)
    j.append(rid, "a", "experiment.finished", {"status": "completed", "result": {"effect": 2, "p_null": .01}, "stdout": j.blob("actual output")}, experiment_id=eid)
    if submitted:
        j.append(rid, "a", "experiment.submitted", {"submission_id": 1}, experiment_id=eid)
    if verdict:
        j.append(rid, "a", "experiment.reviewed", {"submission_id": 1, "verification": verdict}, experiment_id=eid, producer="verifier")


def finish(s, rid="r", status="completed"):
    s.start(rid, 0); s.patch(rid, status=status)
    return s.finalize_budgets(rid)[0]["terminal"]


async def accepted(prompt):
    assert "measured result" in prompt and "actual output" in prompt
    assert "monitor_statistic" not in prompt and "verifier_score" not in prompt
    return json.dumps(dict(relevant=True, nonduplicate=True, evidence_supported=True, reason="Concrete supported new result"))


def test_descendant_artifacts_success_private_and_idempotent(tmp_path):
    m, j, s, trace, _ = setup(tmp_path)
    finding(j); finish(s)
    before = j.events("r")
    result = asyncio.run(adjudicate(m, j, trace, "e", complete_fn=accepted))
    assert result["outcome"] == "success" and result["training_eligible"]
    assert result["label_provenance"]["evidence"][0]["run_id"] == "r~1"
    assert j.events("r") == before
    assert asyncio.run(adjudicate(m, j, trace, "e", complete_fn=accepted)) == result
    assert workflow(m, "e")["attempts"] == 1


def test_unfinished_is_unknown_then_completed_no_finding_unsuccessful(tmp_path):
    m, j, s, trace, _ = setup(tmp_path)
    assert asyncio.run(adjudicate(m, j, trace, "e"))["outcome"] == "unknown"
    finish(s)
    assert asyncio.run(adjudicate(m, j, trace, "e"))["outcome"] == "unsuccessful"


@pytest.mark.parametrize("status", ["failed", "cancelled", "pruned", "reporting_blocked"])
def test_operational_cutoffs_are_censored_not_losses(tmp_path, status):
    m, j, s, trace, _ = setup(tmp_path); finish(s, status=status)
    assert asyncio.run(adjudicate(m, j, trace, "e"))["outcome"] == "censored"


def test_pending_verification_fixed_deadline_and_existing_artifacts_only(tmp_path):
    m, j, s, trace, _ = setup(tmp_path)
    finding(j, verdict=None); end = finish(s)
    assert asyncio.run(adjudicate(m, j, trace, "e", complete_fn=accepted))["outcome"] == "pending"
    deadline = workflow(m, "e")["endpoint"]["deadline"]
    assert deadline == end["at"] + 60
    finding(j, eid="future")  # submitted after the endpoint: never extends the bundle
    j.append("r~1", "a", "experiment.reviewed", {"submission_id": 1, "verification": "CANDIDATE"}, experiment_id="new", producer="verifier")
    result = asyncio.run(adjudicate(m, j, trace, "e", complete_fn=accepted))
    assert result["outcome"] == "success"
    assert [f["finding_id"] for f in workflow(m, "e")["bundle"]] == ["new"]


def test_expired_pending_queue_is_censored(tmp_path):
    m, j, s, trace, _ = setup(tmp_path); finding(j, verdict=None); end = finish(s)
    result = asyncio.run(adjudicate(m, j, trace, "e", now=lambda: end["at"] + 61))
    assert result["outcome"] == "censored" and not result["training_eligible"]


def test_failed_soundness_never_calls_assessor_and_submission_is_not_success(tmp_path):
    m, j, s, trace, _ = setup(tmp_path); finding(j, verdict="KILL"); finish(s)
    async def fail(_): raise AssertionError("Should not assess rejected evidence")
    assert asyncio.run(adjudicate(m, j, trace, "e", complete_fn=fail))["outcome"] == "unsuccessful"


def test_assessor_outage_has_one_attempt_then_censors_at_deadline(tmp_path):
    m, j, s, trace, _ = setup(tmp_path); finding(j); end = finish(s)
    async def outage(_): raise RuntimeError("private credentials must not enter logs")
    assert asyncio.run(adjudicate(m, j, trace, "e", complete_fn=outage))["outcome"] == "pending"
    result = asyncio.run(adjudicate(m, j, trace, "e", complete_fn=outage, now=lambda: end["at"] + 61))
    assert result["outcome"] == "censored" and workflow(m, "e")["attempts"] == 1
    assert "private credentials" not in json.dumps(workflow(m, "e"))


def test_concurrent_label_workers_call_assessor_once(tmp_path):
    m, j, s, trace, _ = setup(tmp_path); finding(j); finish(s)
    calls = []
    async def assessor(prompt):
        calls.append(prompt); await asyncio.sleep(.03); return await accepted(prompt)
    async def run():
        return await asyncio.gather(*[adjudicate(m, j, trace, "e", complete_fn=assessor) for _ in range(2)])
    asyncio.run(run())
    assert len(calls) == 1 and m.episode("e")["outcome"] == "success"


def test_reject_retrospective_enrollment_and_manual_bound_label(tmp_path):
    m, j, s, trace, spec = setup(tmp_path)
    with pytest.raises(ValueError, match="artifact adjudication"):
        m.close("e", termination="natural_finish", provenance={"assessor": "assertion", "artifact_refs": ["not-proof"]})
    j.append("r", "a", "tool.started", {"action": "search"})
    spec["episode_id"] = "late"; spec["group_id"] = "late"
    with pytest.raises(ValueError, match="precede"):
        prepare(m, j, trace, **spec)


def test_duplicate_rubric_is_not_success_and_prompt_frozen(tmp_path):
    m, j, s, trace, _ = setup(tmp_path); finding(j); finish(s)
    async def duplicate(_):
        return json.dumps(dict(relevant=True, nonduplicate=False, evidence_supported=True, reason="Existing result"))
    assert asyncio.run(adjudicate(m, j, trace, "e", complete_fn=duplicate))["outcome"] == "unsuccessful"


def test_corrupt_artifact_is_unavailable_not_negative(tmp_path):
    m, j, s, trace, _ = setup(tmp_path); finding(j); end = finish(s)
    ref = j.blob("actual output")
    (j.directory / "blobs" / ref["sha256"]).write_text("tampered")
    assert asyncio.run(adjudicate(m, j, trace, "e", now=lambda: end["at"] + 61))["outcome"] == "censored"


def test_same_protocol_across_independent_roots_does_not_hash_runtime_timestamps(tmp_path):
    one = setup(tmp_path / "one")[0].episode("e")
    two = setup(tmp_path / "two")[0].episode("e")
    assert one["protocol_hash"] == two["protocol_hash"]


def test_existing_artifact_under_new_name_cannot_earn_success(tmp_path):
    # Create immutable baseline blobs before prospective enrollment.
    j = Journal(tmp_path / "public")
    baseline = [{"finding_id": "old", "claim": "Already known", "artifact_refs":
                 [j.blob("print('measured result')"), j.blob("actual output")]}]
    m, j, s, trace, _ = setup(tmp_path, baseline=baseline)
    finding(j, eid="renamed", title="Renamed existing result"); finish(s)
    async def fail(_): raise AssertionError("Exact baseline replay must not be assessed")
    assert asyncio.run(adjudicate(m, j, trace, "e", complete_fn=fail))["outcome"] == "unsuccessful"


def test_prepare_is_idempotent_but_assessor_cannot_change(tmp_path):
    m, j, s, trace, spec = setup(tmp_path)
    assert prepare(m, j, trace, **spec) == workflow(m, "e")
    spec["outcome_policy"]["assessor_model"] = "changed"
    with pytest.raises(ValueError, match="frozen"):
        prepare(m, j, trace, **spec)


def test_fake_verification_event_cannot_pass_soundness(tmp_path):
    m, j, s, trace, _ = setup(tmp_path); finding(j, verdict=None)
    j.append("r~1", "a", "experiment.reviewed", {"submission_id": 1, "verification": "CANDIDATE"}, experiment_id="new", producer="agent")
    end = finish(s)
    assert asyncio.run(adjudicate(m, j, trace, "e", now=lambda: end["at"] + 61))["outcome"] == "censored"


def test_private_assessment_has_no_future_or_monitor_data(tmp_path):
    m, j, s, trace, _ = setup(tmp_path); finding(j); finish(s)
    j.append("r~1", "a", "human.decision", {"note": "PRIVATE-REVIEW-NOTE"})
    j.append("r~1", "a", "tool.ended", {"observation": j.blob("FUTURE-TOOL-DATA")})
    async def assessor(prompt):
        assert "PRIVATE-REVIEW-NOTE" not in prompt and "FUTURE-TOOL-DATA" not in prompt
        return await accepted(prompt)
    assert asyncio.run(adjudicate(m, j, trace, "e", complete_fn=assessor))["outcome"] == "success"


def test_horizon_mismatch_cannot_be_bound(tmp_path):
    m, j, s, trace, spec = setup(tmp_path)
    spec["episode_id"] = "different"; spec["group_id"] = "different"
    spec["protocol"]["terminal_budget"] = 1000
    with pytest.raises(ValueError, match="match"):
        prepare(m, j, trace, **spec)


@pytest.mark.parametrize("label_first", [True, False])
def test_real_controller_ledger_to_private_label_and_checkpoint_cost(tmp_path, monkeypatch, label_first):
    from test_runtime import make_explorer, action
    from test_branch_control import report
    from dnhacksbio.branch_monitoring.worker import score_pending
    ex, _ = make_explorer(tmp_path / "public", monkeypatch, iter([action("done"), report()]))
    m = MonitorStore(tmp_path / "private")
    budget = ex.control.budgets(ex.run_id)[0]["contract"]
    proto = protocol(); proto.update(policy_id=budget["policy_id"], terminal_budget=budget["actions"])
    prepare(m, ex.journal, tmp_path / "public", episode_id="e", run_id="study", root_id="study", group_id="g",
        objective="Original research question", initial_evidence=[], protocol=proto, start_sequence=0,
        outcome_policy=dict(assessor_model="fake", prompt_version="subtree-outcome-v1",
            verification_policy="legacy-submission-v1", adjudication_seconds=60, assessment_timeout=2,
            max_candidates=10, initial_snapshot=[]))
    ex._allocation_fn = lambda _: {"action": "finish", "reason": "Objective complete"}
    async def fake_score(_):
        if not label_first:
            await adjudicate(m, ex.journal, tmp_path / "public", "e")
        return '{"score": 0.4}'
    async def run():
        await ex.run_investigation(1)
        if label_first:
            await adjudicate(m, ex.journal, tmp_path / "public", "e")
        assert (await score_pending(m, ex.journal, complete_fn=fake_score))["recorded"] == 1
        return m.episode("e")
    try:
        result = asyncio.run(run())
        assert result["outcome"] == "unsuccessful" and result["training_eligible"]
        assert result["label_provenance"]["total_cost"] == 1
        assert m.checkpoints("e")[0]["cumulative_cost"] == 1
        assert result["label_provenance"]["research_control_seconds"] > 0
    finally:
        ex.close()
