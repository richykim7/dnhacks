"""Freeze an explicitly curated, dated full-text collection; optionally build its claim graph.

Search and scientific selection happen before this command. Only reviewed manifest entries are
admitted. Original sources, readable text, Markdown and every referenced image are required.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import shutil
from datetime import date, datetime, timezone
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    tmp.replace(path)


def inside(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError(f'Missing or unsafe artifact: {name}')
    return path


def freeze(selection, output, retrieval, count):
    spec = json.loads(selection.read_text())
    cutoff = date.fromisoformat(spec['last_publication_date'])
    rows = spec['papers']
    if len(rows) != count:
        raise ValueError(f'Expected {count} curated papers; got {len(rows)}')
    if (output / 'MANIFEST.json').exists():
        raise ValueError('Frozen manifest already exists; verify it or choose a new output directory')
    output.mkdir(parents=True, exist_ok=True)
    seen, raw_hashes, papers, files = set(), set(), [], {}
    # Validate the entire selection before copying any material.
    prepared = []
    for row in rows:
        c = row['candidate']
        key = c['key']
        if key in seen or date.fromisoformat(c['publication_date']) > cutoff:
            raise ValueError(f'Duplicate or out-of-window paper: {key}')
        if not row.get('date_source') or not row.get('rationale'):
            raise ValueError(f'Missing date evidence or selection rationale: {key}')
        seen.add(key)
        dest = retrieval / hashlib.sha256(key.encode()).hexdigest()[:20]
        ft = json.loads((dest / 'retrieval.json').read_text())
        if ft['candidate']['key'] != key or not ft.get('is_full_text'):
            raise ValueError(f'No verified full text for {key}')
        raw = inside(dest, ft['raw_file'])
        if sha(raw) != ft['raw_sha256'] or ft['raw_sha256'] in raw_hashes:
            raise ValueError(f'Invalid or duplicated source bytes: {key}')
        raw_hashes.add(ft['raw_sha256'])
        text = inside(dest, ft['parsed_file'])
        if text.read_text() != ft['text'] or len(ft['text']) < 1500:
            raise ValueError(f'Incomplete/mismatched readable text: {key}')
        if ft.get('parser') == 'stdlib-jats' and ft.get('parser_version') != '2':
            raise ValueError(f'Reparse JATS with floating-figure support: {key}')
        markdown = inside(dest, ft['raw_sha256'] + '.md')
        figures = ft.get('figures', [])
        for f in figures:
            if not f.get('path'):
                raise ValueError(f'Unresolved figure in {key}: {f.get("id")}')
            inside(dest, f['path'])
        prepared.append((row, ft, dest, raw, text, markdown))
    for n, (row, ft, dest, raw, text, markdown) in enumerate(prepared, 1):
        rel = Path('papers') / f'{n:03d}'
        target = output / rel
        target.mkdir(parents=True, exist_ok=True)
        paths = [raw, text, markdown] + [inside(dest, f['path']) for f in ft.get('figures', [])]
        for source in dict.fromkeys(paths):
            name = source.relative_to(dest)
            to = target / name
            to.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, to)
            files[str(rel / name)] = sha(to)
        c = row['candidate']
        p = {'ref': n, **{k: c.get(k, '') for k in ('key','doi','pmid','pmcid','title','year','publication_date')},
             'category': row['category'], 'rationale': row['rationale'], 'date_source': row['date_source'],
             'date_evidence': row.get('date_evidence'),
             'raw_file': str(rel / raw.name), 'text_file': str(rel / text.name),
             'markdown_file': str(rel / markdown.name), 'n_chars': len(ft['text']),
             'figures': [{**f, 'path': str(rel / f['path'])} for f in ft.get('figures', [])],
             'license': ft.get('license'), 'url': ft.get('url'), 'source': ft.get('source'),
             'parser': ft.get('parser'), 'parser_version': ft.get('parser_version'),
             'raw_sha256': ft['raw_sha256'], 'retrieved_at': ft.get('retrieved_at')}
        papers.append(p)
    (output / 'prompt.txt').write_text(spec['research_prompt'] + '\n')
    (output / 'corpus_card.md').write_text('# Pancreatic cancer: division and survival\n\n' + spec['scope'] +
        f'\n\n{len(papers)} full-text papers published on or before {cutoff.isoformat()}.\n')
    files['prompt.txt'] = sha(output / 'prompt.txt')
    files['corpus_card.md'] = sha(output / 'corpus_card.md')
    manifest = {'schema_version': 1, 'created_at': datetime.now(timezone.utc).isoformat(),
                'last_publication_date': str(cutoff), 'n_papers': len(papers),
                'scope': spec['scope'], 'papers': papers, 'files_sha256': files,
                'selection_sha256': sha(selection), 'freeze_type': 'curated historical demonstration corpus'}
    write_json(output / 'MANIFEST.json', manifest)
    (output / 'MANIFEST.sha256').write_text(sha(output / 'MANIFEST.json') + '\n')
    render(output, manifest)
    return verify(output)


def render(output, manifest):
    links = []
    for p in manifest['papers']:
        title = html.escape(p['title'])
        gallery = ''.join(f'<figure><img loading="lazy" src="{html.escape(f["path"])}"><figcaption>' +
                          html.escape(f.get('caption') or f.get('label') or 'Figure') + '</figcaption></figure>'
                          for f in p['figures'])
        page = f'paper-{p["ref"]:03d}.html'
        (output / page).write_text('<!doctype html><meta charset="utf-8"><title>'+title+'</title>' +
          '<style>body{max-width:960px;margin:40px auto;padding:20px;font:18px/1.6 system-ui}' +
          'pre{white-space:pre-wrap;font:16px/1.6 system-ui}img{max-width:100%}figure{margin:30px 0}</style>' +
          '<a href="index.html">All papers</a><h1>'+title+'</h1><p>'+p['publication_date']+'</p>' +
          f'<a href="{p["raw_file"]}">Original source</a> · <a href="{p["markdown_file"]}">Markdown</a>' +
          '<pre>'+html.escape((output/p['text_file']).read_text())+'</pre>'+gallery)
        links.append(f'<li><a href="{page}">{title}</a> — {p["publication_date"]} · '+
                     html.escape(p['category'])+f' · {len(p["figures"])} image assets</li>')
    (output/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Pancreatic cancer corpus</title>'+
        '<style>body{max-width:1100px;margin:40px auto;padding:20px;font:17px/1.6 system-ui}li{margin:12px 0}</style>'+
        '<h1>Pancreatic cancer: division and survival</h1><p>'+html.escape(manifest['scope'])+
        '</p><p>Full text and local figures. Publication cutoff: '+manifest['last_publication_date']+'</p><ol>'+''.join(links)+'</ol>')


def verify(output):
    manifest_path = output/'MANIFEST.json'
    if sha(manifest_path) != (output/'MANIFEST.sha256').read_text().strip():
        raise ValueError('Frozen manifest checksum mismatch')
    m = json.loads(manifest_path.read_text())
    for name, expected in m['files_sha256'].items():
        if sha(inside(output, name)) != expected:
            raise ValueError(f'Frozen artifact checksum mismatch: {name}')
    result = {'papers': len(m['papers']), 'files': len(m['files_sha256']),
              'image_assets': sum(len(p['figures']) for p in m['papers']),
              'characters': sum(p['n_chars'] for p in m['papers']), 'manifest_sha256': sha(manifest_path)}
    print(json.dumps(result, indent=2), flush=True)
    return result


def index(output):
    from dnhacksbio.litmap.store import KGStore
    from dnhacksbio.explorer.fulltext import FullTextStore
    m = json.loads((output/'MANIFEST.json').read_text())
    store = KGStore(output/(output.name+'_kg.duckdb'))
    try:
        ft = FullTextStore(con=store.con)
        for p in m['papers']:
            ft.add_paper(source_ref=p['ref'], source_label=f'Paper{p["ref"]}', doi=p['doi'], pmid=p['pmid'],
                         pmcid=p['pmcid'], title=p['title'], year=p['year'], text=(output/p['text_file']).read_text(),
                         license=p['license'] or '', url=p['url'] or '', is_full_text=True, resolve_identity=False)
        print(json.dumps(ft.counts()), flush=True)
    finally:
        store.close()


def fetch_selection(selection, retrieval):
    from concurrent.futures import ThreadPoolExecutor
    from dnhacksbio.litmap.find import Candidate, fetch_fulltext
    rows = json.loads(selection.read_text())['papers']
    def one(row):
        c = Candidate(**row['candidate'])
        ft = fetch_fulltext(c, retrieval)
        print(json.dumps({'key': c.key, 'full_text': ft.get('is_full_text'),
                          'figures': ft.get('figures_status')}), flush=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(one, rows))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--selection', type=Path)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--retrieval', type=Path)
    ap.add_argument('--count', type=int, default=100)
    ap.add_argument('--verify', action='store_true')
    ap.add_argument('--fetch', action='store_true', help='Fetch the exact selection before freezing; no search/ranking')
    ap.add_argument('--index', action='store_true')
    args = ap.parse_args()
    if args.verify:
        verify(args.output)
    elif args.selection and args.retrieval:
        if args.fetch:
            fetch_selection(args.selection, args.retrieval)
        freeze(args.selection, args.output, args.retrieval, args.count)
    else:
        ap.error('Use --verify or provide --selection and --retrieval')
    if args.index:
        index(args.output)


if __name__ == '__main__':
    main()
