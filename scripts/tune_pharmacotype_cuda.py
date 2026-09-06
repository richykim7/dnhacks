"""Bounded training-donor CV for PDO AUC prediction; all fitting uses CUDA."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import time

from dnhacksbio.pharmacotype_data import digest


def predict_auc(raw_fpkm,model):
    """Apply a frozen AUC kernel artifact to rows in its declared gene order."""
    import torch
    if not torch.cuda.is_available():raise RuntimeError('CUDA required')
    if model.get('schema')!='pharmacotype.auc-kernel-model.v1' or digest({k:v for k,v in model.items() if k!='sha256'})!=model.get('sha256'):
        raise ValueError('Invalid AUC model integrity')
    def tensor(value):return torch.as_tensor(value,dtype=torch.float64,device='cuda')
    raw=tensor(raw_fpkm)
    if raw.ndim!=2 or raw.shape[1]!=len(model['genes']) or not torch.isfinite(raw).all() or (raw<0).any():
        raise ValueError('Finite nonnegative FPKM in declared gene order required')
    query=(torch.log2(raw[:,model['features']]+1)-tensor(model['mean']))/tensor(model['scale'])
    reference=tensor(model['reference']);setting=model['setting']
    cross=query@reference.T/query.shape[1] if setting['kernel']=='linear' else torch.exp(-setting['gamma']*torch.cdist(query,reference).square()/model['bandwidth'])
    centered=cross-cross.mean(1,keepdim=True)-tensor(model['kernel_column_mean'])[None,:]+model['kernel_grand_mean']
    return centered@tensor(model['coef'])+tensor(model['target_mean'])


def run(directory):
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA required; no CPU fitting fallback')
    directory=Path(directory)
    data=json.loads((directory/'auc-development.json').read_text())
    integrity=data.pop('integrity_sha256')
    if data['schema']!='pharmacotype.auc-development.v1' or digest(data)!=integrity:
        raise ValueError('Invalid source input')
    donors=data['donors'];splits=data['splits']
    groups=[splits[k] for k in ('train','validation','test')]
    if len(set(sum(groups,[])))!=len(donors) or set(sum(groups,[]))!=set(donors):
        raise ValueError('Disjoint exhaustive donor splits required')
    train=[donors.index(d) for d in splits['train']]
    ordered=sorted(train,key=lambda i:hashlib.sha256(('cv-v1:'+donors[i]).encode()).hexdigest())
    folds=[ordered[i::3] for i in range(3)]
    grid=[dict(features=n,kernel=kernel,gamma=g,penalty=p)
          for n in (128,512,1000) for kernel,gammas in (('linear',(1.,)),('rbf',(.25,1.,4.)))
          for g in gammas for p in (.01,.1,1.,10.,100.)]
    design=dict(schema='pharmacotype.auc-cv-design.v1',input_integrity=integrity,
                selection='minimum pooled training-only three-fold CV MSE; grid order breaks ties',
                grid=grid,fold_rule='SHA256 cv-v1:source-ID ordering round-robin into three folds',
                evaluation='fixed validation; previously inspected test remains development only',
                preprocessing='fold-training log-FPKM variance, center and population standard deviation',
                target='all five registered chemotherapy AUC outputs, equally weighted')
    (directory/'cv-design.json').write_text(json.dumps(design,indent=2)+'\n')
    started=time.monotonic()
    with open('/tmp/dnhacks-gpu.lock','a') as lease:
        fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
        torch.cuda.reset_peak_memory_stats()
        x=torch.log2(torch.as_tensor(data['x'],dtype=torch.float64,device='cuda')+1)
        y=torch.as_tensor(data['y'],dtype=torch.float64,device='cuda')
        if not torch.isfinite(x).all() or not torch.isfinite(y).all():
            raise ValueError('Nonfinite input')

        def fit_predict(fit_indices,pred_indices,setting,*,export=False):
            raw=x[fit_indices]
            features=torch.argsort(raw.var(dim=0),descending=True,stable=True)[:setting['features']]
            raw=raw[:,features]
            mean=raw.mean(0);scale=raw.std(0,correction=0).clamp_min(1e-8)
            a=(raw-mean)/scale;b=(x[pred_indices][:,features]-mean)/scale
            if setting['kernel']=='linear':
                k=a@a.T/a.shape[1];cross=b@a.T/a.shape[1];bandwidth=1.
            else:
                distance=torch.cdist(a,a).square()
                bandwidth=distance[torch.triu(torch.ones_like(distance,dtype=torch.bool),diagonal=1)].median().clamp_min(1e-8)
                k=torch.exp(-setting['gamma']*distance/bandwidth)
                cross=torch.exp(-setting['gamma']*torch.cdist(b,a).square()/bandwidth)
            # Kernel ridge with unpenalized intercept, fitted using only fit_indices.
            column_mean=k.mean(0);grand=k.mean()
            centered=k-column_mean[None,:]-column_mean[:,None]+grand
            centered_cross=cross-cross.mean(1,keepdim=True)-column_mean[None,:]+grand
            target_mean=y[fit_indices].mean(0)
            coef=torch.linalg.solve(centered+setting['penalty']*torch.eye(len(a),device='cuda'),y[fit_indices]-target_mean)
            pred=centered_cross@coef+target_mean
            artifact=dict(features=features.cpu().tolist(),mean=mean.cpu().tolist(),scale=scale.cpu().tolist(),
                          reference=a.cpu().tolist(),bandwidth=float(bandwidth),kernel_column_mean=column_mean.cpu().tolist(),
                          kernel_grand_mean=float(grand),coef=coef.cpu().tolist(),target_mean=target_mean.cpu().tolist()) if export else None
            return pred,artifact

        trials=[]
        baseline_total=0.;count=0
        for held in folds:
            fit=[i for i in train if i not in held]
            baseline_total+=float((y[held]-y[fit].mean(0)).square().sum());count+=len(held)*y.shape[1]
        for setting in grid:
            if time.monotonic()-started>300:raise TimeoutError('Five-minute tuning cap')
            error=0.
            for held in folds:
                fit=[i for i in train if i not in held]
                pred,_=fit_predict(fit,held,setting)
                error+=float((pred-y[held]).square().sum())
            trials.append(dict(**setting,cv_rmse=(error/count)**.5))
        selected=min(range(len(trials)),key=lambda i:trials[i]['cv_rmse'])
        setting=grid[selected]
        # Freeze choice before accessing validation/test prediction errors.
        frozen=dict(design_hash=digest(design),selected=setting,selection_trial=selected)
        (directory/'cv-selection.json').write_text(json.dumps(frozen,indent=2)+'\n')
        held=[donors.index(d) for name in ('validation','test') for d in splits[name]]
        pred,artifact=fit_predict(train,held,setting,export=True)
        artifact.update(schema='pharmacotype.auc-kernel-model.v1',setting=setting,genes=data['genes'],panel=data['panel'],
                        source_hash=data['source_hash'],input_integrity=integrity,selection=frozen)
        artifact['sha256']=digest(artifact)
        (directory/'cv-model.json').write_text(json.dumps(artifact,allow_nan=False)+'\n')
        # Check portable inference before reporting held-out accuracy.
        replay=predict_auc([data['x'][i] for i in held],artifact)
        if not torch.allclose(replay,pred,atol=1e-10,rtol=1e-10):raise ValueError('Portable prediction mismatch')
        metrics={};offset=0
        for name in ('validation','test'):
            size=len(splits[name]);actual=y[held[offset:offset+size]];prediction=pred[offset:offset+size]
            metrics[name]=dict(rmse=float((prediction-actual).square().mean().sqrt()),
                               baseline_rmse=float((y[train].mean(0)-actual).square().mean().sqrt()))
            offset+=size
        torch.cuda.synchronize()
        report=dict(schema='pharmacotype.auc-cv-report.v1',design=design,selection=frozen,trials=trials,
                    cv_baseline_rmse=(baseline_total/count)**.5,metrics=metrics,model_sha256=artifact['sha256'],
                    split_counts={k:len(v) for k,v in splits.items()},seconds=time.monotonic()-started,
                    torch=torch.__version__,device='cuda',peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                    peak_reserved_bytes=torch.cuda.max_memory_reserved(),confirmation_enabled=False)
        (directory/'cv-report.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps({k:v for k,v in report.items() if k not in ('design','trials')},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--data',required=True)
    run(parser.parse_args().data)
