"""CUDA-only conventional PDO AUC benchmark, distinct from the full-curve endpoint."""
import argparse
import fcntl
import json
from pathlib import Path

from dnhacksbio.pharmacotype_data import digest
from dnhacksbio.pharmacotype_encoder import seal
from dnhacksbio.pharmacotype_torch import fit


def run(directory):
    import torch
    if not torch.cuda.is_available():raise RuntimeError('CUDA required; no CPU training fallback')
    directory=Path(directory);data=json.loads((directory/'auc-development.json').read_text())
    expected=data.pop('integrity_sha256')
    if data['schema']!='pharmacotype.auc-development.v1' or digest(data)!=expected:raise ValueError('Invalid AUC input integrity')
    splits=data['splits'];ix=[[data['donors'].index(d) for d in splits[k]] for k in ('train','validation','test')]
    trials=[]
    with open('/tmp/dnhacks-gpu.lock','a') as lease:
        fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
        x=torch.log2(torch.as_tensor(data['x'],dtype=torch.float64,device='cuda')+1)
        selected=torch.argsort(x[ix[0]].var(dim=0),descending=True,stable=True)[:1000]
        indices=selected.cpu().tolist()
        data['genes']=[data['genes'][i] for i in indices]
        data['x']=x[:,selected].cpu().numpy()
        del x
        data['contract_hash']=digest({'original':data['contract_hash'],'features':data['genes']})
        for kind in ('identity','pca','mlp'):
            for seed in (0,1,2):
                model=fit(data,splits,ix,kind=kind,latent=8,seed=seed,epochs=150,ridge=10.,missing_tolerance=0.,device='cuda')
                # The artifact cannot pass verification as a dose-curve model.
                model['schema']='pharmacotype.auc-model.v1'
                model['metrics']={k.replace('curve','auc'):v for k,v in model['metrics'].items()}
                model=seal(model)
                (directory/f'{kind}-seed{seed}.json').write_text(json.dumps(model,allow_nan=False))
                trials.append(dict(kind=kind,seed=seed,model_sha256=model['sha256'],training_seconds=model['training_seconds'],
                                   resources=model['resource_metrics'],**model['metrics']))
        y=torch.as_tensor(data['y'],dtype=torch.float64,device='cuda')
        mean=y[ix[0]].mean(dim=0)
        baseline={name+'_auc_rmse':float((y[i]-mean).square().mean().sqrt()) for name,i in zip(('validation','test'),ix[1:])}
        torch.cuda.synchronize()
    selected=min(('identity','pca','mlp'),key=lambda k:sum(t['validation_auc_rmse'] for t in trials if t['kind']==k)/3)
    learned_error=sum(t['validation_auc_rmse'] for t in trials if t['kind']==selected)/3
    retained=selected if learned_error<baseline['validation_auc_rmse'] else 'training_mean'
    report=dict(schema='pharmacotype.pdo-auc-benchmark.v1',source_hash=data['source_hash'],contract_hash=data['contract_hash'],
                donor_count=len(data['donors']),split_counts={k:len(v) for k,v in splits.items()},trials=trials,
                mean_baseline=baseline,selected_by_mean_validation=selected,
                retained_predictor=retained,confirmation_enabled=False,
                scope='Conventional measured PDO AUC prediction; no dose reconstruction or full-curve claim')
    (directory/'training-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data',required=True);run(p.parse_args().data)
