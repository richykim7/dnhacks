"""Reproducible adaptive-kernel diagnostics; no biological release attestation."""
import argparse
import json
import math
from pathlib import Path

import numpy as np
from dnhacksbio.native_evidence import association_factor, frozen_scores, past_block_update


def interval(hits, n):
    p=hits/n; z=1.959963984540054; d=1+z*z/n
    center=(p+z*z/(2*n))/d
    half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [center-half,center+half]


def run(streams=10000, donors=32, seed=601):
    if streams<10000 or donors<2 or donors%2:raise ValueError('>=10000 streams and even donor budget required')
    rng=np.random.default_rng(seed); results={}
    for case in ('iid_null','heavy_tail_null','simple_alternative','nonlinear_alternative'):
        weights=np.ones(streams); wealth=np.zeros(streams); first=np.zeros(streams,dtype=int)
        means=[]
        for block in range(donors//2):
            x=rng.normal(size=(streams,2)); y=rng.normal(size=(streams,2))
            if case=='heavy_tail_null':x=rng.standard_t(2,size=x.shape); y=rng.standard_t(2,size=y.shape)
            elif case=='simple_alternative':y=x+.25*y
            elif case=='nonlinear_alternative':y=x*x+.25*y
            features=np.stack((x[:,0]*y[:,0],x[:,1]*y[:,1],x[:,0]*y[:,1],x[:,1]*y[:,0]),axis=1)
            scores=np.tanh(features*weights[:,None])
            factors=1+.9*(scores[:,0]+scores[:,1]-scores[:,2]-scores[:,3])/4
            # Check batched arithmetic against the actual scalar production core.
            assert np.isclose(factors[0],association_factor(frozen_scores(x[0,:,None],y[0,:,None],[[weights[0]]])))
            wealth+=np.log(factors)
            first[(first==0)&(wealth>=math.log(20))]=2*(block+1)
            means.append(float(factors.mean()))
            gradient=np.mean(2*(scores-np.array([1,1,-1,-1]))*(1-scores*scores)*features,axis=1)
            updated=weights-.001*np.clip(gradient,-10,10)
            assert np.isclose(updated[0],past_block_update([[weights[0]]],x[0,:,None],y[0,:,None])[0][0])
            weights=updated  # Only after scoring this block.
        final=int((wealth>=math.log(20)).sum()); anytime=int((first>0).sum())
        results[case]=dict(final_rate=final/streams,final_wilson95=interval(final,streams),
                           anytime_rate=anytime/streams,anytime_wilson95=interval(anytime,streams),
                           median_detection_donors=float(np.median(first[first>0])) if anytime else None,
                           block_factor_mean_range=[min(means),max(means)])
    return dict(schema='pharmacotype.adaptive-diagnostics.v1',streams_per_case=streams,
                donors=donors,seed=seed,schedule='past-block-bilinear-sgd-v1',stake=.9,
                initial_critic=[[1.]],threshold=20,results=results,
                release_eligible=False,budget_scope='Synthetic sensitivity budget; no audited fresh PDO denominator')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True)
    p.add_argument('--donors',type=int,default=32);a=p.parse_args()
    Path(a.output).write_text(json.dumps(run(donors=a.donors),indent=2,allow_nan=False)+'\n')
