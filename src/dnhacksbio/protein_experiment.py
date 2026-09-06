"""Operator-only registered protein finite replay; public submissions return receipts.

Real release requires reviewed cohort/processing/identity/privacy artifacts and a
passing power report. The current audited CPTAC development cohort fails eligibility.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .drug_response_scoring import Store as RegistryStore, canonical, digest
from .experiment_transport import REQUEST_ID, serve
from .native_group_replay import PrivateGroupReplayStore, canonical_inputs, runtime_hash, METHOD


class EvidenceUnavailable(ValueError):
    pass


def availability():
    return {"method": METHOD, "status": "unavailable", "blockers": [
        "CPTAC development has 26 grade pairs; Fudan external benchmark has 65 before coverage filtering, 60 after",
        "No approved independent confirmation cohort/processing/identity review",
        "No deployed distinct-identity private worker or passed declared-effect power report"]}


def release_check(manifest):
    """Check concrete operator review references, not a single enable boolean."""
    release = manifest.get("release", {})
    if set(release) != {"reviews", "power_report", "discovery_uid"}:
        raise EvidenceUnavailable("Missing private release evidence")
    if type(release["discovery_uid"]) is not int or release["discovery_uid"] < 0 or release["discovery_uid"] == os.getuid():
        raise EvidenceUnavailable("Worker and discovery must run as different service identities")
    reviews = release["reviews"]
    if set(reviews) != {"sampling", "preprocessing", "untouched_history", "canonical_identity", "privacy"}:
        raise EvidenceUnavailable("Missing independent reviews")
    for review in reviews.values():
        if set(review) != {"status", "artifact_sha256", "reviewer"} or review["status"] != "approved" or not review["reviewer"]:
            raise EvidenceUnavailable("Independent review not approved")
        value = review["artifact_sha256"]
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise EvidenceUnavailable("Reviewed artifact hash required")
    power = release["power_report"]
    if (power.get("model_hash") != manifest["spec"]["model_hash"] or
        power.get("panel_hash") != manifest["spec"]["panel_hash"] or
        power.get("alpha") != .05 or power.get("null_streams", 0) < 10000 or
        not .8 <= power.get("minimum_effect_power_lower95", -1) <= 1 or
        not 0 <= power.get("anytime_null_upper95", 1) <= .06 or
        power.get("pairs") != min(len(g["donors"]) for g in manifest["groups"])):
        raise EvidenceUnavailable("Model-specific null/power release gate failed")


class Store(RegistryStore):
    """Existing QueueStore transport/alias transactions, one shared native ledger."""
    worker_module = "dnhacksbio.protein_experiment"

    def configure(self, manifest_path):
        if not isinstance(manifest_path, (str, Path)):
            raise EvidenceUnavailable("Operator manifest path required")
        path = Path(manifest_path)
        if path.stat().st_size > 48 * 1024 * 1024:
            raise ValueError("Manifest exceeds budget")
        manifest = json.loads(path.read_text())
        if set(manifest) != {"spec", "groups", "release", "ledger_directory"} or len(manifest["groups"]) != 2:
            raise ValueError("Invalid private manifest")
        release_check(manifest)
        canonical_inputs(manifest["spec"], *manifest["groups"])
        ledger = Path(manifest["ledger_directory"])
        if not ledger.is_absolute() or not ledger.is_dir() or ledger.stat().st_uid != os.getuid() or ledger.stat().st_mode & 0o077:
            raise EvidenceUnavailable("Shared ledger must be operator-owned and private")
        config = canonical({"manifest": manifest, "manifest_sha256": digest(manifest),
                            "worker_sha256": self.worker_hash(), "runtime": self.runtime()})
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            old = con.execute("SELECT config FROM settings WHERE id=1").fetchone()
            if old and old[0] != config:
                raise ValueError("Registry already frozen")
            con.execute("INSERT OR IGNORE INTO settings VALUES (1,?)", (config,))
        return self.registration()

    @staticmethod
    def worker_hash():
        import hashlib
        from . import drug_response_scoring, experiment_transport
        return digest({"replay": runtime_hash(), "files": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
            (Path(__file__), Path(drug_response_scoring.__file__), Path(experiment_transport.__file__))}})

    def registration(self):
        c = self.config()
        return {"spec": {"method": METHOD}, "input": {"manifest_sha256": c["manifest_sha256"]}}

    def experiment_key(self, payload):
        m = self.config()["manifest"]
        return digest(canonical_inputs(m["spec"], *m["groups"]))

    def validate_payload(self, payload):
        # A fresh/unconfigured service remains explicitly unavailable.
        with self.connect() as con:
            if not con.execute("SELECT 1 FROM settings WHERE id=1").fetchone():
                raise EvidenceUnavailable("Protein native evidence is unavailable")
        super().validate_payload(payload)

    def _score_one(self, receipt):
        try:
            config = self.config()
            if config["worker_sha256"] != self.worker_hash() or config["runtime"] != self.runtime():
                raise ValueError("Frozen worker changed")
            m = config["manifest"]
            release_check(m)
            with self.connect() as con:
                row = con.execute("SELECT payload FROM jobs WHERE receipt=? AND status='running'", (receipt,)).fetchone()
            if not row:
                return
            payload = json.loads(row[0])
            self.validate_payload(payload)
            store = PrivateGroupReplayStore(m["ledger_directory"])
            # The global receipt includes immutable experiment identity, not caller aliases.
            native_receipt = "protein-" + self.experiment_key(payload)
            store.register(native_receipt, m["spec"], *m["groups"])
            store.replay(native_receipt)
            result = store.export(native_receipt)
            with self.connect() as con:
                con.execute("UPDATE jobs SET status='completed',result=? WHERE receipt=? AND status='running'", (canonical(result), receipt))
        except Exception as exc:
            with self.connect() as con:
                con.execute("UPDATE jobs SET status='failed',error=? WHERE receipt=? AND status='running'", (type(exc).__name__, receipt))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    reg = sub.add_parser("register"); reg.add_argument("--manifest", required=True); reg.add_argument("--output", required=True)
    server = sub.add_parser("serve"); server.add_argument("--port", type=int, default=8798)
    worker = sub.add_parser("score-one"); worker.add_argument("--receipt", required=True)
    export = sub.add_parser("export"); export.add_argument("--output", required=True)
    for command in (reg, server, worker, export):
        command.add_argument("--state", required=True)
    args = p.parse_args(argv)
    store = Store(args.state)
    if args.command == "register":
        result = store.configure(args.manifest)
        with open(args.output, "x", opener=lambda path, flags: os.open(path, flags, 0o600)) as stream:
            json.dump(result, stream)
    elif args.command == "serve":
        store.config(); serve(store, "127.0.0.1", args.port)
    elif args.command == "score-one":
        store.score_one(args.receipt)
    else:
        store.export(args.output)


if __name__ == "__main__":
    main()
