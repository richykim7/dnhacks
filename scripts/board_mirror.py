#!/usr/bin/env python3
"""board_mirror.py — mirror the GitHub Board into a Telegram group chat, and back.

Runs on one machine only (the one with the Telegram harness). Everyone else
just uses `board.py` and the GitHub issue.

Every poll (default 30 s):
  1. New board comments -> one Telegram message each in the group chat.
     Comments that contain @<tmux-session-name> also nudge that session's
     pane (only when it is idle).
  2. New lines in the group's inbox file (humans typing in the group)
     -> posted to the board as "<first name> (telegram)". So both humans can
     talk to every agent from their phones. Needs the harness to route the
     group chat into an inbox file; until then this direction is off.

Never touches bot tokens: sending goes through `tgx`, which handles that.

Usage:
  board_mirror.py --to CHAT_ID [--inbox PATH] [--interval 30] [--dry-run]
Env: BOARD_TG_CHAT (chat id), BOARD_TG_INBOX (inbox path), HARNESS_ROOT.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import board  # noqa: E402

HARNESS = Path(os.environ.get("HARNESS_ROOT", "/home/dev/projects/dashboard"))
TGX = HARNESS / "telegram" / "tgx"
FLEETCTL = HARNESS / "fleet" / "fleetctl"
TG_SUFFIX = "(telegram)"
MENTION_RE = re.compile(r"@([A-Za-z0-9_./-]+)")


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def sanitize(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "-", name)


def drain_stdin():
    try:
        for _ in sys.stdin:
            pass
    except Exception:
        pass


def run_helper(cmd, *, input=None, timeout=5):
    try:
        return board.run_command(cmd, input=input, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        log("helper unavailable or timed out:", Path(cmd[0]).name, cmd[1])
        return None


def tg_send(chat: str, text: str, dry: bool) -> bool:
    if dry:
        log("DRY tgx ->", chat, "|", text.replace("\n", " / ")[:160])
        return True
    p = run_helper([str(TGX), "send", "--to", chat, "-"], input=text, timeout=60)
    if p is None:
        return False
    if p.returncode != 0:
        log("tgx failed", p.returncode, p.stderr.strip()[:200])
        return False
    log("tg ->", chat, p.stdout.strip()[:40])
    return True


def live_sessions() -> dict[str, str]:
    if not FLEETCTL.exists():
        return {}
    p = run_helper([str(FLEETCTL), "list", "--json"])
    if p is None or p.returncode != 0:
        return {}
    try:
        rows = json.loads(p.stdout)
    except json.JSONDecodeError:
        return {}
    return {sanitize(r["session"]): r["session"] for r in rows if r.get("status") != "dead"}


def session_idle(name: str) -> bool:
    p = run_helper([str(FLEETCTL), "status", name, "--raw"])
    return p is not None and p.returncode == 0 and p.stdout.strip() == "idle"


def nudge(session: str, text: str, dry: bool):
    if dry:
        log("DRY nudge ->", session, "|", text[:120])
        return True
    p = run_helper([str(FLEETCTL), "send-keys", session, text])
    return p is not None and p.returncode == 0


def format_tg(p: dict) -> str:
    lines = [f"{p['agent']} · {p['kind'].upper()}", p.get("text", "").strip()]
    if p.get("files"):
        lines.append("files: " + ", ".join(p["files"]))
    meta = []
    if p.get("eta"):
        meta.append(f"eta {p['eta']}")
    if p.get("branch"):
        meta.append(f"{p['branch']} @ {p.get('sha', '')}")
    if meta:
        lines.append(" · ".join(meta))
    lines.append(p["url"])
    return "\n".join(ln for ln in lines if ln)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--to", default=os.environ.get("BOARD_TG_CHAT"), help="Telegram chat id of the group")
    ap.add_argument("--inbox", default=os.environ.get("BOARD_TG_INBOX"), help="inbox JSONL the harness writes for that group")
    ap.add_argument("--interval", type=int, default=30)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if not a.to:
        raise SystemExit("need --to CHAT_ID (or BOARD_TG_CHAT)")

    threading.Thread(target=drain_stdin, daemon=True).start()

    repo = board.owner_repo()
    n = board.find_issue(repo) or board.ensure_issue(repo)
    cache = board.cache_dir()
    bcur = cache / f"mirror-board-{repo.replace('/', '__')}-{n}.json"
    icur = cache / f"mirror-inbox-{sanitize(str(a.to))}.json"
    inbox = Path(a.inbox) if a.inbox else None

    if bcur.exists():
        st = json.loads(bcur.read_text())
        seen_id, since = st.get("id", 0), st.get("since")
    else:
        seen_id, since = 0, board.now_utc().isoformat().replace("+00:00", "Z")
        bcur.write_text(json.dumps({"id": 0, "since": since}))
    if icur.exists():
        inbox_line = json.loads(icur.read_text()).get("line", 0)
    else:
        inbox_line = sum(1 for _ in inbox.open()) if inbox and inbox.exists() else 0
        icur.write_text(json.dumps({"line": inbox_line}))

    log(f"mirror up: {board.issue_url(repo, n)} <-> chat {a.to}"
        f"{' (inbox ' + str(inbox) + ')' if inbox else ' (send-only)'}, every {a.interval}s")
    pending: list[tuple[str, str, int]] = []

    while True:
        try:
            comments = board.fetch_comments(repo, n, since)
        except SystemExit as e:
            log("board fetch failed:", e)
            comments = []
        for c in sorted(comments, key=lambda x: x["id"]):
            if c["id"] <= seen_id:
                continue
            p = board.parse_comment(c)
            if p and not p["agent"].endswith(TG_SUFFIX):
                if not tg_send(str(a.to), format_tg(p), a.dry_run):
                    break  # Keep this comment pending for the next poll.
            seen_id, since = c["id"], c["created_at"]
            bcur.write_text(json.dumps({"id": seen_id, "since": since}))
            if not p:
                continue
            sessions = live_sessions()
            for m in MENTION_RE.findall(p.get("text", "")):
                real = sessions.get(sanitize(m))
                if real and real != p["agent"]:
                    first = p["text"].splitlines()[0][:200]
                    pending.append((real, f"Board: {p['agent']} mentioned you: \"{first}\" "
                                          f"Run `python3 scripts/board.py show` and answer on the board.", 0))

        still = []
        for sess, text, tries in pending:
            if session_idle(sess):
                if nudge(sess, text, a.dry_run):
                    log("nudged", sess)
                else:
                    log("dropped failed nudge", sess)
            elif tries < 20:
                still.append((sess, text, tries + 1))
            else:
                log("dropped nudge for busy session", sess)
        pending = still

        if inbox and inbox.exists():
            with inbox.open() as fh:
                lines = fh.readlines()
            for i in range(inbox_line, len(lines)):
                try:
                    msg = json.loads(lines[i])
                except json.JSONDecodeError:
                    continue
                text = (msg.get("text") or "").strip()
                if text and not text.startswith("/"):
                    who = (msg.get("from") or {}).get("first_name") or "someone"
                    agent = f"{who} {TG_SUFFIX}"
                    if a.dry_run:
                        log("DRY board <-", agent, "|", text[:120])
                    else:
                        try:
                            board.cmd_post(argparse.Namespace(kind="note", files=None, eta=None,
                                                              agent=agent, text=[text]))
                        except SystemExit:
                            log("inbox post failed; retrying next poll")
                            break
                    log("forwarded telegram -> board")
                inbox_line = i + 1
                icur.write_text(json.dumps({"line": inbox_line}))

        time.sleep(a.interval)


if __name__ == "__main__":
    main()
