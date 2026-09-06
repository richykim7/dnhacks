"""Resumable, monitored frozen full-text extraction with ten concurrent papers."""
from __future__ import annotations

import argparse
import asyncio
from contextlib import closing
import dataclasses
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
READER = "claude-opus-4-8"
REPAIR = "claude-sonnet-5"


class ServiceUnavailable(RuntimeError):
    """A model service failure; never an unsupported scientific finding."""


def serial(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    raise TypeError(type(value).__name__)


def save(path, value):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, default=serial, indent=2))
    tmp.replace(path)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(root, manifest):
    for name, expected in manifest["files_sha256"].items():
        if digest(root / name) != expected:
            raise RuntimeError(f"Frozen source changed: {name}")


async def worker(args, manifest):
    from claude_agent_sdk import ClaudeSDKClient, AssistantMessage, TextBlock, ResultMessage
    from dnhacksbio import llm
    from dnhacksbio.litmap import extract, grounding
    implementation_hashes = {p.name: digest(p) for p in Path(extract.__file__).parent.glob("*.py")}

    paper = next(p for p in manifest["papers"] if p["ref"] == args.ref)
    output = args.run / f"{args.ref:03d}"
    output.mkdir(exist_ok=True)
    with (output / "worker.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (output / "result.json").exists():
            return
        grounding.LEXDIR = str(args.lexicons)
        grounding.NCIT_LEXICON = str(args.lexicons.parent / "ncit_lexicon.json")
        text = (args.corpus / paper["text_file"]).read_text()
        expected = manifest["files_sha256"][paper["text_file"]]
        if hashlib.sha256(text.encode()).hexdigest() != expected:
            raise RuntimeError("Source hash mismatch")
        empty = output / "empty"
        empty.mkdir(exist_ok=True)
        original_opts = llm._opts

        def opts(*a, **kw):
            kw.update(tools_disabled=True, cwd=str(empty))
            result = original_opts(*a, **kw)
            result.skills = []
            result.mcp_servers = {}
            result.strict_mcp_config = True
            result.settings = json.dumps({"disableAllHooks": True})
            result.extra_args = {"no-session-persistence": None, "disable-slash-commands": None}
            return result

        def record(value):
            with (output / "transcript.jsonl").open("a") as handle:
                handle.write(json.dumps({"time": time.time(), **value}) + "\n")

        class Client(ClaudeSDKClient):
            def __init__(self, *a, **kw):
                self.expected_model = (a[0] if a else kw["options"]).model
                self.reader_candidate = None
                super().__init__(*a, **kw)

            async def receive_response(self):
                stream = super().receive_response()
                while True:
                    try:
                        msg = await asyncio.wait_for(anext(stream), timeout=600 if self.expected_model == READER else 300)
                    except StopAsyncIteration:
                        break
                    except asyncio.TimeoutError as exc:
                        raise ServiceUnavailable("Model session stopped producing responses before its idle timeout") from exc
                    if isinstance(msg, AssistantMessage):
                        record({"type": "assistant", "model": msg.model,
                                "text": [b.text for b in msg.content if isinstance(b, TextBlock)]})
                        if msg.model != self.expected_model:
                            if msg.model == "<synthetic>":
                                message = "\n".join(b.text for b in msg.content if isinstance(b, TextBlock))
                                raise ServiceUnavailable(message or "Model service returned a synthetic error")
                            raise RuntimeError(f"Model mismatch: {msg.model} != {self.expected_model}")
                        if msg.model == READER:
                            try:
                                raw = extract._parse("\n".join(b.text for b in msg.content if isinstance(b, TextBlock)))
                                if "claims" in raw and not raw.get("_salvaged"):
                                    self.reader_candidate = raw
                            except extract.DeferralError:
                                pass
                    elif isinstance(msg, ResultMessage):
                        record({"type": "result", "model": self.expected_model,
                                "usage": msg.usage, "cost": msg.total_cost_usd, "error": msg.is_error})
                        if msg.is_error:
                            raise ServiceUnavailable(f"Model service error: {msg.result}")
                        if self.expected_model == READER:
                            if (msg.usage or {}).get("output_tokens", 0) >= llm.MAX_OUTPUT_TOKENS:
                                raise RuntimeError("Reader output truncated")
                            if self.reader_candidate is not None:
                                save(output / "reader.json", self.reader_candidate)
                                save(output / "reader-metadata.json", {"source_sha256": expected,
                                     "model": READER, "completed": True})
                    yield msg

        llm._opts = opts
        llm.ClaudeSDKClient = Client
        extract.PROGRESS = lambda ref, stage: print(time.strftime("%H:%M:%S"), ref, stage, flush=True)
        raw_path = output / "reader.json"
        raw = json.loads(raw_path.read_text()) if raw_path.exists() else None
        if raw and raw.get("_salvaged"):
            raise RuntimeError("Incomplete reader checkpoint requires inspection")
        start = time.time()
        result = await extract.extract_paper(
            text, source_ref=args.ref, source_label=f"Paper{args.ref}_{paper['year']}",
            field=(args.corpus / "prompt.txt").read_text(), model=READER,
            repair_model=REPAIR, raw_extraction=raw)
        if result["stats"].get("pass1_failed") or not result.get("raw_extraction"):
            raise RuntimeError("Reader parse failure; paper remains incomplete")
        try:
            validate_result(result, args.ref)
        except ServiceUnavailable:
            save(output / "incomplete-result.json", {**result, "source_ref": args.ref, "source_sha256": expected})
            raise
        if not result["claims"]:
            raise RuntimeError("Zero retained claims requires inspection")
        result.update(source_ref=args.ref, source_sha256=expected, elapsed_seconds=time.time() - start,
                      implementation_commit=args.commit, runner_sha256=args.runner_sha256,
                      implementation_hashes=implementation_hashes, usage=llm.LEDGER.summary())
        result["source_metadata"] = {k: paper.get(k) for k in
            ("ref", "doi", "pmid", "pmcid", "title", "year", "publication_date", "text_file", "markdown_file")}
        save(output / "result.json", result)
        print("COMPLETE", args.ref, result["stats"], flush=True)


def validate_result(result, ref):
    from dnhacksbio.litmap.schema import Claim, Experiment, Deferral
    if result.get("source_ref", ref) != ref:
        raise RuntimeError("Wrong source in result")
    if result.get("raw_extraction", {}).get("_salvaged"):
        raise RuntimeError("Salvaged reader output requires inspection")
    metadata = result.get("extraction_metadata", {})
    if metadata.get("reader_model") != READER or metadata.get("repair_model") != REPAIR:
        raise RuntimeError("Unexpected extraction model metadata")
    claims = [c if isinstance(c, Claim) else Claim.model_validate(c) for c in result["claims"]]
    experiments = [e if isinstance(e, Experiment) else Experiment.model_validate(e) for e in result["experiments"]]
    deferrals = [d if isinstance(d, Deferral) else Deferral.model_validate(d) for d in result["deferrals"]]
    unavailable = [d.reason for d in deferrals if "Repair unavailable:" in d.reason]
    if unavailable:
        raise ServiceUnavailable(unavailable[0])
    ids = {e.experiment_id for e in experiments}
    if any(e.source_ref != ref for e in experiments) or any(d.source_ref != ref for d in deferrals):
        raise RuntimeError("Wrong source in experiment or deferral")
    if any("pass 1 truncated" in d.reason for d in deferrals):
        raise RuntimeError("Incomplete reader extraction")
    for claim in claims:
        if not claim.evidence:
            raise RuntimeError("Claim has no evidence")
        for ev in claim.evidence:
            if ev.source_ref != ref or ev.claim_id != claim.claim_id:
                raise RuntimeError("Evidence source or claim mismatch")
            if ev.experiment_id and ev.experiment_id not in ids:
                raise RuntimeError("Evidence experiment missing")
    return claims, experiments, deferrals


def publish(args, manifest):
    from dnhacksbio.litmap.store import KGStore
    from dnhacksbio.litmap.schema import Claim, Experiment, Deferral

    target = args.corpus / "pdac-frozen_kg.duckdb"
    if Path(str(target) + ".wal").exists():
        raise RuntimeError("Target has active WAL; cannot replace safely")
    backup = args.run / "before-ingestion.duckdb"
    if not backup.exists():
        shutil.copy2(target, backup)
    staged = args.run / "publishing.duckdb"
    shutil.copy2(target, staged)
    store = KGStore(staged)
    try:
        store.con.execute("CREATE TABLE IF NOT EXISTS ingestion_imports (source_ref INTEGER PRIMARY KEY, result_sha256 VARCHAR)")
        for paper in manifest["papers"]:
            path = args.run / f"{paper['ref']:03d}" / "result.json"
            if not path.exists():
                continue
            result_hash = digest(path)
            imported = store.con.execute("SELECT result_sha256 FROM ingestion_imports WHERE source_ref = ?", [paper["ref"]]).fetchone()
            if imported and imported[0] == result_hash:
                continue
            result = json.loads(path.read_text())
            if result["source_sha256"] != manifest["files_sha256"][paper["text_file"]]:
                raise RuntimeError("Stale extraction source")
            claims, experiments, deferrals = validate_result(result, paper["ref"])
            store.con.execute("BEGIN")
            try:
                store.write_paper(paper["ref"], claims, experiments, deferrals)
                store.con.execute("INSERT OR REPLACE INTO ingestion_imports VALUES (?, ?)", [paper["ref"], result_hash])
                store.con.execute("COMMIT")
            except Exception:
                store.con.execute("ROLLBACK")
                raise
        counts = {**store.refresh_status(), **store.graph.counts()}
        missing = store.con.execute("SELECT count(*) FROM evidence e LEFT JOIN claims c USING(claim_id) WHERE c.claim_id IS NULL").fetchone()[0]
        if missing:
            raise RuntimeError("Orphan evidence")
        store.con.execute("CHECKPOINT")
    finally:
        store.close()
    # Closed snapshot, same-filesystem atomic rename: frontend never reads a half-written graph.
    ready = target.with_suffix(".next.duckdb")
    shutil.copy2(staged, ready)
    os.replace(ready, target)
    save(args.run / "graph-counts.json", counts)
    return counts


async def coordinator(args, manifest):
    from dnhacksbio.litmap.timeline import TimelineRecorder
    verify(args.corpus, manifest)
    with (args.run / "coordinator.lock").open("w") as lock, closing(TimelineRecorder(args.run)) as timeline:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        identity = {"reader": READER, "repair": REPAIR,
                    "manifest_sha256": digest(args.corpus / "MANIFEST.json")}
        if (args.run / "run.json").exists():
            previous = json.loads((args.run / "run.json").read_text())
            if any(previous.get(k) != v for k, v in identity.items()):
                raise RuntimeError("Existing run belongs to another corpus or model configuration")
        save(args.run / "run.json", {**identity, "concurrency": 10, "scheduling": "rolling",
                                    "commit": args.commit, "runner_sha256": digest(Path(__file__))})
        timeline.event("ingestion_started", [identity["manifest_sha256"], "rolling"],
                       {**identity, "concurrency": 10, "scheduling": "rolling"})
        papers = manifest["papers"]
        completed_refs = set()
        failures = []

        def record_completed(paper):
            path = args.run / f"{paper['ref']:03d}" / "result.json"
            result = json.loads(path.read_text())
            validate_result(result, paper["ref"])
            if result["source_sha256"] != manifest["files_sha256"][paper["text_file"]]:
                raise RuntimeError("Stale extraction source")
            timeline.paper_completed(paper["ref"], result,
                timestamp=path.stat().st_mtime, timestamp_basis="result_file_mtime")
            completed_refs.add(paper["ref"])

        queued = []
        for paper in papers:
            output = args.run / f"{paper['ref']:03d}"
            output.mkdir(exist_ok=True)
            if (output / "result.json").exists():
                record_completed(paper)
            else:
                queued.append(paper)

        async def one(paper):
            output = args.run / f"{paper['ref']:03d}"
            for attempt in range(1, 3):
                timeline.event("paper_started", [paper["ref"], attempt, time.time()],
                               {"paper_ref": paper["ref"], "attempt": attempt})
                command = [sys.executable, str(Path(__file__).resolve()), "--corpus", str(args.corpus),
                           "--run", str(args.run), "--lexicons", str(args.lexicons), "--ref", str(paper["ref"])]
                with (output / f"worker-{attempt}.log").open("a") as log:
                    proc = await asyncio.create_subprocess_exec(*command, stdout=log, stderr=log)
                    try:
                        code = await asyncio.wait_for(proc.wait(), timeout=2400)
                    except (asyncio.TimeoutError, asyncio.CancelledError) as exc:
                        proc.terminate()
                        try:
                            await asyncio.wait_for(proc.wait(), timeout=5)
                        except asyncio.TimeoutError:
                            proc.kill()
                            await proc.wait()
                        if isinstance(exc, asyncio.CancelledError):
                            raise
                        code = -1
                print("PAPER_EXIT", paper["ref"], "attempt", attempt, "code", code, flush=True)
                if code == 0 and (output / "result.json").exists():
                    record_completed(paper)
                    return
                timeline.event("paper_failed", [paper["ref"], attempt, time.time()],
                               {"paper_ref": paper["ref"], "attempt": attempt, "exit_code": code})
                if code == 75:
                    raise RuntimeError(f"Paper {paper['ref']}: model service unavailable; queued work halted")
            raise RuntimeError(f"Paper {paper['ref']} failed twice; queued work halted")

        pending = set()
        waiting = iter(queued)

        def fill_pool():
            while len(pending) < 10:
                paper = next(waiting, None)
                if paper is None:
                    break
                pending.add(asyncio.create_task(one(paper)))

        def publish_progress():
            # A worker may have atomically saved its result just before its exit notification.
            # Record and validate every artifact the snapshot writer is about to include.
            for paper in papers:
                path = args.run / f"{paper['ref']:03d}" / "result.json"
                if paper['ref'] not in completed_refs and path.exists():
                    record_completed(paper)
            counts = publish(args, manifest)
            timeline.published(args.corpus / "pdac-frozen_kg.duckdb")
            save(args.run / "progress.json", {"scheduling": "rolling", "concurrency": 10,
                 "counts": counts, "completed": len(completed_refs), "total": len(papers),
                 "active": len(pending), "failures": failures})
            print("POOL_PROGRESS", len(completed_refs), "/", len(papers), counts,
                  "failures", failures, flush=True)

        try:
            if completed_refs:
                publish_progress()
            fill_pool()
            while pending:
                finished, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                for task in finished:
                    error = task.exception()
                    if error is not None:
                        failures.append(str(error))
                if not failures:
                    fill_pool()
                    # Start replacements immediately before the single writer publishes a snapshot.
                    await asyncio.sleep(0)
                publish_progress()
            if failures:
                raise RuntimeError("; ".join(failures))
            verify(args.corpus, manifest)
            timeline.event("ingestion_completed", identity["manifest_sha256"], {"papers": len(papers)})
            print("INGESTION_COMPLETE", flush=True)
        except BaseException as exc:
            timeline.event("ingestion_failed", [time.time(), type(exc).__name__],
                           {"error_type": type(exc).__name__, "error": str(exc),
                            "completed": len(completed_refs)})
            raise
        finally:
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--lexicons", type=Path, required=True)
    parser.add_argument("--ref", type=int)
    args = parser.parse_args()
    args.corpus = args.corpus.resolve()
    args.run = args.run.resolve()
    args.run.mkdir(parents=True, exist_ok=True)
    args.commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parents[1], text=True).strip()
    args.runner_sha256 = digest(Path(__file__))
    manifest = json.loads((args.corpus / "MANIFEST.json").read_text())
    try:
        asyncio.run(worker(args, manifest) if args.ref else coordinator(args, manifest))
    except ServiceUnavailable as exc:
        if args.ref:
            save(args.run / f"{args.ref:03d}" / "service-error.json",
                 {"service_unavailable": True, "message": str(exc), "time": time.time(),
                  "quota": any(word in str(exc).lower() for word in ("limit", "quota", "credit"))})
        print("SERVICE_UNAVAILABLE", str(exc), flush=True)
        raise SystemExit(75)
