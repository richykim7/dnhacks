"""Regression coverage for mirror stalls and failed-send cursor handling."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
spec = importlib.util.spec_from_file_location('board_mirror', SCRIPTS / 'board_mirror.py')
mirror = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mirror)


def test_timeout_kills_descendant_holding_output_pipes(tmp_path):
    marker = tmp_path / 'child-survived'
    child = f"import time; from pathlib import Path; time.sleep(1); Path({str(marker)!r}).touch()"
    parent = f"import subprocess, sys, time; subprocess.Popen([sys.executable, '-c', {child!r}]); time.sleep(60)"
    started = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        mirror.board.run_command([sys.executable, '-c', parent], timeout=0.2)
    assert time.monotonic() - started < 2
    time.sleep(1)
    assert not marker.exists()
    assert mirror.board.run_command([sys.executable, '-c', "print('next call')"]).stdout == 'next call\n'


@pytest.mark.parametrize('failure', [subprocess.TimeoutExpired('fleetctl', 5), FileNotFoundError()])
def test_unavailable_helpers_do_not_raise_or_report_success(monkeypatch, failure):
    def fail(*args, **kwargs):
        raise failure
    monkeypatch.setattr(mirror.board, 'run_command', fail)
    monkeypatch.setattr(mirror, 'FLEETCTL', Path(sys.executable))
    assert mirror.live_sessions() == {}
    assert not mirror.session_idle('session')
    assert not mirror.nudge('session', 'hello', False)
    assert not mirror.tg_send('chat', 'hello', False)


class StopLoop(Exception):
    pass


def run_mirror(monkeypatch, tmp_path, comments, send, nudge):
    monkeypatch.setattr(sys, 'argv', ['board_mirror', '--to', 'test-chat'])
    monkeypatch.setattr(mirror.threading.Thread, 'start', lambda self: None)
    monkeypatch.setattr(mirror.board, 'owner_repo', lambda: 'owner/repo')
    monkeypatch.setattr(mirror.board, 'find_issue', lambda repo: 1)
    monkeypatch.setattr(mirror.board, 'cache_dir', lambda: tmp_path)
    monkeypatch.setattr(mirror.board, 'fetch_comments', lambda *args: comments)
    monkeypatch.setattr(mirror.board, 'parse_comment', lambda c: c['parsed'])
    monkeypatch.setattr(mirror, 'tg_send', send)
    monkeypatch.setattr(mirror, 'live_sessions', lambda: {'worker': 'worker'})
    monkeypatch.setattr(mirror, 'session_idle', lambda name: True)
    monkeypatch.setattr(mirror, 'nudge', nudge)
    polls = []
    def sleep(_):
        polls.append(1)
        if len(polls) == 2:
            raise StopLoop
    monkeypatch.setattr(mirror.time, 'sleep', sleep)
    with pytest.raises(StopLoop):
        mirror.main()
    return json.loads((tmp_path / 'mirror-board-owner__repo-1.json').read_text())


def comment(n):
    return {'id': n, 'created_at': f'2026-09-05T23:47:0{n}Z',
            'parsed': {'agent': 'sender', 'kind': 'update', 'text': f'@worker message {n}', 'url': 'test'}}


def test_failed_send_retries_before_advancing_cursor(monkeypatch, tmp_path):
    attempts = []
    def send(chat, text, dry):
        attempts.append(text)
        return len(attempts) > 1
    cursor = run_mirror(monkeypatch, tmp_path, [comment(1), comment(2)], send, lambda *args: True)
    assert len(attempts) == 3
    assert attempts[0] == attempts[1]
    assert cursor['id'] == 2


def test_failed_nudge_does_not_stop_next_poll(monkeypatch, tmp_path, capsys):
    attempts = []
    nudges = []
    def send(*args):
        attempts.append(args)
        return True
    def nudge(*args):
        nudges.append(args)
        return False
    cursor = run_mirror(monkeypatch, tmp_path, [comment(1)], send, nudge)
    assert cursor['id'] == 1
    assert len(attempts) == len(nudges) == 1
    output = capsys.readouterr().out
    assert 'dropped failed nudge' in output
    assert 'nudged worker' not in output
