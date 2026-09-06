#!/usr/bin/env python3
"""Inspect or explicitly resolve the nudger's durable local delivery inbox."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sqlite3
from pathlib import Path


def stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def state_home() -> Path:
    return Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "dnhacks-board"


class Inbox:
    """Cursor and pending recipients commit together; restart never loses a mention."""

    def __init__(self, path: Path, *, dry: bool = False):
        if not dry:
            path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(":memory:" if dry else path, timeout=10)
        if dry and path.exists():
            with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as source:
                source.backup(self.db)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS deliveries (
                key TEXT PRIMARY KEY, comment_id INTEGER NOT NULL, recipient TEXT NOT NULL,
                text TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
                attempts INTEGER NOT NULL DEFAULT 0, last_error TEXT NOT NULL DEFAULT '',
                receipt TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                read_at TEXT
            );
        """)

    def get(self, key: str, default=None):
        row = self.db.execute("SELECT value FROM metadata WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set(self, key: str, value) -> None:
        self.db.execute("INSERT OR REPLACE INTO metadata VALUES (?, ?)", (key, json.dumps(value)))

    def put(self, key: str, comment_id: int, recipient: str, text: str) -> None:
        now = stamp()
        self.db.execute("INSERT OR IGNORE INTO deliveries "
                        "(key,comment_id,recipient,text,created_at,updated_at) VALUES (?,?,?,?,?,?)",
                        (key, comment_id, recipient, text, now, now))

    def pending(self) -> list[dict]:
        return [dict(row) for row in self.db.execute(
            "SELECT * FROM deliveries WHERE status='pending' ORDER BY created_at,key")]

    def mark(self, key: str, status: str, *, error: str = "", receipt: str = "") -> None:
        with self.db:
            self.db.execute("UPDATE deliveries SET status=?,last_error=?,receipt=?,updated_at=?,"
                            "attempts=attempts+? WHERE key=?",
                            (status, error, receipt, stamp(), int(status == "sending"), key))

    def recover(self) -> int:
        # A process can die after the receiver accepted text but before we saved its receipt.
        # Resending then could duplicate input; retain it for explicit reconciliation.
        with self.db:
            result = self.db.execute("UPDATE deliveries SET status='uncertain',last_error=?,updated_at=? "
                                     "WHERE status='sending'",
                                     ("Process stopped during transport; inspect receiver before retry", stamp()))
        return result.rowcount


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--state", type=Path, default=state_home() / "nudger.sqlite3")
    sub = ap.add_subparsers(dest="command", required=True)
    show = sub.add_parser("show", help="read inbox without acknowledging or modifying records")
    show.add_argument("--recipient")
    show.add_argument("--all", action="store_true")
    for command in ("ack", "retry"):
        p = sub.add_parser(command, help="explicitly acknowledge or retry one retained delivery")
        p.add_argument("key")
    args = ap.parse_args(argv)
    inbox = Inbox(args.state.resolve(), dry=args.command == "show")
    if args.command == "show":
        query, values = "SELECT * FROM deliveries WHERE 1=1", []
        if args.recipient:
            query += " AND recipient=?"
            values.append(args.recipient)
        if not args.all:
            query += " AND read_at IS NULL"
        print(json.dumps([dict(r) for r in inbox.db.execute(query + " ORDER BY created_at,key", values)], indent=2))
    else:
        with inbox.db:
            if args.command == "ack":
                result = inbox.db.execute("UPDATE deliveries SET read_at=? WHERE key=?", (stamp(), args.key))
            else:
                result = inbox.db.execute("UPDATE deliveries SET status='pending',last_error='',updated_at=? "
                                         "WHERE key=? AND status='uncertain'", (stamp(), args.key))
            if result.rowcount != 1:
                raise SystemExit("No matching record (retry requires uncertain status)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
