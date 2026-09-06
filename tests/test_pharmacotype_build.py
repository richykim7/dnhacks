import hashlib
import json
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from dnhacksbio.pharmacotype_data import prepare

spec=importlib.util.spec_from_file_location('pharmacotype_builder',Path(__file__).parents[1]/'scripts/build_pharmacotype_data.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)


def test_join_donor_selection_and_training_only_features(tmp_path):
    raw=tmp_path/'raw';raw.mkdir();out=tmp_path/'out'
    for article in (9393293,11384241,27993248):
        (raw/f'article-{article}.json').write_text(json.dumps({'files':[],'license':{'name':'synthetic'}}))
    ids=[f'm{i:03}' for i in range(100)];donors=[f'origin{i}' for i in range(100)]
    donors[1]=donors[0]  # Preferred derivative has incomplete response; no fallback.
    pd.DataFrame({'ModelID':ids,'PatientID':donors}).to_csv(raw/'Model.csv',index=False)
    pd.DataFrame({'row_name':ids,'passed_str_profiling':True,'primary_tissue':['pancreas']+['lung']*99}).to_csv(raw/'secondary-screen-cell-line-info.csv',index=False)
    treatments=[]
    for name in builder.PANEL:
        for dose in range(8):treatments.append(dict(name=name,screen_id='HTS002',dose=4.**dose/1000,broad_id=name,column_name=f'{name}-{dose}'))
    pd.DataFrame(treatments).to_csv(raw/'secondary-screen-replicate-collapsed-treatment-info.csv',index=False)
    y=np.ones((100,32));y[0,0]=np.nan
    pd.DataFrame(y,index=ids,columns=[t['column_name'] for t in treatments]).to_csv(raw/'secondary-screen-replicate-collapsed-logfold-change.csv')
    heldout=[int(hashlib.sha256(d.encode()).hexdigest()[:8],16)%100>=70 for d in donors]
    pd.DataFrame({'train_signal':np.arange(100.),'heldout_only':np.where(heldout,1e9,0)},index=ids).to_csv(raw/'CCLE_expression.csv')
    builder.build(raw,out,genes=1)
    doc=json.loads((out/'development.json').read_text());data=prepare(doc)
    assert donors[0] not in data['donors']
    assert data['genes']==['train_signal']
    assert data['panel'][0]['doses'][0]==pytest.approx(1e-9)
    assert len(data['donors'])==98
    doc['y'][0][0]=99
    with pytest.raises(ValueError,match='integrity'):prepare(doc)
    with pytest.raises(ValueError,match='schema'):prepare(data,role='confirmation')
    metadata={'files':[{'name':'Model.csv','computed_md5':'0'*32}], 'license':{'name':'synthetic'}}
    (raw/'article-27993248.json').write_text(json.dumps(metadata))
    with pytest.raises(ValueError,match='integrity'):builder.build(raw,out,genes=1)


def test_pdo_auc_identity_audit_and_curve_separation(tmp_path, monkeypatch):
    spec=importlib.util.spec_from_file_location('pdo_builder',Path(__file__).parents[1]/'scripts/build_pharmacotype_pdo.py')
    pdo=importlib.util.module_from_spec(spec);spec.loader.exec_module(pdo)
    raw=tmp_path/'raw';raw.mkdir();out=tmp_path/'out'
    ids=[f'CAS-DAC-{i}' for i in range(100)]
    records=[{'B':d,'F':'1','K':'Yes'} for d in ids]
    records[0]['F']='2'  # Repeated patient samples are not independent units.
    records[1]['K']='No'
    monkeypatch.setattr(pdo,'worksheet',lambda path:[{},{}]+records)
    (raw/'metadata.xlsx').write_bytes(b'synthetic metadata fixture')
    pd.DataFrame(np.ones((3,100)),index=['A','B','C'],columns=ids).to_csv(raw/'expression.txt.gz',sep='\t')
    responses=pd.DataFrame(np.ones((5,100))*.4,index=list(pdo.PANEL),columns=ids)
    responses.to_csv(raw/'drug_screening.txt.gz',sep='\t')
    audit=pdo.build(raw,out)
    data=json.loads((out/'auc-development.json').read_text())
    assert audit['eligible_pdac']==98
    assert not set(ids[:2]) & set(data['donors'])
    assert not audit['confirmation_enabled']
    assert all('doses' not in p for p in data['panel'])
    with pytest.raises(ValueError,match='schema'):prepare(data)
    before=data['splits']
    responses.iloc[:]=.8
    responses.to_csv(raw/'drug_screening.txt.gz',sep='\t')
    pdo.build(raw,out)
    assert json.loads((out/'auc-development.json').read_text())['splits']==before
    records.append(records[2])
    with pytest.raises(ValueError,match='Duplicate source organoid'):pdo.build(raw,out)


@pytest.mark.parametrize('pathways',[False,True])
def test_cuda_tuning_excludes_heldout_outcomes(tmp_path,pathways):
    torch=pytest.importorskip('torch')
    if not torch.cuda.is_available():pytest.skip('CUDA fitting requires GPU')
    from dnhacksbio.pharmacotype_data import digest
    spec=importlib.util.spec_from_file_location('pdo_tuner',Path(__file__).parents[1]/'scripts/tune_pharmacotype_cuda.py')
    tuner=importlib.util.module_from_spec(spec);spec.loader.exec_module(tuner)
    library=None
    if pathways:
        library=tmp_path/'frozen.gmt'
        library.write_text('early\tfixture\tG0\tG1\tG2\tG3\tG4\nlate\tfixture\tG7\tG8\tG9\tG10\tG11\n')
    rng=np.random.default_rng(3);z=rng.normal(size=(60,12))
    donors=[f'fixture-{i}' for i in range(60)]
    data=dict(schema='pharmacotype.auc-development.v1',donors=donors,
              genes=[f'G{i}' for i in range(12)],panel=[{'compound':'synthetic'}],source_hash='fixture',
              x=np.exp(z).tolist(),y=(z[:,:1]+.1*rng.normal(size=(60,1))).tolist(),
              splits=dict(train=donors[:40],validation=donors[40:50],test=donors[50:]))
    def run():
        data['integrity_sha256']=digest({k:v for k,v in data.items() if k!='integrity_sha256'})
        (tmp_path/'auc-development.json').write_text(json.dumps(data))
        tuner.run(tmp_path,pathways=library)
        output=tmp_path/'pathways' if pathways else tmp_path
        return [json.loads((output/name).read_text()) for name in ('cv-report.json','cv-model.json')]
    report,model=run()
    if not pathways:assert report['metrics']['test']['rmse']<report['metrics']['test']['baseline_rmse']
    else:
        assert model['pathways']['names']==['early','late']
        assert len(report['trials'])==20
    data['y'][40:]=[[99.] for _ in range(20)]
    changed,model2=run()
    assert changed['selection']['selected']==report['selection']['selected']
    assert changed['trials']==report['trials']
    assert model2['coef']==model['coef']
    assert model2['features']==model['features']


def test_cuda_pathway_ranks_are_sample_local_and_average_ties():
    torch=pytest.importorskip('torch')
    if not torch.cuda.is_available():pytest.skip('CUDA required')
    spec=importlib.util.spec_from_file_location('pdo_tuner',Path(__file__).parents[1]/'scripts/tune_pharmacotype_cuda.py')
    tuner=importlib.util.module_from_spec(spec);spec.loader.exec_module(tuner)
    raw=torch.tensor([[0.,0.,2.,4.],[1.,5.,5.,9.]],device='cuda',dtype=torch.float64)
    programs={'members':[[0,1],[2,3]]}
    result=tuner.inputs(raw,programs)
    assert torch.allclose(result,torch.tensor([[.375,.875],[.4375,.8125]],device='cuda',dtype=torch.float64))
    assert torch.equal(result[:1],tuner.inputs(raw[:1],programs))
    assert torch.equal(result,tuner.inputs(raw*7+11,programs))
