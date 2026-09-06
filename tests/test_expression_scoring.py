"""Exercise receipt-only commands and actual private scoring through the agent path."""
import asyncio
import base64
from contextlib import contextmanager
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import urllib.error
import urllib.request

import numpy as np
import pytest

from dnhacksbio.expression_experiment import submit
from dnhacksbio.expression_scoring import Store, make_server
from dnhacksbio.explorer import skills


@contextmanager
def serving(store):
    server = make_server(store, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.fixture
def experiment(tmp_path):
    pytest.importorskip("torch")
    from dnhacksbio.expr_encoder import fit_pca
    rng = np.random.default_rng(301)
    genes = ["g1", "g2", "g3"]
    model = tmp_path / "model.npz"
    fit_pca(np.exp(rng.normal(size=(16, 3))), genes=genes, units=[f"train-{i}" for i in range(16)],
            source="synthetic fixture", sampling="independent simulated donors",
            unit_namespace="fixture", components=2).save(model)
    path = tmp_path / "experiment.npz"
    np.savez_compressed(path, Xa=np.exp(rng.normal(size=(48, 3))), Xb=np.exp(rng.normal(size=(48, 3))),
                        genes=genes, unit_a=[f"a-{i}" for i in range(48)], unit_b=[f"b-{i}" for i in range(48)])
    spec = tmp_path / "experiment.json"
    spec.write_text(json.dumps({"hypothesis": "Synthetic integration fixture; no biological claim",
        "source": "synthetic independent observations", "assumptions": "independent simulated donors",
        "unit_namespace": "fixture", "input_scale": "TPM"}))
    store = Store(tmp_path / "private")
    store.configure(model, {"seed": 0, "batch_pairs": 8, "max_epochs": 2})
    return store, path, spec


def payload(path, spec, receipt="trial-1"):
    return {"request_id": receipt, "input": base64.b64encode(path.read_bytes()).decode(),
            "spec": json.loads(spec.read_text())}


def test_agent_guide_is_self_contained_and_has_no_scoring_instructions(monkeypatch):
    monkeypatch.setattr(skills, "REFERENCE_PATHS", ())
    snap = skills.snapshot("expression-experiment")
    assert len(snap["files"]) == 1
    assert "python -m dnhacksbio.expression_experiment" in snap["content"]
    assert all(term not in snap["content"].lower() for term in ("e_value", "e-value", "learned_two_sample", "wealth"))
    assert skills.get_skill("learned-evalue") is None
    assert "e_value" not in skills.get_skill("experimental-rigor")
    assert "e_value" not in skills.get_skill("depmap_dependency")


def test_durable_receipt_is_identical_before_after_scoring_and_restart(experiment):
    store, path, spec = experiment
    request = payload(path, spec)
    before = store.enqueue(request)
    restarted = Store(store.directory)
    assert restarted.enqueue(request) == before
    assert restarted.process_one(timeout=60)
    assert not restarted.process_one()
    with restarted.connect() as con:
        status, value = con.execute("SELECT status,result FROM jobs").fetchone()
    result = json.loads(value)
    assert status == "completed" and result["status"] == "ok"
    assert result["e_value"] >= 0 and result["metadata"]["training_updates"]
    assert restarted.enqueue(request) == before == {"receipt": "trial-1", "status": "accepted"}
    altered = payload(path, spec)
    altered["spec"]["hypothesis"] = "changed"
    with pytest.raises(ValueError, match="Conflicting"):
        restarted.enqueue(altered)
    with restarted.connect() as con:
        assert con.execute("SELECT count(*) FROM jobs").fetchone()[0] == 1


def test_private_failure_and_unavailable_return_same_receipt(experiment):
    store, path, spec = experiment
    with np.load(path, allow_pickle=False) as data:
        arrays = dict(data)
    arrays["Xa"][0, 0] = float("nan")
    np.savez_compressed(path, **arrays)
    with serving(store) as endpoint:
        receipt = submit(path, spec, "invalid-data", endpoint=endpoint)
        assert store.process_one(timeout=60)
        assert submit(path, spec, "invalid-data", endpoint=endpoint) == receipt
        for suffix in ("/experiments/invalid-data", "/results", "/status", "/scoring.sqlite3"):
            with pytest.raises(urllib.error.HTTPError) as exc:
                urllib.request.urlopen(endpoint + suffix)
            assert exc.value.code == 404
    with store.connect() as con:
        assert con.execute("SELECT status,result FROM jobs").fetchone() == ("failed", None)
    arrays["Xa"] = np.ones((4, 3))
    arrays["unit_a"] = np.array([f"small-{i}" for i in range(4)])
    np.savez_compressed(path, **arrays)
    receipt = store.enqueue(payload(path, spec, "small"))
    assert store.process_one(timeout=60)
    with store.connect() as con:
        result = json.loads(con.execute("SELECT result FROM jobs WHERE receipt='small'").fetchone()[0])
    assert result["status"] == "unavailable" and result["e_value"] is None
    assert store.enqueue(payload(path, spec, "small")) == receipt


def test_client_never_reads_or_relays_service_body(experiment, monkeypatch):
    _, path, spec = experiment
    class Response:
        status = 202
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def read(self, *_): raise AssertionError("client must never read response body")
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: Response())
    assert submit(path, spec, "receipt") == {"receipt": "receipt", "status": "accepted"}
    def failing(*a, **k):
        raise RuntimeError("private e_value=123456.789")
    monkeypatch.setattr(urllib.request, "urlopen", failing)
    with pytest.raises(RuntimeError) as exc:
        submit(path, spec, "receipt")
    assert "123456" not in str(exc.value) and "e_value" not in str(exc.value)


def test_worker_timeout_stays_private(experiment, monkeypatch):
    store, path, spec = experiment
    request = payload(path, spec)
    receipt = store.enqueue(request)
    def timeout(*a, **kw):
        raise subprocess.TimeoutExpired("worker", 1)
    monkeypatch.setattr(subprocess, "run", timeout)
    assert store.process_one(timeout=1)
    with store.connect() as con:
        assert con.execute("SELECT status,error FROM jobs").fetchone() == ("failed", "worker_timeout")
    assert store.enqueue(request) == receipt


def test_explorer_runs_command_without_receiving_background_results(experiment, tmp_path, monkeypatch):
    from dnhacksbio.explorer.explorer import Explorer
    from dnhacksbio.explorer import embed
    from dnhacksbio.explorer.sandbox import RunResult
    store, path, spec = experiment
    actions = iter([
        {"intent": "Load expression command", "action": "get_skill", "args": {"name": "expression-experiment"}},
        {"intent": "Submit declared expression experiment", "action": "run_experiments", "args": {}},
        {"intent": "Continue after receipt", "action": "done", "args": {}},
    ])
    prompts = []
    with serving(store) as endpoint:
        command = [sys.executable, "-m", "dnhacksbio.expression_experiment", "--input", str(path),
                   "--spec", str(spec), "--request-id", "agent-trial"]
        code = f"import subprocess\nsubprocess.run({command!r}, check=True)"
        async def complete(prompt):
            prompts.append(prompt)
            action = next(actions)
            if action["action"] == "run_experiments":
                action["args"] = {"experiments": [{"method_id": "expression-experiment",
                    "hypothesis": "Synthetic distribution comparison", "code": code}]}
            return json.dumps(action)
        def native_runner(codes):
            results = []
            for source in codes:
                proc = subprocess.run([sys.executable, "-c", source], capture_output=True, text=True, timeout=60,
                    env=os.environ | {"DNHACKS_EXPRESSION_ENDPOINT": endpoint})
                results.append(RunResult(proc.returncode == 0, proc.returncode, proc.stdout, proc.stderr, 0, False))
            # Complete actual scoring BEFORE the next model request, so the test catches dataflow leaks.
            assert store.process_one(timeout=60)
            return results
        monkeypatch.setattr(embed, "embed_one", lambda *_: None)
        ex = Explorer("receipt-test", "Submit an expression comparison", db_path=tmp_path / "kg.duckdb",
                      trace_dir=str(tmp_path / "agent"), complete_fn=complete, sandbox_run=native_runner)
        monkeypatch.setattr(ex, "_state", lambda: "Synthetic integration fixture")
        try:
            asyncio.run(ex.run(3))
            events = ex.journal.events("receipt-test")
            assert not any(e["kind"] == "policy.rejected" for e in events)
            event = next(e for e in events if e["kind"] == "experiment.finished")
            assert event["payload"]["status"] == "completed" and event["payload"]["result"] is None
            with store.connect() as con:
                result = json.loads(con.execute("SELECT result FROM jobs").fetchone()[0])
            assert result["status"] == "ok" and result["metadata"]["scored_pairs"] == 32
            agent_files = [p.read_text(errors="replace") for p in (tmp_path / "agent").rglob("*") if p.is_file()]
            visible = "\n".join(prompts + agent_files) + json.dumps(ex.log.frontier())
            assert "agent-trial" in visible and "accepted" in visible
            for secret in (str(result["e_value"]), "log_wealth_path", "training_updates", str(store.directory)):
                assert secret not in visible
        finally:
            ex.close()


def test_service_process_scores_in_background_and_recovers_interrupted_job(experiment, tmp_path):
    import signal
    import socket
    import time
    _, path, spec = experiment
    private = tmp_path / "live-service"
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    endpoint = f"http://127.0.0.1:{port}"
    command = [sys.executable, "-m", "dnhacksbio.expression_scoring", "serve", "--state", str(private),
               "--encoder", str(tmp_path / "model.npz"), "--port", str(port)]
    for restart in (False, True):
        if restart:
            with Store(private).connect() as con:
                con.execute("UPDATE jobs SET status='running', result=NULL")
        proc = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            deadline = time.monotonic() + 40
            while True:
                assert proc.poll() is None, "service exited unexpectedly"
                try:
                    receipt = submit(path, spec, "live-trial", endpoint=endpoint)
                    break
                except RuntimeError:
                    assert time.monotonic() < deadline, "service did not accept submission"
                    time.sleep(0.05)
            assert receipt == {"receipt": "live-trial", "status": "accepted"}
            store = Store(private)
            while True:
                with store.connect() as con:
                    status, result = con.execute("SELECT status,result FROM jobs WHERE receipt='live-trial'").fetchone()
                if status == "completed":
                    assert json.loads(result)["status"] == "ok"
                    break
                assert status != "failed" and time.monotonic() < deadline
                time.sleep(0.05)
            assert submit(path, spec, "live-trial", endpoint=endpoint) == receipt
            with store.connect() as con:
                assert con.execute("SELECT count(*) FROM jobs").fetchone()[0] == 1
        finally:
            proc.send_signal(signal.SIGINT)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


def test_settings_are_frozen_and_worker_rejects_modified_encoder(experiment):
    store, path, spec = experiment
    with store.connect() as con:
        config = json.loads(con.execute("SELECT config FROM settings").fetchone()[0])
    model = Path(config["encoder"])
    with pytest.raises(ValueError, match="Settings are frozen"):
        store.configure(model, {"seed": 1})
    request = payload(path, spec)
    store.enqueue(request)
    model.write_bytes(b"modified")
    assert store.process_one(timeout=60)
    with store.connect() as con:
        assert con.execute("SELECT status,error FROM jobs").fetchone() == ("failed", "ValueError")
