"""Operator-only durable background scoring. No result-reading HTTP endpoint.

Deploy the state directory and worker outside the discovery agent's filesystem permissions
when OS-level confidentiality is required. A separate process alone is not an access boundary.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

from .expression_experiment import MAX_INPUT, REQUEST_ID

from .experiment_transport import QueueStore, make_server, serve, register_method

MAX_BODY = 2 * MAX_INPUT
SPEC_FIELDS = {"hypothesis", "source", "assumptions", "unit_namespace", "input_scale"}


def validate_payload(payload):
    if not isinstance(payload, dict) or set(payload) != {"request_id", "spec", "input"}:
        raise ValueError("Invalid envelope")
    if not isinstance(payload["request_id"], str) or not REQUEST_ID.fullmatch(payload["request_id"]):
        raise ValueError("Invalid request ID")
    spec = payload["spec"]
    if not isinstance(spec, dict) or set(spec) != SPEC_FIELDS:
        raise ValueError("Invalid specification")
    if any(not isinstance(v, str) or not v.strip() or len(v) > 4000 for v in spec.values()):
        raise ValueError("Invalid specification value")
    if spec["input_scale"] != "TPM":
        raise ValueError("Only TPM supported")
    raw = base64.b64decode(payload["input"], validate=True)
    if len(raw) > MAX_INPUT:
        raise ValueError("Input too large")
    # Bound expansion before numpy allocates arrays. The scoring child verifies actual shapes/types.
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = archive.infolist()
        if len(entries) != 5 or {e.filename for e in entries} != {
                "Xa.npy", "Xb.npy", "genes.npy", "unit_a.npy", "unit_b.npy"}:
            raise ValueError("Invalid NPZ fields")
        if sum(e.file_size for e in entries) > 256 * 1024 * 1024:
            raise ValueError("Expanded input too large")
    return raw


register_method("expression-tpm-v1", validate_payload)


class Store(QueueStore):
    worker_module = "dnhacksbio.expression_scoring"
    method = "expression-tpm-v1"

    def configure(self, encoder, config):
        source = Path(encoder).resolve()
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        frozen = self.directory / (digest + ".npz")
        if not frozen.exists():
            shutil.copyfile(source, frozen)
            os.chmod(frozen, 0o600)
        value = json.dumps({**config, "encoder": str(frozen), "encoder_sha256": digest}, sort_keys=True)
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            previous = con.execute("SELECT config FROM settings WHERE id=1").fetchone()
            if previous and previous[0] != value:
                raise ValueError("Settings are frozen for this queue; use a new state directory")
            con.execute("INSERT OR IGNORE INTO settings VALUES (1, ?)", (value,))

    def _score_one(self, receipt):
        try:
            import numpy as np
            import torch
            from .learned_evalue import LearnedEConfig, SamplingContract, learned_two_sample_e
            torch.set_num_threads(1)
            with self.connect() as con:
                payload = json.loads(con.execute("SELECT payload FROM jobs WHERE receipt=? AND status='running'",
                                                  (receipt,)).fetchone()[0])
                config = json.loads(con.execute("SELECT config FROM settings WHERE id=1").fetchone()[0])
            digest = config.pop("encoder_sha256")
            if hashlib.sha256(Path(config["encoder"]).read_bytes()).hexdigest() != digest:
                raise ValueError("Frozen artifact changed")
            raw = validate_payload(payload)
            # Reject forged NPY shapes before numpy can allocate based on their headers.
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                import math
                for entry in archive.infolist():
                    with archive.open(entry) as stream:
                        version = np.lib.format.read_magic(stream)
                        if version == (1, 0):
                            shape, _, dtype = np.lib.format.read_array_header_1_0(stream)
                        elif version == (2, 0):
                            shape, _, dtype = np.lib.format.read_array_header_2_0(stream)
                        else:
                            raise ValueError("Unsupported array format")
                        if dtype.hasobject or math.prod(shape) * dtype.itemsize != entry.file_size - stream.tell():
                            raise ValueError("Invalid array storage")
            with np.load(io.BytesIO(raw), allow_pickle=False) as data:
                arrays = {name: data[name] for name in ("Xa", "Xb", "genes", "unit_a", "unit_b")}
            spec = payload["spec"]
            result = learned_two_sample_e(**arrays, config=LearnedEConfig(**config),
                sampling=SamplingContract(mode="expression", source=spec["source"],
                    assumptions=spec["assumptions"], unit_namespace=spec["unit_namespace"], input_scale="TPM"))
            value = json.dumps(result.to_dict(), allow_nan=False)
            with self.connect() as con:
                con.execute("UPDATE jobs SET status='completed', result=? WHERE receipt=?", (value, receipt))
        except Exception as exc:
            with self.connect() as con:
                con.execute("UPDATE jobs SET status='failed', error=? WHERE receipt=?",
                            (type(exc).__name__, receipt))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("serve")
    run.add_argument("--state", required=True)
    run.add_argument("--encoder", required=True)
    run.add_argument("--host", default="127.0.0.1")
    run.add_argument("--port", type=int, default=8793)
    run.add_argument("--seed", type=int, default=0)
    run.add_argument("--batch-pairs", type=int, default=8)
    score = commands.add_parser("score-one", help=argparse.SUPPRESS)
    score.add_argument("--state", required=True)
    score.add_argument("--receipt", required=True)
    export = commands.add_parser("export", help="Operator-only offline result export")
    export.add_argument("--state", required=True)
    export.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    store = Store(args.state)
    if args.command == "serve":
        from .learned_evalue import LearnedEConfig
        from .expr_encoder import FrozenEncoder
        LearnedEConfig(seed=args.seed, batch_pairs=args.batch_pairs).validate()
        FrozenEncoder.load(args.encoder)
        store.configure(args.encoder, {"seed": args.seed, "batch_pairs": args.batch_pairs})
        serve(store, args.host, args.port)
    elif args.command == "score-one":
        store.score_one(args.receipt)
    else:
        with store.connect() as con:
            rows = con.execute("SELECT receipt, digest, status, result, error FROM jobs ORDER BY rowid").fetchall()
        records = [{"receipt": r[0], "input_sha256": r[1], "status": r[2],
                    "result": json.loads(r[3]) if r[3] else None, "error": r[4]} for r in rows]
        with open(args.output, "w", opener=lambda path, flags: os.open(path, flags, 0o600)) as stream:
            json.dump(records, stream, indent=2, allow_nan=False)
            stream.write("\n")


if __name__ == "__main__":
    main()
