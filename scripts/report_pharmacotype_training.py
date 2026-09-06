"""Publish aggregate model cards without donor identifiers or expression data."""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from dnhacksbio.pharmacotype_data import prepare
from dnhacksbio.pharmacotype_encoder import predict, verify


def report(directory):
    directory=Path(directory)
    cpu=json.loads((directory/'training-report.json').read_text())
    gpu=json.loads((directory/'gpu/training-report.json').read_text())
    data=prepare(json.loads((directory/'development.json').read_text()))
    splits=json.loads((directory/'splits.json').read_text())
    for trial_report in (cpu,gpu):
        if any(trial_report[k]!=data[k] for k in ('source_hash','contract_hash')):
            raise ValueError('Reports refer to a different development source or contract')
    candidates={('numpy',kind):[r for r in cpu['trials'] if r['kind']==kind] for kind in ('identity','pca','mlp')}
    candidates[('torch-cuda','mlp')]=gpu['trials']
    selected=min(candidates,key=lambda key:np.mean([r['validation_curve_rmse'] for r in candidates[key]]))
    folder=directory/'gpu' if selected[0]=='torch-cuda' else directory
    # Seed zero is a predeclared representative, never selected using its error.
    model=json.loads((folder/f'{selected[1]}-seed0.json').read_text());verify(model)
    ix=[data['donors'].index(d) for d in splits['test']]
    prediction=predict(data['x'][ix],model);truth=data['y'][ix]
    by_drug=[];offset=0
    for panel in data['panel']:
        n=len(panel['doses']);p=prediction[:,offset:offset+n];y=truth[:,offset:offset+n]
        # Descriptive rank correlation of observed log-dose curve means.
        dose=np.log(panel['doses'])
        a=np.trapezoid(p,x=dose,axis=1)/(dose[-1]-dose[0])
        b=np.trapezoid(y,x=dose,axis=1)/(dose[-1]-dose[0])
        by_drug.append(dict(compound=panel['name'],test_curve_rmse=float(np.sqrt(np.mean((p-y)**2))),
                            predicted_observed_logdose_mean_spearman=float(np.corrcoef(pd.Series(a).rank(),pd.Series(b).rank())[0,1])))
        offset+=n
    return dict(schema='pharmacotype.public-model-card.v1',cpu=cpu,gpu=gpu,
                selected='-'.join(selected),selection_rule='lowest mean validation RMSE across all three seeds; no test or seed selection',
                per_drug_test=by_drug,confirmation_enabled=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();Path(a.output).write_text(json.dumps(report(a.data),indent=2,allow_nan=False)+'\n')
