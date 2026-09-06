#!/usr/bin/env python3
"""Dismiss only Codex's recognized keep-waiting popup on explicitly scoped tmux panes."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import signal
import subprocess
import time

from tmux_input import Tmux, dismiss_waiting, state_dir, waiting_popup


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-prefix", required=True, help="Only sessions starting with this prefix")
    parser.add_argument("--socket", help="tmux socket path (defaults to current/default server)")
    parser.add_argument("--interval", type=float, default=2)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not args.session_prefix or args.interval < 0.5:
        parser.error("provide a nonempty prefix and interval >= 0.5 seconds")
    client = Tmux(args.socket)
    name = hashlib.sha256(client.socket.encode()).hexdigest()
    lock = (state_dir() / ("watcher-" + name + ".lock")).open("a")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        parser.error("a popup watcher already owns this tmux server")
    running = True

    def stop(*_):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    # Latch after any attempted navigation. An unchanged menu is never hammered.
    attempted: dict[str, float] = {}
    latched: set[str] = set()
    print(f"Watching {args.session_prefix!r} every {args.interval:g}s; dry_run={args.dry_run}", flush=True)
    while running:
        try:
            rows = client.run("list-panes", "-a", "-F",
                              "#{session_name}\t#{pane_id}\t#{cursor_flag}\t#{pane_in_mode}\t#{pane_dead}").stdout.splitlines()
            for row in rows:
                session, pane, cursor, mode, dead = row.split("\t")
                if not session.startswith(args.session_prefix):
                    continue
                if cursor != "0" or mode != "0" or dead != "0":
                    latched.discard(pane)
                    continue
                if pane in latched:
                    try:
                        if waiting_popup(client.screen(pane)) is None:
                            latched.remove(pane)
                    except (OSError, ValueError, subprocess.SubprocessError):
                        pass
                    continue
                if time.monotonic() - attempted.get(pane, -100) < 30:
                    continue
                try:
                    result = dismiss_waiting(client, pane, dry=args.dry_run)
                except (OSError, ValueError, subprocess.SubprocessError):
                    continue  # A disappearing pane or unreadable screen never permits input.
                if result in ("dismissed", "still-open", "selection-not-verified", "would-dismiss"):
                    attempted[pane] = time.monotonic()
                    if result in ("still-open", "selection-not-verified"):
                        latched.add(pane)
                    print(f"{time.strftime('%H:%M:%S')} {pane} {result}", flush=True)
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            print(f"tmux unavailable: {type(exc).__name__}", flush=True)
        if args.once:
            break
        time.sleep(args.interval)
    lock.close()


if __name__ == "__main__":
    main()
