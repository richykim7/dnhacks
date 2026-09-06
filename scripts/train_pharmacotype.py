"""Bounded real-development encoder/predictor comparison with donor holdouts."""
import argparse
import json
import resource
from pathlib import Path

import numpy as np

from dnhacksbio.pharmacotype_encoder import train, predict
from dnhacksbio.pharmacotype_data import prepare


def run(directory, *, epochs=150, backend='torch', device='cuda'):
    directory = Path(directory)
    data = prepare(json.loads((directory/'development.json').read_text()))
    splits = json.loads((directory/'splits.json').read_text())
    mean=None
    results, models = [], {}
    kinds=('identity','pca','mlp')
    for kind in kinds:
        for seed in (0,1,2):
            model = train(data,splits,kind=kind,latent=32,seed=seed,epochs=epochs,ridge=10.,backend=backend,device=device)
            if mean is None:mean=np.asarray(model['response']['mean'])
            path=directory/f'{kind}-seed{seed}.json'
            path.write_text(json.dumps(model,allow_nan=False))
            models[(kind,seed)] = model
            results.append(dict(kind=kind,seed=seed,model_sha256=model['sha256'],
                                training_seconds=model['training_seconds'],resources=model['resource_metrics'],**model['metrics']))
    selected = min(kinds,key=lambda k:np.mean([r['validation_curve_rmse'] for r in results if r['kind']==k]))
    # Select only the architecture by average validation error; report every seed.
    # Test errors are evaluated after selection and cannot select seeds or endpoints.
    groups = {'test':splits['test'], 'pancreatic_development':data['pdac_donors']}
    heldout = {}
    for name, donors in groups.items():
        ix=[data['donors'].index(d) for d in donors]
        heldout[name]={'n':len(ix),'training_mean_rmse':float(np.sqrt(np.mean((data['y'][ix]-mean)**2))),
                      'selected_model_seed_rmse':[float(np.sqrt(np.mean((predict(data['x'][ix],models[(selected,seed)])-data['y'][ix])**2))) for seed in (0,1,2)]}
    report=dict(schema='pharmacotype.training-report.v1',source_hash=data['source_hash'],
                contract_hash=data['contract_hash'],selected_by_validation=selected,
                trials=results,heldout=heldout,epochs_cap=epochs,
                peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                biological_scope='Public pooled established cell-line development, not PDO confirmation')
    (directory/'training-report.json').write_text(json.dumps(report,indent=2,allow_nan=False))
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data',required=True);parser.add_argument('--epochs',type=int,default=150)
    parser.add_argument('--backend',choices=['numpy','torch'],default='torch')
    parser.add_argument('--device',choices=['cpu','cuda'],default='cuda')
    args=parser.parse_args();run(args.data,epochs=args.epochs,backend=args.backend,device=args.device)
