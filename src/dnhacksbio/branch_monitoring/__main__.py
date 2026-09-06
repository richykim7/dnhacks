"""Explicit operator commands. Importing this package starts no scoring or model calls."""
import argparse
import asyncio
import json
import os
from pathlib import Path

from .store import MonitorStore
from . import statistics


def read(path):
    return json.loads(Path(path).read_text())


def write(path, data):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, indent=2, allow_nan=False)
    os.chmod(target, 0o600)


def main():
    parser = argparse.ArgumentParser(description="Private observation-only subtree monitoring")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("enroll", "prepare", "associate", "review"):
        p = sub.add_parser(name)
        p.add_argument("--state", required=True)
        p.add_argument("--spec", required=True)
        if name == "prepare": p.add_argument("--trace-dir", required=True)
    p = sub.add_parser("label", help="Privately adjudicate actual terminal artifacts under the frozen policy")
    p.add_argument("--state", required=True)
    p.add_argument("--trace-dir", required=True)
    p.add_argument("--episode-id", required=True)
    p.add_argument("--watch", action="store_true")
    p = sub.add_parser("score")
    p.add_argument("--state", required=True)
    p.add_argument("--trace-dir", required=True)
    p.add_argument("--model")
    p.add_argument("--calibration")
    p.add_argument("--watch", action="store_true")
    p = sub.add_parser("export")
    p.add_argument("--state", required=True)
    p.add_argument("--output", required=True)
    for name in ("fit", "calibrate", "evaluate"):
        p = sub.add_parser(name)
        p.add_argument("--data", required=True)
        p.add_argument("--output", required=True)
        if name != "fit": p.add_argument("--model", required=True)
        if name == "calibrate":
            p.add_argument("--alpha", type=float, default=.045)
            p.add_argument("--delta", type=float, default=.005)
        if name == "evaluate": p.add_argument("--calibration", required=True)
    p = sub.add_parser("serve")
    p.add_argument("--state", required=True)
    p.add_argument("--port", type=int, default=8804)
    p = sub.add_parser("disclose")
    p.add_argument("--state", required=True)
    p.add_argument("--boundary", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--authorize-boundary", action="store_true", required=True)
    args = parser.parse_args()
    store = MonitorStore(args.state) if hasattr(args, "state") else None
    if args.command == "enroll": store.enroll(**read(args.spec))
    elif args.command == "prepare":
        from .outcomes import prepare
        from .worker import ReadOnlyJournal
        prepare(store, ReadOnlyJournal(args.trace_dir, create=False), args.trace_dir, **read(args.spec))
    elif args.command == "label":
        from .outcomes import adjudicate
        from .worker import ReadOnlyJournal
        async def label():
            while True:
                result = await adjudicate(store, ReadOnlyJournal(args.trace_dir, create=False), args.trace_dir, args.episode_id)
                if not args.watch or result["status"] == "closed": break
                await asyncio.sleep(5)
        asyncio.run(label())
    elif args.command == "associate":
        from .receipts import import_receipt
        import_receipt(store, **read(args.spec))
    elif args.command == "review":
        spec = read(args.spec)
        store.review(spec["review_id"], spec["decision"], spec["note"])
    elif args.command == "export": write(args.output, store.export())
    elif args.command == "disclose": write(args.output, store.disclosure_export(args.boundary, authorized=args.authorize_boundary))
    elif args.command == "score":
        from dnhacksbio.explorer.runtime import Journal
        from .worker import score_pending, ReadOnlyJournal
        async def run():
            while True:
                await score_pending(store, ReadOnlyJournal(args.trace_dir, create=False),
                                    model=read(args.model) if args.model else None,
                                    calibration=read(args.calibration) if args.calibration else None)
                if not args.watch: break
                await asyncio.sleep(5)
        asyncio.run(run())
    elif args.command == "fit":
        rows = [e for e in read(args.data) if e["partition"] == "fit" and e.get("training_eligible") is True]
        if not rows: parser.error("No fitting episodes")
        write(args.output, statistics.fit(rows, rows[0]["protocol_hash"]))
    elif args.command == "calibrate":
        rows = [e for e in read(args.data) if e["partition"] == "calibration" and e.get("training_eligible") is True]
        write(args.output, statistics.calibrate(read(args.model), rows, args.alpha, args.delta))
    elif args.command == "evaluate":
        rows = [e for e in read(args.data) if e["partition"] == "test" and e.get("training_eligible") is True]
        write(args.output, statistics.evaluate(read(args.model), read(args.calibration), rows))
    elif args.command == "serve":
        from .server import make_server
        token = os.environ.get("DNHACKS_MONITOR_OPERATOR_TOKEN", "")
        if len(token) < 32: parser.error("Set a separate operator-only token of at least 32 characters")
        make_server(store, token, port=args.port).serve_forever()


if __name__ == "__main__":
    main()
