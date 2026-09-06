"""Synthetic contracts; these fixtures are not biological validation."""
import copy
import numpy as np
import pytest
from dnhacksbio.pharmacotype_data import prepare
from dnhacksbio.pharmacotype_encoder import train, predict, verify
from dnhacksbio.pharmacotype import profile, neighbors, compare_programs


def document(n=12, role='development', prefix='d'):
    assay = {k: 'declared' for k in ('version', 'technology', 'media', 'seeding', 'vehicle_control',
        'positive_control', 'molecular_sampling', 'population', 'license')}
    assay.update(scale='fraction_viability', source_sha256='a'*64, exposure_hours=72,
                 dose_unit='M', response_bounds=[-.2, 2.])
    ids = [f'{prefix}{i:02d}' for i in range(n)]
    return {'schema': 'pharmacotype.data.v1', 'role': role, 'assay': assay,
        'genes': ['g1', 'g2', 'g3'], 'panel': [{'compound': 'drug1', 'formulation': 'f1', 'doses': [1e-8, 1e-7]}],
        'aliases': {d:d for d in ids}, 'selected_cultures': {d:'c'+d for d in ids},
        'cultures': [{'origin': d, 'culture': 'c'+d, 'passage': 'p2', 'baseline_time': 'pre-treatment',
            'rna': [i+1, (i%3)+2, (i%5)+1], 'responses': [
                {'compound': 'drug1', 'dose': dose, 'plate': 'plate'+d, 'run': 'run'+d,
                 'pool': 'unpooled', 'replicate': str(r), 'value': 1.2 - i*.04 - j*.2 + r*.01}
                for j, dose in enumerate([1e-8,1e-7]) for r in range(2)]} for i,d in enumerate(ids)]}


def fitted(kind='pca'):
    doc = document(); data = prepare(doc); ids = data['donors']
    model = train(data, {'train': ids[:6], 'validation': ids[6:9], 'test': ids[9:]}, kind=kind, epochs=10)
    return doc, data, model


def test_curve_contract_and_source_scale():
    doc = document(); data = prepare(doc)
    assert data['y'][0,0] > 1
    assert data['y'].shape == (12,2)
    assert profile(doc)['status'] == 'development'
    doc['cultures'][0]['responses'] = doc['cultures'][0]['responses'][:2]
    data = prepare(doc)
    assert len(data['donors']) == 11
    assert data['exclusions'][0]['reason'] == 'incomplete_curve'


@pytest.mark.parametrize('change', ['alias','dose','scale','replicate','culture'])
def test_reject_invalid_assay_and_identity(change):
    doc = document()
    if change == 'alias': doc['aliases'].pop('d00')
    if change == 'dose': doc['assay']['dose_unit'] = 'uM'
    if change == 'scale': doc['cultures'][0]['responses'][0]['value'] = 3
    if change == 'replicate': doc['cultures'][0]['responses'].append(copy.deepcopy(doc['cultures'][0]['responses'][0]))
    if change == 'culture': doc['cultures'].append(copy.deepcopy(doc['cultures'][0]))
    with pytest.raises(ValueError): prepare(doc)


@pytest.mark.parametrize('kind', ['identity','pca','mlp'])
def test_training_prediction_and_tampering(kind):
    doc, data, model = fitted(kind)
    assert np.isfinite(predict(data['x'], model)).all()
    assert model['metrics']['test_curve_rmse'] >= 0
    assert len(neighbors(doc, [1,2,1], model, k=3)['neighbors']) == 3
    assert len(compare_programs(doc, model, ['g1'])['observed_high_minus_low']) == 2
    model['fill'][0] += 1
    with pytest.raises(ValueError, match='integrity'): verify(model)


def test_training_scaling_does_not_see_test():
    doc, data, model = fitted()
    data['x'][9:] *= 1000
    again = train(data, model['splits'], epochs=10)
    assert model['fill'] == again['fill']
    assert model['molecular'] == again['molecular']
    assert model['response'] == again['response']
    assert model['predictor'] == again['predictor']
    assert model['critic'] == again['critic']


def test_overlap_missingness_role():
    doc, data, model = fitted()
    bad = copy.deepcopy(model['splits']); bad['test'][0] = bad['train'][0]
    with pytest.raises(ValueError, match='disjoint'): train(data,bad)
    with pytest.raises(ValueError, match='Missing'): predict([[None,None,1]],model)
    doc['role'] = 'confirmation'
    with pytest.raises(ValueError, match='role'): profile(doc)


def manifest():
    _, _, model = fitted()
    cohort = document(n=4, role='confirmation', prefix='fresh')
    protocol = dict(schedule='fully-frozen-v1', sampling='iid-independent-donors',
        null='independence of frozen measured RNA and response representations',
        population='declared', family='family1', parent='parent1',
        eligibility_justification='Frozen complete-case eligibility independent of pairing',
        normalization_justification='Separate development-only scaling, no pooled controls',
        required_donors=4, null_streams=10000, power_lower_bound=.8, release='operator-reviewed',
        stake=.9, donor_order=prepare(cohort, role='confirmation')['donors'])
    protocol.update({k:'b'*64 for k in ('access_review','identity_review','sampling_review','power_review','privacy_review')})
    return dict(protocol_id='protocol1', hypothesis_id='hypothesis1', family_id='family1', cohort_id='cohort1',
                cohort=cohort, model=model, protocol=protocol)


def test_registration_fail_closed():
    from dnhacksbio.pharmacotype_scoring import registered
    m = manifest(); assert len(registered(m)['donors']) == 4
    for field, value in [('power_lower_bound',.7), ('null_streams',9999), ('sampling','shuffled finite cohort'),
                         ('privacy_review',''), ('required_donors',8)]:
        bad = copy.deepcopy(m); bad['protocol'][field] = value
        with pytest.raises(ValueError): registered(bad)
    m['model']['development_donors'].append('fresh00')
    from dnhacksbio.pharmacotype_encoder import seal
    m['model'] = seal(m['model'])
    with pytest.raises(ValueError, match='overlap'): registered(m)


@pytest.mark.parametrize('schedule',['fully-frozen-v1','past-block-bilinear-sgd-v1'])
def test_private_queue_alias_replay_and_tamper(tmp_path,schedule):
    import json
    from dnhacksbio.pharmacotype_scoring import Store
    m = manifest(); m['protocol']['schedule']=schedule
    path = tmp_path/'manifest.json'; path.write_text(json.dumps(m))
    store = Store(tmp_path/'queue')
    registration = store.configure(path, ledger=tmp_path/'ledger')
    assert 'donors' not in json.dumps(registration)
    for receipt in ('one','two'):
        assert store.enqueue(dict(request_id=receipt, **registration)) == dict(receipt=receipt,status='accepted')
    with store.connect() as con:
        assert con.execute('SELECT count(*) FROM jobs').fetchone()[0] == 1
        con.execute("UPDATE jobs SET status='running'")
    store.score_one('one')
    with store.connect() as con:
        status, raw = con.execute('SELECT status,result FROM jobs').fetchone()
        assert status == 'completed'
        result = json.loads(raw)
        assert result['cursor'] == 2
        con.execute("UPDATE jobs SET status='running'")
    store.score_one('one')
    with store.connect() as con:
        assert con.execute('SELECT result FROM jobs').fetchone()[0] == raw
    changed = copy.deepcopy(m); changed['protocol']['stake'] = .8
    path.write_text(json.dumps(changed))
    with pytest.raises(ValueError, match='frozen'): store.configure(path, ledger=tmp_path/'ledger')


def test_reject_pooled_and_shared_controls():
    from dnhacksbio.pharmacotype_scoring import registered
    m = manifest(); m['cohort']['cultures'][0]['responses'][0]['pool'] = 'sharedpool'
    with pytest.raises(ValueError, match='Pooled'): registered(m)
    m = manifest()
    for row in m['cohort']['cultures']:
        for well in row['responses']:
            well['run'] = 'sharedrun'; well['plate'] = 'sharedplate'
    with pytest.raises(ValueError, match='Shared plate'): registered(m)


def test_http_never_exposes_result(tmp_path):
    import json
    import threading
    import urllib.request
    import urllib.error
    from dnhacksbio.experiment_transport import make_server
    from dnhacksbio.pharmacotype_scoring import Store
    m = manifest(); path = tmp_path/'manifest.json'; path.write_text(json.dumps(m))
    store = Store(tmp_path/'queue'); registration = store.configure(path,ledger=tmp_path/'ledger')
    server = make_server(store,port=0)
    thread = threading.Thread(target=server.serve_forever); thread.start()
    base = 'http://127.0.0.1:'+str(server.server_port)
    try:
        payload = json.dumps(dict(request_id='private-request', **registration)).encode()
        request = urllib.request.Request(base+'/experiments',payload,{'Content-Type':'application/json'})
        with urllib.request.urlopen(request) as response:
            assert json.load(response) == dict(receipt='private-request',status='accepted')
        for route in ('/experiments/private-request','/results','/export'):
            with pytest.raises(urllib.error.HTTPError) as exc:
                urllib.request.urlopen(base+route)
            assert exc.value.code == 404
            assert exc.value.read() == b'{"error": "not found"}'
    finally:
        server.shutdown(); thread.join(); server.server_close()


def test_predict_unmeasured_query_and_cli(tmp_path):
    import json
    import subprocess
    import sys
    from dnhacksbio.pharmacotype import predict_document
    _, _, model = fitted()
    query = dict(schema='pharmacotype.query.v1', genes=list(model['genes']), contract_hash=model['contract_hash'],
                 ids=['unmeasured-model'], rna=[[1,2,3]])
    result = predict_document(query,model)
    assert len(result['curves'][0]) == 2
    for name,value in [('query',query), ('model',model)]:
        (tmp_path/(name+'.json')).write_text(json.dumps(value))
    subprocess.run([sys.executable,'-m','dnhacksbio.pharmacotype','predict','--data',str(tmp_path/'query.json'),
                    '--model',str(tmp_path/'model.json'),'--output',str(tmp_path/'predicted.json')],check=True)
    assert json.loads((tmp_path/'predicted.json').read_text()) == result
    query['genes'].reverse()
    with pytest.raises(ValueError, match='contract'): predict_document(query,model)


def test_plate_aggregation_weights_plates_equally():
    doc = document()
    wells = doc['cultures'][0]['responses']
    for w in wells: w['value'] = 0.
    for i in range(10):
        w = copy.deepcopy(wells[0]); w.update(plate='another',replicate=str(i),value=1.)
        wells.append(w)
    assert prepare(doc)['y'][0,0] == .5


def test_separate_view_encoding():
    _, data, model = fitted()
    data['y'] = data['y'] ** 2
    changed = train(data,model['splits'],epochs=10)
    assert changed['molecular'] == model['molecular']
    assert changed['response'] != model['response']


def test_optional_torch_artifact_and_invalid_device():
    _,data,model=fitted()
    with pytest.raises(ValueError):train(data,model['splits'],device='cuda')
    pytest.importorskip('torch')
    learned=train(data,model['splits'],kind='mlp',epochs=5,backend='torch')
    assert np.isfinite(predict(data['x'],learned)).all()
    assert learned['resource_metrics']['device']=='cpu'


def test_constant_critic_is_wealth_one_not_unavailable(tmp_path):
    import json
    from dnhacksbio.pharmacotype_scoring import Store
    from dnhacksbio.pharmacotype_encoder import seal
    m = manifest(); m['model']['critic'] = np.zeros_like(m['model']['critic']).tolist()
    m['model'] = seal(m['model']); path = tmp_path/'m.json'; path.write_text(json.dumps(m))
    store = Store(tmp_path/'q'); reg = store.configure(path,ledger=tmp_path/'l')
    store.enqueue(dict(request_id='constant',**reg))
    with store.connect() as con: con.execute("UPDATE jobs SET status='running'")
    store.score_one('constant')
    with store.connect() as con:
        status, raw = con.execute('SELECT status,result FROM jobs').fetchone()
    assert status == 'completed'
    assert json.loads(raw)['log_wealth'] == 0.


def test_crash_after_first_committed_block_recovers_in_worker(tmp_path, monkeypatch):
    import json
    import subprocess
    import sys
    from dnhacksbio.native_evidence import PrivateProcessStore
    from dnhacksbio.pharmacotype_scoring import Store
    path = tmp_path/'m.json'; path.write_text(json.dumps(manifest()))
    store = Store(tmp_path/'q'); reg = store.configure(path,ledger=tmp_path/'l')
    store.enqueue(dict(request_id='crash',**reg))
    with store.connect() as con: con.execute("UPDATE jobs SET status='running'")
    original = PrivateProcessStore.advance
    def crash_after_commit(self,*args,**kwargs):
        original(self,*args,**kwargs)
        raise RuntimeError('simulated interruption after ledger commit')
    with monkeypatch.context() as patch:
        patch.setattr(PrivateProcessStore,'advance',crash_after_commit)
        store.score_one('crash')
    with store.connect() as con:
        assert con.execute('SELECT status FROM jobs').fetchone()[0] == 'failed'
    result = subprocess.run([sys.executable,'-m','dnhacksbio.pharmacotype_scoring','replay',
                             '--state',str(tmp_path/'q')],capture_output=True,check=True)
    assert not result.stdout and not result.stderr
    with store.connect() as con:
        status, raw = con.execute('SELECT status,result FROM jobs').fetchone()
    assert status == 'completed'
    assert json.loads(raw)['cursor'] == 2
    assert len(json.loads(raw)['blocks']) == 2
