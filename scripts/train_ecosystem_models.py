#!/usr/bin/env python3
"""Fit real development models, compare held-out donors, save inspectable reports."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import time
import resource
import numpy as np
from dnhacksbio.ecosystem_design import CountData, bags, digest
from dnhacksbio.ecosystem_encoder import fit_pca, fit_nb, fit_pseudobulk_pca, evaluate_holdout, profile


def state_readout(train, test, model, states, cells_per_donor, seed):
    """Descriptive preservation of fixed expression-program labels, donor weighted.

    Labels are defined from these genes, so this is representation fidelity,
    not independent validation of biological cell-state truth.
    """
    def values(data,role):
        selected,_=bags(data,model.manifest['compartment'],min_cells=cells_per_donor,
                        cells_per_donor=cells_per_donor,seed=seed,roles=(role,))
        batches=[]
        for donor,rows in selected.items():
            counts=data.rows(rows)
            z=model.transform(counts,data.genes,data.library_sizes(rows,counts))
            y=np.asarray([states.index(data.cells[i]['state']) for i in rows])
            batches.append((donor,np.column_stack([np.ones(len(z)),z]),y))
        return batches
    training=values(train,'training'); testing=values(test,'development')
    x=np.concatenate([v[1] for v in training]);y=np.concatenate([v[2] for v in training])
    ridge=np.eye(x.shape[1]);ridge[0,0]=0
    beta=np.linalg.solve(x.T@x+ridge,x.T@np.eye(len(states))[y])
    results={donor:float(np.mean((z@beta).argmax(1)==target)) for donor,z,target in testing}
    majority=int(np.bincount(y,minlength=len(states)).argmax())
    return dict(donor_mean_accuracy=float(np.mean(list(results.values()))) if results else None,
                donor_mean_majority_accuracy=float(np.mean([np.mean(target==majority) for _,_,target in testing])) if testing else None,
                eligible_donors=len(results),interpretation='fidelity to frozen expression-program labels, not independently validated biology')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True);parser.add_argument('--epochs',type=int,default=20)
    parser.add_argument('--device',default='cpu');parser.add_argument('--lease-path')
    args=parser.parse_args()
    root=Path(args.root);prepared=root/'prepared';output=root/'models';output.mkdir(exist_ok=True)
    report={'schema':'ecosystem-real-model-comparison-v1','confirmation':'unavailable','seed':1701,
            'cells_per_donor':32,'model_selection_surface':'exposed development; no private data inspected','models':{}}
    for compartment in ('malignant','fibroblast'):
        train=CountData.load(prepared/f'peng-{compartment}-training.npz',roles=('training',))
        datasets={name:CountData.load(prepared/f'{name}-{compartment}-development.npz',roles=('development',)) for name in ('peng','lin')}
        ref=json.loads((prepared/f'{compartment}-state-reference.json').read_text());states=list(ref['programs'])
        for method in ('pseudobulk-pca','cell-pca','nb'):
            print(compartment,method,'training',flush=True);start=time.monotonic()
            kwargs=dict(components=32,cells_per_donor=32,seed=1701)
            if method=='nb':
                model=fit_nb(train,compartment,epochs=args.epochs,device=args.device,lease_path=args.lease_path,**kwargs)
            else:
                model=(fit_pca if method=='cell-pca' else fit_pseudobulk_pca)(train,compartment,**kwargs)
            elapsed=time.monotonic()-start
            path=output/f'{compartment}-{method}.npz';model.save(path)
            measured=dict(model_hash=model.identity,artifact=str(path),training_seconds=elapsed,
                          training_donors=len(model.manifest['training_donors']),training_cells=32*len(model.manifest['training_donors']),
                          latent_dimensions=model.transform(train.rows([0]),train.genes,train.library_sizes([0])) .shape[1],
                          process_peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                          manifest=model.manifest,held_out={})
            for source,data in datasets.items():
                started=time.monotonic()
                evaluation=evaluate_holdout(data,model,states=states,min_cells=32,cells_per_donor=32,seed=1701)
                evaluation['donor_mean_reconstruction_mse']=float(np.mean(list(evaluation.pop('donor_log_library_reconstruction_mse').values())))
                evaluation['state_fidelity']=state_readout(train,data,model,states,32,1701)
                evaluation['evaluation_seconds']=time.monotonic()-started
                measured['held_out'][source]=evaluation
                p=profile(data,model,states=states,min_cells=32,cells_per_donor=32,seed=1701)
                (output/f'{source}-{compartment}-{method}-profile.json').write_text(json.dumps(p,indent=2)+'\n')
            report['models'][f'{compartment}-{method}']=measured
            (output/'model-comparison.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
            print(compartment,method,{source:round(v['donor_mean_reconstruction_mse'],4) for source,v in measured['held_out'].items()},flush=True)
    return report

if __name__=='__main__':main()
