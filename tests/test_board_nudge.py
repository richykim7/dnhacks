"""Durable mention delivery, transport ambiguity, and private-socket regression coverage."""
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import board_inbox as storage
import board_nudge as nudge
import board_nudge_service as service
import tmux_input as guard


@pytest.fixture
def inbox(tmp_path):
    return storage.Inbox(tmp_path / "inbox.sqlite3")


@pytest.fixture
def config():
    return {"repo": "fixture/repository", "issue": 1,
            "routes": {"test/agent": {"kind": "inbox"}}}


def comment(number, text="@test/agent review this"):
    return {"id": number, "body": text, "created_at": "2026-09-06T08:00:00Z",
            "html_url": f"https://example.invalid/{number}", "user": {"login": "fixture"}}


def rows(inbox):
    return [dict(row) for row in inbox.db.execute("SELECT * FROM deliveries ORDER BY key")]


def test_cursor_and_all_mentions_survive_restart_and_same_timestamp_replay(tmp_path, config):
    path = tmp_path / "inbox.sqlite3"
    inbox = storage.Inbox(path)
    nudge.collect(inbox, config, [comment(2), comment(1, "@test/agent @test/agent second")])
    assert len(rows(inbox)) == 2
    assert inbox.get("cursor:fixture/repository:1")["id"] == 2
    inbox.db.close()
    reopened = storage.Inbox(path)
    nudge.collect(reopened, config, [comment(1), comment(2), comment(3)])
    nudge.deliver(reopened, config)
    assert len(rows(reopened)) == 3
    assert all(row["status"] == "delivered" for row in rows(reopened))
    assert reopened.get("cursor:fixture/repository:1")["id"] == 3


def test_every_fetch_overlaps_strict_after_boundary_across_restart(tmp_path, config, monkeypatch):
    config["start_since"] = "2026-09-06T07:59:00Z"
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config))
    state_path = tmp_path / "state.sqlite3"
    args = ["--config", str(config_path), "--state", str(state_path), "--once",
            "--lock", str(tmp_path / "owned.lock"), "--cursor", str(tmp_path / "no-legacy.json")]
    available, boundaries = [comment(1)], []
    def strict_after(repo, issue, since):
        boundaries.append(since)
        return [c for c in available if nudge.board.parse_ts(c["created_at"]) > nudge.board.parse_ts(since)]
    monkeypatch.setattr(nudge.board, "fetch_comments", strict_after)
    monkeypatch.setattr(nudge, "mirror_running", lambda: False)
    assert nudge.main(args) == 0
    available.append(comment(2))  # Arrives later, but GitHub reports the same second.
    assert nudge.main(args) == 0
    assert nudge.main(args) == 0
    assert boundaries == ["2026-09-06T07:58:58Z", "2026-09-06T07:59:58Z", "2026-09-06T07:59:58Z"]
    reopened = storage.Inbox(state_path)
    assert [r["comment_id"] for r in rows(reopened)] == [1, 2]
    assert all(r["status"] == "delivered" for r in rows(reopened))
    assert reopened.get("cursor:fixture/repository:1")["id"] == 2


def test_cursor_does_not_advance_when_pending_transaction_fails(inbox, config, monkeypatch):
    original = inbox.put
    def broken(key, number, *args):
        if number == 2:
            raise RuntimeError("simulated disk failure")
        original(key, number, *args)
    monkeypatch.setattr(inbox, "put", broken)
    with pytest.raises(RuntimeError):
        nudge.collect(inbox, config, [comment(1), comment(2)])
    assert rows(inbox) == []
    assert inbox.get("cursor:fixture/repository:1") is None


def test_first_start_requires_explicit_history_choice_and_restart_preserves_it(inbox, config, tmp_path):
    legacy = tmp_path / "no-legacy.json"
    with pytest.raises(ValueError, match="explicit start_since"):
        nudge.initialize(inbox, config, legacy)
    assert inbox.get("cursor:fixture/repository:1") is None
    config["start_since"] = "2026-09-05T10:00:00+02:00"
    config["bootstrap_note"] = "Replay from the reviewed window"
    nudge.initialize(inbox, config, legacy)
    assert inbox.get("cursor:fixture/repository:1")["since"] == "2026-09-05T08:00:00Z"
    nudge.initialize(inbox, config, legacy, bootstrap_now=True)
    assert inbox.get("cursor:fixture/repository:1")["since"] == "2026-09-05T08:00:00Z"
    assert inbox.get("bootstrap")["reason"] == "Replay from the reviewed window"


def test_legacy_cursor_import_and_corruption_are_explicit(inbox, config, tmp_path):
    legacy = tmp_path / "legacy.json"
    legacy.write_text("{broken")
    with pytest.raises(ValueError):
        nudge.initialize(inbox, config, legacy)
    legacy.write_text(json.dumps({"id": 34, "since": "2026-09-05T08:00:00Z"}))
    nudge.initialize(inbox, config, legacy)
    assert inbox.get("cursor:fixture/repository:1")["id"] == 34
    assert legacy.exists()


def test_missing_or_similarly_named_route_never_gets_input(inbox, config):
    nudge.collect(inbox, config, [comment(1, "@test-agent @unknown/agent"), comment(2)])
    assert [row["comment_id"] for row in rows(inbox)] == [2]
    config["routes"] = {}
    nudge.deliver(inbox, config)
    assert rows(inbox)[0]["status"] == "pending"


def test_self_mentions_and_control_characters(inbox, config):
    body = '<!-- board {"agent":"test/agent"} -->\n@test/agent no echo'
    nudge.collect(inbox, config, [comment(1, body)])
    assert rows(inbox) == []
    text = nudge.nudge_text({"agent": "fixture", "text": "test\x1b[31m\rline\x00"})
    assert "\x1b" not in text and "\r" not in text and "\x00" not in text
    assert "Reply only if" in text


def test_busy_routes_are_never_dropped(inbox, config, monkeypatch):
    config["routes"]["test/agent"] = {"kind": "tmux", "socket": "/tmp/private-fixture", "session": "owned"}
    nudge.collect(inbox, config, [comment(1)])
    monkeypatch.setattr(nudge, "tmux", lambda *args: SimpleNamespace(returncode=0, stdout="codex\n"))
    monkeypatch.setattr(nudge, "session_idle", lambda *_: False)
    monkeypatch.setattr(nudge, "nudge", lambda *_: pytest.fail("must not send to busy pane"))
    for _ in range(25):
        nudge.deliver(inbox, config)
    assert rows(inbox)[0]["status"] == "pending"
    assert rows(inbox)[0]["attempts"] == 0


def test_tmux_guard_failure_is_not_reported_as_delivered(monkeypatch):
    calls = []
    def send(*args, **kwargs):
        calls.append((args, kwargs))
        return False
    monkeypatch.setattr(nudge, "send_board_message", send)
    monkeypatch.setattr(nudge, "TMUX_SOCKET", "/tmp/explicit-private-fixture.sock")
    assert not nudge.nudge("owned", "literal $() text", False)
    assert calls == [(("owned", "literal $() text"), {"socket": "/tmp/explicit-private-fixture.sock"})]


def test_literal_text_followed_by_failed_enter_remains_failure(tmp_path, monkeypatch):
    before = guard.Screen("%1", 123, True, False, False, 2, 0, 100, 30, "›\n")
    after = guard.Screen("%1", 123, True, False, False, 14, 0, 100, 30, "› Board notice\n")
    screens, commands = iter([before, before, after, after]), []
    class Client:
        socket = str(tmp_path / "fixture.sock")
        def screen(self, target):
            return next(screens)
        def run(self, *args):
            commands.append(args)
        def key(self, pane, key):
            commands.append((pane, key))
            raise subprocess.CalledProcessError(1, "tmux")
    monkeypatch.setattr(guard, "Tmux", lambda socket=None: Client())
    monkeypatch.setattr(guard, "state_dir", lambda: tmp_path)
    assert not guard.send_board_message("owned", "Board notice", socket=Client.socket)
    assert commands == [("send-keys", "-t", "%1", "-l", "--", "Board notice"), ("%1", "Enter")]


@pytest.mark.parametrize("failure", [subprocess.TimeoutExpired("codex", 20), FileNotFoundError()])
def test_ambiguous_transport_is_retained_and_never_automatically_retried(inbox, config, monkeypatch, failure):
    config["routes"]["test/agent"] = {"kind": "codex", "thread": "fixture-thread"}
    nudge.collect(inbox, config, [comment(1)])
    calls = []
    def fail(*args, **kwargs):
        calls.append(args)
        raise failure
    monkeypatch.setattr(nudge.board, "run_command", fail)
    nudge.deliver(inbox, config)
    nudge.deliver(inbox, config)
    assert len(calls) == 1
    assert rows(inbox)[0]["status"] == "uncertain"


def test_restart_reconciles_inflight_send_without_losing_or_duplicating_it(inbox, config):
    nudge.collect(inbox, config, [comment(1), comment(2)])
    inbox.mark(rows(inbox)[0]["key"], "sending")
    assert inbox.recover() == 1
    nudge.deliver(inbox, config)
    assert [row["status"] for row in rows(inbox)] == ["uncertain", "delivered"]
    assert inbox.recover() == 0


def test_codex_acceptance_receipt_and_duplicate_suppression(inbox, config, monkeypatch):
    config["routes"]["test/agent"] = {"kind": "codex", "thread": "exact-thread"}
    nudge.collect(inbox, config, [comment(1)])
    calls = []
    def queued(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout="Queued message fixture for thread exact-thread.", stderr="")
    monkeypatch.setattr(nudge.board, "run_command", queued)
    nudge.deliver(inbox, config)
    nudge.collect(inbox, config, [comment(1)])
    nudge.deliver(inbox, config)
    assert len(calls) == 1
    assert calls[0][1:4] == ["queue", "--thread", "exact-thread"]
    assert rows(inbox)[0]["receipt"].startswith("Queued message fixture")


@pytest.mark.parametrize("state,draft,thread,expected", [
    ("working", "› Ask Codex to do anything", "exact-thread", True),
    ("idle", "›", "exact-thread", True),
    ("blocked", "›", "exact-thread", False),
    ("working", "› My unfinished draft", "exact-thread", False),
    ("idle", "›", "another-thread", False),
    ("working", "› 1. Retry with a faster model", "exact-thread", False),
])
def test_herdr_routes_exact_live_thread_and_preserves_blocked_or_draft_input(
        inbox, config, monkeypatch, state, draft, thread, expected):
    config["routes"]["test/agent"] = {"kind": "herdr", "pane": "w1:p1", "thread": "exact-thread",
                                       "terminal_id": "term_fixture", "pid": 123, "process_start_ticks": 456}
    nudge.collect(inbox, config, [comment(1)])
    calls = []
    agent = {"agent": "codex", "pane_id": "w1:p1", "terminal_id": "term_fixture", "agent_session": {"value": thread},
             "agent_status": state, "revision": 5}
    def command(args, **kwargs):
        calls.append(args)
        if args[2] == "process-info":
            text = json.dumps({"result": {"process_info": {"pane_id": "w1:p1",
                "foreground_processes": [{"pid": 123, "name": "codex"}]}}})
        elif args[2] == "read":
            text = "Working (esc to interrupt)\n\n" + draft
        else:
            text = json.dumps({"result": {"type": "agent_prompted" if args[2] == "prompt" else "agent_info", "agent": agent}})
        return SimpleNamespace(returncode=0, stdout=text, stderr="")
    monkeypatch.setattr(nudge.board, "run_command", command)
    monkeypatch.setattr(nudge, "process_start_ticks", lambda pid: 456)
    nudge.deliver(inbox, config)
    prompted = [args for args in calls if args[2] == "prompt"]
    assert bool(prompted) == expected
    assert rows(inbox)[0]["status"] == ("delivered" if expected else "pending")
    if expected:
        assert prompted[0][3] == "w1:p1"
        assert json.loads(rows(inbox)[0]["receipt"])["thread"] == "exact-thread"


@pytest.mark.parametrize("change", ["pid", "start_time", "terminal", "receipt_thread"])
def test_herdr_replacement_fails_closed(inbox, config, monkeypatch, change):
    route = {"kind": "herdr", "pane": "w1:p1", "thread": "exact-thread", "terminal_id": "term_fixture",
             "pid": 123, "process_start_ticks": 456}
    config["routes"]["test/agent"] = route
    nudge.collect(inbox, config, [comment(1)])
    prompted = []
    def command(args, **kwargs):
        if args[2] == "read":
            return SimpleNamespace(returncode=0, stdout="›", stderr="")
        if args[2] == "process-info":
            result = {"process_info": {"pane_id": "w1:p1", "foreground_processes": [
                {"pid": 124 if change == "pid" else 123, "name": "codex"}]}}
        else:
            is_prompt = args[2] == "prompt"
            if is_prompt:
                prompted.append(args)
            result = {"type": "agent_prompted" if is_prompt else "agent_info", "agent": {
                "agent": "codex", "pane_id": "w1:p1", "agent_status": "working", "revision": 5,
                "terminal_id": "term_replacement" if change == "terminal" else "term_fixture",
                "agent_session": {"value": "replacement-thread" if is_prompt and change == "receipt_thread" else "exact-thread"}}}
        return SimpleNamespace(returncode=0, stdout=json.dumps({"result": result}), stderr="")
    monkeypatch.setattr(nudge.board, "run_command", command)
    monkeypatch.setattr(nudge, "process_start_ticks", lambda pid: 457 if change == "start_time" else 456)
    nudge.deliver(inbox, config)
    nudge.deliver(inbox, config)
    assert len(prompted) == (1 if change == "receipt_thread" else 0)
    assert rows(inbox)[0]["status"] == ("uncertain" if change == "receipt_thread" else "pending")


def test_dry_run_does_not_mutate_cursor_or_delivery_state(tmp_path, config):
    path = tmp_path / "state.sqlite3"
    real = storage.Inbox(path)
    nudge.collect(real, config, [comment(1)])
    dry = storage.Inbox(path, dry=True)
    nudge.collect(dry, config, [comment(2)])
    nudge.deliver(dry, config, dry=True)
    assert len(rows(real)) == 1
    assert rows(real)[0]["status"] == "pending"
    assert real.get("cursor:fixture/repository:1")["id"] == 1


def test_machine_lock_rejects_second_process(tmp_path):
    path = tmp_path / "machine.lock"
    handle = nudge.acquire_lock(path)
    with pytest.raises(SystemExit, match="Another local nudger"):
        nudge.acquire_lock(path)
    handle.close()
    nudge.acquire_lock(path).close()


def test_source_config_and_dependency_changes_alter_release_fingerprint(tmp_path, config, monkeypatch):
    source = tmp_path / "source"
    (source / "scripts").mkdir(parents=True)
    for name in service.FILES:
        (source / "scripts" / name).write_text("# fixture\n")
    dependency = tmp_path / "gh"
    dependency.write_text("first dependency")
    monkeypatch.setattr(service.shutil, "which", lambda name, **kwargs: str(dependency) if name == "gh" else None)
    monkeypatch.setattr(service, "run", lambda *args, **kwargs: SimpleNamespace(stdout="version 1"))
    first = service.fingerprint(source, config)[0]
    (source / "scripts" / "board.py").write_text("# changed source\n")
    second = service.fingerprint(source, config)[0]
    config["interval"] = 45
    third = service.fingerprint(source, config)[0]
    dependency.write_text("updated dependency")
    fourth = service.fingerprint(source, config)[0]
    assert len({first, second, third, fourth}) == 4


def test_actual_private_socket_literal_enter_and_restart(tmp_path):
    evidence = service.transport_self_test(tmp_path / "transport.json")
    assert evidence["literal_text_and_enter"] == "passed"
    assert evidence["restart_and_replay"] == "one delivery"
    assert "ACK" in evidence["captured_ack"]
    assert not Path(evidence["private_socket"]).exists()
