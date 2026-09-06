#!/usr/bin/env python3
"""board_nudge.py — turn Board @mentions into a typed nudge in the mentioned agent's tmux pane.

Portable: needs only `gh` (logged in) and `tmux`. No Telegram, no dashboard harness. Run ONE copy
per machine, in a spare tmux window or under nohup:

    python3 scripts/board_nudge.py                 # poll every 30 s, forever
    python3 scripts/board_nudge.py --once --dry-run # what would be nudged right now
    python3 scripts/board_nudge.py --since-minutes 20 --once --dry-run   # replay recent posts

Every poll: fetch new Board comments; for each `@name` in a post, if a tmux session on THIS machine
sanitises to the same name (`ian/graph-plan` == `ian-graph-plan`), and that pane looks idle, type:

    Board: <poster> mentioned you: "<first line>" Run `python3 scripts/board.py show` and answer on the board.

followed by Enter. A busy pane is retried on later polls (up to --max-tries) and then dropped: typing
into a working agent interleaves with its own input. Delivery additionally requires a recognized empty
composer, no menu, and a shared input lock with the popup watcher (docs/board-popup-watcher.md).
A mention only reaches an agent whose
tmux session name IS its board name, which is the default (`board.py` names you after your session).

On the machine that runs `board_mirror.py`, do not also run this: the mirror already nudges there.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import board  # noqa: E402
from tmux_input import Tmux, menu_or_busy, send_board_message  # noqa: E402

MENTION_RE = re.compile(r"@([A-Za-z0-9_./-]+)")
# Pane text that means "still working". Both TUIs print "esc to interrupt" next to a live spinner;
# a finished one reads "Crunched for 5m · done 5:02 PM" and must NOT count as busy.
BUSY_RE = re.compile(r"esc to interrupt|ctrl\+c to interrupt", re.I)


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def sanitize(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "-", name)


def tmux(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["tmux", *args], text=True, capture_output=True)


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
        if menu_or_busy(Tmux().screen("=" + session + ":")):
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
    return send_board_message(session, text)


def nudge_text(p: dict) -> str:
    first = (p.get("text") or "").strip().splitlines()[0][:200] if (p.get("text") or "").strip() else ""
    return (f"Board: {p['agent']} mentioned you: \"{first}\" "
            f"Run `python3 scripts/board.py show` and answer on the board.")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--interval", type=int, default=30, help="seconds between polls (default 30)")
    ap.add_argument("--once", action="store_true", help="one poll, then exit")
    ap.add_argument("--dry-run", action="store_true", help="print nudges instead of typing them")
    ap.add_argument("--since-minutes", type=int, default=0,
                    help="ignore the saved cursor and process posts from the last N minutes")
    ap.add_argument("--max-tries", type=int, default=20,
                    help="polls to keep retrying a busy pane before dropping the nudge (default 20)")
    ap.add_argument("--cursor", help="cursor file (default: board.py's cache dir)")
    a = ap.parse_args(argv)

    repo = board.owner_repo()
    n = board.find_issue(repo) or board.ensure_issue(repo)
    cursor = Path(a.cursor) if a.cursor else board.cache_dir() / f"nudge-{repo.replace('/', '__')}-{n}.json"

    seen_id, since = 0, None
    if a.since_minutes:
        since = (board.now_utc() - timedelta(minutes=a.since_minutes)).isoformat().replace("+00:00", "Z")
    elif cursor.exists():
        try:
            st = json.loads(cursor.read_text())
            seen_id, since = st.get("id", 0), st.get("since")
        except json.JSONDecodeError:
            pass
    if since is None:  # first run: from now, never replay the whole log into people's panes
        since = board.now_utc().isoformat().replace("+00:00", "Z")
        cursor.write_text(json.dumps({"id": 0, "since": since}))

    log(f"nudger up: {board.issue_url(repo, n)}, every {a.interval}s, sessions: "
        + (", ".join(sorted(live_sessions().values())) or "(none)"))
    pending: list[tuple[str, str, int]] = []

    while True:
        try:
            comments = board.fetch_comments(repo, n, since)
        except SystemExit as e:
            log("board fetch failed, retrying:", e)
            comments = []
        for c in sorted(comments, key=lambda x: x["id"]):
            if c["id"] <= seen_id:
                continue
            seen_id, since = c["id"], c["created_at"]
            if not a.since_minutes:
                cursor.write_text(json.dumps({"id": seen_id, "since": since}))
            p = board.parse_comment(c)
            if not p:
                continue
            sessions = live_sessions()
            for m in MENTION_RE.findall(p.get("text") or ""):
                real = sessions.get(sanitize(m))
                if real and real != p["agent"] and not any(s == real for s, _, _ in pending):
                    pending.append((real, nudge_text(p), 0))

        still = []
        for sess, text, tries in pending:
            if session_idle(sess):
                if nudge(sess, text, a.dry_run):
                    log("nudged", sess)
                elif tries < a.max_tries:
                    still.append((sess, text, tries + 1))
            elif tries < a.max_tries:
                if tries == 0:
                    log("busy, will retry:", sess)
                still.append((sess, text, tries + 1))
            else:
                log("dropped nudge for busy session", sess)
        pending = still

        if a.once:
            return 0
        time.sleep(a.interval)


if __name__ == "__main__":
    sys.exit(main())
