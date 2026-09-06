"""Operator-only durable background scoring. No result-reading HTTP endpoint.

Deploy the state directory and worker outside the discovery agent's filesystem permissions
when OS-level confidentiality is required. A separate process alone is not an access boundary.
"""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import threading

import re
import urllib.request

MAX_INPUT = 48 * 1024 * 1024
REQUEST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,119}$")

MAX_BODY = 2 * MAX_INPUT

VALIDATORS = {}


def register_method(name, validator):
    if name in VALIDATORS and VALIDATORS[name] is not validator:
        raise ValueError("Method already registered")
    VALIDATORS[name] = validator


class QueueStore:
    worker_module = ""

    def validate_payload(self, payload):
        return VALIDATORS[self.method](payload)

    def experiment_key(self, payload):
        return hashlib.sha256(json.dumps({k: v for k, v in payload.items() if k != "request_id"},
            sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()

    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.directory, 0o700)
        self.path = self.directory / "scoring.sqlite3"
        with self.connect() as con:
            con.executescript("""
                CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY, config TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS jobs (
                  receipt TEXT PRIMARY KEY, digest TEXT NOT NULL, payload TEXT NOT NULL,
                  status TEXT NOT NULL, result TEXT, error TEXT);
                CREATE TABLE IF NOT EXISTS aliases (receipt TEXT PRIMARY KEY, digest TEXT NOT NULL,
                  payload TEXT NOT NULL, canonical TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS identities (experiment_key TEXT PRIMARY KEY, receipt TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS submissions (id INTEGER PRIMARY KEY, receipt TEXT NOT NULL,
                  digest TEXT NOT NULL, payload TEXT NOT NULL, outcome TEXT NOT NULL,
                  received_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')));
            """)
        os.chmod(self.path, 0o600)

    @contextmanager
    def connect(self):
        con = sqlite3.connect(self.path, timeout=30)
        try:
            with con:
                con.execute("PRAGMA synchronous=FULL")
                yield con
        finally:
            con.close()

    def enqueue(self, payload):
        self.validate_payload(payload)
        value = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        digest = hashlib.sha256(value.encode()).hexdigest()
        receipt = payload["request_id"]
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            if not con.execute("SELECT 1 FROM settings WHERE id=1").fetchone():
                raise ValueError("Queue not configured")
            # Adopt pre-extraction queues without losing receipts or rescoring old inputs.
            for old_receipt, old_digest, old_payload in con.execute(
                    "SELECT receipt,digest,payload FROM jobs WHERE receipt NOT IN (SELECT receipt FROM aliases)").fetchall():
                old_key = self.experiment_key(json.loads(old_payload))
                con.execute("INSERT OR IGNORE INTO identities VALUES (?, ?)", (old_key, old_receipt))
                con.execute("INSERT INTO aliases VALUES (?, ?, ?, ?)",
                            (old_receipt, old_digest, old_payload, old_receipt))
            existing = con.execute("SELECT digest FROM aliases WHERE receipt=?", (receipt,)).fetchone()
            legacy = con.execute("SELECT digest FROM jobs WHERE receipt=?", (receipt,)).fetchone()
            conflict = bool((existing and existing[0] != digest) or (legacy and legacy[0] != digest))
            con.execute("INSERT INTO submissions (receipt,digest,payload,outcome) VALUES (?, ?, ?, ?)",
                        (receipt, digest, value, "conflicting_retry" if conflict else "accepted"))
            if not conflict:
                key = self.experiment_key(payload)
                identity = con.execute("SELECT receipt FROM identities WHERE experiment_key=?", (key,)).fetchone()
                canonical = identity[0] if identity else receipt
                con.execute("INSERT OR IGNORE INTO identities VALUES (?, ?)", (key, canonical))
                con.execute("INSERT OR IGNORE INTO aliases VALUES (?, ?, ?, ?)",
                            (receipt, digest, value, canonical))
                if canonical == receipt:
                    con.execute("INSERT OR IGNORE INTO jobs VALUES (?, ?, ?, 'queued', NULL, NULL)",
                                (receipt, digest, value))
        if conflict:
            raise ValueError("Conflicting retry")
        return {"receipt": receipt, "status": "accepted"}

    def score_one(self, receipt):
        if not REQUEST_ID.fullmatch(receipt):
            raise ValueError("Invalid receipt")
        # Surviving children and restarted services cannot score one job concurrently.
        with (self.directory / ("job-" + hashlib.sha256(receipt.encode()).hexdigest() + ".lock")).open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            with self.connect() as con:
                row = con.execute("SELECT status FROM jobs WHERE receipt=?", (receipt,)).fetchone()
            if row and row[0] == "running":
                self._score_one(receipt)

    def process_one(self, *, timeout=600):
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT receipt FROM jobs WHERE status='queued' ORDER BY rowid LIMIT 1").fetchone()
            if not row:
                return False
            receipt = row[0]
            con.execute("UPDATE jobs SET status='running' WHERE receipt=?", (receipt,))
        # Training globals/RNG and any numerical output stay in a separate child process.
        # Neither stdout nor tracebacks enter the discovery journal or its shared artifact collector.
        try:
            proc = subprocess.run([sys.executable, "-m", self.worker_module,
                                   "score-one", "--state", str(self.directory), "--receipt", receipt],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout,
                                  env=os.environ | {"OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"})
            error = "worker_exit" if proc.returncode else "incomplete_worker"
        except subprocess.TimeoutExpired:
            error = "worker_timeout"
        except OSError:
            error = "worker_start_failed"
        with self.connect() as con:
            con.execute("UPDATE jobs SET status='failed', error=? WHERE receipt=? AND status='running'",
                        (error, receipt))
        return True


def make_server(store, host="127.0.0.1", port=8793):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def reply(self, status, value):
            body = json.dumps(value).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            self.connection.settimeout(30)
            if self.path != "/experiments":
                self.reply(404, {"error": "not found"})
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= MAX_BODY:
                    raise ValueError("Invalid size")
                body = self.rfile.read(size)
                if len(body) != size:
                    raise ValueError("Incomplete body")
                receipt = store.enqueue(json.loads(body))
            except Exception:
                self.reply(400, {"error": "submission not accepted"})
                return
            self.reply(202, receipt)

        def do_GET(self):
            self.reply(404, {"error": "not found"})

    return ThreadingHTTPServer((host, port), Handler)


def serve(store, host, port):
    # One worker owner per queue; recover interrupted jobs only while holding this lock.
    with (store.directory / "worker.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with store.connect() as con:
            con.execute("UPDATE jobs SET status='queued' WHERE status='running'")
        stop = threading.Event()

        def work():
            while not stop.is_set():
                if not store.process_one():
                    stop.wait(0.25)

        server = make_server(store, host, port)
        worker = threading.Thread(target=work, daemon=True)
        worker.start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
            stop.set()
            worker.join()



def send_payload(payload, endpoint):
    body = json.dumps(payload, allow_nan=False).encode()
    request_id = payload["request_id"]
    req = urllib.request.Request(endpoint.rstrip("/") + "/experiments", body,
                                 {"Content-Type": "application/json"}, method="POST")
    # Never relay server bodies, error details, statistics, paths or worker state.
    # A receipt is constructed locally only after the server acknowledges durable acceptance.
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            if response.status != 202:
                raise RuntimeError("Unexpected acknowledgement")
    except Exception:
        raise RuntimeError("Submission not acknowledged; retry unchanged inputs with the same request ID") from None
    return {"receipt": request_id, "status": "accepted"}

