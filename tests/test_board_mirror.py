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
    monkeypatch.setattr(mirror, 'send_board_message', lambda *args, **kwargs: False)
    monkeypatch.setattr(mirror, 'FLEETCTL', Path(sys.executable))
    assert mirror.live_sessions() == {}
    assert not mirror.session_idle('session')
    assert not mirror.nudge('session', 'hello', False)
    assert not mirror.tg_send('chat', 'hello', False)


class StopLoop(Exception):
    pass


def run_mirror(monkeypatch, tmp_path, comments, send, nudge, *, idle=True, polls_count=2, sessions=None, dry=False):
    monkeypatch.setattr(sys, 'argv', ['board_mirror', '--to', 'test-chat'] + (['--dry-run'] if dry else []))
    monkeypatch.setattr(mirror.threading.Thread, 'start', lambda self: None)
    monkeypatch.setattr(mirror.board, 'owner_repo', lambda: 'owner/repo')
    monkeypatch.setattr(mirror.board, 'find_issue', lambda repo: 1)
    monkeypatch.setattr(mirror.board, 'cache_dir', lambda: tmp_path)
    monkeypatch.setattr(mirror.board, 'fetch_comments', lambda *args: comments)
    monkeypatch.setattr(mirror.board, 'parse_comment', lambda c: c['parsed'])
    monkeypatch.setattr(mirror, 'tg_send', send)
    monkeypatch.setattr(mirror, 'live_sessions', lambda: {'worker': 'worker'} if sessions is None else sessions)
    monkeypatch.setattr(mirror, 'session_idle', lambda name: idle)
    monkeypatch.setattr(mirror, 'nudge', nudge)
    polls = []
    def sleep(_):
        polls.append(1)
        if len(polls) == polls_count:
            raise StopLoop
    monkeypatch.setattr(mirror.time, 'sleep', sleep)
    with pytest.raises(StopLoop):
        mirror.main()
    db = mirror.Inbox(tmp_path / 'mirror-board-owner__repo-1.sqlite3', dry=True)
    return db.get('cursor')


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
    assert len(attempts) == 1
    assert len(nudges) == 2  # A deferred menu is retried, not silently lost.
    output = capsys.readouterr().out
    assert 'dropped' not in output
    assert 'nudged worker' not in output


def records(tmp_path):
    db = mirror.Inbox(tmp_path / 'mirror-board-owner__repo-1.sqlite3', dry=True)
    return [dict(row) for row in db.db.execute('SELECT * FROM deliveries ORDER BY key')]


def test_busy_survives_25_polls_and_restart_without_resending_telegram(monkeypatch, tmp_path):
    sends, nudges = [], []
    send = lambda *args: sends.append(args) or True
    nudge = lambda *args: nudges.append(args) or True
    run_mirror(monkeypatch, tmp_path, [comment(1)], send, nudge, idle=False, polls_count=25)
    assert records(tmp_path)[0]['status'] == 'pending'
    assert not nudges
    run_mirror(monkeypatch, tmp_path, [comment(1)], send, nudge)
    assert len(sends) == len(nudges) == 1
    assert records(tmp_path)[0]['status'] == 'delivered'
    run_mirror(monkeypatch, tmp_path, [comment(1)], send, nudge)
    assert len(nudges) == 1


def test_absent_route_is_retained_until_session_returns(monkeypatch, tmp_path):
    run_mirror(monkeypatch, tmp_path, [comment(1)], lambda *a: True, lambda *a: True, sessions={})
    assert records(tmp_path)[0]['status'] == 'pending'
    run_mirror(monkeypatch, tmp_path, [], lambda *a: True, lambda *a: True)
    assert records(tmp_path)[0]['status'] == 'delivered'


def test_two_comments_each_retained_repeated_mention_deduplicated(monkeypatch, tmp_path):
    first = comment(1)
    first['parsed']['text'] += ' @worker'
    run_mirror(monkeypatch, tmp_path, [first, comment(2)], lambda *a: True, lambda *a: True, idle=False)
    assert [r['comment_id'] for r in records(tmp_path)] == [1, 2]


def test_interrupted_transport_becomes_uncertain_without_automatic_retry(monkeypatch, tmp_path):
    def crash(session, text, dry, before_send):
        before_send()
        raise StopLoop
    run_mirror(monkeypatch, tmp_path, [comment(1)], lambda *a: True, crash)
    assert records(tmp_path)[0]['status'] == 'sending'
    nudges = []
    run_mirror(monkeypatch, tmp_path, [], lambda *a: True, lambda *a: nudges.append(a))
    assert records(tmp_path)[0]['status'] == 'uncertain'
    assert not nudges


def test_partial_send_failure_retained_as_uncertain(monkeypatch, tmp_path):
    def fail(session, text, dry, before_send):
        before_send()
        return False
    run_mirror(monkeypatch, tmp_path, [comment(1)], lambda *a: True, fail)
    row = records(tmp_path)[0]
    assert row['status'] == 'uncertain'
    assert row['attempts'] == 1


def test_imports_legacy_cursor_and_dry_run_does_not_mutate(monkeypatch, tmp_path):
    legacy = tmp_path / 'mirror-board-owner__repo-1.json'
    legacy.write_text(json.dumps({'id': 1, 'since': comment(1)['created_at']}))
    run_mirror(monkeypatch, tmp_path, [comment(1), comment(2)], lambda *a: True, lambda *a: True, dry=True)
    assert not (tmp_path / 'mirror-board-owner__repo-1.sqlite3').exists()
    assert not (tmp_path / 'mirror-inbox-test-chat.json').exists()
    nudges = []
    run_mirror(monkeypatch, tmp_path, [comment(1), comment(2)], lambda *a: True, lambda *a: nudges.append(a) or True)
    assert [r['comment_id'] for r in records(tmp_path)] == [2]
    assert len(nudges) == 1


def test_enqueue_failure_rolls_back_cursor_and_other_recipients(monkeypatch, tmp_path):
    original = mirror.Inbox.put
    def fail(self, *args):
        original(self, *args)
        raise StopLoop
    monkeypatch.setattr(mirror.Inbox, 'put', fail)
    cursor = run_mirror(monkeypatch, tmp_path, [comment(1)], lambda *a: True, lambda *a: True)
    assert cursor['id'] == 0
    assert records(tmp_path) == []
