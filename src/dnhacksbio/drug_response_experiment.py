"""Submit an operator-registered biomarker/AUC experiment; expose only its receipt."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import urllib.request

from .expression_experiment import REQUEST_ID


def submit(spec_path, request_id, *, endpoint=None):
    if not isinstance(request_id, str) or not REQUEST_ID.fullmatch(request_id):
        raise ValueError("Invalid request ID")
    with Path(spec_path).open("rb") as stream:
        raw = stream.read(16385)
    if len(raw) > 16384:
        raise ValueError("Specification exceeds 16 KiB")
    document = json.loads(raw)
    if not isinstance(document, dict) or set(document) != {"spec", "input"}:
        raise ValueError("Expected spec and registered input")
    body = json.dumps({"request_id": request_id, **document}, allow_nan=False).encode()
    endpoint = endpoint or os.environ.get("DNHACKS_DRUG_RESPONSE_ENDPOINT", "http://127.0.0.1:8795")
    request = urllib.request.Request(endpoint.rstrip("/") + "/experiments", body,
                                    {"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status != 202:
                raise ValueError("Unexpected acknowledgement")
            receipt = json.loads(response.read(1025))
            if receipt != {"receipt": request_id, "status": "accepted"}:
                raise ValueError("Invalid acknowledgement")
    except Exception:
        raise RuntimeError("Submission not acknowledged; retry unchanged with the same request ID") from None
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True)
    parser.add_argument("--request-id", required=True)
    args = parser.parse_args(argv)
    try:
        receipt = submit(args.spec, args.request_id)
    except (OSError, ValueError, RuntimeError):
        print("Experiment not acknowledged. Check inputs and service setup; retry with the same request ID.",
              file=sys.stderr)
        return 1
    print(json.dumps(receipt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
