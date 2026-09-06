"""Submit an expression experiment; the only public response is a durable receipt."""
from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import sys

from .experiment_transport import MAX_INPUT, REQUEST_ID, send_payload


def submit(input_path, spec_path, request_id, *, endpoint=None):
    """Transport inputs without importing the numerical implementation or reading results."""
    if not REQUEST_ID.fullmatch(request_id):
        raise ValueError("Use a stable request ID of 1–120 letters, digits, dots, dashes or underscores")
    with Path(input_path).open("rb") as stream:
        raw = stream.read(MAX_INPUT + 1)
    if len(raw) > MAX_INPUT:
        raise ValueError("Input exceeds 48 MiB")
    with Path(spec_path).open("rb") as stream:
        spec_raw = stream.read(16_385)
    if len(spec_raw) > 16_384:
        raise ValueError("Specification exceeds 16 KiB")
    spec = json.loads(spec_raw)
    payload = {"request_id": request_id, "spec": spec,
               "input": base64.b64encode(raw).decode("ascii")}
    endpoint = endpoint or os.environ.get("DNHACKS_EXPRESSION_ENDPOINT", "http://127.0.0.1:8793")
    return send_payload(payload, endpoint)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="NPZ with Xa, Xb, genes, unit_a, unit_b")
    parser.add_argument("--spec", required=True, help="JSON experiment specification")
    parser.add_argument("--request-id", required=True, help="Stable ID; reuse for transport retries")
    args = parser.parse_args(argv)
    try:
        receipt = submit(args.input, args.spec, args.request_id)
    except (OSError, ValueError, RuntimeError):
        print("Experiment not acknowledged. Check inputs and service setup; retry with the same request ID.",
              file=sys.stderr)
        return 1
    print(json.dumps(receipt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
