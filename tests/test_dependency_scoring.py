import copy
import hashlib
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import urllib.error
import urllib.request

import pytest

from dnhacksbio.dependency_experiment import submit, validate_payload
from dnhacksbio.dependency_scoring import Store, digest, validate_registration, make_server


@pytest.fixture
def registration():
    rows = [{"unit_id": f"u{i}", "model_id": f"m{i}", "disease": "PDAC", "block_id": "library-1",
             "event_status": "deleted" if i < 8 else "intact", "target_effect": -1 if i < 8 else 0}
            for i in range(16)]
    return {"protocol": {"schema_version": 1, "method": "dependency-chronos-v1", "protocol_id": "frozen",
        "hypothesis": "Synthetic deletion dependency fixture", "family_id": "synthetic", "target": "PRMT5",
        "event_gene": "MTAP", "event": "curated_deletion", "disease": "PDAC", "direction": "stronger_in_deleted",
        "statistic": "block_size_weighted_mean_difference", "min_group": 8, "uninformative_blocks": "exclude",
        "permutations": 9999, "exact_limit": 100000, "seed": 0,
        "exchangeability_justification": "Synthetic uniformly assigned labels",
        "chronos_invariance_audit": "Synthetic scores; no shared fitting",
        "block_justification": "Single simulated library", "eligibility": "Sixteen simulated donors",
        "power_assessment": "Synthetic test fixture, not a biological power justification",
        "exchangeability_supported": True},
        "manifest": {"schema_version": 1, "cohort_id": "synthetic-cohort",
            "sources": [{"url": "https://example.org/synthetic", "release": "synthetic-v1",
                         "sha256": "a" * 64, "scale": "simulated Chronos"}],
            "annotation_scale": "curated_deleted_intact_unknown", "annotation_definition": "Simulated deletion labels",
            "target": "PRMT5", "biological_unit_mapping": {r["model_id"]: r["unit_id"] for r in rows},
            "discovery_units": [], "exposure": "operator-held-confirmation",
            "release_overlap_audit": "Synthetic distinct units; no previous releases", "table_sha256": digest(rows)},
        "rows": rows}


def payload(registration, request_id="trial"):
    return {"request_id": request_id, "spec": {k: registration["protocol"][k] for k in
            ("schema_version", "method", "protocol_id", "hypothesis", "family_id")},
            "input": {"cohort_id": registration["manifest"]["cohort_id"],
                      "manifest_sha256": digest(registration["manifest"])}}


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


def private_result(store):
    with store.connect() as con:
        status, result, error = con.execute("SELECT status,result,error FROM jobs ORDER BY rowid DESC LIMIT 1").fetchone()
    assert status == "completed", error
    return json.loads(result)


def test_concurrent_renamed_retries_one_result_restart_and_immutable_settings(tmp_path, registration):
    store = Store(tmp_path / "private")
    store.configure(registration)
    with ThreadPoolExecutor(max_workers=8) as pool:
        receipts = list(pool.map(lambda i: store.enqueue(payload(registration, f"trial-{i % 4}")), range(16)))
    assert all(r["status"] == "accepted" for r in receipts)
    restarted = Store(store.directory)
    assert restarted.process_one()
    assert not restarted.process_one()
    result = private_result(restarted)
    assert result["status"] == "ok" and result["e_value"] > 0
    with restarted.connect() as con:
        assert con.execute("SELECT count(*) FROM jobs").fetchone()[0] == 1
        assert con.execute("SELECT count(*) FROM aliases").fetchone()[0] == 4
    assert restarted.enqueue(payload(registration, "trial-0")) == receipts[0]
    changed = payload(registration, "trial-0")
    changed["spec"]["hypothesis"] = "altered"
    with pytest.raises(ValueError, match="Conflicting"):
        restarted.enqueue(changed)
    with restarted.connect() as con:
        assert con.execute("SELECT outcome FROM submissions ORDER BY id DESC LIMIT 1").fetchone()[0] == "conflicting_retry"
        assert con.execute("SELECT count(*) FROM submissions").fetchone()[0] == 18
    altered = copy.deepcopy(registration)
    altered["protocol"]["seed"] = 1
    with pytest.raises(ValueError, match="frozen"):
        restarted.configure(altered)


@pytest.mark.parametrize("change,reason", [("hash", "registration_mismatch"), ("hypothesis", "registration_mismatch"),
    ("exchangeability", "exchangeability_unsupported"), ("overlap", "discovery_confirmation_overlap"),
    ("development", "development_data"), ("small", "insufficient_independent_units")])
def test_private_unavailable_is_not_public_feedback(tmp_path, registration, change, reason):
    if change == "exchangeability": registration["protocol"]["exchangeability_supported"] = False
    if change == "overlap": registration["manifest"]["discovery_units"] = ["u0"]
    if change == "development": registration["manifest"]["exposure"] = "development"
    if change == "small":
        registration["rows"][0]["event_status"] = "unknown"
        registration["manifest"]["table_sha256"] = digest(registration["rows"])
    store = Store(tmp_path / "private")
    store.configure(registration)
    request = payload(registration)
    if change == "hash": request["input"]["manifest_sha256"] = "0" * 64
    if change == "hypothesis": request["spec"]["hypothesis"] = "changed declaration"
    before = store.enqueue(request)
    assert store.process_one()
    result = private_result(store)
    assert result["status"] == "unavailable" and result["reason"] == reason and result["e_value"] is None
    assert store.enqueue(request) == before == {"receipt": "trial", "status": "accepted"}


def test_alias_hash_and_schema_validation(registration):
    validate_registration(registration)
    wrong = copy.deepcopy(registration)
    wrong["rows"][0]["target_effect"] = 2
    with pytest.raises(ValueError, match="hash"):
        validate_registration(wrong)
    wrong = copy.deepcopy(registration)
    wrong["manifest"]["biological_unit_mapping"]["m1"] = "u0"
    wrong["rows"][1]["unit_id"] = "u0"
    wrong["manifest"]["table_sha256"] = digest(wrong["rows"])
    with pytest.raises(ValueError, match="Shared donor"):
        validate_registration(wrong)
    request = payload(registration)
    for container, key, value in [(request, "p", 0.01), (request["spec"], "code", "print(1)"),
                                   (request["input"], "path", "/private")]:
        container[key] = value
        with pytest.raises(ValueError): validate_payload(request)
        del container[key]


def test_http_cli_lost_ack_and_no_numeric_output(tmp_path, registration, monkeypatch):
    store = Store(tmp_path / "private")
    store.configure(registration)
    request = payload(registration)
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({k: request[k] for k in ("spec", "input")}))
    with serving(store) as endpoint:
        # Lost acknowledgement: server already committed; retry must return same receipt.
        store.enqueue(request)
        assert submit(spec, "trial", endpoint=endpoint) == {"receipt": "trial", "status": "accepted"}
        assert store.process_one()
        proc = subprocess.run([sys.executable, "-m", "dnhacksbio.dependency_experiment", "--spec", str(spec),
                               "--request-id", "trial"], env=os.environ | {"DNHACKS_DEPENDENCY_ENDPOINT": endpoint},
                              capture_output=True, text=True, check=True)
        assert json.loads(proc.stdout) == {"receipt": "trial", "status": "accepted"} and proc.stderr == ""
        for route in ("/results", "/status", "/experiments/trial", "/scoring.sqlite3"):
            with pytest.raises(urllib.error.HTTPError) as err: urllib.request.urlopen(endpoint + route)
            assert err.value.code == 404
    secret = "private result 12345.67"
    def fail(*a, **k): raise RuntimeError(secret)
    monkeypatch.setattr(urllib.request, "urlopen", fail)
    with pytest.raises(RuntimeError) as err: submit(spec, "trial")
    assert secret not in str(err.value)


def test_surviving_worker_lock_and_restart_do_not_rescore(tmp_path, registration):
    import fcntl
    store = Store(tmp_path / "private")
    store.configure(registration)
    store.enqueue(payload(registration))
    with store.connect() as con: con.execute("UPDATE jobs SET status='running'")
    # Recovered job waits behind the previous child; a completed result wins after lock acquisition.
    with (store.directory / ("job-" + hashlib.sha256(b"trial").hexdigest() + ".lock")).open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        child = subprocess.Popen([sys.executable, "-m", "dnhacksbio.dependency_scoring", "score-one", "--state",
                                  str(store.directory), "--receipt", "trial"], stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
        with store.connect() as con:
            con.execute("UPDATE jobs SET status='completed', result=?", ('{"sentinel": true}',))
    assert child.wait(timeout=10) == 0
    assert private_result(store) == {"sentinel": True}


def test_explorer_dependency_receipt_has_no_result_leak(registration, tmp_path, monkeypatch):
    from dnhacksbio.explorer.explorer import Explorer
    from dnhacksbio.explorer import embed
    from dnhacksbio.explorer.sandbox import RunResult
    import asyncio
    from dnhacksbio.explorer import skills
    store = Store(tmp_path / "private")
    store.configure(registration)
    spec = tmp_path / "submission.json"
    request = payload(registration)
    spec.write_text(json.dumps({k: request[k] for k in ("spec", "input")}))
    actions = iter([
        {"intent": "Load expression command", "action": "get_skill", "args": {"name": "dependency-experiment"}},
        {"intent": "Submit declared expression experiment", "action": "run_experiments", "args": {}},
        {"intent": "Continue after receipt", "action": "done", "args": {}},
    ])
    prompts = []
    with serving(store) as endpoint:
        command = [sys.executable, "-m", "dnhacksbio.dependency_experiment",
                   "--spec", str(spec), "--request-id", "agent-trial"]
        code = f"import subprocess\nsubprocess.run({command!r}, check=True)"
        async def complete(prompt):
            prompts.append(prompt)
            action = next(actions)
            if action["action"] == "run_experiments":
                action["args"] = {"experiments": [{"method_id": "dependency-experiment",
                    "hypothesis": "Synthetic distribution comparison", "code": code}]}
            return json.dumps(action)
        def native_runner(codes):
            results = []
            for source in codes:
                proc = subprocess.run([sys.executable, "-c", source], capture_output=True, text=True, timeout=60,
                    env=os.environ | {"DNHACKS_DEPENDENCY_ENDPOINT": endpoint})
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
            assert result["status"] == "ok" and result["counts"]["deleted"] == 8
            agent_files = [p.read_text(errors="replace") for p in (tmp_path / "agent").rglob("*") if p.is_file()]
            visible = "\n".join(prompts + agent_files) + json.dumps(ex.log.frontier())
            assert "agent-trial" in visible and "accepted" in visible
            for secret in (str(result["e_value"]), "p_value", "e_value", "canonical_experiment_key", str(store.directory)):
                assert secret not in visible
        finally:
            ex.close()



def test_live_dependency_service_recovers_interrupted_job(registration, tmp_path):
    import signal
    import socket
    import time
    registration_path = tmp_path / "registration.json"
    registration_path.write_text(json.dumps(registration))
    spec = tmp_path / "submission.json"
    request = payload(registration)
    spec.write_text(json.dumps({k: request[k] for k in ("spec", "input")}))
    private = tmp_path / "live-service"
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    endpoint = f"http://127.0.0.1:{port}"
    command = [sys.executable, "-m", "dnhacksbio.dependency_scoring", "serve", "--state", str(private),
               "--registration", str(registration_path), "--port", str(port)]
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
                    receipt = submit(spec, "live-trial", endpoint=endpoint)
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
            assert submit(spec, "live-trial", endpoint=endpoint) == receipt
            with store.connect() as con:
                assert con.execute("SELECT count(*) FROM jobs").fetchone()[0] == 1
        finally:
            proc.send_signal(signal.SIGINT)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()



def test_legacy_queue_adoption_export_and_conflicting_audit(tmp_path, registration):
    store = Store(tmp_path / "private")
    store.configure(registration)
    store.enqueue(payload(registration, "original"))
    assert store.process_one()
    with store.connect() as con:
        con.execute("DELETE FROM identities")
        con.execute("DELETE FROM aliases")
    store.enqueue(payload(registration, "renamed"))
    assert not store.process_one()
    conflict = payload(registration, "original")
    conflict["input"]["manifest_sha256"] = "b" * 64
    with pytest.raises(ValueError, match="Conflicting"):
        store.enqueue(conflict)
    output = tmp_path / "export.json"
    proc = subprocess.run([sys.executable, "-m", "dnhacksbio.dependency_scoring", "export", "--state",
                           str(store.directory), "--output", str(output)], capture_output=True, text=True, check=True)
    assert proc.stdout == proc.stderr == ""
    exported = json.loads(output.read_text())
    assert len(exported["jobs"]) == 1 and len(exported["attempts"]) == 2
    assert exported["submissions"][-1]["outcome"] == "conflicting_retry"
    assert json.loads(exported["submissions"][-1]["payload"]) == conflict
    assert output.stat().st_mode & 0o777 == 0o600


def test_worker_timeout_and_exception_stay_private(tmp_path, registration, monkeypatch):
    store = Store(tmp_path / "private")
    store.configure(registration)
    request = payload(registration)
    receipt = store.enqueue(request)
    def timeout(*a, **k): raise subprocess.TimeoutExpired("private-worker", 1)
    monkeypatch.setattr(subprocess, "run", timeout)
    assert store.process_one(timeout=1)
    with store.connect() as con:
        assert con.execute("SELECT status,error FROM jobs").fetchone() == ("failed", "worker_timeout")
    assert store.enqueue(request) == receipt
