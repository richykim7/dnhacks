"""Standard corpus builds record replay data automatically, without an observer."""
import asyncio
import hashlib
import json

import pytest

from dnhacksbio.litmap import corpus_build, extract
from dnhacksbio.litmap.find import Candidate
from dnhacksbio.litmap.schema import Claim, ClaimSpine, EntityRef, Evidence
from dnhacksbio.webui.jobs import Progress


@pytest.fixture
def prepared_build(tmp_path, monkeypatch):
    spec = {"queries": ["test"], "theme": "test biology", "n_papers": 3,
            "concurrency": 3, "seed_dois": [], "exclude_terms": [],
            "year_min": None, "year_max": None, "full_text_only": True}
    papers = [Candidate(key=f"10.1000/{ref}", doi=f"10.1000/{ref}", title=f"Study {ref}",
                        year=2020, channels={"test"}) for ref in (1, 2, 3)]
    text = "EGFR increases KRAS activity. " * 12
    monkeypatch.setattr(corpus_build.projects, "load", lambda pid: {"name": "Test", "spec": spec})
    monkeypatch.setattr(corpus_build.projects, "validate_spec", lambda value, **kw: value)
    monkeypatch.setattr(corpus_build.projects, "project_dir", lambda pid: tmp_path)
    monkeypatch.setattr(corpus_build.projects, "kg_path", lambda pid: tmp_path / "graph.duckdb")
    monkeypatch.setattr(corpus_build.projects, "write_corpus_card", lambda pid: tmp_path / "card.md")
    monkeypatch.setattr(corpus_build.find, "europepmc_search", lambda *a, **kw: papers)
    monkeypatch.setattr(corpus_build.find, "openalex_search", lambda *a, **kw: [])
    monkeypatch.setattr(corpus_build, "_attachment_documents", lambda *a: ([], []))
    monkeypatch.setattr(corpus_build, "_rank_by_theme", lambda candidates, *a: candidates)
    monkeypatch.setattr(corpus_build, "_fetch_selected", lambda *a: [
        (p, {"text": text, "is_full_text": True, "source": "txt"}) for p in papers])
    return tmp_path, text


def successful_result(ref, label):
    spine = ClaimSpine(subject=EntityRef(curie="HGNC:3236", label="EGFR"),
                       object=EntityRef(curie="HGNC:6407", label="KRAS"),
                       predicate="increases", object_aspect="activity")
    claim = Claim(spine=spine, evidence=[Evidence(claim_id=spine.claim_id(), source_ref=ref,
                  source_label=label, quote="EGFR increases KRAS activity.")])
    return {"claims": [claim], "experiments": [], "deferrals": [], "stats": {"kept": 1}}


def run_build(root):
    progress = Progress(root / "progress.jsonl")
    try:
        return asyncio.run(corpus_build.build("test", progress))
    finally:
        progress.close()


def events(root):
    paths = list(root.glob("extraction_audits/*/timeline/events.jsonl"))
    assert len(paths) == 1
    return paths[0], [json.loads(line) for line in paths[0].read_text().splitlines()]


def test_build_records_success_failure_metadata_and_publication(prepared_build, monkeypatch):
    root, text = prepared_build

    async def fake_extract(text, *, source_ref, source_label, **kw):
        if source_ref == 2:
            raise RuntimeError("simulated worker failure")
        if source_ref == 3:
            return {"claims": [], "experiments": [], "deferrals": [], "stats": {"pass1_failed": True}}
        return successful_result(source_ref, source_label)

    monkeypatch.setattr(extract, "extract_paper", fake_extract)
    summary = run_build(root)
    path, recorded = events(root)
    assert summary["n_claims"] == 1
    assert len([e for e in recorded if e["type"] == "paper_started"]) == 3
    failures = [e for e in recorded if e["type"] == "paper_failed"]
    assert {e["source_ref"] for e in failures} == {2, 3}
    assert {e["error_type"] for e in failures} == {"RuntimeError", "ReaderParseFailure"}
    completed = [e for e in recorded if e["type"] == "paper_completed"]
    assert len(completed) == 1
    metadata = completed[0]["result"]["source_metadata"]
    assert metadata["doi"] == "10.1000/1"
    assert metadata["title"] == "Study 1" and metadata["year"] == 2020
    assert metadata["source_sha256"] == hashlib.sha256(text.encode()).hexdigest()
    assert completed[0]["timestamp_basis"] == "ingestion_wall_clock"
    assert not completed[0]["recovered"]
    published = next(e for e in recorded if e["type"] == "graph_published")
    assert published["counts"]["claims"] == 1
    assert published["timestamp"] >= completed[0]["timestamp"]
    snapshot_event = next(e for e in recorded if e["type"] == "graph_published_observed")
    snapshot = json.loads((path.parent / snapshot_event["snapshot"]).read_text())
    assert len(snapshot["tables"]["papers"]) == 3
    assert len(snapshot["tables"]["evidence"]) == 1


def test_build_failure_records_error_without_publication(prepared_build, monkeypatch):
    root, _ = prepared_build

    async def fail(*a, **kw):
        raise RuntimeError("simulated service failure")

    monkeypatch.setattr(extract, "extract_paper", fail)
    with pytest.raises(corpus_build.BuildError, match="zero claims"):
        run_build(root)
    path, recorded = events(root)
    assert len([e for e in recorded if e["type"] == "paper_failed"]) == 3
    assert recorded[-1]["type"] == "ingestion_failed"
    assert not any(e["type"] in {"graph_published", "paper_completed"} for e in recorded)
    # Failed builds release the writer lock so the recorded history remains usable.
    from dnhacksbio.litmap.timeline import TimelineRecorder
    recorder = TimelineRecorder(path.parent.parent)
    recorder.close()
