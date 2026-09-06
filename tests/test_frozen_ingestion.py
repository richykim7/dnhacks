"""Exercise frozen ingestion publication using real DuckDB files, without model calls."""
import importlib.util
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest

from dnhacksbio.explorer.fulltext import FullTextStore
from dnhacksbio.litmap.schema import Claim, ClaimSpine, EntityRef, Evidence, Experiment
from dnhacksbio.litmap.store import KGStore


@pytest.fixture
def runner():
    path = Path(__file__).resolve().parents[1] / "scripts" / "ingest_frozen_corpus.py"
    spec = importlib.util.spec_from_file_location("frozen_ingestion_test_runner", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def extraction(runner, ref=1):
    spine = ClaimSpine(subject=EntityRef(curie="HGNC:11998", label="TP53"),
                       predicate="increases", object=EntityRef(curie="HGNC:1784", label="CDKN1A"),
                       object_aspect="abundance")
    experiment = Experiment(experiment_id=f"E{ref}.fixture", source_ref=ref,
                            quote="TP53 increases CDKN1A abundance.")
    claim = Claim(spine=spine, evidence=[Evidence(
        claim_id=spine.claim_id(), source_ref=ref, source_label=f"Paper{ref}_2020",
        experiment_id=experiment.experiment_id, quote=experiment.quote)])
    return {"source_ref": ref, "source_sha256": f"hash-{ref}",
            "raw_extraction": {"claims": [{"subject": "TP53"}]},
            "extraction_metadata": {"reader_model": runner.READER, "repair_model": runner.REPAIR},
            "claims": [claim.model_dump(mode="json")],
            "experiments": [experiment.model_dump(mode="json")], "deferrals": []}


@pytest.fixture
def corpus(tmp_path, runner):
    args = SimpleNamespace(corpus=tmp_path / "corpus", run=tmp_path / "run")
    args.corpus.mkdir()
    args.run.mkdir()
    target = args.corpus / "pdac-frozen_kg.duckdb"
    store = KGStore(target)
    try:
        fulltext = FullTextStore(con=store.con)
        for ref in (1, 2):
            fulltext.add_paper(source_ref=ref, title=f"Source {ref}", doi=f"10.1000/{ref}",
                               text="TP53 increases CDKN1A abundance.", is_full_text=True)
    finally:
        store.close()
    manifest = {"papers": [{"ref": ref, "text_file": f"{ref}.txt"} for ref in (1, 2)],
                "files_sha256": {f"{ref}.txt": f"hash-{ref}" for ref in (1, 2)}}
    return args, manifest, target


def write_result(runner, args, result):
    folder = args.run / f"{result['source_ref']:03d}"
    folder.mkdir(exist_ok=True)
    runner.save(folder / "result.json", result)


def test_unavailable_repair_is_incomplete_work_not_scientific_deferral(runner):
    result = extraction(runner)
    result["deferrals"] = [{"source_ref": 1,
        "reason": "Repair unavailable: session limit resets at 3:30am"}]
    with pytest.raises(runner.ServiceUnavailable, match="session limit"):
        runner.validate_result(result, 1)


def test_publish_retry_preserves_fulltext_and_independent_source_support(runner, corpus):
    args, manifest, target = corpus
    write_result(runner, args, extraction(runner, 1))
    first = runner.publish(args, manifest)
    assert (first["claims"], first["evidence"]) == (1, 1)
    write_result(runner, args, extraction(runner, 2))
    second = runner.publish(args, manifest)
    retry = runner.publish(args, manifest)
    assert second == retry
    assert (retry["claims"], retry["evidence"], retry["experiments"], retry["papers"]) == (1, 2, 2, 2)
    with duckdb.connect(str(target), read_only=True) as con:
        assert con.execute("SELECT count(*), count(DISTINCT source_ref) FROM papers").fetchone() == (2, 2)
        assert con.execute("SELECT min(n_sources), min(first_year) FROM claim_edges").fetchone() == (2, 2020)
        assert con.execute("SELECT count(*) FROM evidence e JOIN experiments x "
                           "ON e.experiment_id=x.experiment_id AND e.source_ref=x.source_ref").fetchone()[0] == 2


def test_failed_staged_write_keeps_published_graph_and_can_retry(runner, corpus, monkeypatch):
    args, manifest, target = corpus
    write_result(runner, args, extraction(runner, 1))
    runner.publish(args, manifest)
    published_hash = runner.digest(target)
    write_result(runner, args, extraction(runner, 2))
    real_write = KGStore.write_paper

    def fail_after_writing(self, source_ref, *a, **kw):
        result = real_write(self, source_ref, *a, **kw)
        if source_ref == 2:
            raise RuntimeError("injected post-insert failure")
        return result

    with monkeypatch.context() as patch:
        patch.setattr(KGStore, "write_paper", fail_after_writing)
        with pytest.raises(RuntimeError, match="injected"):
            runner.publish(args, manifest)
    assert runner.digest(target) == published_hash
    with duckdb.connect(str(args.run / "publishing.duckdb"), read_only=True) as con:
        assert con.execute("SELECT DISTINCT source_ref FROM evidence").fetchall() == [(1,)]
    assert runner.publish(args, manifest)["evidence"] == 2


@pytest.mark.parametrize("fault, message", [
    ("result_source", "Wrong source"),
    ("evidence_source", "Evidence source"),
    ("claim_id", "claim mismatch"),
    ("experiment_source", "Wrong source"),
    ("missing_experiment", "experiment missing"),
    ("empty_evidence", "no evidence"),
    ("truncated", "Incomplete reader"),
    ("salvaged", "Salvaged reader"),
    ("wrong_model", "model metadata"),
])
def test_validate_result_rejects_incomplete_or_inconsistent_records(runner, fault, message):
    result = extraction(runner)
    evidence = result["claims"][0]["evidence"][0]
    if fault == "result_source":
        result["source_ref"] = 2
    elif fault == "evidence_source":
        evidence["source_ref"] = 2
    elif fault == "claim_id":
        evidence["claim_id"] = "wrong-claim"
    elif fault == "experiment_source":
        result["experiments"][0]["source_ref"] = 2
    elif fault == "missing_experiment":
        result["experiments"] = []
    elif fault == "empty_evidence":
        result["claims"][0]["evidence"] = []
    elif fault == "truncated":
        result["deferrals"] = [{"source_ref": 1, "reason": "pass 1 truncated; paper extraction is incomplete"}]
    elif fault == "salvaged":
        result["raw_extraction"]["_salvaged"] = "invalid JSON"
    elif fault == "wrong_model":
        result["extraction_metadata"]["reader_model"] = "another-model"
    with pytest.raises(RuntimeError, match=message):
        runner.validate_result(result, 1)


def test_coordinator_replaces_finished_paper_while_first_is_slow_and_resumes(runner, corpus, monkeypatch):
    args, _, target = corpus
    args.lexicons = args.corpus / "lexicons"
    args.commit = "test-implementation"
    manifest = {"papers": [], "files_sha256": {}}
    for ref in range(1, 13):
        name = f"{ref}.txt"
        (args.corpus / name).write_text("TP53 increases CDKN1A abundance.")
        manifest["papers"].append({"ref": ref, "text_file": name})
        manifest["files_sha256"][name] = runner.digest(args.corpus / name)
    runner.save(args.corpus / "MANIFEST.json", manifest)
    active = set()
    completed = set()
    launched = []
    maximum_active = 0
    first_wave_ready = None
    release_slow = None

    async def fake_subprocess(*command, **kwargs):
        nonlocal first_wave_ready, release_slow, maximum_active
        ref = int(command[command.index("--ref") + 1])
        if first_wave_ready is None:
            first_wave_ready = asyncio.Event()
            release_slow = asyncio.Event()
        active.add(ref)
        launched.append(ref)
        maximum_active = max(maximum_active, len(active))
        assert len(active) <= 10
        if len(launched) == 10:
            first_wave_ready.set()
        if ref == 11:
            assert 1 in active and 1 not in completed, "slow first paper blocked replacement"
            release_slow.set()

        async def wait():
            await first_wave_ready.wait()
            if ref == 1:
                await release_slow.wait()
            await asyncio.sleep(0)
            result = extraction(runner, ref)
            result["source_sha256"] = manifest["files_sha256"][f"{ref}.txt"]
            write_result(runner, args, result)
            active.remove(ref)
            completed.add(ref)
            return 0

        return SimpleNamespace(wait=wait)

    monkeypatch.setattr(runner.asyncio, "create_subprocess_exec", fake_subprocess)
    real_publish = runner.publish
    publication_sizes = []

    def publish_after_replay(args, manifest):
        rows = [json.loads(line) for line in
                (args.run / "timeline" / "events.jsonl").read_text().splitlines()]
        replay = [e for e in rows if e["type"] == "replay_materialized"][-1]
        snapshot = json.loads((args.run / "timeline" / replay["snapshot"]).read_text())
        assert set(map(int, snapshot["results"])) == completed
        publication_sizes.append(len(completed))
        return real_publish(args, manifest)

    monkeypatch.setattr(runner, "publish", publish_after_replay)
    asyncio.run(asyncio.wait_for(runner.coordinator(args, manifest), timeout=30))
    assert launched == list(range(1, 13))
    assert maximum_active == 10
    assert publication_sizes[-1] == 12
    assert publication_sizes[0] < 12
    assert not active

    async def no_new_workers(*a, **kw):
        pytest.fail("resume must reuse completed results")

    monkeypatch.setattr(runner.asyncio, "create_subprocess_exec", no_new_workers)
    monkeypatch.setattr(runner, "publish", real_publish)
    asyncio.run(runner.coordinator(args, manifest))
    rows = [json.loads(line) for line in (args.run / "timeline" / "events.jsonl").read_text().splitlines()]
    assert len([e for e in rows if e["type"] == "paper_completed"]) == 12
    assert any(e["type"] == "ingestion_completed" for e in rows)
    with duckdb.connect(str(target), read_only=True) as con:
        assert con.execute("SELECT count(*), count(DISTINCT source_ref) FROM evidence").fetchone() == (12, 12)


def test_quota_exit_stops_queued_work_without_retry_and_drains_active(runner, corpus, monkeypatch):
    args, _, target = corpus
    args.lexicons = args.corpus / "lexicons"
    args.commit = "test-implementation"
    manifest = {"papers": [{"ref": ref, "text_file": f"{ref}.txt"} for ref in range(1, 13)],
                "files_sha256": {f"{ref}.txt": f"hash-{ref}" for ref in range(1, 13)}}
    runner.save(args.corpus / "MANIFEST.json", manifest)
    monkeypatch.setattr(runner, "verify", lambda *a: None)
    launched = []
    gate = None

    async def fake_subprocess(*command, **kwargs):
        nonlocal gate
        if gate is None:
            gate = asyncio.Event()
        ref = int(command[command.index("--ref") + 1])
        launched.append(ref)
        if len(launched) == 10:
            gate.set()

        async def wait():
            await gate.wait()
            if ref == 1:
                return 75
            await asyncio.sleep(0)
            write_result(runner, args, extraction(runner, ref))
            return 0

        return SimpleNamespace(wait=wait)

    monkeypatch.setattr(runner.asyncio, "create_subprocess_exec", fake_subprocess)
    with pytest.raises(RuntimeError, match="service unavailable"):
        asyncio.run(asyncio.wait_for(runner.coordinator(args, manifest), timeout=30))
    assert launched == list(range(1, 11))
    assert not (args.run / "001" / "result.json").exists()
    progress = json.loads((args.run / "progress.json").read_text())
    assert progress["completed"] == 9 and progress["active"] == 0
    assert progress["failures"]
    with duckdb.connect(str(target), read_only=True) as con:
        assert con.execute("SELECT count(*) FROM evidence").fetchone()[0] == 9
