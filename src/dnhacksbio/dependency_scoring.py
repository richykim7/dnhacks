"""Operator-only registered Chronos scoring. No public result or completion endpoint."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import os
from pathlib import Path

from .dependency_experiment import METHOD, SHA256, validate_payload
from .dependency_evalue import blocked_permutation
from .experiment_transport import QueueStore, make_server, serve, register_method


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def fields(value, expected):
    if not isinstance(value, dict) or set(value) != set(expected.split()):
        raise ValueError("Invalid registration fields")


def description(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 16000:
        raise ValueError("Missing design declaration")


def validate_registration(registration):
    fields(registration, "protocol manifest rows")
    protocol, manifest, rows = (registration[k] for k in ("protocol", "manifest", "rows"))
    fields(protocol, "schema_version method protocol_id hypothesis family_id target event_gene event disease direction "
           "statistic min_group uninformative_blocks permutations exact_limit seed exchangeability_justification "
           "chronos_invariance_audit block_justification eligibility power_assessment exchangeability_supported")
    if type(protocol["schema_version"]) is not int or protocol["schema_version"] != 1 or protocol["method"] != METHOD:
        raise ValueError("Unsupported protocol")
    for name in ("protocol_id", "hypothesis", "family_id", "target", "event_gene", "disease", "exchangeability_justification",
                 "chronos_invariance_audit", "block_justification", "eligibility", "power_assessment"):
        description(protocol[name])
    if (protocol["event"] != "curated_deletion" or protocol["direction"] != "stronger_in_deleted"
            or protocol["statistic"] != "block_size_weighted_mean_difference"
            or protocol["uninformative_blocks"] != "exclude"):
        raise ValueError("Unsupported endpoint/statistic")
    if type(protocol["min_group"]) is not int or protocol["min_group"] < 8:
        raise ValueError("At least eight units per group required")
    if type(protocol["permutations"]) is not int or protocol["permutations"] != 9999:
        raise ValueError("Monte Carlo configuration must use 9999 draws")
    if type(protocol["exchangeability_supported"]) is not bool:
        raise ValueError("Declare exchangeability support")
    fields(manifest, "schema_version cohort_id sources annotation_scale annotation_definition target "
           "biological_unit_mapping discovery_units exposure release_overlap_audit table_sha256")
    if type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1:
        raise ValueError("Unsupported manifest")
    if manifest["annotation_scale"] != "curated_deleted_intact_unknown" or manifest["target"] != protocol["target"]:
        raise ValueError("Conflicting annotation or target")
    for name in ("annotation_definition", "release_overlap_audit"):
        description(manifest[name])
    if manifest["exposure"] not in ("operator-held-confirmation", "development"):
        raise ValueError("Declare confirmation exposure")
    if not isinstance(manifest["sources"], list) or not manifest["sources"]:
        raise ValueError("Missing source provenance")
    for source in manifest["sources"]:
        fields(source, "url release sha256 scale")
        for value in source.values():
            description(value)
        if not source["url"].startswith("https://") or not SHA256.fullmatch(source["sha256"]):
            raise ValueError("Invalid source provenance")
    if not isinstance(rows, list) or not rows or len(rows) > 100_000:
        raise ValueError("Invalid cohort table")
    if manifest["table_sha256"] != digest(rows):
        raise ValueError("Table hash mismatch")
    mapping = manifest["biological_unit_mapping"]
    if not isinstance(mapping, dict) or not mapping:
        raise ValueError("Missing biological-unit mapping")
    for model, unit in mapping.items():
        description(model)
        description(unit)
    discovery = manifest["discovery_units"]
    if not isinstance(discovery, list) or any(not isinstance(u, str) or not u for u in discovery):
        raise ValueError("Invalid discovery-unit audit")
    # Validate rows without looking at their group difference or selecting a design by outcome.
    seen_units, seen_models = set(), set()
    for row in rows:
        fields(row, "unit_id model_id disease event_status block_id target_effect")
        for name in ("unit_id", "model_id", "disease", "block_id"):
            description(row[name])
        if mapping.get(row["model_id"]) != row["unit_id"]:
            raise ValueError("Unresolved model alias")
        if row["unit_id"] in seen_units or row["model_id"] in seen_models:
            raise ValueError("Shared donor or repeated screen")
        seen_units.add(row["unit_id"])
        seen_models.add(row["model_id"])
        if row["disease"] != protocol["disease"]:
            raise ValueError("Cohort violates frozen disease eligibility")
        if row["event_status"] not in ("deleted", "intact", "unknown"):
            raise ValueError("Invalid curated event call")
        effect = row["target_effect"]
        if effect is not None and (type(effect) not in (int, float) or not math.isfinite(effect)):
            raise ValueError("Invalid target effect")
    # Configuration validation, with no outcomes passed to the numerical routine.
    blocked_permutation([], min_group=protocol["min_group"], exact_limit=protocol["exact_limit"],
                        permutations=protocol["permutations"], seed=protocol["seed"])
    validate_payload({"request_id": "registration", "spec": {k: protocol[k] for k in
                     ("schema_version", "method", "protocol_id", "hypothesis", "family_id")},
                     "input": {"cohort_id": manifest["cohort_id"], "manifest_sha256": digest(manifest)}})


register_method("dependency-chronos-v1", validate_payload)


class Store(QueueStore):
    immutable_completions = True
    worker_module = "dnhacksbio.dependency_scoring"
    method = "dependency-chronos-v1"

    def configure(self, registration):
        """Copy the entire operator registration into immutable, private queue settings."""
        validate_registration(registration)
        value = canonical(registration)
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            previous = con.execute("SELECT config FROM settings WHERE id=1").fetchone()
            if previous and previous[0] != value:
                raise ValueError("Settings are frozen for this queue; use a new state directory")
            con.execute("INSERT OR IGNORE INTO settings VALUES (1, ?)", (value,))

    def experiment_key(self, payload):
        # Registration matching is private: acceptance must not reveal cohort existence or validity.
        # Names in descriptions/request IDs never create additional numerical evidence.
        with self.connect() as con:
            config = json.loads(con.execute("SELECT config FROM settings WHERE id=1").fetchone()[0])
        return digest({"method": METHOD, "protocol_sha256": digest(config["protocol"]),
                       "input": payload["input"], "protocol_id": payload["spec"]["protocol_id"],
                       "hypothesis": payload["spec"]["hypothesis"], "family_id": payload["spec"]["family_id"]})

    def _score_one(self, receipt):
        try:
            with self.connect() as con:
                payload = json.loads(con.execute("SELECT payload FROM jobs WHERE receipt=?", (receipt,)).fetchone()[0])
                registration = json.loads(con.execute("SELECT config FROM settings WHERE id=1").fetchone()[0])
            validate_registration(registration)
            protocol, manifest, rows = (registration[k] for k in ("protocol", "manifest", "rows"))
            expected = {k: protocol[k] for k in ("schema_version", "method", "protocol_id", "hypothesis", "family_id")}
            reason = None
            if payload["spec"] != expected or payload["input"] != {
                    "cohort_id": manifest["cohort_id"], "manifest_sha256": digest(manifest)}:
                reason = "registration_mismatch"
            elif not protocol["exchangeability_supported"]:
                reason = "exchangeability_unsupported"
            elif manifest["exposure"] != "operator-held-confirmation":
                reason = "development_data"
            elif set(manifest["discovery_units"]) & {r["unit_id"] for r in rows}:
                reason = "discovery_confirmation_overlap"
            if reason:
                result = {"status": "unavailable", "reason": reason, "effect": None, "p_value": None, "e_value": None}
            else:
                result = blocked_permutation(rows, **{k: protocol[k] for k in
                    ("min_group", "exact_limit", "permutations", "seed")})
            result.update({"canonical_experiment_key": self.experiment_key(payload),
                           "protocol_sha256": digest(protocol), "manifest_sha256": digest(manifest),
                           "table_sha256": manifest["table_sha256"], "protocol": protocol,
                           "manifest": manifest, "implementation": "dependency-chronos-v1",
                           "python_version": sys.version,
                           "implementation_sha256": hashlib.sha256(
                               Path(__file__).with_name("dependency_evalue.py").read_bytes()).hexdigest()})
            with self.connect() as con:
                con.execute("UPDATE jobs SET status='completed', result=? WHERE receipt=?", (canonical(result), receipt))
        except Exception as exc:
            with self.connect() as con:
                con.execute("UPDATE jobs SET status='failed', error=? WHERE receipt=?", (type(exc).__name__, receipt))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("serve")
    run.add_argument("--state", required=True)
    run.add_argument("--registration", required=True, help="Operator-only JSON protocol, manifest and rows")
    run.add_argument("--host", default="127.0.0.1")
    run.add_argument("--port", type=int, default=8794)
    score = commands.add_parser("score-one", help=argparse.SUPPRESS)
    score.add_argument("--state", required=True)
    score.add_argument("--receipt", required=True)
    export = commands.add_parser("export")
    export.add_argument("--state", required=True)
    export.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    store = Store(args.state)
    if args.command == "serve":
        store.configure(json.loads(Path(args.registration).read_text()))
        serve(store, args.host, args.port)
    elif args.command == "score-one":
        store.score_one(args.receipt)
    else:
        with store.connect() as con:
            jobs = [dict(zip(("receipt", "status", "result", "error"), r)) for r in con.execute(
                "SELECT receipt,status,result,error FROM jobs ORDER BY rowid")]
            attempts = [dict(zip(("receipt", "digest", "payload", "canonical"), r)) for r in con.execute(
                "SELECT receipt,digest,payload,canonical FROM aliases ORDER BY rowid")]
            submissions = [dict(zip(("id", "receipt", "digest", "payload", "outcome", "received_at"), r))
                           for r in con.execute("SELECT * FROM submissions ORDER BY id")]
        for job in jobs:
            job["result"] = json.loads(job["result"]) if job["result"] else None
        # Exclusive creation prevents accidentally writing private output into an existing public file.
        with open(args.output, "x", opener=lambda path, flags: os.open(path, flags, 0o600)) as stream:
            json.dump({"jobs": jobs, "attempts": attempts, "submissions": submissions}, stream, indent=2, allow_nan=False)
            stream.write("\n")


if __name__ == "__main__":
    main()
