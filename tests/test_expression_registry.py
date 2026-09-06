import copy
import json
import threading
import urllib.error
import urllib.request
import numpy as np
import pytest
from dnhacksbio.registered_expression_scoring import Store, canonical, sha, validate_payload
from dnhacksbio.experiment_transport import make_server
from dnhacksbio.expression_experiment import submit_dataset, main
from test_pathway_evalue import arrays, protocol


def fixture(tmp_path):
    a = arrays()
    np.savez(tmp_path/'data.npz', **a)
    manifest = {'data_sha256': sha((tmp_path/'data.npz').read_bytes()), 'source': 'synthetic fixture', 'release': 'v1',
                'organism': 'human', 'input_scale': 'TPM', 'unit_namespace': 'fixture-donors', 'aliases_resolved': True,
                'discovery_units': [], 'confirmation': False, 'aggregation': 'one aliquot per donor/condition; lanes aggregated', 'mapping': 'fixture canonical genes'}
    p = {**protocol(), 'organism': 'human', 'endpoint': 'fixed pathway', 'dose': 'fixed', 'time': 'fixed',
         'exclusions': 'none', 'aggregation': manifest['aggregation'], 'mapping': manifest['mapping'],
         'resource_id': 'r1', 'cohort_id': 'c1', 'hypothesis': 'fixed hypothesis', 'family_id': 'f1', 'count_effects': False}
    registry = {'schema_version': 1, 'protocols': {'p1': p},
                'resources': {'r1': {'organism': 'human', 'mapping': manifest['mapping'], 'source': 'synthetic fixture', 'release': 'v1', 'weights': {'A': 2., 'C': -1.}}},
                'cohorts': {'c1': {'path': 'data.npz', 'manifest': manifest}}}
    path = tmp_path/'registry.json'; path.write_text(json.dumps(registry))
    payload = {'request_id': 'receipt1', 'spec': {'schema_version': 2, 'method': 'paired-pathway-v1', 'protocol_id': 'p1', 'hypothesis': p['hypothesis'], 'family_id': 'f1'},
               'input': {'cohort_id': 'c1', 'manifest_sha256': sha(canonical(manifest).encode())}}
    store = Store(tmp_path/'state'); store.configure(path)
    return store, path, registry, payload


def test_retries_private_score_and_restart(tmp_path):
    store, path, registry, payload = fixture(tmp_path)
    assert store.enqueue(payload) == {'receipt': 'receipt1', 'status': 'accepted'}
    store.enqueue(payload)
    store.enqueue({**payload, 'request_id': 'receipt2'})
    with store.connect() as con:
        assert con.execute('SELECT count(*) FROM jobs').fetchone()[0] == 1
        assert con.execute('SELECT count(*) FROM aliases').fetchone()[0] == 2
    store = Store(store.directory); store.configure(path)
    assert store.process_one()
    assert not store.process_one()
    with store.connect() as con:
        status, result, error = con.execute('SELECT status, result, error FROM jobs').fetchone()
    assert (status, error) == ('completed', None)
    r = json.loads(result)
    assert r['e'] == 63 and r['confirmation'] is False
    assert r['resource_sha256'] and r['protocol_sha256']
    store.enqueue({**payload, 'request_id': 'receipt3'})
    assert not store.process_one()


def test_frozen_and_tampering(tmp_path):
    store, path, registry, payload = fixture(tmp_path)
    registry['protocols']['p1']['seed'] = 0; path.write_text(json.dumps(registry))
    with pytest.raises(ValueError): store.configure(path)
    wrong = copy.deepcopy(payload); wrong['spec']['hypothesis'] = 'changed'
    with pytest.raises(ValueError): store.enqueue(wrong)
    wrong = copy.deepcopy(payload); wrong['input']['manifest_sha256'] = '0'*64
    with pytest.raises(ValueError): store.enqueue(wrong)
    with store.connect() as con:
        assert con.execute("SELECT count(*) FROM submissions WHERE outcome='rejected_validation'").fetchone()[0] == 2
    store.enqueue(payload)
    next(store.directory.glob('*.npz')).write_bytes(b'tampered')
    store.process_one()
    with store.connect() as con:
        assert con.execute('SELECT status, result FROM jobs').fetchone() == ('failed', None)


@pytest.mark.parametrize('mutation', ['overlap', 'alias', 'pair', 'batch'])
def test_design_rejection(tmp_path, mutation):
    store, path, registry, payload = fixture(tmp_path)
    manifest = registry['cohorts']['c1']['manifest']
    if mutation == 'overlap': manifest['discovery_units'] = ['u0']
    elif mutation == 'alias': manifest['aliases_resolved'] = False
    else:
        a = arrays()
        if mutation == 'pair': a['unit_ids'][1] = 'bad'
        else: a['batch'][1] = 'b2'
        np.savez(tmp_path/'data.npz', **a)
        manifest['data_sha256'] = sha((tmp_path/'data.npz').read_bytes())
    path.write_text(json.dumps(registry))
    with pytest.raises(ValueError): Store(tmp_path/'different').configure(path)


def test_http_no_leak_and_cli(tmp_path, capsys):
    store, path, registry, payload = fixture(tmp_path)
    server = make_server(store, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    endpoint = f'http://127.0.0.1:{server.server_port}'
    spec = tmp_path/'spec.json'; spec.write_text(json.dumps({'spec': payload['spec'], 'manifest_sha256': payload['input']['manifest_sha256']}))
    try:
        assert submit_dataset('c1', spec, 'receipt1', endpoint=endpoint) == {'receipt': 'receipt1', 'status': 'accepted'}
        store.process_one()
        for route in ('/experiments', '/results', '/status', '/receipt1'):
            with pytest.raises(urllib.error.HTTPError) as error: urllib.request.urlopen(endpoint + route)
            assert error.value.code == 404
            assert error.value.read() == b'{"error": "not found"}'
        wrong = copy.deepcopy(payload); wrong['spec']['p'] = .001
        req = urllib.request.Request(endpoint+'/experiments', json.dumps(wrong).encode(), method='POST')
        with pytest.raises(urllib.error.HTTPError) as error: urllib.request.urlopen(req)
        assert error.value.read() == b'{"error": "submission not accepted"}'
        assert capsys.readouterr() == ('', '')
    finally:
        server.shutdown(); thread.join(); server.server_close()
    with pytest.raises(SystemExit): main(['--input', 'x', '--dataset-id', 'c1', '--spec', 's', '--request-id', 'r'])


def test_approximate_count_fixture():
    pytest.importorskip('pydeseq2')
    from dnhacksbio.count_expression import paired_count_effects
    a = arrays(8)
    rng = np.random.default_rng(419)
    a['X'] = rng.negative_binomial(20, .2, size=(16, 100))
    a['X'][1::2, 0] *= 4
    a['genes'] = np.array([f'g{i}' for i in range(100)])
    r = paired_count_effects(a)
    assert r['inference'].startswith('model-based approximate')
    assert len(r['results']) == 100
    assert r['results'][0]['log2FoldChange'] == pytest.approx(2.165352085, abs=1e-5)
    assert r['results'][0]['lfcSE'] == pytest.approx(.1610542012, abs=1e-5)
    assert 'e' not in r


def test_protocol_aliases_share_one_result(tmp_path):
    store, path, registry, payload = fixture(tmp_path)
    registry['protocols']['p2'] = {**registry['protocols']['p1'], 'hypothesis': 'alias hypothesis', 'family_id': 'f2'}
    path.write_text(json.dumps(registry))
    store = Store(tmp_path/'aliases'); store.configure(path)
    store.enqueue(payload)
    other = copy.deepcopy(payload)
    other['request_id'] = 'alias-request'
    other['spec'].update(protocol_id='p2', hypothesis='alias hypothesis', family_id='f2')
    store.enqueue(other)
    with store.connect() as con:
        assert con.execute('SELECT count(*) FROM jobs').fetchone()[0] == 1
        assert con.execute('SELECT count(*) FROM submissions').fetchone()[0] == 2
    # Reuse the first receipt with a conflicting, but registered declaration.
    other['request_id'] = payload['request_id']
    with pytest.raises(ValueError): store.enqueue(other)
    with store.connect() as con:
        assert con.execute('SELECT outcome FROM submissions ORDER BY id DESC LIMIT 1').fetchone()[0] == 'conflicting_retry'


def test_timeout_is_private(tmp_path, monkeypatch, capsys):
    import subprocess
    store, _, _, payload = fixture(tmp_path)
    store.enqueue(payload)
    def timeout(*args, **kwargs):
        assert kwargs['stdout'] == subprocess.DEVNULL and kwargs['stderr'] == subprocess.DEVNULL
        raise subprocess.TimeoutExpired('private worker', 1)
    monkeypatch.setattr(subprocess, 'run', timeout)
    assert store.process_one(timeout=1)
    with store.connect() as con:
        assert con.execute('SELECT status, error FROM jobs').fetchone() == ('failed', 'worker_timeout')
    assert capsys.readouterr() == ('', '')


def test_private_count_worker_and_export(tmp_path, capsys):
    pytest.importorskip('pydeseq2')
    from dnhacksbio.registered_expression_scoring import main as service_main
    _, path, registry, payload = fixture(tmp_path)
    a = arrays(8)
    rng = np.random.default_rng(419)
    a['X'] = rng.negative_binomial(20, .2, size=(16, 100))
    a['X'][1::2, 0] *= 4
    a['genes'] = np.array([f'g{i}' for i in range(100)])
    np.savez(tmp_path/'data.npz', **a)
    manifest = registry['cohorts']['c1']['manifest']
    manifest.update(input_scale='counts', data_sha256=sha((tmp_path/'data.npz').read_bytes()))
    registry['protocols']['p1'].update(input_scale='counts', count_effects=True)
    registry['resources']['r1']['weights'] = {'g0': 2., 'g1': -1.}
    payload['input']['manifest_sha256'] = sha(canonical(manifest).encode())
    path.write_text(json.dumps(registry))
    store = Store(tmp_path/'counts'); store.configure(path)
    store.enqueue(payload); store.process_one()
    output = tmp_path/'export.json'; output.write_text(''); output.chmod(0o644)
    service_main(['export', '--state', str(store.directory), '--output', str(output)])
    export = json.loads(output.read_text())
    assert output.stat().st_mode & 0o777 == 0o600
    result = export['experiments'][0]['result']
    assert result['count_effects']['results'][0]['log2FoldChange'] == pytest.approx(2.165352085, abs=1e-5)
    assert result['scale'] == 'counts'
    assert len(export['submissions']) == 1
    assert capsys.readouterr() == ('', '')
