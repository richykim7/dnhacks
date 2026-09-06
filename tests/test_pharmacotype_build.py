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
