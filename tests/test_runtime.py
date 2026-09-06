import asyncio
import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from dnhacksbio.explorer.runtime import Journal, reduce_event
from dnhacksbio.explorer import skills
from dnhacksbio.explorer.artifacts import collect, validate_structure
from dnhacksbio.explorer.sandbox import RunResult, stream_process

PDB = "ATOM      1  CA  ALA A   1      10.000  10.000  10.000  1.00 20.00           C  \nEND\n"


def test_concurrent_serialization_idempotency_and_resume(tmp_path):
    j = Journal(tmp_path)
    j.register("study", "Original question", project="p")
    with ThreadPoolExecutor(6) as pool:
        list(pool.map(lambda i: j.append(f"study~{i % 3}", "a", "intent", {"intent": str(i)}), range(60)))
    events = j.events("study")
    assert [e["sequence"] for e in events] == list(range(1, 61))
    first = j.append("study", "a", "heartbeat", event_id="fixed")
    assert j.append("study", "a", "heartbeat", event_id="fixed") == first
    assert j.events("study", after=30) == j.events("study")[30:]
    assert j.register("study", "Replacement question")["original_question"] == "Original question"
    with pytest.raises(FileNotFoundError):
        j.manifest("study", "other")


def test_every_playback_cursor_excludes_future_artifacts_and_children(tmp_path):
    j = Journal(tmp_path)
    j.register("study", "Question")
    j.append("study", "a", "attempt.started", {"original_question": "Question"})
    j.append("study~1", "b", "attempt.started", {"branch_objective": "Specific test"})
    j.append("study~1", "b", "experiment.queued", {"status": "queued"}, experiment_id="x")
    j.append("study~1", "b", "experiment.finished", {"result": {"effect": 2}}, experiment_id="x")
    j.append("study~1", "b", "artifact", {"artifact_id": "mol"}, experiment_id="x")
    assert "study~1" not in j.snapshot("study", 1)["runs"]
    exp = j.snapshot("study", 3)["runs"]["study~1"]["experiments"]["x"]
    assert "result" not in exp and not exp["artifacts"]
    assert not j.snapshot("study", 4)["runs"]["study~1"]["experiments"]["x"]["artifacts"]
    assert j.snapshot("study", 5)["runs"]["study~1"]["experiments"]["x"]["artifacts"][0]["available_sequence"] == 5
    state = {"sequence": 0, "runs": {}, "schema_version": 1}
    for e in j.events("study"):
        reduce_event(state, e)
    assert state == j.snapshot("study")
    with pytest.raises(ValueError, match="gap"):
        reduce_event({"sequence": 0, "runs": {}}, j.events("study")[1])


def make_explorer(tmp_path, monkeypatch, replies, sandbox=None):
    from dnhacksbio.explorer.explorer import Explorer
    from dnhacksbio.explorer import embed
    monkeypatch.setattr(embed, "embed_one", lambda *_: None)
    prompts = []
    async def complete(prompt):
        prompts.append(prompt)
        item = next(replies)
        if isinstance(item, BaseException):
            raise item
        return json.dumps(item)
    ex = Explorer("study", "Original research question", db_path=tmp_path / "kg.duckdb",
                  trace_dir=str(tmp_path), complete_fn=complete, sandbox_run=sandbox)
    monkeypatch.setattr(ex, "_state", lambda: "Question")
    monkeypatch.setattr(ex, "_turn_message", lambda obs: obs)
    return ex, prompts


def action(name, args=None):
    return {"action": name, "intent": "Test the proposed mechanism", "args": args or {}}


@pytest.mark.parametrize("replies,steps,state", [
    ([action("done")], 3, "reporting_blocked"), ([action("reflect")], 1, "reporting_blocked"),
    ([RuntimeError("model error")], 1, "failed"), ([TimeoutError("timeout")], 1, "failed"),
    ([{"action": "done"}, {"action": "done"}], 1, "failed"),
    ([{"action": "done"}, action("done")], 1, "reporting_blocked"),
])
def test_lifecycle_protocol_and_complete_instructions(tmp_path, monkeypatch, replies, steps, state):
    ex, prompts = make_explorer(tmp_path, monkeypatch, iter(replies))
    try:
        if state == "failed":
            with pytest.raises(Exception):
                asyncio.run(ex.run(steps))
        else:
            asyncio.run(ex.run(steps))
        run = ex.journal.snapshot("study")["runs"]["study"]
        assert run["lifecycle"] == state
        assert skills.snapshot("agent-runtime")["content"] in prompts[0]
        assert any(e["kind"] == "instructions.delivered" for e in run["history"])
        assert sum(e["kind"] == "protocol.repair" for e in run["history"]) <= 1
    finally:
        ex.close()


def test_dispatch_prerequisite_gate_and_pinned_skill(tmp_path, monkeypatch):
    exp = {"code": "print('x')", "method_id": "regression-glm", "hypothesis": "A test"}
    called = []
    def sandbox(codes):
        called.extend(codes)
        return [RunResult(True, 0, "", "", 1, False)]
    ex, prompts = make_explorer(tmp_path, monkeypatch, iter([
        action("run_experiments", {"experiments": [exp]}),
        action("get_skill", {"name": "regression-glm"}),
        action("run_experiments", {"experiments": [exp]}), action("done")]), sandbox)
    try:
        asyncio.run(ex.run(4))
        assert called == [exp["code"]]
        assert skills.snapshot("regression-glm")["content"] in prompts[2]
        assert any(e["kind"] == "policy.rejected" for e in ex.journal.events("study"))
    finally:
        ex.close()


def test_tool_start_visible_while_blocked_and_cancelled(tmp_path, monkeypatch):
    ex, _ = make_explorer(tmp_path, monkeypatch, iter([action("reflect")]))
    async def scenario():
        entered = asyncio.Event()
        async def blocked(_):
            entered.set()
            await asyncio.Event().wait()
        monkeypatch.setattr(ex, "_dispatch", blocked)
        task = asyncio.create_task(ex.run())
        await entered.wait()
        assert ex.journal.snapshot("study")["runs"]["study"]["activity"]["action"] == "reflect"
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert ex.journal.snapshot("study")["runs"]["study"]["lifecycle"] == "cancelled"
    try:
        asyncio.run(scenario())
    finally:
        ex.close()


def test_audit_storage_failure_blocks_execution(tmp_path, monkeypatch):
    ex, _ = make_explorer(tmp_path, monkeypatch, iter([action("done")]))
    calls = []
    monkeypatch.setattr(ex, "_dispatch", lambda _: calls.append(1))
    monkeypatch.setattr(ex.journal, "append", lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    try:
        with pytest.raises(OSError):
            asyncio.run(ex.run())
        assert ex._degraded and not calls
    finally:
        ex.close()


def test_failed_process_cannot_publish_promising_result(tmp_path, monkeypatch):
    ex, _ = make_explorer(tmp_path, monkeypatch, iter([
        action("run_experiments", {"experiments": [{"method_id": "exploratory", "code": "x"}]}), action("done")
    ]), lambda _: [RunResult(False, 1, 'RESULT: {"effect": 2, "p_null": 0.01}', 'error', 1, False)])
    try:
        asyncio.run(ex.run(2))
        exp = next(iter(ex.journal.snapshot("study")["runs"]["study"]["experiments"].values()))
        assert exp["status"] == "failed" and exp["result"] is None
    finally:
        ex.close()


def test_skill_containment_cycles_missing_and_no_truncation(tmp_path, monkeypatch):
    monkeypatch.setattr(skills, "SKILLS_DIR", tmp_path / "skills")
    path = tmp_path / "skills" / "test"
    path.mkdir(parents=True)
    (path / "SKILL.md").write_text("a" * 12000)
    assert len(skills.snapshot("test")["content"]) > 12000
    assert skills.get_skill("../outside") is None
    (path / "SKILL.md").write_text("[cycle](SKILL.md)")
    with pytest.raises(ValueError, match="Cyclic"):
        skills.snapshot("test")
    (path / "SKILL.md").write_text("[missing](absent.md)")
    with pytest.raises(FileNotFoundError):
        skills.snapshot("test")
    (path / "SKILL.md").write_text("[escape](../../outside.md)")
    with pytest.raises(ValueError, match="escaped"):
        skills.snapshot("test")


def test_real_incremental_stdout_stderr_before_exit():
    chunks = []
    rc, out, err, timeout = stream_process([sys.executable, "-u", "-c", "import time,sys; print('first'); time.sleep(.2); print('last',file=sys.stderr)"], 3,
                                          on_output=chunks.append)
    assert rc == 0 and not timeout and "first" in out and "last" in err
    assert chunks[0]["stream"] == "stdout" and chunks[0]["offset"] == 0
    assert "".join(c["text"] for c in chunks if c["stream"] == "stdout") == "first\n"


@pytest.mark.parametrize("path", ["../outside.pdb", "/etc/passwd", "linked.pdb", "invalid.pdb"])
def test_artifacts_reject_invalid_and_escaped_files(tmp_path, path):
    output = tmp_path / "output"; output.mkdir()
    (tmp_path / "outside.pdb").write_text(PDB)
    (output / "linked.pdb").symlink_to(tmp_path / "outside.pdb")
    (output / "invalid.pdb").write_text("not coordinates")
    manifest = {"schema_version": 1, "artifacts": [{"path": path, "kind": "molecular_structure", "format": "pdb",
        "provenance": {"category": "illustration", "source_ids": [], "tool": "fixture", "tool_version": "1"}}]}
    (output / "manifest.json").write_text(json.dumps(manifest))
    assert collect(output, Journal(tmp_path))[0]["status"] == "rejected"


def test_collected_structure_is_durable_and_integrity_checked(tmp_path):
    output = tmp_path / "output"; output.mkdir()
    p = output / "molecule.pdb"; p.write_text(PDB)
    (output / "manifest.json").write_text(json.dumps({"schema_version": 1, "artifacts": [{
        "path": p.name, "kind": "molecular_structure", "format": "pdb", "provenance": {
            "category": "illustration", "source_ids": [], "tool": "fixture", "tool_version": "1"}}]}))
    j = Journal(tmp_path)
    a = collect(output, j)[0]
    assert a["status"] == "available" and a["atom_count"] == 1
    p.unlink()
    assert j.read_blob(a["storage_key"]).decode() == PDB
    assert validate_structure(PDB.encode(), "pdb") == 1


def test_resume_and_fork_redeliver_guidance_preserve_question(tmp_path, monkeypatch):
    from test_branch_control import report
    ex, prompts = make_explorer(tmp_path, monkeypatch, iter([action("done"), report()] * 3))
    try:
        asyncio.run(ex.run(1))
        old = ex.attempt_id
        ex._resume_sid = "injected-session"
        ex.control.decide("study", 1, {"action": "continue", "reason": "Useful next question",
                                      "objective": "Inspect evidence", "allowance": 1})
        asyncio.run(ex.run(1))
        assert old != ex.attempt_id and len(prompts) == 4
        assert all(skills.snapshot("agent-runtime")["content"] in prompts[i] for i in [0, 2])
        child = ex._spawn_child("study~1", "injected-child", "Branch briefing", "Test independent evidence")
        asyncio.run(child.run(1))
        assert child.manifest["original_question"] == "Original research question"
        assert child.manifest["branch_objective"] == "Test independent evidence"
        assert skills.snapshot("agent-runtime")["content"] in prompts[4]
    finally:
        ex.close()


def test_model_timeout_is_enforced(tmp_path, monkeypatch):
    ex, _ = make_explorer(tmp_path, monkeypatch, iter([]))
    async def blocked(_):
        await asyncio.Event().wait()
    ex._inject_complete = blocked
    ex.model_timeout_s = .01
    try:
        with pytest.raises(TimeoutError):
            asyncio.run(ex.run(1))
        assert ex.journal.snapshot("study")["runs"]["study"]["lifecycle"] == "failed"
    finally:
        ex.close()


def test_sqlite_rolls_back_incomplete_event_transaction(tmp_path):
    j = Journal(tmp_path)
    with pytest.raises(RuntimeError):
        with j.connect() as con:
            con.execute("INSERT INTO events VALUES ('study',1,'uncommitted','{}')")
            raise RuntimeError("interrupted before commit")
    assert j.events("study") == []
    assert j.append("study", "a", "heartbeat")["sequence"] == 1


def test_mmcif_parsing_and_quota(tmp_path, monkeypatch):
    import gemmi
    from dnhacksbio.explorer import artifacts
    structure = gemmi.read_pdb_string(PDB)
    raw = structure.make_mmcif_document().as_string().encode()
    assert validate_structure(raw, "cif") == 1
    monkeypatch.setattr(artifacts, "MAX_ATOMS", 0)
    with pytest.raises(ValueError, match="atom limit"):
        validate_structure(raw, "cif")
    p = tmp_path / "large.pdb"; p.write_bytes(b"a" * 100)
    with pytest.raises(ValueError, match="size limit"):
        artifacts.read_regular(tmp_path, "large.pdb", 50)


def test_verifier_publication_recovers_idempotently_from_durable_queue(tmp_path, monkeypatch):
    ex, _ = make_explorer(tmp_path, monkeypatch, iter([]))
    try:
        sid = ex.vq.submit(run_id="study", hypothesis="Test", subject="A", object="B", method="test",
                           expected_sign=1, result={"effect": 1, "p_null": .01},
                           provenance={"experiment_id": "exp", "attempt_id": "a"})
        ex.vq.con.execute("UPDATE verification_queue SET status='verified',verdict='KILL',reason='Control failed' WHERE submission_id=?", [sid])
        ex.vq._publish_verified("study")
        ex.vq._publish_verified("study")
        events = ex.journal.events("study")
        assert len(events) == 1 and events[0]["kind"] == "experiment.reviewed"
        assert events[0]["payload"]["verification_reason"] == "Control failed"
    finally:
        ex.close()


@pytest.mark.skipif(os.environ.get("DN_RUNTIME_DOCKER_SMOKE") != "1", reason="Opt-in real Docker sandbox smoke")
def test_docker_smoke_streaming_and_durable_artifact(tmp_path):
    from dnhacksbio.explorer.sandbox import run_code
    manifest = {"schema_version": 1, "artifacts": [{"path": "reference.pdb", "kind": "molecular_structure",
                "format": "pdb", "provenance": {"category": "illustration", "source_ids": [],
                "tool": "deterministic fixture", "tool_version": "1"}}]}
    code = ("import os,json,time\nfrom pathlib import Path\n"
            "print('started',flush=True)\ntime.sleep(.3)\n"
            "out=Path(os.environ['DN_ARTIFACT_DIR'])\n"
            f"(out/'reference.pdb').write_text({PDB!r})\n"
            f"(out/'manifest.json').write_text({json.dumps(manifest)!r})\n"
            "print('finished',flush=True)\n")
    observed = []
    j = Journal(tmp_path)
    result = run_code(code, timeout=20, cpus=1, memory="256m", network="none", data_dir=None,
                      journal=j, progress=lambda kind, payload: observed.append((kind, payload)),
                      job_base=str(tmp_path))
    assert result.ok, result.stderr
    assert observed[0][0] == "experiment.started"
    assert "started" in observed[1][1]["text"]
    assert result.artifacts[0]["status"] == "available"
    assert j.read_blob(result.artifacts[0]["storage_key"]).decode() == PDB
    assert not list(tmp_path.glob("explorer-job-*"))
