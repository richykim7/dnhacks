"""Submit a registered dependency experiment and print only its durable receipt."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import sys

from .expression_experiment import REQUEST_ID
from .experiment_transport import send_payload

METHOD = "dependency-chronos-v1"
SHA256 = re.compile(r"[0-9a-f]{64}")


def validate_payload(payload):
    if not isinstance(payload, dict) or set(payload) != {"request_id", "spec", "input"}:
        raise ValueError("Invalid envelope")
    if not isinstance(payload["request_id"], str) or not REQUEST_ID.fullmatch(payload["request_id"]):
        raise ValueError("Invalid request ID")
    spec, inp = payload["spec"], payload["input"]
    if not isinstance(spec, dict) or set(spec) != {"schema_version", "method", "protocol_id", "hypothesis", "family_id"}:
        raise ValueError("Invalid specification")
    if type(spec["schema_version"]) is not int or spec["schema_version"] != 1 or spec["method"] != METHOD:
        raise ValueError("Unsupported method/version")
    for field in ("protocol_id", "hypothesis", "family_id"):
        if not isinstance(spec[field], str) or not spec[field].strip() or len(spec[field]) > 4000:
            raise ValueError("Invalid specification value")
    if not isinstance(inp, dict) or set(inp) != {"cohort_id", "manifest_sha256"}:
        raise ValueError("Invalid input reference")
    if not isinstance(inp["cohort_id"], str) or not REQUEST_ID.fullmatch(inp["cohort_id"]):
        raise ValueError("Invalid cohort ID")
    if not isinstance(inp["manifest_sha256"], str) or not SHA256.fullmatch(inp["manifest_sha256"]):
        raise ValueError("Invalid manifest digest")


def submit(spec_path, request_id, *, endpoint=None):
    with Path(spec_path).open("rb") as stream:
        raw = stream.read(16_385)
    if len(raw) > 16_384:
        raise ValueError("Specification too large")
    document = json.loads(raw)
    if not isinstance(document, dict) or set(document) != {"spec", "input"}:
        raise ValueError("Expected spec and input reference")
    payload = {"request_id": request_id, **document}
    validate_payload(payload)
    return send_payload(payload, endpoint or os.environ.get("DNHACKS_DEPENDENCY_ENDPOINT", "http://127.0.0.1:8794"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True)
    parser.add_argument("--request-id", required=True)
    args = parser.parse_args(argv)
    try:
        receipt = submit(args.spec, args.request_id)
    except (OSError, ValueError, RuntimeError):
        print("Experiment not acknowledged. Check inputs and service setup; retry with the same request ID.", file=sys.stderr)
        return 1
    print(json.dumps(receipt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
