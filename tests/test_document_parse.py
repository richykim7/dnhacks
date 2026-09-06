from pathlib import Path

import pytest

from dnhacksbio.litmap.document_parse import parse_document_bytes


def test_jats_keeps_boundaries_tables_references_and_figures():
    source = b'''<article xmlns:xlink="http://www.w3.org/1999/xlink"><front><article-meta>
    <title-group><article-title>PDAC biology</article-title></title-group><abstract><p>Background.</p></abstract>
    </article-meta></front><body><sec><title>Results</title><p>First result.</p><p>Second result.</p>
    <table-wrap><label>Table 1</label><table><tr><th>Group</th><th>N</th></tr><tr><td>A</td><td>12</td></tr></table></table-wrap>
    <fig id="f1"><label>Figure 1</label><caption><p>Observed expression.</p></caption><graphic xlink:href="fig1.jpg"/></fig>
    </sec></body><back><ref-list><ref>Author. Reference title.</ref></ref-list></back></article>'''
    out = parse_document_bytes(source, 'xml')
    assert 'First result.\n\nSecond result.' in out['text']
    assert '| A | 12 |' in out['markdown']
    assert 'Author. Reference title.' in out['text']
    assert out['has_body']
    assert out['figures_status'] == 'referenced'
    assert out['figures'][0]['caption'] == 'Observed expression.'
    assert out['figures'][0]['url'] == 'fig1.jpg'


def test_html_article_isolation():
    out = parse_document_bytes(b'<html><nav>Login menus</nav><article><h1>Paper</h1><p>Actual results.</p><figure><img src="f.png"><figcaption>Measured values</figcaption></figure></article><footer>Cookies</footer></html>', 'html')
    assert 'Login' not in out['text'] and 'Cookies' not in out['text']
    assert out['figures'][0]['caption'] == 'Measured values'
    with pytest.raises(ValueError, match='article body'):
        parse_document_bytes(b'<html><p>Paywall landing page</p></html>', 'html')


def _pdf():
    pymupdf = pytest.importorskip('pymupdf')
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((40, 40), 'Research paper: pancreatic cancer', fontsize=18)
    page.insert_text((40, 75), 'Results', fontsize=14)
    page.insert_textbox((40, 100, 550, 200), 'A controlled experiment compared expression across independent samples. ' * 6)
    # Vector chart: extracting only embedded raster objects would lose this.
    page.draw_rect((60, 240, 440, 460))
    for x, h in [(100, 80), (200, 150), (300, 110)]:
        page.draw_rect((x, 450-h, x+50, 450), fill=(0.2, 0.4, 0.8))
    page.insert_text((60, 490), 'Figure 1. Observed expression by group.')
    # Raster image with a visible pattern.
    pix = pymupdf.Pixmap(pymupdf.csRGB, (0, 0, 100, 100))
    pix.clear_with(160)
    page.insert_image((60, 540, 260, 740), pixmap=pix)
    data = doc.tobytes()
    doc.close()
    return data


def test_pdf_preserves_vector_and_raster_regions(tmp_path):
    pytest.importorskip('pymupdf4llm')
    out = parse_document_bytes(_pdf(), 'pdf', tmp_path)
    assert 'controlled experiment' in out['text']
    assert out['pages'] == 1
    assert not out['needs_ocr']
    assert out['figures_status'] == 'extracted'
    assert len(out['figures']) >= 2
    for fig in out['figures']:
        assert fig['page'] == 1 and len(fig['bbox']) == 4
        assert fig['caption'] is None
        assert not Path(fig['path']).is_absolute()
        assert (tmp_path / fig['path']).is_file()
    assert str(tmp_path) not in out['markdown']


def test_pdf_without_output_explicitly_does_not_persist():
    pytest.importorskip('pymupdf4llm')
    out = parse_document_bytes(_pdf(), 'pdf')
    assert out['figures_status'] == 'not_extracted'
    assert all(f['path'] is None for f in out['figures'])


def test_scanned_pdf_rejected(monkeypatch):
    pymupdf = pytest.importorskip('pymupdf')
    pytest.importorskip('pymupdf4llm')
    monkeypatch.delenv('DNHACKS_PDF_OCR', raising=False)
    doc = pymupdf.open()
    page = doc.new_page()
    pix = pymupdf.Pixmap(pymupdf.csRGB, (0, 0, 80, 80))
    pix.clear_with(180)
    page.insert_image(page.rect, pixmap=pix)
    with pytest.raises(ValueError, match='no readable text'):
        parse_document_bytes(doc.tobytes(), 'pdf')
    doc.close()


def test_mixed_scanned_pdf_reports_unreadable_pages(monkeypatch):
    pymupdf = pytest.importorskip('pymupdf')
    pytest.importorskip('pymupdf4llm')
    monkeypatch.delenv('DNHACKS_PDF_OCR', raising=False)
    with pymupdf.open(stream=_pdf(), filetype='pdf') as doc:
        doc.new_page()
        out = parse_document_bytes(doc.tobytes(), 'pdf')
    assert out['needs_ocr'] and out['unreadable_pages'] == [2]
    assert out['text']


def test_parser_image_path_cannot_escape_scratch(monkeypatch, tmp_path):
    library = pytest.importorskip('pymupdf4llm')
    foreign = tmp_path / 'foreign.png'
    foreign.write_bytes(b'not ours')
    markdown = f'Content\n![image]({foreign})'
    monkeypatch.setattr(library, 'to_markdown', lambda *a, **k: [
        {'metadata': {'page_number': 1}, 'text': markdown,
         'page_boxes': [{'class': 'picture', 'bbox': [0, 0, 10, 10], 'pos': [0, len(markdown)]}]}
    ])
    with pytest.raises(ValueError, match='invalid image path'):
        parse_document_bytes(_pdf(), 'pdf', tmp_path / 'output')
    assert foreign.read_bytes() == b'not ours'


def test_xml_rejects_declared_entities():
    with pytest.raises(ValueError, match='entity declarations'):
        parse_document_bytes(b'<!DOCTYPE article [<!ENTITY foo "expanded">]><article><body>&foo;</body></article>', 'xml')
