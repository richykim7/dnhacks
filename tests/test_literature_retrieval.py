"""No-network retrieval contracts: counts, identity, source retention and alternative routes."""
import io
import json
import tarfile
from pathlib import Path

import pytest

from dnhacksbio.litmap import find
from dnhacksbio.litmap import document_parse


TITLE = "Pancreatic ductal adenocarcinoma surface mesothelin targeting"
BODY = TITLE + "\nIntroduction\n" + ("Mechanisms of pancreatic malignancy and expression evidence. " * 40) + "\nResults\n" + ("Independent patient cohort observations. " * 30)
XML = f"<article><front><article-title>{TITLE}</article-title></front><body><sec><title>Introduction</title><p>{'Evidence in pancreatic tumors. ' * 70}</p></sec></body></article>".encode()


class Response:
    def __init__(self, data=b"", status=200, payload=None, content_type="application/xml"):
        self.content, self.status_code, self.payload = data, status, payload
        self.headers = {"Content-Type": content_type}
        self.text = data.decode(errors="replace")

    def iter_content(self, chunk_size=65536):
        yield self.content

    def close(self):
        pass

    def json(self):
        return self.payload if self.payload is not None else {}


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("unexpected network request")
    monkeypatch.setattr(find.requests, "get", forbidden)
    monkeypatch.setattr(find.time, "sleep", lambda _: None)


def test_canonical_dedup_merges_identifier_bridge_and_enriches():
    candidates = [find.Candidate("PMID:42", pmid="42", abstract="abstract", channels={"epmc"}),
                  find.Candidate("PMC:7", pmcid="PMC7", is_oa=True),
                  find.Candidate("HTTPS://DOI.ORG/10.1234/ABC", doi="https://doi.org/10.1234/ABC",
                                 pmid="42", pmcid="PMC7", channels={"openalex"})]
    merged = find.dedup_candidates(candidates)
    assert list(merged) == ["10.1234/abc"]
    assert merged["10.1234/abc"].abstract == "abstract"
    assert merged["10.1234/abc"].is_oa
    assert merged["10.1234/abc"].channels == {"epmc", "openalex"}


def test_openalex_search_paginates_and_decodes_abstract(monkeypatch):
    calls = []
    def get(url, **kwargs):
        calls.append(kwargs["params"])
        page = len(calls)
        return Response(payload={"results": [{"id": f"W{page}", "doi": f"https://doi.org/10.1234/{page}",
                            "title": TITLE, "publication_year": 2020, "publication_date": "2020-03-02",
                            "abstract_inverted_index": {"study": [1], "A": [0]}}],
                            "meta": {"next_cursor": "next" if page == 1 else None}})
    monkeypatch.setattr(find.requests, "get", get)
    hits = find.openalex_search("pancreatic cancer", max_results=2)
    assert len(hits) == 2 and hits[0].abstract == "A study"
    assert hits[0].publication_date == "2020-03-02"
    assert calls[1]["cursor"] == "next"


def test_long_abstract_xml_is_not_fulltext(monkeypatch, tmp_path):
    data = f"<article><article-title>{TITLE}</article-title><abstract>{BODY}</abstract></article>".encode()
    monkeypatch.setattr(find, "_request", lambda *a, **k: Response(data))
    c = find.Candidate("PMC:1", pmcid="PMC1", title=TITLE, abstract="fallback")
    result = find.fetch_fulltext(c, tmp_path)
    assert not result["is_full_text"]
    assert result["source"] == "abstract"
    artifacts = list(tmp_path.glob("*/retrieval.json"))
    assert len(artifacts) == 1
    assert list(artifacts[0].parent.glob("*.xml")), "rejected raw source must survive"


def test_alternate_pdf_and_retention_before_success(monkeypatch, tmp_path):
    c = find.Candidate("10.1234/test", doi="10.1234/test", title=TITLE,
                       locations=[{"is_oa": True, "pdf_url": "https://example.org/bad.pdf"},
                                  {"is_oa": True, "pdf_url": "https://example.org/good.pdf"}])
    monkeypatch.setattr(find, "_resolve_pmcid", lambda *a: "")
    monkeypatch.setattr(find, "openalex_by_doi", lambda *a: None)
    monkeypatch.setattr(find, "_json_request", lambda *a, **k: {})
    urls = []
    def request(url, **kwargs):
        urls.append(url)
        return Response(b"%PDF-good" if "good" in url else b"%PDF-bad")
    def parse(data, kind, output_dir=None):
        # Raw retention happens BEFORE parser invocation, including rejected sources.
        assert list(output_dir.parent.glob("*.pdf"))
        if data == b"%PDF-bad":
            raise ValueError("corrupt PDF")
        return {"text": BODY, "markdown": BODY, "figures": [], "parser": "test", "parser_version": "1"}
    monkeypatch.setattr(find, "_request", request)
    monkeypatch.setattr(document_parse, "parse_document_bytes", parse)
    result = find.fetch_fulltext(c, tmp_path)
    assert result["is_full_text"] and result["url"].endswith("good.pdf")
    assert len(urls) == 2
    folder = Path(result["artifact_dir"])
    assert len(list(folder.glob("*.pdf"))) == 2
    assert json.loads((folder / "retrieval.json").read_text())["attempts"][0]["status"] == "parse-failed"
    assert (folder / result["parsed_file"]).read_text() == BODY
    urls.clear()
    assert find.fetch_fulltext(c, tmp_path)["cache_hit"]
    assert urls == []


def test_partial_scanned_pdf_rejected(monkeypatch, tmp_path):
    c = find.Candidate("W1", title=TITLE, locations=[{"is_oa": True, "pdf_url": "https://example.org/a.pdf"}])
    monkeypatch.setattr(find, "_resolve_pmcid", lambda *a: "")
    monkeypatch.setattr(find, "_request", lambda *a, **k: Response(b"%PDF-x"))
    monkeypatch.setattr(document_parse, "parse_document_bytes", lambda *a, **k: {"text": BODY, "needs_ocr": True})
    assert not find.fetch_fulltext(c, tmp_path)["is_full_text"]


def test_pmc_package_reads_matching_figures_without_extracting_paths(monkeypatch, tmp_path):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for name, data in [("article/fig1.jpg", b"image"), ("../../escape.txt", b"bad")]:
            info = tarfile.TarInfo(name); info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    def request(url, **kwargs):
        if "oa.fcgi" in url:
            return Response(b'<OA><records><record><link format="tgz" href="ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/a.tar.gz"/></record></records></OA>')
        return Response(buffer.getvalue())
    monkeypatch.setattr(find, "_request", request)
    figures = [{"id": "F1", "url": "fig1", "path": None}]
    find._pmc_figure_assets("PMC1", figures, tmp_path, [])
    assert (tmp_path / figures[0]["path"]).read_bytes() == b"image"
    assert not (tmp_path.parent / "escape.txt").exists()


class Progress:
    def emit(self, *args, **kwargs):
        pass


def test_fulltext_refill_skips_abstract_and_preserves_count(monkeypatch, tmp_path):
    from dnhacksbio.litmap.corpus_build import _fetch_selected
    cands = [find.Candidate(f"W{i}") for i in range(4)]
    called = []
    def fetch(c, root):
        called.append(c.key)
        return {"text": BODY, "is_full_text": c.key != "W0", "source": "test"}
    monkeypatch.setattr(find, "fetch_fulltext", fetch)
    result = _fetch_selected(cands, 2, True, tmp_path, Progress())
    assert len(result) == 2 and all(ft["is_full_text"] for _, ft in result)
    assert "W2" in called and "W3" not in called
    assert len(json.loads((tmp_path / "attempts.json").read_text())) == 3


def test_shortfall_fails_before_extraction(monkeypatch, tmp_path):
    from dnhacksbio.litmap.corpus_build import _fetch_selected, BuildError
    monkeypatch.setattr(find, "fetch_fulltext", lambda *a: {"text": BODY, "is_full_text": False})
    with pytest.raises(BuildError, match="minimum not met: 0/2"):
        _fetch_selected([find.Candidate("W1")], 2, True, tmp_path, Progress())
    assert (tmp_path / "attempts.json").is_file()


def test_request_retries_transient_status_and_reports_failure(monkeypatch):
    statuses = iter([503, 429, 404])
    monkeypatch.setattr(find.requests, "get", lambda *a, **k: Response(status=next(statuses)))
    attempts = []
    assert find._request("https://example.org/x", attempts=attempts) is None
    assert [a["status"] for a in attempts] == ["http-503", "http-429", "http-404"]


def test_streaming_limit_stops_download(monkeypatch):
    response = Response(b"x" * 20)
    monkeypatch.setattr(find.requests, "get", lambda *a, **k: response)
    attempts = []
    assert find._request("https://example.org/large", max_bytes=10, attempts=attempts) is None
    assert attempts[0]["status"] == "download-too-large"


def test_markdown_image_links_resolve_from_persisted_markdown(monkeypatch, tmp_path):
    c = find.Candidate("W1", title=TITLE, locations=[{"is_oa": True, "pdf_url": "https://example.org/a.pdf"}])
    monkeypatch.setattr(find, "_resolve_pmcid", lambda *a: "")
    monkeypatch.setattr(find, "_request", lambda *a, **k: Response(b"%PDF-x"))
    def parse(data, kind, output_dir=None):
        (output_dir / "figure.png").write_bytes(b"image")
        return {"text": BODY, "markdown": BODY + "\n![Figure](figure.png)",
                "figures": [{"path": "figure.png", "page": 1}], "parser": "test"}
    monkeypatch.setattr(document_parse, "parse_document_bytes", parse)
    result = find.fetch_fulltext(c, tmp_path)
    relative = result["figures"][0]["path"]
    folder = Path(result["artifact_dir"])
    assert (folder / relative).is_file()
    assert f"]({relative})" in result["markdown"]
    assert f"]({relative})" in next(folder.glob("*.md")).read_text()


def test_refill_deduplicates_identical_downloads(monkeypatch, tmp_path):
    from dnhacksbio.litmap.corpus_build import _fetch_selected
    candidates = [find.Candidate(f"W{i}") for i in range(3)]
    monkeypatch.setattr(find, "fetch_fulltext", lambda c, _: {
        "text": BODY, "is_full_text": True, "raw_sha256": "same" if c.key in {"W0", "W1"} else "different"})
    result = _fetch_selected(candidates, 2, True, tmp_path, Progress())
    assert [c.key for c, _ in result] == ["W0", "W2"]


def test_landing_page_follows_explicit_pdf_metadata(monkeypatch, tmp_path):
    c = find.Candidate("W1", title=TITLE, locations=[{"is_oa": True, "landing_page_url": "https://example.org/article"}])
    monkeypatch.setattr(find, "_resolve_pmcid", lambda *a: "")
    def request(url, **kwargs):
        if url.endswith("article"):
            return Response(b'<html><meta name="citation_pdf_url" content="/paper.pdf"></html>', content_type="text/html")
        assert url == "https://example.org/paper.pdf"
        return Response(b"%PDF-x")
    def parse(data, kind, output_dir=None):
        if kind == "html":
            raise ValueError("no article body")
        return {"text": BODY, "figures": []}
    monkeypatch.setattr(find, "_request", request)
    monkeypatch.setattr(document_parse, "parse_document_bytes", parse)
    result = find.fetch_fulltext(c, tmp_path)
    assert result["is_full_text"] and result["url"] == "https://example.org/paper.pdf"
    assert result["source"] == "openalex:linked-pdf"


def test_pdf_quality_gate_accepts_markdown_bold_and_combined_headings():
    text = BODY.replace("Introduction", "### **Methods**").replace("Results", "### **Results and Discussion**")
    assert find._has_body(b"%PDF-x", "pdf", text)


def test_refilled_paper_list_records_actual_sources(monkeypatch, tmp_path):
    from dnhacksbio.litmap.corpus_build import _fetch_selected, _write_selected_papers
    candidates = [find.Candidate("W0", title="unavailable"),
                  find.Candidate("W1", title=TITLE, publication_date="2020-03-02")]
    monkeypatch.setattr(find, "fetch_fulltext", lambda c, _: {"text": BODY, "is_full_text": c.key == "W1",
                                                           "url": "https://example.org/paper", "raw_sha256": "hash"})
    selected = _fetch_selected(candidates, 1, True, tmp_path / "retrieval", Progress())
    path = tmp_path / "paper_list.json"
    path.write_text(json.dumps({"papers": [{"title": "unavailable"}]}))
    _write_selected_papers(path, selected, ["query"], {})
    saved = json.loads(path.read_text())
    assert saved["selection"] == "retrieved"
    assert [p["title"] for p in saved["papers"]] == [TITLE]
    assert saved["papers"][0]["publication_date"] == "2020-03-02"
    assert saved["papers"][0]["is_full_text"]


def test_manuscript_figures_fall_back_to_official_html_after_missing_packages(monkeypatch, tmp_path):
    html = b'<article><h1>Paper</h1><figure id="F1"><img src="https://cdn.ncbi.nlm.nih.gov/pmc/blobs/one.jpg"><figcaption>Spindle</figcaption></figure><figure id="other"><img src="https://cdn.ncbi.nlm.nih.gov/pmc/blobs/other.jpg"></figure></article>'
    requested = []
    def request(url, **kwargs):
        requested.append(url)
        if url.endswith('/PMC42/'):
            return Response(html, content_type='text/html')
        if url.endswith('/one.jpg'):
            return Response(b'image-bytes', content_type='image/jpeg')
        assert 'supplementaryFiles' in url or 'oa.fcgi' in url
        return None
    monkeypatch.setattr(find, '_request', request)
    figures = [{'id': 'F1', 'url': 'manuscript-f1', 'path': None}]
    find._pmc_figure_assets('PMC42', figures, tmp_path, [])
    assert (tmp_path / figures[0]['path']).read_bytes() == b'image-bytes'
    assert figures[0]['resolution_source'] == 'https://pmc.ncbi.nlm.nih.gov/articles/PMC42/'
    assert (tmp_path / figures[0]['resolution_file']).read_bytes() == html
    assert not any('/other.jpg' in url for url in requested)


@pytest.mark.parametrize('image_url,mime', [
    ('https://cdn.ncbi.nlm.nih.gov/pmc/blobs/one.jpg', 'text/html'),
    ('https://unrelated.example/one.jpg', 'image/jpeg'),
])
def test_pmc_html_figure_fallback_rejects_challenges_and_external_images(monkeypatch, tmp_path, image_url, mime):
    def request(url, **kwargs):
        if url.endswith('/PMC42/'):
            return Response(f'<article><figure id="F1"><img src="{image_url}"></figure></article>'.encode(), content_type='text/html')
        if url == image_url:
            return Response(b'challenge', content_type=mime)
        return None
    monkeypatch.setattr(find, '_request', request)
    figures = [{'id': 'F1', 'url': 'f1', 'path': None}]
    find._pmc_figure_assets('PMC42', figures, tmp_path, [])
    assert figures[0]['path'] is None


@pytest.mark.parametrize('alternate_succeeds', [True, False])
def test_pmc_figure_html_challenge_tries_one_alternate_representation(monkeypatch, tmp_path, alternate_succeeds):
    requested = []
    base = 'https://pmc.ncbi.nlm.nih.gov/articles/PMC42/'
    image_url = 'https://cdn.ncbi.nlm.nih.gov/pmc/blobs/one.jpg'
    def request(url, **kwargs):
        requested.append(url)
        if url == base + '?report=xml' and alternate_succeeds:
            return Response(f'<article><figure id="F1"><img src="{image_url}"></figure></article>'.encode(), content_type='text/html')
        if url in (base, base + '?report=xml'):
            return Response(b'<html><p>Checking your browser</p></html>', content_type='text/html')
        if url == image_url:
            return Response(b'image-bytes', content_type='image/jpeg')
        return None
    monkeypatch.setattr(find, '_request', request)
    figures = [{'id': 'F1', 'url': 'f1', 'path': None}]
    attempts = []
    find._pmc_figure_assets('PMC42', figures, tmp_path, attempts)
    assert [u for u in requested if u.startswith(base)] == [base, base + '?report=xml']
    assert bool(figures[0]['path']) is alternate_succeeds
    assert sum(a['status'] == 'no-article-figure-markup' for a in attempts) == (1 if alternate_succeeds else 2)
    if alternate_succeeds:
        assert figures[0]['resolution_source'] == base + '?report=xml'
