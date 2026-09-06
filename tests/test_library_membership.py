"""Membership tests use tiny private graphs and never acquire literature or call models."""
import json
from pathlib import Path
import subprocess
import sys

import duckdb
import pytest

from dnhacksbio.webui import data, jobs, library, membership, projects
from dnhacksbio.litmap.store import KGStore
from dnhacksbio.explorer.fulltext import FullTextStore


@pytest.fixture
def private(tmp_path, monkeypatch):
    monkeypatch.setattr(projects, 'PROJECTS', tmp_path / 'projects')
    monkeypatch.setattr(projects, 'CORPORA', tmp_path / 'corpora')
    monkeypatch.setattr(data, 'list_runs', lambda **kwargs: [])
    rec = projects.create('Private test')
    store = KGStore(projects.kg_path(rec['id']))
    FullTextStore(con=store.con)
    for pid, ref in [('10.1234/a', 1), ('10.1234/b', 2)]:
        store.con.execute('insert into papers(paper_id,source_ref,doi,title,text) values (?,?,?,?,?)', [pid,ref,pid,pid,'text'])
    for cid in ['shared', 'only-a', 'engine']:
        store.con.execute('insert into claims(claim_id) values (?)', [cid])
        store.con.execute('insert into claim_vectors(claim_id,embedding) values (?,?)', [cid,b'vector'])
    for eid, cid, ref in [(1,'shared',1),(2,'shared',2),(3,'only-a',1)]:
        store.con.execute('insert into evidence(evidence_id,claim_id,source_ref) values (?,?,?)', [eid,cid,ref])
        store.con.execute('insert into evidence_context(ctx_id,evidence_id,claim_id,source_ref) values (?,?,?,?)', [eid,eid,cid,ref])
        store.con.execute('insert into evidence_cites(evidence_id,claim_id,source_ref) values (?,?,?)', [eid,cid,ref])
    store.con.close()
    return rec['id']


def test_remove_preserves_shared_claims_engine_history_and_assets(private):
    root = projects.project_dir(private)
    asset = root / 'papers' / 'figure.png'
    asset.parent.mkdir()
    asset.write_bytes(b'preserved')
    result = membership.remove_paper(private, '10.1234/a')
    assert result['project_id'] == private and not result['copied']
    con = duckdb.connect(str(projects.kg_path(private)), read_only=True)
    assert set(con.execute('select claim_id from claims').fetchnumpy()['claim_id']) == {'shared','engine'}
    assert set(con.execute('select claim_id from claim_vectors').fetchnumpy()['claim_id']) == {'shared','engine'}
    for table in ['evidence','evidence_context','evidence_cites','papers']:
        assert con.execute(f'select count(*) from {table} where source_ref=1').fetchone()[0] == 0
    assert con.execute("select count(*) from evidence where claim_id='shared'").fetchone()[0] == 1
    con.close()
    assert asset.read_bytes() == b'preserved'
    with pytest.raises(FileNotFoundError):
        membership.remove_paper(private, '10.1234/a')
    assert library.list_papers(private)['total'] == 1


def test_adopted_removal_copies_and_never_changes_original(private):
    source = projects.CORPORA / 'source'
    source.mkdir(parents=True)
    original = source / 'source_kg.duckdb'
    original.write_bytes(projects.kg_path(private).read_bytes())
    (source / 'papers').mkdir()
    (source / 'papers' / 'asset.png').write_bytes(b'original')
    (source / 'MANIFEST.json').write_text(json.dumps({'papers': [{'ref':1}]}))
    (source / 'corpus_card.md').write_text('# Original scientific framing\nScope: conserved mechanisms.\n')
    before = {p.relative_to(source): p.read_bytes() for p in source.rglob('*') if p.is_file()}
    result = membership.remove_paper('source', '10.1234/a')
    assert result['copied'] and result['project_id'] != 'source'
    assert library.list_papers('source')['total'] == 2
    assert library.list_papers(result['project_id'])['total'] == 1
    membership.refresh_card(result['project_id'])
    card = projects.corpus_card_path(result['project_id']).read_text()
    assert card.startswith('# Original scientific framing\nScope: conserved mechanisms.')
    assert card.count('<!-- library-membership -->') == 1
    assert 'currently contains 1 papers and 2 claims' in card
    assert before == {p.relative_to(source):p.read_bytes() for p in source.rglob('*') if p.is_file()}


def test_live_job_and_concurrent_project_lease_block_changes(private, monkeypatch):
    before = projects.kg_path(private).read_bytes()
    monkeypatch.setattr(jobs, 'active_job', lambda pid: {'id':'active'})
    with pytest.raises(RuntimeError, match='active job'):
        membership.remove_paper(private, '10.1234/a')
    assert projects.kg_path(private).read_bytes() == before
    monkeypatch.setattr(jobs, 'active_job', lambda pid: None)
    with membership.project_lease(private):
        with pytest.raises(RuntimeError, match='busy'):
            membership.remove_paper(private, '10.1234/a')


def test_doi_duplicates_skip_work_and_refs_remain_monotonic(private, monkeypatch):
    captured = []
    monkeypatch.setattr(membership, '_launch', lambda pid, items, fd: captured.append(items) or {'id':'job','kind':'membership'})
    result = membership.add_dois(private, ['https://doi.org/10.1234/A','10.1234/new','10.1234/new'])
    assert result['duplicates'] == ['10.1234/a']
    assert len(captured[0]) == 1 and captured[0][0]['doi'] == '10.1234/new'
    first_ref = captured[0][0]['ref']
    membership.add_dois(private, ['10.1234/next'])
    assert captured[1][0]['ref'] > first_ref


def test_external_duckdb_writer_blocks_removal(private):
    db = projects.kg_path(private)
    script = 'import duckdb,sys; c=duckdb.connect(sys.argv[1]); print("ready",flush=True); sys.stdin.readline()'
    child = subprocess.Popen([sys.executable,'-c',script,str(db)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
    try:
        assert child.stdout.readline().strip() == 'ready'
        with pytest.raises(RuntimeError, match='database is in use'):
            membership.remove_paper(private,'10.1234/a')
    finally:
        child.communicate('\n',timeout=10)


def test_detached_job_inherits_lease_until_exit(private):
    import os
    script = 'import time; time.sleep(0.5)'
    job = jobs._spawn(private, 'membership', [sys.executable, '-c', script])
    try:
        with pytest.raises(RuntimeError, match='busy'):
            with membership.project_lease(private):
                pass
    finally:
        os.waitpid(job['pid'], 0)
    with membership.project_lease(private):
        pass


def test_legacy_attachment_remove_clears_graph(private):
    rec = projects.load(private)
    rec['attachments'] = [{'id':'uploaded-a','ref':1,'filename':'a.txt'}]
    projects.save(rec)
    projects.write_corpus_card(private)
    assert 'a.txt' in projects.corpus_card_path(private).read_text()
    membership.remove_attachment(private, 'uploaded-a')
    assert 'a.txt' not in projects.corpus_card_path(private).read_text()
    assert library.list_papers(private)['total'] == 1
    assert projects.load(private)['attachments'] == []


def test_borrowed_project_graph_is_never_mutated(private, tmp_path):
    db = projects.kg_path(private)
    shared = tmp_path / 'live-study.duckdb'
    db.replace(shared)
    db.symlink_to(shared)
    before = shared.read_bytes()
    with pytest.raises(RuntimeError, match='shared data'):
        membership.remove_paper(private, '10.1234/a')
    with pytest.raises(RuntimeError, match='shared data'):
        membership.add_dois(private, ['10.1234/new'])
    assert shared.read_bytes() == before


def test_http_encoded_doi_remove_and_add_response(private, monkeypatch):
    from http.client import HTTPConnection
    from http.server import ThreadingHTTPServer
    from threading import Thread
    from dnhacksbio.webui.server import Handler
    monkeypatch.setattr(membership, '_launch', lambda pid, items, fd: {'id':'queued','kind':'membership','status':'running'})
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        def post(path, body):
            conn = HTTPConnection('127.0.0.1', server.server_port, timeout=5)
            conn.request('POST', path, json.dumps(body), {'Content-Type':'application/json'})
            response = conn.getresponse()
            result = response.status, json.loads(response.read())
            conn.close()
            return result
        status, response = post(f'/api/projects/{private}/papers/10.1234%2Fa/remove', {})
        assert status == 200 and response['removed'] == '10.1234/a'
        status, response = post(f'/api/projects/{private}/papers/add', {'dois':['10.1234/new']})
        assert status == 202 and response['project_id'] == private and response['job']['kind'] == 'membership'
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_http_launches_real_worker_in_private_projects_root(private, monkeypatch):
    """A tombstoned ref exercises real launch/import/lease/progress with zero model work."""
    import os
    import time
    from http.client import HTTPConnection
    from http.server import ThreadingHTTPServer
    from threading import Thread
    from dnhacksbio.webui.server import Handler
    monkeypatch.setenv('PYTHONPATH', os.pathsep.join(filter(None, [str(projects.ROOT / 'src'), os.environ.get('PYTHONPATH', '')])))
    con = duckdb.connect(str(projects.kg_path(private)))
    con.execute('create table library_removed_sources(source_ref integer primary key)')
    con.execute('insert into library_removed_sources values (10000)')
    con.close()
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    child_pid = None
    try:
        conn = HTTPConnection('127.0.0.1', server.server_port, timeout=10)
        conn.request('POST', f'/api/projects/{private}/papers/add', json.dumps({'dois':['10.1234/never-fetch']}), {'Content-Type':'application/json'})
        response = conn.getresponse()
        payload = json.loads(response.read())
        conn.close()
        assert response.status == 202, payload
        job = payload['job']
        child_pid = job['pid']
        assert job['argv'][job['argv'].index('--projects-root') + 1] == str(projects.PROJECTS.resolve())
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            done, status = os.waitpid(child_pid, os.WNOHANG)
            if done:
                child_pid = None
                assert os.waitstatus_to_exitcode(status) == 0, jobs.log_tail(private, job['id'])
                break
            time.sleep(.05)
        else:
            pytest.fail('private membership worker failed to finish')
        finished = jobs.get_job(private, job['id'])
        assert finished['status'] == 'done', finished
        assert finished['summary']['added'] == 0
        assert finished['summary']['duplicates'] == 1
        assert any(e['stage'] == 'removed' for e in jobs.events(private, job['id']))
        assert library.list_papers(private)['total'] == 2
    finally:
        if child_pid is not None:
            os.kill(child_pid, 15)
            os.waitpid(child_pid, 0)
        server.shutdown()
        server.server_close()
        thread.join()


def test_remove_updates_managed_manifest_counts_and_metadata(private):
    path = projects.project_dir(private) / 'MANIFEST.json'
    path.write_text(json.dumps({
        'n_papers': 2, 'n_claims': 3, 'papers': {'papers':2, 'full_text':0},
        'kg': {'claims':3, 'custom':'preserved'},
        'papers_meta': [{'ref':1, 'title':'removed'}, {'ref':2, 'title':'kept'}],
    }))
    membership.remove_paper(private, '10.1234/a')
    manifest = json.loads(path.read_text())
    assert manifest['papers'] == {'papers':1, 'full_text':0}
    assert manifest['papers_meta'] == [{'ref':2, 'title':'kept'}]
    assert manifest['n_papers'] == 1 and manifest['n_claims'] == 2
    assert manifest['kg']['claims'] == 2 and manifest['kg']['custom'] == 'preserved'
    assert library.list_papers(private)['total'] == 1
