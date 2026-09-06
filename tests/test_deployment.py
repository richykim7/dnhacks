import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import threading
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer

import pytest
from dnhacksbio.webui.deployment import Busy, lease

spec = importlib.util.spec_from_file_location('deploy_cli', Path(__file__).parents[1] / 'scripts/deploy.py')
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)


def test_deploy_excludes_launches(tmp_path):
    p = tmp_path / 'lease'
    with lease(exclusive=True, path=p):
        with pytest.raises(Busy):
            with lease(path=p):
                pytest.fail('launch was allowed')


def test_active_request_excludes_deploy(tmp_path):
    p = tmp_path / 'lease'
    with lease(path=p):
        with pytest.raises(Busy):
            with lease(exclusive=True, path=p):
                pytest.fail('deployment was allowed')


def test_child_keeps_lease_after_parent_closes(tmp_path):
    p = tmp_path / 'lease'
    with lease(path=p) as fd:
        child = subprocess.Popen([sys.executable, '-c', 'import sys; sys.stdin.read()'],
                                 stdin=subprocess.PIPE, pass_fds=(fd,), start_new_session=True)
    try:
        with pytest.raises(Busy):
            with lease(exclusive=True, path=p):
                pytest.fail('active detached job lost its lease')
    finally:
        child.communicate(timeout=5)
    with lease(exclusive=True, path=p):
        pass


def test_activity_refuses_uncertain_record(tmp_path):
    jobs = tmp_path / 'data/projects/p/jobs'
    jobs.mkdir(parents=True)
    (jobs / 'a.json').write_text('{"status":"running"}')
    proc = tmp_path / 'proc'
    proc.mkdir()
    with pytest.raises(Busy):
        deploy.activity(tmp_path / 'data', proc)
    (jobs / 'a.json').write_text('broken')
    with pytest.raises(ValueError):
        deploy.activity(tmp_path / 'data', proc)


def test_standalone_ingestion_blocks(tmp_path):
    p = tmp_path / 'proc/123'
    p.mkdir(parents=True)
    (p / 'cmdline').write_bytes(b'python\0/scripts/ingest_frozen_corpus.py\0')
    with pytest.raises(Busy):
        deploy.activity(tmp_path / 'data', p.parent)


def test_paused_or_unstarted_journal_blocks(tmp_path):
    from dnhacksbio.explorer.runtime import Journal
    data = tmp_path / 'data'
    proc = tmp_path / 'proc'
    proc.mkdir()
    journal = Journal(data / 'processed')
    journal.register('research', 'A research question')
    with pytest.raises(Busy):
        deploy.activity(data, proc)
    journal.append('research', 'a', 'lifecycle', {'lifecycle': 'awaiting_parent'})
    with pytest.raises(Busy):
        deploy.activity(data, proc)
    journal.append('research', 'a', 'lifecycle', {'lifecycle': 'completed'})
    deploy.activity(data, proc)


def test_failed_release_rolls_back(tmp_path):
    old, new = tmp_path / 'old', tmp_path / 'new'
    old.mkdir(); new.mkdir()
    current = tmp_path / 'current'
    current.symlink_to(old)
    restarts = []
    def check(sha):
        if sha == 'new':
            raise RuntimeError('broken build')
    with pytest.raises(RuntimeError):
        deploy.activate(new, current, lambda: restarts.append(current.resolve()), check)
    assert current.resolve() == old
    assert restarts == [new, old]


def test_http_mutations_rejected_during_switch(tmp_path, monkeypatch):
    from dnhacksbio.webui.server import Handler
    lock = tmp_path / 'lease'
    monkeypatch.setenv('DNHACKS_DEPLOY_LOCK', str(lock))
    called = []
    monkeypatch.setattr(Handler, '_post', lambda self: (called.append(True), self._send_json({'ok': True})))
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f'http://127.0.0.1:{server.server_port}/api/projects/example/run'
    try:
        with lease(exclusive=True, path=lock):
            with pytest.raises(urllib.error.HTTPError) as exc:
                urllib.request.urlopen(urllib.request.Request(url, data=b'{}'), timeout=2)
            assert exc.value.code == 503
            assert not called
        with urllib.request.urlopen(urllib.request.Request(url, data=b'{}'), timeout=2) as r:
            assert r.status == 200
        assert called == [True]
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
