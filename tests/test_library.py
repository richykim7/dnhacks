"""Paper browsing reads stored artifacts without changing the corpus."""
import json
from pathlib import Path

import duckdb
import pytest

from dnhacksbio.webui import library, projects


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    root = tmp_path / "corpora" / "collection"
    root.mkdir(parents=True)
    monkeypatch.setattr(projects, "CORPORA", root.parent)
    monkeypatch.setattr(projects, "PROJECTS", tmp_path / "projects")
    con = duckdb.connect(str(root / "collection_kg.duckdb"))
    con.execute("create table papers(paper_id varchar, source_ref integer, title varchar, year integer, text varchar, sections varchar, is_full_text boolean)")
    con.execute("insert into papers values ('10.1/paper', 1, 'Stored article', 2020, 'Full local text', NULL, true), ('ref:2', 2, 'Abstract only', NULL, 'An abstract', 'invalid json', false), ('ref:3', 3, 'Metadata only', 2019, NULL, NULL, true)")
    con.close()
    (root / "papers" / "001").mkdir(parents=True)
    (root / "papers" / "001" / "raw.html").write_text('<meta name="citation_author" content="A &amp; B"><script>never execute</script>')
    (root / "papers" / "001" / "figure.jpg").write_bytes(b'local-image')
    (root / "MANIFEST.json").write_text(json.dumps({"papers": [{"ref": 1, "category": "Division", "raw_file": "papers/001/raw.html", "figures": [{"id": "F1", "path": "papers/001/figure.jpg", "caption": "Recorded caption"}, {"id": "F2", "path": "papers/001/missing.jpg"}]}]}))
    return root


def test_all_papers_text_availability_and_local_figures(corpus):
    before = {p: p.read_bytes() for p in corpus.rglob('*') if p.is_file()}
    result = library.list_papers('collection')
    assert result['total'] == 3
    first, abstract, metadata = result['papers']
    assert first['authors'] == ['A & B']
    assert first['category'] == 'Division' and first['figure_count'] == 1
    assert abstract['has_text'] and not abstract['is_full_text']
    assert not metadata['has_text'] and not metadata['is_full_text']
    paper = library.paper_detail('collection', '10.1/paper')['paper']
    assert paper['text'] == 'Full local text'
    assert paper['figures'][0]['url'].endswith('/10.1%2Fpaper/figures/0')
    assert paper['figures'][1]['url'] is None
    assert library.figure('collection', '10.1/paper', 0) == (b'local-image', 'image/jpeg')
    assert library.paper_detail('collection', 'ref:2')['paper']['sections'] is None
    assert before == {p: p.read_bytes() for p in corpus.rglob('*') if p.is_file()}


def test_missing_paper_and_unsafe_manifest_paths(corpus, tmp_path):
    secret = tmp_path / 'outside.jpg'
    secret.write_bytes(b'outside')
    manifest = corpus / 'MANIFEST.json'
    for unsafe in (str(secret), '../../../outside.jpg', 'papers/001/link.jpg'):
        link = corpus / 'papers/001/link.jpg'
        if not link.exists():
            link.symlink_to(secret)
        manifest.write_text(json.dumps({'papers': [{'ref': 1, 'raw_file': unsafe, 'figures': [{'path': unsafe}]}]}))
        assert library.list_papers('collection')['papers'][0]['figure_count'] == 0
        with pytest.raises(FileNotFoundError):
            library.figure('collection', '10.1/paper', 0)
    with pytest.raises(FileNotFoundError):
        library.paper_detail('collection', 'foreign-paper')
    with pytest.raises(FileNotFoundError):
        library.figure('collection', '10.1/paper', -1)


def test_xml_authors_exclude_cited_authors(corpus):
    raw = corpus / 'papers/001/raw.xml'
    raw.write_text('<article><front><article-meta><contrib-group><contrib contrib-type="author"><name><surname>Doe</surname><given-names>Jane</given-names></name></contrib><contrib contrib-type="editor"><name><surname>Editor</surname></name></contrib></contrib-group></article-meta></front><back><ref-list><name><surname>Cited</surname></name></ref-list></back></article>')
    manifest = corpus / 'MANIFEST.json'
    meta = json.loads(manifest.read_text())
    meta['papers'][0]['raw_file'] = 'papers/001/raw.xml'
    manifest.write_text(json.dumps(meta))
    assert library.list_papers('collection')['papers'][0]['authors'] == ['Jane Doe']


def test_http_encoded_doi_and_scoped_image(corpus):
    from http.client import HTTPConnection
    from http.server import ThreadingHTTPServer
    import threading
    from dnhacksbio.webui.server import Handler

    httpd = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        def get(path):
            conn = HTTPConnection('127.0.0.1', httpd.server_port, timeout=3)
            conn.request('GET', path)
            response = conn.getresponse()
            result = response.status, response.read()
            conn.close()
            return result

        prefix = '/api/projects/collection/papers'
        assert json.loads(get(prefix)[1])['total'] == 3
        status, body = get(prefix + '/10.1%2Fpaper')
        assert status == 200
        figure_url = json.loads(body)['paper']['figures'][0]['url']
        assert get(figure_url) == (200, b'local-image')
        assert get(prefix + '/foreign-paper')[0] == 404
        assert get(figure_url.replace('/collection/', '/foreign/'))[0] == 404
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join()
