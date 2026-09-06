#!/usr/bin/env python3
"""Deliver Board mentions through explicit local routes and a durable inbox.

Install one managed instance with board_nudge_service.py. No route is inferred from a
similar session name. Busy/offline targets remain pending across restarts; ambiguous
sends remain visible for reconciliation instead of risking duplicate agent input.
See docs/board-nudger.md. Do not run alongside the Telegram mirror.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import subprocess
import sys
import time
from datetime import timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import board  # noqa: E402
from board_inbox import Inbox, stamp, state_home  # noqa: E402
from tmux_input import Tmux, menu_or_busy, send_board_message  # noqa: E402

MENTION_RE = re.compile(r"@([A-Za-z0-9_./-]+)")
# Pane text that means "still working". Both TUIs print "esc to interrupt" next to a live spinner;
# a finished one reads "Crunched for 5m · done 5:02 PM" and must NOT count as busy.
BUSY_RE = re.compile(r"esc to interrupt|ctrl\+c to interrupt", re.I)
TMUX_SOCKET: str | None = None


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def sanitize(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "-", name)


def tmux(*args: str) -> subprocess.CompletedProcess:
    if not TMUX_SOCKET:
        raise RuntimeError("tmux routes require an explicit socket")
    return board.run_command(["tmux", "-S", TMUX_SOCKET, *args], timeout=5)


def live_sessions() -> dict[str, str]:
    p = tmux("list-sessions", "-F", "#{session_name}")
    if p.returncode != 0:
        return {}
    return {sanitize(n): n for n in p.stdout.split() if n}


def pane_text(session: str) -> str | None:
    p = tmux("capture-pane", "-p", "-t", "=" + session + ":", "-S", "-40")
    return p.stdout if p.returncode == 0 else None


def session_idle(session: str) -> bool:
    """Heuristic: no busy marker, and the pane text has not changed for two seconds."""
    try:
        screen = Tmux(TMUX_SOCKET).screen("=" + session + ":")
        lines = screen.text.splitlines()
        if (menu_or_busy(screen) or screen.y >= len(lines) or screen.x != 2
                or lines[screen.y].strip() not in ("›", "❯", "› Ask Codex to do anything")):
            return False
    except (OSError, ValueError, subprocess.SubprocessError):
        return False
    a = pane_text(session)
    if a is None or BUSY_RE.search(a):
        return False
    time.sleep(2)
    b = pane_text(session)
    return b is not None and b == a and not BUSY_RE.search(b)


def nudge(session: str, text: str, dry: bool) -> bool:
    if dry:
        log("DRY nudge ->", session, "|", text[:140])
        return True
    if not TMUX_SOCKET:
        raise RuntimeError("tmux routes require an explicit socket")
    return send_board_message(session, text, socket=TMUX_SOCKET)


def nudge_text(p: dict) -> str:
    first = (p.get("text") or "").strip().splitlines()[0][:200] if (p.get("text") or "").strip() else ""
    text = (f"Board: {p['agent']} mentioned you: \"{first}\" "
            "Run `python3 scripts/board.py show`. Reply only if an answer or action is needed.")
    return "".join(c for c in text if ord(c) >= 32 and ord(c) != 127)


def load_config(path: Path) -> dict:
    config = json.loads(path.read_text())
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", config.get("repo", "")):
        raise ValueError("config requires owner/repo")
    if not isinstance(config.get("issue"), int) or config["issue"] < 1:
        raise ValueError("config requires a positive Board issue number")
    if not config.get("routes"):
        raise ValueError("No explicit recipient routes configured; refusing inferred delivery")
    for name, route in config["routes"].items():
        if not re.fullmatch(r"[A-Za-z0-9_./-]+", name):
            raise ValueError("Invalid exact Board recipient")
        if route.get("kind") == "tmux":
            if not Path(route.get("socket", "")).is_absolute() or not route.get("session"):
                raise ValueError("tmux route requires absolute socket and exact session")
        elif route.get("kind") in ("codex", "herdr"):
            if not re.fullmatch(r"[0-9a-f-]{36}", route.get("thread", "")):
                raise ValueError("Codex route requires the exact thread UUID")
            if route["kind"] == "herdr":
                if not re.fullmatch(r"w[A-Za-z0-9]+:p[A-Za-z0-9]+", route.get("pane", "")):
                    raise ValueError("Herdr route requires the exact pane ID")
                if (not re.fullmatch(r"term_[A-Za-z0-9]+", route.get("terminal_id", ""))
                        or not isinstance(route.get("pid"), int) or route["pid"] < 1
                        or not isinstance(route.get("process_start_ticks"), int) or route["process_start_ticks"] < 1):
                    raise ValueError("Herdr route requires pinned terminal_id, pid and process_start_ticks")
        elif route.get("kind") != "inbox":
            raise ValueError("Route kind must be tmux, codex, herdr or inbox")
    return config


def acquire_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        raise SystemExit("Another local nudger holds the machine lock")
    return handle


def mirror_running() -> bool:
    # Read argv only, never process environments or credentials. Do not stop the mirror.
    for path in Path("/proc").glob("[0-9]*/cmdline"):
        try:
            parts = path.read_bytes().split(b"\0")
            if any(Path(os.fsdecode(p)).name == "board_mirror.py" for p in parts[:3] if p):
                return True
        except (OSError, ValueError):
            continue
    return False


def collect(inbox: Inbox, config: dict, comments: list[dict]) -> None:
    cursor_key = f"cursor:{config['repo']}:{config['issue']}"
    cursor = inbox.get(cursor_key, {"id": 0, "since": stamp()})
    with inbox.db:
        for comment in sorted(comments, key=lambda c: c["id"]):
            parsed = board.parse_comment(comment)
            if parsed:
                for recipient in sorted(set(MENTION_RE.findall(parsed.get("text") or ""))):
                    if recipient in config["routes"] and recipient != parsed["agent"]:
                        key = f"{config['repo']}:{config['issue']}:{comment['id']}:{recipient}"
                        inbox.put(key, comment["id"], recipient, nudge_text(parsed))
            if comment["id"] > cursor["id"]:
                cursor = {"id": comment["id"], "since": comment["created_at"]}
        inbox.set(cursor_key, cursor)


def initialize(inbox: Inbox, config: dict, legacy: Path, *, bootstrap_now: bool = False) -> None:
    key = f"cursor:{config['repo']}:{config['issue']}"
    if inbox.get(key) is not None:
        return
    if legacy.exists():
        initial, reason = json.loads(legacy.read_text()), f"Imported legacy cursor {legacy}"
    else:
        since = stamp() if bootstrap_now else config.get("start_since")
        if not since:
            raise ValueError("First start requires explicit start_since after a history audit, or --bootstrap-now")
        initial = {"id": 0, "since": since}
        reason = "Explicit --bootstrap-now" if bootstrap_now else config.get("bootstrap_note", "Explicit configured start_since")
    initial["since"] = board.parse_ts(initial["since"]).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if not isinstance(initial.get("id"), int):
        raise ValueError("Legacy cursor requires an integer id")
    with inbox.db:
        inbox.set(key, initial)
        inbox.set("bootstrap", {"time": stamp(), "reason": reason, "cursor": initial})
    log("initialized cursor:", initial, "reason:", reason)


def herdr_agent(route: dict) -> dict:
    result = board.run_command([route.get("executable", "herdr"), "agent", "get", route["pane"]], timeout=5)
    if result.returncode:
        return {}
    agent = json.loads(result.stdout).get("result", {}).get("agent", {})
    if (agent.get("pane_id") != route["pane"] or agent.get("agent") != "codex"
            or agent.get("terminal_id") != route["terminal_id"]
            or agent.get("agent_session", {}).get("value") != route["thread"]):
        return {}
    return agent


def process_start_ticks(pid: int) -> int:
    # Linux process start time distinguishes PID reuse; never read the environment.
    return int(Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19])


def herdr_process_matches(route: dict) -> bool:
    result = board.run_command([route.get("executable", "herdr"), "pane", "process-info",
                                "--pane", route["pane"]], timeout=5)
    if result.returncode:
        return False
    info = json.loads(result.stdout).get("result", {}).get("process_info", {})
    return (info.get("pane_id") == route["pane"]
            and any(p.get("pid") == route["pid"] and p.get("name") == "codex"
                    for p in info.get("foreground_processes", []))
            and process_start_ticks(route["pid"]) == route["process_start_ticks"])


def herdr_ready(route: dict) -> dict:
    before = herdr_agent(route)
    if before.get("agent_status") not in ("idle", "working", "done") or not herdr_process_matches(route):
        return {}
    result = board.run_command([route.get("executable", "herdr"), "agent", "read", route["pane"],
                                "--source", "visible", "--format", "text", "--lines", "40"], timeout=5)
    if result.returncode:
        return {}
    # Agent prompt safely buffers a working Codex turn; preserve drafts and defer menus.
    prompts = [line.strip() for line in result.stdout.splitlines() if line.strip().startswith(("›", "❯"))]
    if not prompts or prompts[-1] not in ("›", "❯", "› Ask Codex to do anything"):
        return {}
    if re.search(r"press enter to confirm|enter to select|do you want to proceed|retry with a faster model|dismiss and keep waiting", result.stdout, re.I):
        return {}
    after = herdr_agent(route)
    if (after and after.get("revision") == before.get("revision")
            and after.get("agent_status") in ("idle", "working", "done") and herdr_process_matches(route)):
        return after
    return {}


def deliver(inbox: Inbox, config: dict, *, dry: bool = False) -> None:
    global TMUX_SOCKET
    for item in inbox.pending():
        route = config["routes"].get(item["recipient"])
        if item["recipient"] == "__local_health__":
            route = {"kind": "inbox"}
        if not route:
            continue  # Mapping removed: keep the mention visible, never send it elsewhere.
        kind = route["kind"]
        if dry:
            log("DRY", item["key"], "->", kind)
            continue
        if kind == "inbox":
            inbox.mark(item["key"], "delivered", receipt="durable local inbox; agent consumption not implied")
            continue
        if kind == "tmux":
            TMUX_SOCKET = route["socket"]
            try:
                current = tmux("display-message", "-p", "-t", "=" + route["session"] + ":",
                               "#{pane_current_command}")
                if current.returncode or current.stdout.strip() not in route.get("commands", ["codex", "claude"]):
                    continue
                if not session_idle(route["session"]):
                    continue
            except (OSError, subprocess.TimeoutExpired):
                continue
        if kind == "herdr":
            try:
                receiver_before = herdr_ready(route)
                if not receiver_before:
                    continue
            except (OSError, ValueError, subprocess.TimeoutExpired):
                continue
        inbox.mark(item["key"], "sending")  # Commit before crossing the nontransactional boundary.
        try:
            if kind == "tmux":
                accepted = nudge(route["session"], item["text"], False)
                receipt = "tmux literal text and Enter accepted; agent consumption not implied"
            elif kind == "codex":
                result = board.run_command([route.get("executable", "codex"), "queue", "--thread",
                                            route["thread"], "--message", item["text"]], timeout=20)
                accepted = result.returncode == 0 and "Queued message " in result.stdout
                receipt = result.stdout.strip() if accepted else result.stderr.strip()[:300]
            else:
                result = board.run_command([route.get("executable", "herdr"), "agent", "prompt",
                                            route["pane"], item["text"]], timeout=10)
                response = json.loads(result.stdout).get("result", {}) if result.stdout.strip() else {}
                receiver = response.get("agent", {})
                accepted = (result.returncode == 0 and response.get("type") == "agent_prompted"
                            and receiver.get("pane_id") == route["pane"]
                            and receiver.get("terminal_id") == route["terminal_id"]
                            and receiver.get("revision") == receiver_before.get("revision")
                            and receiver.get("agent_session", {}).get("value") == route["thread"]
                            and herdr_process_matches(route))
                receipt = json.dumps({"transport": "herdr agent prompt", "pane": route["pane"],
                                      "thread": route["thread"], "terminal_id": route["terminal_id"],
                                      "pid": route["pid"], "accepted": accepted,
                                      "atomic_thread_guard": False})
            inbox.mark(item["key"], "delivered" if accepted else "uncertain",
                       receipt=receipt, error="" if accepted else "Transport did not confirm; inspect receiver before retry")
            log("delivered" if accepted else "uncertain", item["key"], "via", kind)
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            inbox.mark(item["key"], "uncertain", error=f"Transport interrupted: {type(exc).__name__}; inspect before retry")


def health(path: Path | None, inbox: Inbox, config: dict) -> None:
    if path is None:
        return
    data = {"pid": os.getpid(), "time": stamp(), "release": str(HERE.parent),
            "source": config.get("source_root"), "fingerprint": config.get("fingerprint"),
            "cursor": inbox.get(f"cursor:{config['repo']}:{config['issue']}"),
            "counts": dict(inbox.db.execute("SELECT status,count(*) FROM deliveries GROUP BY status"))}
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n")
    temporary.replace(path)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--config", type=Path, default=state_home() / "config.json")
    ap.add_argument("--state", type=Path, default=state_home() / "nudger.sqlite3")
    ap.add_argument("--lock", type=Path, default=state_home() / "machine.lock")
    ap.add_argument("--health", type=Path)
    ap.add_argument("--bootstrap-now", action="store_true", help="explicitly start from now only if no cursor exists")
    ap.add_argument("--interval", type=int, help="override configured polling interval")
    ap.add_argument("--once", action="store_true", help="one poll, then exit")
    ap.add_argument("--dry-run", action="store_true", help="print nudges instead of typing them")
    ap.add_argument("--since-minutes", type=int, default=0,
                    help="ignore the saved cursor and process posts from the last N minutes")
    ap.add_argument("--cursor", type=Path, help="legacy JSON cursor to import once")
    a = ap.parse_args(argv)

    config = load_config(a.config)
    lock = None if a.dry_run else acquire_lock(a.lock)
    if mirror_running():
        raise SystemExit("Telegram mirror already runs here; refusing duplicate nudger")
    inbox = Inbox(a.state.resolve(), dry=a.dry_run)
    if not a.dry_run:
        recovered = inbox.recover()
        if recovered:
            log("Retained interrupted sends for reconciliation:", recovered)
    key = f"cursor:{config['repo']}:{config['issue']}"
    legacy = a.cursor or board.cache_dir() / f"nudge-{config['repo'].replace('/', '__')}-{config['issue']}.json"
    initialize(inbox, config, legacy, bootstrap_now=a.bootstrap_now)
    replay_since = ((board.now_utc() - timedelta(minutes=a.since_minutes)).isoformat().replace("+00:00", "Z")
                    if a.since_minutes else None)
    interval = a.interval or config.get("interval", 30)
    if interval < 1:
        raise SystemExit("interval must be positive")
    log("nudger up:", board.issue_url(config['repo'], config['issue']), "routes:", ", ".join(config["routes"]))

    while True:
        try:
            # GitHub's strict-after filter has second precision: overlap every poll,
            # including restarts/replays, then deduplicate by durable comment key.
            boundary = board.parse_ts(replay_since or inbox.get(key)["since"]) - timedelta(seconds=2)
            since = boundary.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
            comments = board.fetch_comments(config["repo"], config["issue"], since)
            collect(inbox, config, comments)
            replay_since = None
        except (SystemExit, OSError, ValueError) as e:
            log("board fetch failed, retrying:", e)
        deliver(inbox, config, dry=a.dry_run)
        if not a.dry_run:
            health(a.health, inbox, config)
        if a.once:
            return 0
        time.sleep(interval)


if __name__ == "__main__":
    sys.exit(main())
