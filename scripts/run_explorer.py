"""Run the explorer — one curious agent that roams the graph + reads papers, writes and runs its own code
in parallel Docker sandboxes, does divergent tree-search over experiments, and hands good ones to the
verification pipeline WHILE it keeps going (a concurrent worker drains the queue).

  uv run python scripts/run_explorer.py --goal "..." --steps 30           # explore + verify
  uv run python scripts/run_explorer.py --run-id <same> --steps 20 --resume  # continue a stopped run's thread
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from dnhacksbio import llm
from dnhacksbio.webui import jobs
from dnhacksbio.explorer.explorer import (Explorer, goal_from_card, load_corpus_card,
                                            load_session_id)
from dnhacksbio.explorer.sandbox import docker_ok, ensure_image

# Generic fallback goal — used only when no corpus card and no --goal is given. Corpus-specific goals live
# in the corpus card (data/corpora/<name>/corpus_card.md), not here.
DEFAULT_GOAL = ("Explore the knowledge graph and its literature for a GENUINELY NEW, testable relationship "
                "— not a re-confirmation of established biology. Follow intuitions, read papers, design "
                "divergent experiments, and submit the promising ones.")


def _resolve_card(card_arg: str | None, db: str | None) -> str | None:
    """Find the corpus card for this run: an explicit --corpus-card path wins; else infer it from the --db
    path's corpus dir (data/corpora/<name>/corpus_card.md sits next to <name>_kg.duckdb). Returns a path or
    None (fully generic run)."""
    if card_arg:
        if not Path(card_arg).is_file():
            raise SystemExit(f"--corpus-card not found: {card_arg}")
        return card_arg
    if db:
        cand = Path(db).parent / "corpus_card.md"
        if cand.is_file():
            return str(cand)
    return None


async def _run(goal: str, steps: int, interval: float, run_id: str, db: str | None,
               freeze_year: int | None = None, corpus_card: str | None = None, network: str = "none",
               resume: bool = False) -> dict:
    sid = load_session_id("data/processed", run_id) if resume else None
    if resume:
        if sid is None:
            raise SystemExit(f"--resume: no recorded session for run-id {run_id!r}. A run without a "
                             f"recorded session id cannot be resumed, but a NEW run against the same --db "
                             f"still inherits its findings via the exploration log.")
        print(f"resuming {run_id} on session {sid}")
    ex = Explorer(run_id, goal, db_path=db, freeze_year=freeze_year, corpus_card=corpus_card, network=network,
                  resume_sid=sid)
    stop = asyncio.Event()

    async def worker():
        # verify WHILE the explorer keeps exploring: drain the queue periodically (single shared DB
        # connection, single-threaded asyncio -> drains interleave safely between the explorer's awaits)
        while not stop.is_set():
            try:
                ex.vq.drain(run_id)
            except Exception as e:
                print(f"[worker] {type(e).__name__}: {e}")
            await asyncio.sleep(interval)

    w = asyncio.create_task(worker())
    try:
        summary = await ex.run(max_steps=steps)
    finally:
        stop.set()
        await w
        # final drain to catch anything submitted after the worker's last pass
        ex.vq.drain(run_id)
    summary["queue"] = ex.vq.counts()
    ex.close()
    return summary


async def main() -> dict:
    ap = argparse.ArgumentParser()
    ap.add_argument("--goal", default=None, help="the run's goal; if omitted, taken from the corpus card, "
                    "else a generic fallback")
    ap.add_argument("--steps", type=int, default=30)
    ap.add_argument("--interval", type=float, default=5.0, help="seconds between verification-worker drains")
    ap.add_argument("--run-id", default="explorer")
    ap.add_argument("--db", default=None,
                    help="knowledge-graph DuckDB path (default = data/processed/litmap_kg.duckdb)")
    ap.add_argument("--corpus-card", default=None,
                    help="path to a corpus card (data/corpora/<name>/corpus_card.md) — the per-run framing "
                    "(goal, which /data tables are mounted + catalogs, domain notes) injected as CORPUS "
                    "CONTEXT. If omitted, inferred from the --db path's corpus dir.")
    ap.add_argument("--network", choices=("none", "bridge"), default="none",
                    help="sandbox network for experiment code: 'none' (isolated, DEFAULT) or 'bridge' "
                    "(internet — lets experiments fetch papers/public datasets). The container still "
                    "runs non-root with memory/cpu/pids caps; 'bridge' is open egress on your own machine.")
    ap.add_argument("--freeze-year", type=int, default=None,
                    help="the explorer only sees literature published in or before this year")
    ap.add_argument("--resume", action="store_true",
                    help="continue a STOPPED run on its ORIGINAL conversation instead of starting a "
                         "fresh one. Needs the run_id -> session_id recorded by a previous run "
                         "(data/processed/sessions_<root>.json). Findings carry over either way via the "
                         "exploration log; --resume additionally keeps the REASONING THREAD.")
    ap.add_argument("--progress", default="",
                    help="append JSONL progress events here (the console's job stream). Without it the "
                         "run reports only to stdout, which is what the CLI wants.")
    args = ap.parse_args()

    prog = jobs.Progress(args.progress) if args.progress else None

    card_path = _resolve_card(args.corpus_card, args.db)
    card_text = load_corpus_card(card_path)
    goal = args.goal or goal_from_card(card_text) or DEFAULT_GOAL
    if prog:
        # The run id is emitted FIRST, before anything that can fail.
        prog.start("run", f"{goal[:160]}", run_id=args.run_id, steps=args.steps, goal=goal)

    if not docker_ok():
        raise SystemExit("Docker is not reachable (native or via sg). Install/enable Docker first.")
    print("ensuring sandbox image…")
    if prog:
        prog.emit("run", "progress", "preparing the sandbox image", run_id=args.run_id)
    ensure_image()
    if prog:
        prog.emit("run", "progress", f"exploring — up to {args.steps} steps", run_id=args.run_id)

    summary = await _run(goal, args.steps, args.interval, args.run_id, args.db,
                         freeze_year=args.freeze_year, corpus_card=card_path, network=args.network,
                         resume=args.resume)
    usage = llm.LEDGER.summary()
    summary["usage"] = usage
    print(summary)
    if prog:
        prog.emit("finish", "done",
                  f"run complete — {summary.get('steps')} steps, queue {summary.get('queue')}",
                  run_id=args.run_id, summary={"run_id": args.run_id, **summary})
        prog.close()
    return summary


def _fail(msg: str) -> None:
    """Write a terminal `fail` event if this run was launched with a progress stream."""
    path = ""
    argv = sys.argv
    for i, a in enumerate(argv):
        if a == "--progress" and i + 1 < len(argv):
            path = argv[i + 1]
        elif a.startswith("--progress="):
            path = a.split("=", 1)[1]
    if not path:
        return
    p = jobs.Progress(path)
    p.emit("fail", "error", msg[:2000])
    p.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except SystemExit as exc:
        _fail(str(exc) or "the run exited early")
        raise
    except BaseException as exc:
        _fail(f"{type(exc).__name__}: {exc}")
        raise
