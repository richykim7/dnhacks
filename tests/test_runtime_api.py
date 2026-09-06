import json
from types import SimpleNamespace

import pytest

from dnhacksbio.explorer.runtime import Journal, process_identity
from dnhacksbio.webui import data, runtime


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(data, "PROCESSED", tmp_path)
    j = Journal(tmp_path)
    j.register("study", "Original question", project="alpha")
    j.register("study~1", "Original question", project="alpha")
    j.append("study", "a", "attempt.started", {"original_question": "Original question"})
    blob = j.blob("A full immutable observation")
    j.append("study", "a", "tool.ended", {"observation": blob})
    handler = SimpleNamespace(_project_arg=lambda qs: qs.get("project", [None])[0],
                              _send_json=lambda obj: obj, _send_bytes=lambda raw, _: raw)
    return j, handler, blob


def test_scoped_snapshot_and_cursor(api):
    j, h, blob = api
    assert runtime.handle(h, "study/snapshot", {"project": ["alpha"]})["sequence"] == 2
    with pytest.raises(FileNotFoundError):
        runtime.handle(h, "study/snapshot", {"project": ["beta"]})
    assert len(runtime.handle(h, "study/events", {"after": ["1"]})["events"]) == 1
    path = f"study/blob/{blob['storage_key']}"
    assert runtime.handle(h, path, {"project": ["alpha"]}) == b"A full immutable observation"
    with pytest.raises(FileNotFoundError):
        runtime.handle(h, path, {"through": ["1"]})
    with pytest.raises(FileNotFoundError):
        runtime.handle(h, path.replace("study/", "study~1/"), {})


def test_untrusted_result_cannot_grant_blob_access(api):
    j, h, blob = api
    private = j.blob("Not in this run")
    j.append("study", "a", "experiment.finished", {"result": {"storage_key": private["storage_key"]}}, experiment_id="e")
    with pytest.raises(FileNotFoundError):
        runtime.handle(h, f"study/blob/{private['storage_key']}", {})


def test_terminal_unavailable_without_registration_never_invokes_tmux(api, monkeypatch):
    j, h, _ = api
    monkeypatch.setattr(runtime.subprocess, "run", lambda *a, **k: pytest.fail("Unexpected terminal capture"))
    assert runtime.handle(h, "study/terminal", {})["available"] is False


def test_terminal_capture_is_exact_scoped_read_only_argv(api, monkeypatch):
    j, h, _ = api
    import os
    pid = os.getpid()
    calls = []
    def invoke(args, **kw):
        calls.append(args)
        return SimpleNamespace(stdout=str(pid) if "display-message" in args else "hello\n\x1b[31mworld")
    monkeypatch.setattr(runtime.subprocess, "run", invoke)
    runtime.register_terminal(j, "study", "a", socket="/tmp/owned-tmux", pane="%12")
    assert runtime.handle(h, "study/terminal", {})["text"] == "hello\nworld"
    assert calls[-1] == ["tmux", "-S", "/tmp/owned-tmux", "capture-pane", "-p", "-t", "%12", "-S", "-120", "-E", "-"]
    assert all("send-keys" not in c for c in calls)


def test_reconciliation_requires_process_identity_and_ignores_heartbeat_delay(api, monkeypatch):
    j, h, _ = api
    import os
    j.append("study", "b", "attempt.started", {"pid": os.getpid(), "process_identity": process_identity()})
    runtime.reconcile(j, "study")
    assert j.snapshot("study")["runs"]["study"]["lifecycle"] == "running"
    monkeypatch.setattr(runtime, "process_identity", lambda *_: "different-boot-or-start")
    runtime.reconcile(j, "study")
    assert j.snapshot("study")["runs"]["study"]["lifecycle"] == "failed"
    j.append("study", "c", "attempt.started", {})
    with pytest.raises(ValueError, match="attempt changed"):
        j.append("study", "b", "lifecycle", {"lifecycle": "failed"}, producer="supervisor")


def test_new_run_discovery_before_first_legacy_trace(api, monkeypatch):
    j, _, _ = api
    monkeypatch.setattr(data, "_fork_index", lambda: {})
    monkeypatch.setattr(data, "_job_for_run", lambda *_: None)
    rows = data.investigations(include_all=True, project="alpha")
    assert rows[0]["goal"] == "Original question" and rows[0]["runtime"]
    assert not data.investigations(include_all=True, project="beta")


def test_cross_namespace_worker_is_not_falsely_declared_dead(api):
    j, _, _ = api
    j.append("study", "b", "attempt.started", {"pid": 1, "process_identity": "boot|another-namespace|1|10"})
    runtime.reconcile(j, "study")
    assert j.snapshot("study")["runs"]["study"]["lifecycle"] == "running"


def test_host_executed_code_is_scoped_and_replay_bound(api):
    j,h,_=api
    code=j.blob("print('resolved host code')")
    j.append('study','a','experiment.started',{'status':'running','code':code,'execution_backend':'host'},experiment_id='host')
    path=f"study/blob/{code['storage_key']}"
    assert runtime.handle(h,path,{})==b"print('resolved host code')"
    with pytest.raises(FileNotFoundError):runtime.handle(h,path,{'through':['2']})
    with pytest.raises(FileNotFoundError):runtime.handle(h,path.replace('study/','study~1/'),{})
