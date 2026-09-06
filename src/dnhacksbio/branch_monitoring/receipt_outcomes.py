"""Private, versioned outcome adapters for frozen registered experiments.

Reads existing queue snapshots only; never scores, dispatches, or writes research state.
Statistical support is method-specific evidence for the frozen rubric, not a universal
p/e threshold. Operator design review is a declared assumption, not an inferred guarantee.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import sqlite3

from .store import belongs, canonical, digest

POLICY = "registered-receipts-v1"
METHODS = {
    "paired-pathway-v1": ("registered_expression_scoring.py", "expression_design.py", "pathway_evalue.py", "count_expression.py", "evalues.py"),
    "dependency-chronos-v1": ("dependency_scoring.py", "dependency_evalue.py", "dependency_experiment.py", "evalues.py"),
    "biomarker_auc.v1": ("drug_response_scoring.py", "drug_response.py", "evalues.py", "experiment_transport.py"),
}


def implementation_hash():
    root = Path(__file__).parent.parent
    files = {name for names in METHODS.values() for name in names}
    files.update(("experiment_transport.py", "explorer/private_experiments.py", "branch_monitoring/receipt_outcomes.py"))
    return digest({name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in sorted(files)})


@contextmanager
def connect(directory):
    path = Path(directory).resolve() / "scoring.sqlite3"
    con = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=5)
    try:
        con.execute("PRAGMA query_only=ON")
        con.execute("BEGIN")
        yield con
    finally:
        con.close()


def validate_sources(sources):
    if not isinstance(sources, dict) or not sources or not set(sources) <= METHODS.keys():
        raise ValueError("Explicit supported receipt sources required")
    for method, source in sources.items():
        if not isinstance(source, dict) or set(source) != {"directory", "validity_review"}:
            raise ValueError("Receipt sources require private directory and frozen validity review")
        if not isinstance(source["directory"], str) or not Path(source["directory"]).is_absolute():
            raise ValueError("Absolute operator queue directory required")
        review = source["validity_review"]
        if not isinstance(review, dict) or set(review) != {
                "review_id", "method_id", "assumptions", "family_policy", "disclosure_boundary",
                "confirmation_units_disjoint", "design_supported", "selection_frozen"}:
            raise ValueError("Explicit method validity and family/selection review required")
        if review["method_id"] != method or any(review[k] is not True for k in
                ("confirmation_units_disjoint", "design_supported", "selection_frozen")):
            raise ValueError("Receipt design has not been reviewed for this frozen use")
        if any(not isinstance(review[k], str) or not 1 <= len(review[k].strip()) <= 8000 for k in
               ("review_id", "assumptions", "family_policy", "disclosure_boundary")):
            raise ValueError("Bounded explicit validity declarations required")
    return sources


def protocol_policy(policy):
    """Storage locations and review record IDs are episode provenance, not scientific policy."""
    result = {k: v for k, v in policy.items() if k != "initial_snapshot"}
    if "receipt_sources" in result:
        result["receipt_sources"] = {method: {k: v for k, v in source["validity_review"].items() if k != "review_id"}
                                     for method, source in result["receipt_sources"].items()}
    return result


def freeze(sources):
    frozen = {}
    for method, source in validate_sources(sources).items():
        with connect(source["directory"]) as c:
            config = json.loads(c.execute("SELECT config FROM settings WHERE id=1").fetchone()[0])
            c.execute("SELECT completed_at FROM completions LIMIT 1")  # migration required, never performed here
            baseline = [r[0] for r in c.execute("SELECT experiment_key FROM identities ORDER BY experiment_key")]
            if c.execute("SELECT count(*) FROM jobs WHERE receipt NOT IN (SELECT receipt FROM identities)").fetchone()[0]:
                raise ValueError("Legacy queue identities must be adopted before enrollment")
        # Reject the wrong service even if the directory contains a perfectly valid queue.
        if method == "paired-pathway-v1":
            if set(config) != {"registry", "software", "implementation"}:
                raise ValueError("Expected registered pathway service")
            root = Path(__file__).parent.parent
            _equal(config["implementation"], {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                    for name in METHODS[method]})
        elif method == "dependency-chronos-v1":
            if config["protocol"]["method"] != method:
                raise ValueError("Expected registered dependency service")
        elif config["manifest"]["protocol"]["version"] != method:
            raise ValueError("Expected registered drug-response service")
        if method == "biomarker_auc.v1":
            root = Path(__file__).parent.parent
            _equal(config["worker_sha256"], digest({name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                    for name in METHODS[method]}))
        frozen[method] = {"config_hash": digest(config), "baseline_keys": baseline}
    return frozen


def collect(journal, ep, endpoint, sources):
    from .outcomes import blob
    result = []
    for rid, run in journal.snapshot(ep["root_id"], endpoint["through_sequence"])["runs"].items():
        if not belongs(rid, ep["run_id"]):
            continue
        for e in run["history"]:
            if e["sequence"] <= ep["start_sequence"] or e["recorded_at"] > endpoint["at"]:
                continue
            if e["kind"] != "private_experiment.requested" or e["producer"] != "runner":
                continue
            p = e["payload"]
            if p["method_id"] not in sources:
                raise ValueError("Uncovered private method in monitored subtree")
            artifact = blob(journal, p["request"])
            payload = json.loads(artifact["text"])
            if (set(payload) != {"request_id", "spec", "input"} or
                    payload["request_id"] != p["receipt"] or p["receipt"] != e["experiment_id"]):
                raise ValueError("Runner request identity mismatch")
            result.append(dict(finding_id=e["experiment_id"], run_id=rid, title=payload["spec"].get("hypothesis", payload["spec"].get("hypothesis_id")),
                method_id=p["method_id"], receipt=p["receipt"], request=payload, requested_at=e["recorded_at"],
                result=None, artifacts=[artifact], artifact_refs=[artifact["sha256"]], source_events=[e["event_id"]],
                fingerprint=digest({"method": p["method_id"], "spec": payload["spec"], "input": payload["input"]})))
    return result


def _equal(actual, expected):
    if actual != expected:
        raise ValueError("Private evidence provenance mismatch")


def _number(value, *, probability=False):
    if type(value) not in (int, float) or not math.isfinite(value) or probability and not 0 < value <= 1:
        raise ValueError("Invalid numerical evidence")


def validate_result(method, config, payload, key, result):
    """Match actual method contracts and worker provenance without calling numerical scoring."""
    spec, inp = payload["spec"], payload["input"]
    if method == "paired-pathway-v1":
        registry = config["registry"]
        protocol = registry["protocols"][spec["protocol_id"]]
        cohort = registry["cohorts"][protocol["cohort_id"]]
        resource = registry["resources"][protocol["resource_id"]]
        _equal(spec, {"schema_version": 2, "method": method, "protocol_id": spec["protocol_id"],
                      "hypothesis": protocol["hypothesis"], "family_id": protocol["family_id"]})
        _equal(inp, {"cohort_id": protocol["cohort_id"], "manifest_sha256": digest(cohort["manifest"])})
        scientific = {k: v for k, v in protocol.items() if k not in {"cohort_id", "resource_id", "hypothesis", "family_id"}}
        _equal(key, digest({"data": cohort["manifest"]["data_sha256"], "protocol": scientific, "resource": resource}))
        for k, v in {"spec": spec, "experiment_key": key, "protocol": protocol, "protocol_sha256": digest(protocol),
                     "manifest": cohort["manifest"], "manifest_sha256": inp["manifest_sha256"],
                     "resource_sha256": digest(resource), "software": config["software"],
                     "implementation": config["implementation"], "confirmation": True}.items():
            _equal(result[k], v)
        _equal(cohort["manifest"]["confirmation"], True)
        if protocol["assignment"] not in {"randomized-pairs", "swap-symmetry"} or not protocol["assignment_justification"].strip():
            raise ValueError("Unsupported assignment")
        if result.get("status") != "completed":
            return False
        if result["n_units"] < protocol["min_pairs"] or result["observed_targets"] < protocol["min_targets"]:
            raise ValueError("Insufficient independent evidence")
        pk, ek = "p", "e"
    elif method == "dependency-chronos-v1":
        protocol, manifest = config["protocol"], config["manifest"]
        _equal(spec, {k: protocol[k] for k in ("schema_version", "method", "protocol_id", "hypothesis", "family_id")})
        _equal(inp, {"cohort_id": manifest["cohort_id"], "manifest_sha256": digest(manifest)})
        _equal(manifest["table_sha256"], digest(config["rows"]))
        _equal(key, digest({"method": method, "protocol_sha256": digest(protocol), "input": inp,
                           **{k: spec[k] for k in ("protocol_id", "hypothesis", "family_id")}}))
        for k, v in {"canonical_experiment_key": key, "protocol_sha256": digest(protocol), "protocol": protocol,
                     "manifest_sha256": digest(manifest), "manifest": manifest,
                     "table_sha256": manifest["table_sha256"], "implementation": method}.items():
            _equal(result[k], v)
        expected_code = hashlib.sha256((Path(__file__).parent.parent / "dependency_evalue.py").read_bytes()).hexdigest()
        _equal(result["implementation_sha256"], expected_code)
        if (protocol["exchangeability_supported"] is not True or manifest["exposure"] != "operator-held-confirmation"
                or set(manifest["discovery_units"]) & {r["unit_id"] for r in config["rows"]}):
            raise ValueError("Unsupported confirmation design")
        if result.get("status") != "ok":
            return False
        if min(result["counts"]["deleted"], result["counts"]["intact"]) < protocol["min_group"]:
            raise ValueError("Insufficient independent units")
        pk, ek = "p_value", "e_value"
    else:
        manifest = config["manifest"]
        _equal(config["manifest_sha256"], digest(manifest))
        _equal(spec, {"schema": "drug_response.v1", "method": "biomarker_auc",
                      **{k: manifest[k] for k in ("protocol_id", "hypothesis_id", "family_id")}})
        _equal(inp, {"cohort_id": manifest["cohort_id"], "manifest_sha256": digest(manifest)})
        _equal(key, digest({"protocol": manifest["protocol"], "cohort": manifest["cohort"]}))
        for k, v in {"method": method, "experiment_key": key, "spec": spec, "manifest_sha256": digest(manifest),
                     "worker_sha256": config["worker_sha256"], "protocol": manifest["protocol"],
                     "source": manifest["cohort"]["source"]}.items():
            _equal(result[k], v)
        if result["n_units"] < manifest["protocol"]["min_units"]:
            raise ValueError("Insufficient independent units")
        pk, ek = "p", "e"
    _number(result[pk], probability=True)
    _number(result[ek])
    _number(result["effect"])
    if result[ek] < 0 or not isinstance(result.get("null"), str) or not result["null"].strip():
        raise ValueError("Missing method null/evidence")
    # Validate the declared fixed-p calibration, without rerunning the experiment.
    from dnhacksbio.evalues import p_to_e
    if not math.isclose(result[ek], p_to_e(result[pk]), rel_tol=1e-12, abs_tol=1e-12):
        raise ValueError("Evidence calibration mismatch")
    return True


class ReceiptVerification:
    policy_id = POLICY

    def __init__(self, sources, frozen, endpoint):
        self.sources, self.frozen, self.endpoint = sources, frozen, endpoint

    def __call__(self, journal, ep, candidate, deadline):
        if "receipt" not in candidate:
            from .outcomes import JournalVerification
            return JournalVerification()(journal, ep, candidate, deadline)
        method = candidate["method_id"]
        source, frozen = self.sources[method], self.frozen[method]
        try:
            with connect(source["directory"]) as c:
                config = json.loads(c.execute("SELECT config FROM settings WHERE id=1").fetchone()[0])
                _equal(digest(config), frozen["config_hash"])
                alias = c.execute("SELECT digest,payload,canonical FROM aliases WHERE receipt=?", (candidate["receipt"],)).fetchone()
                if not alias:
                    return {"status": "pending"}
                payload = json.loads(alias[1])
                _equal(payload, candidate["request"])
                _equal(alias[0], digest(payload))
                accepted = c.execute("SELECT received_at FROM submissions WHERE receipt=? AND digest=? AND outcome='accepted' ORDER BY id LIMIT 1",
                                     (candidate["receipt"], alias[0])).fetchone()
                if not accepted:
                    raise ValueError("No durable accepted request")
                accepted_at = datetime.fromisoformat(accepted[0].replace("Z", "+00:00")).timestamp()
                # SQLite submission timestamps have millisecond precision; conservative lower bound.
                if accepted_at < candidate["requested_at"] - .001 or accepted_at > self.endpoint["at"]:
                    raise ValueError("Request outside frozen production interval")
                keys = c.execute("SELECT experiment_key FROM identities WHERE receipt=?", (alias[2],)).fetchall()
                if len(keys) != 1:
                    raise ValueError("Ambiguous scientific identity")
                key = keys[0][0]
                if key in frozen["baseline_keys"]:
                    return {"status": "duplicate", "experiment_key": key}
                if alias[2] != candidate["receipt"]:
                    # Reusing another request's scientific evidence is not production by this run.
                    # The original runner request receives credit if it belongs to this subtree.
                    return {"status": "duplicate", "experiment_key": key}
                job = c.execute("SELECT digest,payload,status,result FROM jobs WHERE receipt=?", (alias[2],)).fetchone()
                if not job:
                    raise ValueError("Missing canonical job")
                canonical_payload = json.loads(job[1])
                _equal(job[0], digest(canonical_payload))
                _equal(canonical_payload, payload)
                completion = c.execute("SELECT digest,status,result,config,completed_at FROM completions WHERE receipt=?", (alias[2],)).fetchone()
                if not completion:
                    return {"status": "pending" if job[2] in {"queued", "running"} else "unavailable"}
                _equal((completion[0], completion[1], completion[2]), (job[0], job[2], job[3]))
                _equal(digest(json.loads(completion[3])), frozen["config_hash"])
                if not accepted_at <= completion[4] <= deadline or completion[1] != "completed":
                    return {"status": "unavailable"}
                result = json.loads(completion[2])
                if not validate_result(method, config, canonical_payload, key, result):
                    return {"status": "unavailable"}
            return {"status": "passed", "canonical_receipt": alias[2], "experiment_key": key,
                    "completed_at": completion[4], "result_hash": digest(result), "result": result,
                    "validity_review": source["validity_review"], "config_hash": frozen["config_hash"]}
        except (ValueError, KeyError, TypeError, IndexError, OSError, sqlite3.Error):
            return {"status": "unavailable", "error": "private_receipt_unavailable"}


def associate(store, candidate, verified):
    """One deterministic private review association, shared by live routing and final labeling."""
    return store.associate_review(receipt=verified["canonical_receipt"], run_id=candidate["run_id"],
        experiment_id=candidate["finding_id"], finding_id=candidate["finding_id"], method_id=candidate["method_id"],
        null=verified["result"]["null"], validity_policy=canonical(verified["validity_review"]), evidence=verified["result"],
        provenance={"association": "runner-request-and-queue-v1", "source_events": candidate["source_events"],
                    "request_hash": digest(candidate["request"]),
                    **{k: verified[k] for k in ("experiment_key", "result_hash", "config_hash", "completed_at")}},
        disclosure_boundary=verified["validity_review"]["disclosure_boundary"])


def route(store, journal, trace_dir, eid, *, now=None):
    """Discover completed evidence during research without invoking an assessor or closing a label."""
    import time
    from .outcomes import workflow, read_control
    now = time.time() if now is None else now
    ep, w = store.episode(eid), workflow(store, eid)
    policy = w["frozen"]["policy"]
    if policy["verification_policy"] != POLICY:
        raise ValueError("Live routing requires a registered receipt workflow")
    if w["frozen"]["receipt_implementation_hash"] != implementation_hash():
        raise ValueError("Frozen receipt implementation changed")
    audit = read_control(trace_dir, ep["run_id"])
    if audit["budget"]["contract"] != w["frozen"]["budget_contract"] or audit["budget"]["created_at"] != w["frozen"]["budget_created_at"]:
        raise ValueError("Runtime budget identity changed")
    terminal = audit["budget"]["terminal"]
    endpoint = {"at": terminal["at"] if terminal else now, "through_sequence": journal.snapshot(ep["root_id"])["sequence"]}
    deadline = min(now, terminal["at"] + policy["adjudication_seconds"]) if terminal else now
    verifier = ReceiptVerification(policy["receipt_sources"], w["frozen"]["receipt_sources"], endpoint)
    counts = dict(routed=0, pending=0, unavailable=0, duplicate=0)
    try:
        candidates = collect(journal, ep, endpoint, policy["receipt_sources"])
        if len(candidates) > policy["max_candidates"]:
            raise ValueError("Candidate limit exceeded")
    except (ValueError, OSError, KeyError, TypeError, sqlite3.Error):
        counts["unavailable"] = 1
        return counts
    for candidate in candidates:
        verified = verifier(journal, ep, candidate, deadline)
        if verified["status"] == "passed":
            associate(store, candidate, verified)
            counts["routed"] += 1
        else:
            counts[verified["status"]] += 1
    return counts
