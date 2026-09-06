"""Operator-only registry and private drug-response worker; no public results API."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform

from .experiment_transport import REQUEST_ID, QueueStore, serve

MAX_MANIFEST = 48 * 1024 * 1024
MANIFEST_FIELDS = {"protocol_id", "hypothesis_id", "family_id", "cohort_id", "protocol", "cohort"}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class Store(QueueStore):
    worker_module = "dnhacksbio.drug_response_scoring"

    def configure(self, manifest_path):
        from .drug_response import prepare
        with Path(manifest_path).open("rb") as stream:
            raw = stream.read(MAX_MANIFEST + 1)
        if len(raw) > MAX_MANIFEST:
            raise ValueError("Manifest too large")
        manifest = json.loads(raw)
        if not isinstance(manifest, dict) or set(manifest) != MANIFEST_FIELDS:
            raise ValueError("Invalid registry manifest")
        for name in ("protocol_id", "hypothesis_id", "family_id", "cohort_id"):
            if not isinstance(manifest[name], str) or not REQUEST_ID.fullmatch(manifest[name]):
                raise ValueError("Invalid registration ID")
        prepare(manifest["cohort"], manifest["protocol"])
        config = canonical({"manifest": manifest, "manifest_sha256": digest(manifest),
                            "worker_sha256": self.worker_hash(), "runtime": self.runtime()})
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            old = con.execute("SELECT config FROM settings WHERE id=1").fetchone()
            if old and old[0] != config:
                raise ValueError("Registration is frozen; use a new queue")
            con.execute("INSERT OR IGNORE INTO settings VALUES (1, ?)", (config,))
        return self.registration()

    @staticmethod
    def runtime():
        import numpy as np
        return {"python": platform.python_version(), "numpy": np.__version__}

    @staticmethod
    def worker_hash():
        from . import drug_response, evalues, experiment_transport
        return digest({p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in (Path(__file__), Path(drug_response.__file__), Path(evalues.__file__),
                                 Path(experiment_transport.__file__))})

    def config(self):
        with self.connect() as con:
            row = con.execute("SELECT config FROM settings WHERE id=1").fetchone()
        if not row:
            raise ValueError("Queue not configured")
        value = json.loads(row[0])
        if digest(value["manifest"]) != value["manifest_sha256"]:
            raise ValueError("Registry integrity failure")
        return value

    def registration(self):
        config = self.config()
        m = config["manifest"]
        return {"spec": {"schema": "drug_response.v1", "method": "biomarker_auc",
                    **{k: m[k] for k in ("protocol_id", "hypothesis_id", "family_id")}},
                "input": {"cohort_id": m["cohort_id"], "manifest_sha256": config["manifest_sha256"]}}

    def validate_payload(self, payload):
        if not isinstance(payload, dict) or set(payload) != {"request_id", "spec", "input"}:
            raise ValueError("Invalid envelope")
        if not isinstance(payload["request_id"], str) or not REQUEST_ID.fullmatch(payload["request_id"]):
            raise ValueError("Invalid request ID")
        if {k: payload[k] for k in ("spec", "input")} != self.registration():
            raise ValueError("Unregistered experiment")

    def enqueue(self, payload):
        # Keep rejected method-specific requests in the private audit, too. Shared transport
        # owns accepted/conflicting retry transactions. Never disclose rejection details.
        try:
            self.validate_payload(payload)
        except ValueError:
            value = canonical(payload)
            request_id = payload.get("request_id", "") if isinstance(payload, dict) else ""
            if not isinstance(request_id, str):
                request_id = ""
            with self.connect() as con:
                con.execute("INSERT INTO submissions (receipt,digest,payload,outcome) VALUES (?, ?, ?, ?)",
                            (request_id[:120], digest(payload), value, "rejected_validation"))
            raise
        return super().enqueue(payload)

    def experiment_key(self, payload):
        # Administrative request/hypothesis/family/cohort names cannot create fresh evidence.
        manifest = self.config()["manifest"]
        return digest({"protocol": manifest["protocol"], "cohort": manifest["cohort"]})

    def _score_one(self, receipt):
        try:
            from .drug_response import score
            config = self.config()
            if config["worker_sha256"] != self.worker_hash() or config["runtime"] != self.runtime():
                raise ValueError("Frozen software changed")
            with self.connect() as con:
                row = con.execute("SELECT payload FROM jobs WHERE receipt=? AND status='running'", (receipt,)).fetchone()
            if not row:
                return
            payload = json.loads(row[0])
            self.validate_payload(payload)
            m = config["manifest"]
            result = score(m["cohort"], m["protocol"])
            result.update({"manifest_sha256": config["manifest_sha256"],
                "worker_sha256": config["worker_sha256"], "python_version": platform.python_version(),
                "experiment_key": self.experiment_key(payload), "spec": payload["spec"]})
            with self.connect() as con:
                con.execute("UPDATE jobs SET status='completed', result=? WHERE receipt=? AND status='running'",
                            (canonical(result), receipt))
        except Exception as exc:
            with self.connect() as con:
                con.execute("UPDATE jobs SET status='failed', error=? WHERE receipt=? AND status='running'",
                            (type(exc).__name__, receipt))

    def export(self, output):
        with self.connect() as con:
            rows = con.execute("SELECT receipt,digest,status,result,error FROM jobs ORDER BY rowid").fetchall()
            aliases = con.execute("SELECT receipt,digest,canonical FROM aliases ORDER BY rowid").fetchall()
            submissions = con.execute("SELECT receipt,digest,outcome,received_at FROM submissions ORDER BY id").fetchall()
        value = {"registration": self.config(), "aliases": [dict(zip(("receipt", "digest", "canonical"), r)) for r in aliases],
                 "attempts": [dict(zip(("receipt", "digest", "outcome", "received_at"), r)) for r in submissions],
                 "jobs": [dict(zip(("receipt", "digest", "status", "result", "error"),
                              (r[0], r[1], r[2], json.loads(r[3]) if r[3] else None, r[4]))) for r in rows]}
        # Exclusive creation avoids following symlinks or retaining permissive existing-file modes.
        with open(output, "x", opener=lambda p, flags: os.open(p, flags, 0o600)) as stream:
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.write("\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    register = sub.add_parser("register")
    register.add_argument("--manifest", required=True)
    register.add_argument("--output", required=True, help="Agent-visible registration JSON, no measurements")
    run = sub.add_parser("serve")
    run.add_argument("--host", default="127.0.0.1")
    run.add_argument("--port", type=int, default=8795)
    worker = sub.add_parser("score-one", help=argparse.SUPPRESS)
    worker.add_argument("--receipt", required=True)
    export = sub.add_parser("export")
    export.add_argument("--output", required=True)
    for command in (register, run, worker, export):
        command.add_argument("--state", required=True)
    args = parser.parse_args(argv)
    store = Store(args.state)
    if args.command == "register":
        registration = store.configure(args.manifest)
        with open(args.output, "x", opener=lambda p, flags: os.open(p, flags, 0o600)) as stream:
            json.dump(registration, stream, indent=2)
            stream.write("\n")
    elif args.command == "serve":
        store.config()
        serve(store, args.host, args.port)
    elif args.command == "score-one":
        store.score_one(args.receipt)
    else:
        store.export(args.output)


if __name__ == "__main__":
    main()
