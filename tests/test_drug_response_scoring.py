"""Receipt-only HTTP/runtime path and private worker replay using synthetic data."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from copy import deepcopy
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

import pytest

from dnhacksbio.drug_response_experiment import submit
from dnhacksbio.drug_response_scoring import Store
from dnhacksbio.experiment_transport import make_server
from test_drug_response import cohort, protocol


@pytest.fixture
def experiment(tmp_path):
    manifest = {"protocol_id": "p1", "hypothesis_id": "h1", "family_id": "f1", "cohort_id": "c1",
                "protocol": protocol(), "cohort": cohort()}
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    store = Store(tmp_path / "private")
    registration = store.configure(path)
    spec = tmp_path / "registration.json"
    spec.write_text(json.dumps(registration))
    return store, spec, path


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


def payload(spec, request_id="trial-1"):
    return {"request_id": request_id, **json.loads(spec.read_text())}


def test_concurrent_renamed_retries_one_durable_result(experiment):
    store, spec, _ = experiment
    with ThreadPoolExecutor(max_workers=8) as pool:
        replies = list(pool.map(lambda i: store.enqueue(payload(spec, f"retry-{i % 4}")), range(16)))
    assert all(set(r) == {"receipt", "status"} and r["status"] == "accepted" for r in replies)
    with store.connect() as con:
        assert con.execute("SELECT count(*) FROM jobs").fetchone()[0] == 1
        assert con.execute("SELECT count(*) FROM aliases").fetchone()[0] == 4
    assert store.process_one(timeout=30)
    assert not store.process_one()
    restarted = Store(store.directory)
    assert restarted.enqueue(payload(spec, "retry-0")) == {"receipt": "retry-0", "status": "accepted"}
    with store.connect() as con:
        row = con.execute("SELECT status,result FROM jobs").fetchone()
    assert row[0] == "completed"
    assert json.loads(row[1])["p"] == pytest.approx(1 / 3)


def test_http_no_results_and_acknowledgement_loss(experiment):
    store, spec, _ = experiment
    # Simulate a durable acceptance whose reply never reached the client.
    store.enqueue(payload(spec))
    with serving(store) as endpoint:
        before = submit(spec, "trial-1", endpoint=endpoint)
        assert store.process_one(timeout=30)
        assert submit(spec, "trial-1", endpoint=endpoint) == before
        for route in ("/results", "/status", "/experiments/trial-1", "/"):
            with pytest.raises(urllib.error.HTTPError) as exc:
                urllib.request.urlopen(endpoint + route)
            assert exc.value.code == 404
            assert json.loads(exc.value.read()) == {"error": "not found"}
        request = payload(spec)
        request["spec"]["hypothesis_id"] = "changed"
        req = urllib.request.Request(endpoint + "/experiments", json.dumps(request).encode(), method="POST")
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(req)
        assert json.loads(exc.value.read()) == {"error": "submission not accepted"}


@pytest.mark.parametrize("change", [
    lambda r: r.update(p=.001),
    lambda r: r["spec"].update(method="bliss"),
    lambda r: r["input"].update(manifest_sha256="0" * 64),
    lambda r: r["input"].update(cohort_id="renamed"),
    lambda r: r.update(input="arbitrary-upload"),
    lambda r: r["spec"].update(executable="/bin/true"),
])
def test_unregistered_requests_rejected(experiment, change):
    store, spec, _ = experiment
    request = payload(spec)
    change(request)
    with pytest.raises(ValueError):
        store.enqueue(request)
    with store.connect() as con:
        assert con.execute("SELECT count(*) FROM jobs").fetchone()[0] == 0
        assert con.execute("SELECT outcome FROM submissions").fetchone()[0] == "rejected_validation"


def test_registry_is_copied_frozen_and_export_private(experiment, tmp_path):
    store, spec, path = experiment
    original = store.registration()
    m = json.loads(path.read_text())
    m["protocol"]["seed"] += 1
    path.write_text(json.dumps(m))
    assert store.registration() == original
    with pytest.raises(ValueError, match="frozen"):
        store.configure(path)
    store.enqueue(payload(spec))
    assert store.process_one(timeout=30)
    output = tmp_path / "export.json"
    store.export(output)
    assert output.stat().st_mode & 0o777 == 0o600
    result = json.loads(output.read_text())
    assert result["attempts"][0]["outcome"] == "accepted"
    assert result["jobs"][0]["result"]["prepared"]["unit_ids"] == ["d000", "d001", "d002"]
    with pytest.raises(FileExistsError):
        store.export(output)


def test_altered_private_registry_and_software_fail_closed(experiment):
    store, spec, _ = experiment
    store.enqueue(payload(spec))
    with store.connect() as con:
        settings = json.loads(con.execute("SELECT config FROM settings").fetchone()[0])
        settings["worker_sha256"] = "0" * 64
        con.execute("UPDATE settings SET config=?", (json.dumps(settings),))
    assert store.process_one(timeout=30)
    with store.connect() as con:
        assert con.execute("SELECT status,result,error FROM jobs").fetchone() == ("failed", None, "ValueError")
    assert store.enqueue(payload(spec))["status"] == "accepted"
    with store.connect() as con:
        settings["manifest"]["cohort"]["rows"][0]["viability"] = .22
        con.execute("UPDATE settings SET config=?", (json.dumps(settings),))
    with pytest.raises(ValueError, match="integrity"):
        store.registration()


def test_worker_timeout_is_private(experiment, monkeypatch):
    store, spec, _ = experiment
    request = payload(spec)
    receipt = store.enqueue(request)
    def timeout(*args, **kwargs):
        assert kwargs["stdout"] == kwargs["stderr"] == subprocess.DEVNULL
        raise subprocess.TimeoutExpired("private", 1)
    monkeypatch.setattr(subprocess, "run", timeout)
    assert store.process_one(timeout=1)
    with store.connect() as con:
        assert con.execute("SELECT status,error FROM jobs").fetchone() == ("failed", "worker_timeout")
    assert store.enqueue(request) == receipt


def test_service_recovers_running_job_and_holds_worker_lock(experiment):
    store, spec, _ = experiment
    store.enqueue(payload(spec))
    with store.connect() as con:
        con.execute("UPDATE jobs SET status='running'")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    command = [sys.executable, "-m", "dnhacksbio.drug_response_scoring", "serve",
               "--state", str(store.directory), "--port", str(port)]
    proc = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            with store.connect() as con:
                status = con.execute("SELECT status FROM jobs").fetchone()[0]
            if status == "completed":
                break
            assert proc.poll() is None
            time.sleep(.05)
        assert status == "completed"
        duplicate = subprocess.run(command, capture_output=True, timeout=5)
        assert duplicate.returncode != 0
        assert submit(spec, "trial-1", endpoint=f"http://127.0.0.1:{port}")["status"] == "accepted"
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_explorer_receives_receipt_without_private_feedback(experiment, tmp_path, monkeypatch):
    from dnhacksbio.explorer.explorer import Explorer
    from dnhacksbio.explorer import embed
    from dnhacksbio.explorer.sandbox import RunResult
    store, spec, _ = experiment
    actions = iter([
        {"intent": "Load command", "action": "get_skill", "args": {"name": "drug-response-experiment"}},
        {"intent": "Submit frozen experiment", "action": "run_experiments", "args": {}},
        {"intent": "Continue after receipt", "action": "done", "args": {}},
    ])
    prompts = []
    with serving(store) as endpoint:
        command = [sys.executable, "-m", "dnhacksbio.drug_response_experiment", "--spec", str(spec),
                   "--request-id", "agent-trial"]
        code = f"import subprocess\nsubprocess.run({command!r}, check=True)"
        async def complete(prompt):
            prompts.append(prompt)
            action = next(actions)
            if action["action"] == "run_experiments":
                action["args"] = {"experiments": [{"method_id": "drug-response-experiment",
                    "hypothesis": "Synthetic association", "code": code}]}
            return json.dumps(action)
        def native_runner(codes):
            results = []
            for source in codes:
                proc = subprocess.run([sys.executable, "-c", source], capture_output=True, text=True, timeout=30,
                    env=os.environ | {"DNHACKS_DRUG_RESPONSE_ENDPOINT": endpoint})
                results.append(RunResult(proc.returncode == 0, proc.returncode, proc.stdout, proc.stderr, 0, False))
            assert store.process_one(timeout=30)
            return results
        monkeypatch.setattr(embed, "embed_one", lambda *_: None)
        ex = Explorer("drug-receipt", "Submit registered experiment", db_path=tmp_path / "kg.duckdb",
                      trace_dir=str(tmp_path / "agent"), complete_fn=complete, sandbox_run=native_runner)
        monkeypatch.setattr(ex, "_state", lambda: "Synthetic integration fixture")
        try:
            asyncio.run(ex.run(3))
            events = ex.journal.events("drug-receipt")
            assert not any(e["kind"] == "policy.rejected" for e in events)
            event = next(e for e in events if e["kind"] == "experiment.finished")
            assert event["payload"]["status"] == "completed" and event["payload"]["result"] is None
            with store.connect() as con:
                assert con.execute("SELECT status FROM jobs").fetchone()[0] == "completed"
            files = [p.read_text(errors="replace") for p in (tmp_path / "agent").rglob("*") if p.is_file()]
            visible = "\n".join(prompts + files) + json.dumps(ex.log.frontier())
            assert "agent-trial" in visible and "accepted" in visible
            for secret in ("inhibition_area", "extreme", "d000", str(store.directory)):
                assert secret not in visible
        finally:
            ex.close()


def test_client_rejects_forged_or_numerical_acknowledgements(experiment, monkeypatch):
    _, spec, _ = experiment
    class Response:
        status = 202
        def __enter__(self):
            return self
        def __exit__(self, *_):
            pass
        def read(self, _):
            return b'{"receipt":"trial-1","status":"accepted","e":999,"private":"secret"}'
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: Response())
    with pytest.raises(RuntimeError) as exc:
        submit(spec, "trial-1", endpoint="http://localhost")
    assert "999" not in str(exc.value) and "secret" not in str(exc.value)


def test_runtime_change_fails_privately(experiment):
    store, spec, _ = experiment
    store.enqueue(payload(spec))
    with store.connect() as con:
        settings = json.loads(con.execute("SELECT config FROM settings").fetchone()[0])
        settings["runtime"]["numpy"] = "changed"
        con.execute("UPDATE settings SET config=?", (json.dumps(settings),))
    assert store.process_one(timeout=30)
    with store.connect() as con:
        assert con.execute("SELECT status,result FROM jobs").fetchone() == ("failed", None)


def test_pinned_pharmacogx_raw_adapter_when_available(tmp_path):
    import shutil
    rscript = shutil.which("Rscript")
    if rscript is None:
        pytest.skip("Rscript unavailable; optional PharmacoGx adapter not executed")
    setup = subprocess.run([rscript, "--vanilla", "-e",
        'if (!requireNamespace("PharmacoGx",quietly=TRUE) || '
        'as.character(packageVersion("PharmacoGx")) != "3.16.0") quit(status=31); '
        'data("CCLEsmall",package="PharmacoGx"); saveRDS(CCLEsmall,commandArgs(TRUE)[1])',
        str(tmp_path / "source.rds")], capture_output=True, timeout=60)
    if setup.returncode == 31:
        pytest.skip("PharmacoGx 3.16.0 unavailable")
    assert setup.returncode == 0, setup.stderr.decode()
    adapter = Path(__file__).resolve().parents[1] / "scripts/r/prepare_pharmacogx.R"
    output = tmp_path / "prepared"
    proc = subprocess.run([rscript, "--vanilla", str(adapter), str(tmp_path / "source.rds"), str(output)],
                          capture_output=True, timeout=60)
    assert proc.returncode == 0, proc.stderr.decode()
    assert "viability_source_scale" in (output / "raw_points.csv").read_text()
    assert "3.16.0" in (output / "provenance.txt").read_text()


def test_operator_registration_and_export_cli(experiment, tmp_path):
    _, _, manifest = experiment
    state, spec, output = tmp_path / "cli-private", tmp_path / "cli-spec.json", tmp_path / "cli-export.json"
    command = [sys.executable, "-m", "dnhacksbio.drug_response_scoring"]
    proc = subprocess.run(command + ["register", "--manifest", str(manifest), "--state", str(state),
                                    "--output", str(spec)], capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0 and not proc.stdout
    assert set(json.loads(spec.read_text())) == {"spec", "input"}
    store = Store(state)
    store.enqueue(payload(spec))
    assert store.process_one(timeout=30)
    proc = subprocess.run(command + ["export", "--state", str(state), "--output", str(output)],
                          capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0 and not proc.stdout
    assert json.loads(output.read_text())["jobs"][0]["status"] == "completed"
