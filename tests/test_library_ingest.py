"""Private-data membership worker checks. No models, downloads or live graphs."""
import asyncio
import json

import pytest

from dnhacksbio.webui import projects, attachments
from dnhacksbio.litmap import library_ingest as worker
from dnhacksbio.litmap.store import KGStore
from dnhacksbio.litmap.schema import Claim, ClaimSpine, EntityRef, Evidence


class Progress:
    def __init__(self):
        self.events = []

    def start(self, *args, **kwargs):
        self.events.append((args, kwargs))

    done = error = start


@pytest.fixture
def private(tmp_path, monkeypatch):
    monkeypatch.setattr(projects, "PROJECTS", tmp_path / "projects")
    monkeypatch.setattr(projects, "CORPORA", tmp_path / "corpora")
    from dnhacksbio.explorer import embed
    monkeypatch.setattr(embed, "embed", lambda texts: [[1.0, 0.5] for _ in texts])
    monkeypatch.setattr(embed, "embed_one", lambda text: [1.0, 0.5])
    return projects.create("Private ingest check")["id"]


def extraction(ref):
    spine = ClaimSpine(subject=EntityRef(curie="HGNC:1", label="A"), predicate="increases",
                       object=EntityRef(curie="GO:0008283", label="proliferation", kind="process"))
    claim = Claim(spine=spine, evidence=[Evidence(claim_id=spine.claim_id(), source_ref=ref,
                                              quote="A increases proliferation.")])
    return {"claims": [claim], "experiments": [], "deferrals": [], "stats": {}}


def test_upload_retry_reuses_extraction_and_duplicate_keeps_existing(private, monkeypatch):
    from dnhacksbio.litmap import extract
    calls = []
    async def fake(text, **kwargs):
        calls.append(kwargs["source_ref"])
        return extraction(kwargs["source_ref"])
    monkeypatch.setattr(extract, "extract_paper", fake)
    upload = attachments.add(private, "paper.txt", ("A increases proliferation. " * 30).encode())
    item = {"ref": 10000, "attachment_id": upload["id"]}
    original = KGStore.embed_claims
    monkeypatch.setattr(KGStore, "embed_claims", lambda self: {"n_failed": 1})
    failed = asyncio.run(worker.ingest(private, [item], Progress()))
    assert failed["failed"][0]["stage"] == "index"
    monkeypatch.setattr(KGStore, "embed_claims", original)
    retried = asyncio.run(worker.ingest(private, [item], Progress()))
    assert retried["added"] == 1
    assert calls == [10000]
    duplicate = asyncio.run(worker.ingest(private, [{**item, "ref": 10001}], Progress()))
    assert duplicate["duplicates"] == 1
    assert calls == [10000]
    store = KGStore(projects.kg_path(private))
    try:
        assert store.con.execute("SELECT count(*) FROM papers").fetchone()[0] == 1
        assert store.con.execute("SELECT count(*) FROM evidence").fetchone()[0] == 1
        assert store.con.execute("SELECT count(*) FROM claim_vectors").fetchone()[0] == 1
    finally:
        store.close()


def test_doi_fulltext_cache_and_figures(private, monkeypatch):
    from dnhacksbio.litmap import find, extract
    root = projects.project_dir(private)
    candidate = find.Candidate(key="10.1234/paper", doi="10.1234/paper", title="A paper")
    monkeypatch.setattr(find, "openalex_by_doi", lambda doi: candidate)
    fetched = []
    def fetch(c, artifact_root):
        fetched.append(c.doi)
        dest = find._artifact_dir(artifact_root, c)
        (dest / "figure.png").write_bytes(b"private-test-image")
        return {"text": "A paper. " * 50, "is_full_text": True,
                "figures": [{"path": "figure.png", "label": "Figure 1"}]}
    monkeypatch.setattr(find, "fetch_fulltext", fetch)
    async def fake(text, **kw):
        return extraction(kw["source_ref"])
    monkeypatch.setattr(extract, "extract_paper", fake)
    item = {"ref": 1, "doi": "10.1234/paper"}
    assert not asyncio.run(worker.ingest(private, [item], Progress()))["failed"]
    assert not asyncio.run(worker.ingest(private, [item], Progress()))["failed"]
    assert fetched == ["10.1234/paper"]
    meta = json.loads((root / "MANIFEST.json").read_text())["papers"][0]
    assert (root / meta["figures"][0]["path"]).is_file()


def test_reject_external_graph_before_processing(private, monkeypatch):
    rec = projects.load(private)
    rec["kg_db"] = "/tmp/not-this-collection.duckdb"
    monkeypatch.setattr(projects, "load", lambda pid: rec)
    with pytest.raises(ValueError, match="private collection"):
        asyncio.run(worker.ingest(private, [{"ref": 1, "doi": "10.1234/paper"}], Progress()))


def test_removed_ref_is_not_resurrected_by_retry(private, monkeypatch):
    rec = projects.load(private)
    rec["membership_removed_refs"] = [23]
    projects.save(rec)
    monkeypatch.setattr(worker, "_source", lambda *args: pytest.fail("removed ref acquired"))
    result = asyncio.run(worker.ingest(private, [{"ref": 23, "doi": "10.1234/removed"}], Progress()))
    assert result["duplicates"] == 1
    assert not result["failed"]


def test_xml_upload_preserves_structured_text(private, monkeypatch):
    from dnhacksbio.litmap import extract
    seen = []
    async def fake(text, **kw):
        seen.append(text)
        return extraction(kw["source_ref"])
    monkeypatch.setattr(extract, "extract_paper", fake)
    xml = ("<article><front><article-title>XML paper</article-title></front><body><sec>"
           "<title>Results</title><p>" + "A increases proliferation. " * 20 + "</p></sec></body></article>")
    upload = attachments.add(private, "paper.xml", xml.encode())
    result = asyncio.run(worker.ingest(private, [{"ref": 10000, "attachment_id": upload["id"]}], Progress()))
    assert not result["failed"]
    assert "## Results" in seen[0]


def test_pdf_upload_has_readable_text(private, monkeypatch):
    fitz = pytest.importorskip("pymupdf")
    pytest.importorskip("pymupdf4llm")
    from dnhacksbio.litmap import extract
    async def fake(text, **kw):
        assert "proliferation" in text
        return extraction(kw["source_ref"])
    monkeypatch.setattr(extract, "extract_paper", fake)
    doc = fitz.open()
    page = doc.new_page()
    page.insert_textbox(fitz.Rect(40, 40, 500, 700), "A increases proliferation.\n" * 25)
    picture = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 180, 140), False)
    picture.clear_with(100)
    page.insert_image(fitz.Rect(60, 500, 240, 640), stream=picture.tobytes("png"))
    body = doc.tobytes()
    doc.close()
    upload = attachments.add(private, "paper.pdf", body)
    result = asyncio.run(worker.ingest(private, [{"ref": 10000, "attachment_id": upload["id"]}], Progress()))
    assert not result["failed"]
    from dnhacksbio.webui import library
    paper = library.paper_detail(private, "ref:10000")["paper"]
    assert paper["figure_count"] >= 1
    image, mime = library.figure(private, "ref:10000", 0)
    assert mime.startswith("image/") and len(image) > 50


@pytest.mark.parametrize("partial", [False, True])
def test_failed_extraction_is_actionable_and_not_published(private, monkeypatch, partial):
    from dnhacksbio.litmap import extract
    async def failed(text, **kw):
        return {"stats": {"pass1_failed": not partial}, "claims": [],
                "deferrals": [{"reason": "pass 1 truncated; paper extraction is incomplete"}] if partial else []}
    monkeypatch.setattr(extract, "extract_paper", failed)
    upload = attachments.add(private, "paper.txt", ("An unfinished extraction. " * 30).encode())
    result = asyncio.run(worker.ingest(private, [{"ref": 10000, "attachment_id": upload["id"]}], Progress()))
    assert result["failed"][0]["stage"] == "extract"
    store = KGStore(projects.kg_path(private))
    try:
        assert store.con.execute("SELECT count(*) FROM papers").fetchone()[0] == 0
    finally:
        store.close()


def test_upload_doi_duplicates_existing_paper(private, monkeypatch):
    from dnhacksbio.explorer.fulltext import FullTextStore
    store = KGStore(projects.kg_path(private))
    FullTextStore(con=store.con).add_paper(source_ref=1, doi="10.1234/identity", text="different stored text")
    store.close()
    upload = attachments.add(private, "paper.txt", ("DOI: 10.1234/identity\n" + "New formatting of same source. " * 30).encode())
    from dnhacksbio.litmap import extract
    monkeypatch.setattr(extract, "extract_paper", lambda *a, **kw: pytest.fail("duplicate extraction"))
    result = asyncio.run(worker.ingest(private, [{"ref": 10000, "attachment_id": upload["id"]}], Progress()))
    assert result["duplicates"] == 1
    assert not result["failed"]


def test_repair_retry_reuses_completed_reader(private, monkeypatch):
    from dnhacksbio.litmap import extract
    calls = []
    async def fake(text, **kw):
        calls.append(kw.get("raw_extraction"))
        if len(calls) == 1:
            return {"claims": [], "raw_extraction": {"claims": ["saved reader"]},
                    "deferrals": [{"source_ref": kw["source_ref"], "reason": "Repair unavailable: model offline"}]}
        return extraction(kw["source_ref"])
    monkeypatch.setattr(extract, "extract_paper", fake)
    upload = attachments.add(private, "paper.txt", ("An extraction to validate. " * 30).encode())
    items = [{"ref": 10000, "attachment_id": upload["id"]}]
    assert asyncio.run(worker.ingest(private, items, Progress()))["failed"]
    assert not asyncio.run(worker.ingest(private, items, Progress()))["failed"]
    assert calls == [None, {"claims": ["saved reader"]}]


def test_console_manifest_counts_and_unrelated_claim_survive_add(private, monkeypatch):
    from dnhacksbio.explorer.fulltext import FullTextStore
    from dnhacksbio.litmap import extract
    store = KGStore(projects.kg_path(private))
    unrelated = extraction(1)["claims"][0]
    unrelated.spine.subject = EntityRef(curie="HGNC:2", label="Prior engine entity")
    unrelated.evidence = []
    store.write_paper(1, [unrelated])
    FullTextStore(con=store.con).add_paper(source_ref=1, doi="10.1234/existing",
        title="Existing paper", text="Already indexed", is_full_text=True)
    before = store.con.execute("SELECT * FROM claims WHERE claim_id=?", [unrelated.claim_id]).fetchone()
    store.close()
    path = projects.project_dir(private) / "MANIFEST.json"
    path.write_text(json.dumps({"papers": {"papers": 1, "full_text": 1}, "n_claims": 1,
        "papers_meta": [{"ref": 1, "title": "Existing paper", "category": "Preserved topic"}]}))
    async def fake(text, **kw):
        return extraction(kw["source_ref"])
    monkeypatch.setattr(extract, "extract_paper", fake)
    upload = attachments.add(private, "additional.txt", ("Another paper to add. " * 30).encode())
    result = asyncio.run(worker.ingest(private, [{"ref": 10000, "attachment_id": upload["id"]}], Progress()))
    assert not result["failed"]
    manifest = json.loads(path.read_text())
    assert manifest["papers"] == {"papers": 2, "full_text": 2}
    assert manifest["n_papers"] == 2 and manifest["n_claims"] == 2
    assert manifest["papers_meta"][0]["category"] == "Preserved topic"
    assert len(manifest["papers_meta"]) == 2
    store = KGStore(projects.kg_path(private))
    try:
        after = store.con.execute("SELECT * FROM claims WHERE claim_id=?", [unrelated.claim_id]).fetchone()
        assert after == before
    finally:
        store.close()
