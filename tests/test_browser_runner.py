"""OS-level checks for browser queuing, failure propagation and process cleanup."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/browser_tests.py"
spec = importlib.util.spec_from_file_location("browser_tests", SCRIPT)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def test_browser_slot_queues_and_releases_on_exception(tmp_path):
    marker = tmp_path / "entered"
    lock_path = tmp_path / "queue.lock"
    code = f"""
import sys
from pathlib import Path
sys.path.insert(0, {str(SCRIPT.parent)!r})
from browser_tests import browser_slot
with browser_slot({str(lock_path)!r}):
    Path({str(marker)!r}).touch()
"""
    process = None
    try:
        with pytest.raises(ValueError), runner.browser_slot(lock_path):
            process = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
            assert "Waiting for another browser run" in process.stdout.readline()
            assert not marker.exists()
            raise ValueError("simulated failed run")
        assert process.wait(timeout=5) == 0
        assert marker.exists()
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait()


def test_failed_server_does_not_attach_to_stale_ready_file(tmp_path):
    ready = tmp_path / "ready.json"
    ready.write_text(json.dumps({"url": "http://127.0.0.1:5174"}))
    process = subprocess.Popen([sys.executable, "-c", "raise SystemExit(7)"])
    process.wait()
    with pytest.raises(RuntimeError, match="Server exited \\(7\\)"):
        runner.wait_ready(process, ready)


def test_startup_timeout_and_owned_process_cleanup(tmp_path):
    # A grandchild inherits the process group; a test runner can exit before Chromium.
    marker = tmp_path / "child.json"
    code = f"""
import subprocess, sys, json
from pathlib import Path
p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
Path({str(marker)!r}).write_text(json.dumps(p.pid))
p.wait()
"""
    process = subprocess.Popen([sys.executable, "-c", code], start_new_session=True)
    try:
        deadline = time.monotonic() + 5
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert marker.exists()
        child = json.loads(marker.read_text())
        with pytest.raises(RuntimeError, match="startup timed out"):
            runner.wait_ready(process, tmp_path / "absent", timeout=0.01)
    finally:
        runner.stop(process)
    assert process.poll() is not None
    # On Linux an orphan may briefly be a zombie pending init's reap, but cannot run.
    status = Path(f"/proc/{child}/stat")
    deadline = time.monotonic() + 5
    while True:
        try:
            state = status.read_text().split()[2]
        except (FileNotFoundError, ProcessLookupError):
            break  # The process was reaped, including during the read.
        if state == "Z":
            break
        assert time.monotonic() < deadline, f"Owned child remained live: {state}"
        time.sleep(0.02)


def test_private_backend_does_not_inherit_source_root_state(tmp_path,monkeypatch):
    from dnhacksbio.webui import data,projects,jobs
    from dnhacksbio.explorer.runtime import Journal
    # Restore every module binding after checking the actual backend reader.
    for module,keys in [(data,['ROOT','PROCESSED','CORPORA','WORKING_KG','MASTER_KG','PROMOTION_DECISIONS_PATH','_CACHE']),
                        (projects,['ROOT','PROJECTS','CORPORA']),(jobs,['ROOT'])]:
        for key in keys:monkeypatch.setattr(module,key,getattr(module,key))
    populated=tmp_path/'operator-state';journal=Journal(populated)
    journal.register('existing-research','Private existing experiment',project='operator')
    monkeypatch.setattr(data,'PROCESSED',populated)
    assert data.list_runs(include_all=True)
    isolated=tmp_path/'isolated';runner.configure_backend(isolated)
    assert data.list_runs(include_all=True)==[]
    assert data.PROCESSED.is_relative_to(isolated) and data.WORKING_KG.is_relative_to(isolated)
    assert projects.PROJECTS.is_relative_to(isolated) and jobs.ROOT==isolated
    assert len(journal.manifests())==1
