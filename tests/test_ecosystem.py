import copy
import json
import threading
import urllib.error
import urllib.request

import numpy as np
import pytest

from dnhacksbio.ecosystem_design import CountData, bags, digest
from dnhacksbio.ecosystem_encoder import CompartmentEncoder, fit_pca, profile
from dnhacksbio.ecosystem_experiments import EcosystemQueue, couple, compare, main, spatial_profile
from dnhacksbio.experiment_transport import make_server
from test_native_evidence import spec


def dataset(role='development', prefix='dev'):
    cells=[]; counts=[]; crosswalk=[]
    for d in range(4):
        donor=f'{prefix}-{d}'
        crosswalk.append(dict(accession=prefix,specimen=donor,donor=donor,timepoint='baseline',identity_reviewed=True))
        for compartment in ('malignant','fibroblast'):
            for i in range(6):
                cells.append(dict(cell_id=f'{donor}-{compartment}-{i}',accession=prefix,specimen=donor,
                                  compartment=compartment,state='s1' if i<3 else 's2'))
                counts.append([i+d+1, 7-i, d+2])
    dense=np.asarray(counts,dtype=np.int64)
    return CountData(dense.ravel(),np.tile(np.arange(3),len(cells)),np.arange(0,dense.size+1,3),('g1','g2','g3'),cells,
        dict(schema='ecosystem-counts-v1',scale='UMI counts',population='untreated-primary-human-PDAC',organism='human',
             tissue='pancreas',assay='scRNA',ontology='test-ontology-v1',state_dictionary='test-states-v1',
             sampling_justification='synthetic independent donors',specimen_rule='one-preselected-specimen-per-donor',
             sources=[dict(accession=prefix,license='synthetic',access_status='verified-local',role=role,sha256='a'*64)],
             crosswalk=crosswalk))


def test_sparse_roundtrip_and_frozen_profile(tmp_path):
    train=dataset('training','train'); dev=dataset()
    train.save(tmp_path/'counts.npz')
    loaded=CountData.load(tmp_path/'counts.npz',roles=('training',))
    assert train.identity()==loaded.identity()
    model=fit_pca(train,'malignant',components=2,cells_per_donor=4)
    model.save(tmp_path/'model.npz')
    frozen=CompartmentEncoder.load(tmp_path/'model.npz')
    assert frozen.identity==model.identity
    p=profile(dev,frozen,states=['s1','s2'],min_cells=4,cells_per_donor=4)
    assert len(p['donors'])==4
    assert p['confirmation']=='unavailable'
    assert all(v['sampled_cells']==4 and sum(v['occupancy'])==1 for v in p['donors'].values())
    assert p==profile(dev,frozen,states=['s1','s2'],min_cells=4,cells_per_donor=4)
    with pytest.raises(ValueError): frozen.transform([[1,2,3]],['g2','g1','g3'])
    with pytest.raises(ValueError): frozen.transform([[1.2,2,3]],train.genes)
    train.manifest['sources'][0]['role']='development'
    with pytest.raises(ValueError): profile(train,frozen,states=['s1','s2'],min_cells=4,cells_per_donor=4)


def test_identity_coverage_and_assay_fail_closed():
    d=dataset(); d.validate()
    d.manifest['crosswalk'][0]['identity_reviewed']=False
    with pytest.raises(ValueError): d.validate()
    d=dataset(); d.indices[1]=0
    with pytest.raises(ValueError): d.validate()
    d=dataset(); d.data=d.data.astype(float)
    with pytest.raises(ValueError): d.validate()
    d=dataset(); d.manifest['crosswalk'][1]['donor']='dev-0'
    with pytest.raises(ValueError): d.validate()
    d=dataset(); selected, missing=bags(d,'immune',min_cells=4,cells_per_donor=4,seed=0)
    assert not selected and len(missing)==4
    d=dataset(); d.manifest['sources'][0]['role']='private'
    with pytest.raises(ValueError): d.validate()
    model=fit_pca(dataset('training','train'),'malignant',components=2,cells_per_donor=4)
    d=dataset(); d.manifest['assay']='snRNA'
    with pytest.raises(ValueError): profile(d,model,states=['s1','s2'],min_cells=4,cells_per_donor=4)


def profiles(prefix='dev'):
    train=dataset('training','train'); dev=dataset(prefix=prefix)
    return [profile(dev,fit_pca(train,c,components=2,cells_per_donor=4),states=['s1','s2'],min_cells=4,cells_per_donor=4)
            for c in ('malignant','fibroblast')]


def test_development_operations():
    a,b=profiles()
    assert couple(a,b)['n_donors']==4
    with pytest.raises(ValueError): couple(a,a)
    with pytest.raises(ValueError): compare(a,a)
    other,_=profiles('other')
    assert compare(a,other)['n_donors']==[4,4]
    doc=dict(role='development',resolution='segmented-single-cell',assay='synthetic-imaging',
             segmentation_hash='a'*64,coordinate_units='micrometer',specimen_rule='one-preselected-section-per-donor',
             radius=2,compartments=['malignant','fibroblast'],states=['s1'],cells=[
                 dict(cell_id='a',donor='d',section='s',compartment='malignant',state='s1',xy=[0,0],identity_reviewed=True),
                 dict(cell_id='b',donor='d',section='s',compartment='fibroblast',state='s1',xy=[1,0],identity_reviewed=True)])
    assert spatial_profile(doc)['donors']['d']['mean_state_occupancy']==[1]
    doc['resolution']='GeoMx'
    with pytest.raises(ValueError): spatial_profile(doc)


def private_document():
    s=spec(); s['null']='independence-of-measured-malignant-and-fibroblast-states'; s['population']='untreated-primary-human-PDAC'
    s['eligible_donors']=[f'private-{i}' for i in range(10)]
    observations=[dict(donor=d,x=[float(i%2)],y=[float(i%2)]) for i,d in enumerate(s['eligible_donors'])]
    s['data_hash']=digest(observations)
    gates={k:dict(approved=True,reviewer='synthetic-test-operator',artifact_sha256='a'*64)
           for k in ('identity','access','sampling','transfer','selection','privacy','novelty')}
    gates['power']=dict(null_streams=10000,alpha=.05,power_lower_bound=.8,artifact_sha256='b'*64,available_donors=10)
    return dict(spec=s,observations=observations,gates=gates)


@pytest.mark.parametrize('schedule', ['fully-frozen-v1', 'past-block-bilinear-sgd-v1'])
def test_private_queue_retry_receipts_and_http_containment(tmp_path, schedule):
    q=EcosystemQueue(tmp_path)
    doc=private_document(); doc['spec']['schedule']=schedule
    doc['ledger_directory']=str(tmp_path/'shared-ledger'); registration=q.configure(doc)
    server=make_server(q,port=0); thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    url=f'http://127.0.0.1:{server.server_port}'
    try:
        for request_id,ref in [('r',registration),('alias',registration),('unknown','0'*64)]:
            req=urllib.request.Request(url+'/experiments',json.dumps(dict(request_id=request_id,registration=ref)).encode(),{'Content-Type':'application/json'})
            with urllib.request.urlopen(req) as response:
                assert response.status==202
                assert json.load(response)==dict(receipt=request_id,status='accepted')
        with pytest.raises(urllib.error.HTTPError) as e: urllib.request.urlopen(url+'/results/r')
        assert e.value.code==404
        with q.connect() as con:
            assert con.execute('SELECT count(*) FROM jobs').fetchone()[0]==2
            con.execute("UPDATE jobs SET status='running'")
        q.score_one('r'); q.score_one('unknown')
        with q.connect() as con:
            assert con.execute("SELECT status FROM jobs WHERE receipt='r'").fetchone()[0]=='complete'
            assert con.execute("SELECT status FROM jobs WHERE receipt='unknown'").fetchone()[0]=='failed'
        assert q.export_private('alias')==q.export_private('r')
        # Outcome-independent receipt after completion or private failure.
        assert q.enqueue(dict(request_id='again',registration=registration))==dict(receipt='again',status='accepted')
    finally:
        server.shutdown();server.server_close();thread.join()


def test_private_gates_and_cli(tmp_path,capsys):
    q=EcosystemQueue(tmp_path/'q'); doc=private_document()
    doc['gates']['power']['power_lower_bound']=.79
    with pytest.raises(ValueError): q.configure(doc)
    doc=private_document();doc['observations'][0]['donor']='alias'
    with pytest.raises(ValueError): q.configure(doc)
    assert main(['register','--registration','invalid','--request-id','r','--endpoint','http://localhost:1'])==1
    output=capsys.readouterr()
    assert output.out=='' and 'unavailable' in output.err


def test_nb_count_training_artifact_and_inference(tmp_path):
    pytest.importorskip('torch')
    from dnhacksbio.ecosystem_encoder import fit_nb, load_encoder
    model=fit_nb(dataset('training','train'),'malignant',components=2,cells_per_donor=4,epochs=1,batch_size=8)
    assert np.isfinite(model.manifest['training_loss']).all()
    model.save(tmp_path/'nb.npz')
    loaded=load_encoder(tmp_path/'nb.npz')
    assert loaded.identity==model.identity
    result=profile(dataset(),loaded,states=['s1','s2'],min_cells=4,cells_per_donor=4)
    assert len(result['donors'])==4
    assert all(len(v['mean'])==2 for v in result['donors'].values())


def test_malicious_npz_header_is_rejected_before_allocation(tmp_path):
    import io
    import zipfile
    from dnhacksbio.ecosystem_design import safe_npz
    buffer=io.BytesIO()
    np.lib.format.write_array_header_1_0(buffer,dict(descr='<f8',fortran_order=False,shape=(10**12,)))
    with zipfile.ZipFile(tmp_path/'bad.npz','w') as z:
        z.writestr('data.npy',buffer.getvalue())
    with pytest.raises(ValueError,match='storage'):
        safe_npz(tmp_path/'bad.npz',{'data'})


def test_donor_holdout_evaluation():
    from dnhacksbio.ecosystem_encoder import evaluate_holdout
    model=fit_pca(dataset('training','train'),'malignant',components=2,cells_per_donor=4)
    result=evaluate_holdout(dataset(),model,states=['s1','s2'],min_cells=4,cells_per_donor=4)
    assert result['unseen_study'] is True
    assert len(result['donor_log_library_reconstruction_mse'])==4
    assert all(v>=0 for v in result['donor_log_library_reconstruction_mse'].values())


def test_simulation_summary_keeps_noncrossers():
    from dnhacksbio.ecosystem_simulations import summarize
    result=summarize(np.log([[1,30],[1,2],[21,1]]))
    assert result['noncrossers']==1
    assert result['detection_delay_blocks']=={'1':1,'2':1}
    assert result['final_rejection']==pytest.approx(1/3)


def test_measured_library_offsets_are_frozen_and_not_selected_totals():
    from dnhacksbio.ecosystem_encoder import log_library
    train=dataset('training','train');train.manifest['library_size_rule']='measured-all-genes'
    for c in train.cells:c['library_size']=100
    model=fit_pca(train,'malignant',components=2,cells_per_donor=4)
    with pytest.raises(ValueError,match='offsets'):model.transform([[1,2,3]],train.genes)
    assert not np.allclose(log_library([[1,2,3]],[100]),log_library([[1,2,3]]))
    with pytest.raises(ValueError):log_library([[1,2,3]],[5])
    with pytest.raises(ValueError):log_library([[1,2,3]],[float('nan')])
    train.data[:3]=0
    assert np.array_equal(train.rows([0]),[[0,0,0]])
    train.cells[0]['library_size']=0
    with pytest.raises(ValueError):train.rows([0])


def test_original_count_parser_rejects_truncated_rows(tmp_path):
    from dnhacksbio.ecosystem_data import count_rows
    path=tmp_path/'matrix.txt';path.write_text('"T1_a" "T2_b"\n"G1" 1 2\n"G2" 0 3\n')
    rows=list(count_rows(path));assert [g for g,_ in rows]==['G1','G2']
    assert rows[0][1].tolist()==[1,2]
    path.write_text('"T1_a" "T2_b"\n"G1" 1\n')
    with pytest.raises(ValueError):list(count_rows(path))


def test_pseudobulk_uses_donors_and_full_library_offsets():
    from dnhacksbio.ecosystem_encoder import fit_pseudobulk_pca
    train=dataset('training','train')
    model=fit_pseudobulk_pca(train,'malignant',components=32,cells_per_donor=4)
    assert model.projection.shape==(3,3)
    assert len(model.manifest['training_donors'])==4
    assert model.manifest['model_choice']=='donor-pseudobulk-PCA-baseline'


def test_learned_set_frozen_invariant_and_donor_safe(tmp_path):
    pytest.importorskip('torch')
    from dnhacksbio.ecosystem_encoder import FrozenSetAggregator, fit_set_aggregator, evaluate_set_aggregator
    train=dataset('training','train');dev=dataset()
    cell=fit_pca(train,'malignant',components=2,cells_per_donor=4)
    model,baseline=fit_set_aggregator(train,cell,components=2,cells_per_donor=4,epochs=2)
    model.save(tmp_path/'set.npz');loaded=FrozenSetAggregator.load(tmp_path/'set.npz')
    assert loaded.identity==model.identity
    rows=[0,1,2,3];z=cell.transform(dev.rows(rows),dev.genes,dev.library_sizes(rows))
    np.testing.assert_allclose(loaded.transform(z,cell_encoder_hash=cell.identity),loaded.transform(z[::-1],cell_encoder_hash=cell.identity))
    with pytest.raises(ValueError):loaded.transform(z,cell_encoder_hash='a'*64)
    with pytest.raises(ValueError):loaded.weights[0][0,0]=0
    result=evaluate_set_aggregator(dev,cell,loaded,baseline,cells_per_donor=4)
    assert result['eligible_donors']==4 and all(np.isfinite(v) for v in result['means'].values())
    p=profile(dev,cell,states=['s1','s2'],min_cells=4,cells_per_donor=4,set_encoder=loaded)
    shifted=dataset();shifted.manifest['assay']='snRNA'
    with pytest.raises(ValueError,match='domain shift'):evaluate_set_aggregator(shifted,cell,loaded,baseline,cells_per_donor=4)
    assert p['set_model_hash']==loaded.identity
    assert all(len(v['learned_set_embedding'])==2 for v in p['donors'].values())
    overlap=dataset('development','train')
    with pytest.raises(ValueError,match='overlap'):evaluate_set_aggregator(overlap,cell,loaded,baseline,cells_per_donor=4)


def test_original_count_parser_rejects_fractional_or_negative_counts(tmp_path):
    from dnhacksbio.ecosystem_data import count_rows
    for values in ('1 2.5','1 -2','1 NaN'):
        path=tmp_path/'matrix.txt';path.write_text('"T1_a" "T2_b"\n"G1" '+values+'\n')
        with pytest.raises(ValueError):list(count_rows(path))
