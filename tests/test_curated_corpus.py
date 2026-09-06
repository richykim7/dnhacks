import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('curated', Path(__file__).parents[1] / 'scripts/build_pdac_corpus.py')
corpus = importlib.util.module_from_spec(spec)
spec.loader.exec_module(corpus)


def packet(tmp_path):
    key = '10.1234/example'
    retrieval = tmp_path / 'retrieval'
    dest = retrieval / hashlib.sha256(key.encode()).hexdigest()[:20]
    dest.mkdir(parents=True)
    raw = b'<article><body>Historical paper</body></article>'
    digest = hashlib.sha256(raw).hexdigest()
    text = 'A complete historical source. ' * 100
    (dest / (digest + '.xml')).write_bytes(raw)
    for suffix in ('.txt', '.md'):
        (dest / (digest + suffix)).write_text(text)
    c = dict(key=key, doi=key, pmid='123', pmcid='PMC123', title='Historical paper', year=2025,
             publication_date='2025-12-10')
    ft = dict(candidate=c, is_full_text=True, raw_file=digest+'.xml', raw_sha256=digest,
              parsed_file=digest+'.txt', text=text, parser='stdlib-jats', parser_version='2', figures=[])
    (dest / 'retrieval.json').write_text(json.dumps(ft))
    selection = tmp_path / 'selection.json'
    selection.write_text(json.dumps(dict(last_publication_date='2026-01-25', research_prompt='A neutral question',
        scope='Historical science', papers=[dict(candidate=c, category='biology', rationale='Relevant mechanism', date_source='https://example.org/date') ])))
    return selection, retrieval, dest, tmp_path/'frozen'


def test_freeze_integrity_detects_modified_text(tmp_path):
    selection, retrieval, dest, output = packet(tmp_path)
    assert corpus.freeze(selection, output, retrieval, 1)['papers'] == 1
    assert (output/'index.html').exists()
    manifest = json.loads((output/'MANIFEST.json').read_text())
    (output / manifest['papers'][0]['text_file']).write_text('Changed after freeze')
    with pytest.raises(ValueError, match='checksum mismatch'):
        corpus.verify(output)


def test_freeze_rejects_postcutoff_before_copying(tmp_path):
    selection, retrieval, dest, output = packet(tmp_path)
    s = json.loads(selection.read_text())
    s['papers'][0]['candidate']['publication_date'] = '2026-01-26'
    selection.write_text(json.dumps(s))
    with pytest.raises(ValueError, match='out-of-window'):
        corpus.freeze(selection, output, retrieval, 1)
    assert not (output/'papers').exists()


def test_freeze_rejects_missing_figure_and_old_parser(tmp_path):
    selection, retrieval, dest, output = packet(tmp_path)
    path = dest/'retrieval.json'
    r = json.loads(path.read_text())
    r['figures'] = [{'id': 'F1', 'path': None}]
    path.write_text(json.dumps(r))
    with pytest.raises(ValueError, match='Unresolved figure'):
        corpus.freeze(selection, output, retrieval, 1)
    r.update(figures=[], parser_version='1')
    path.write_text(json.dumps(r))
    with pytest.raises(ValueError, match='floating-figure'):
        corpus.freeze(selection, output, retrieval, 1)
