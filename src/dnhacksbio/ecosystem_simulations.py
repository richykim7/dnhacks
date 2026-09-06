"""Synthetic measured-donor stress tests, not an assay-specific power approval."""
from __future__ import annotations

import math
import numpy as np


def interval(hits, n):
    p = hits/n; z=1.959963984540054
    denom=1+z*z/n
    center=(p+z*z/(2*n))/denom
    radius=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/denom
    return [max(0.,center-radius), min(1.,center+radius)]


def summarize(logw, alpha=.05):
    crossed=logw>=-math.log(alpha)
    anycross=crossed.any(1)
    final=crossed[:,-1]
    delays=np.where(anycross,crossed.argmax(1)+1,0)
    return dict(streams=len(logw),final_rejection=float(final.mean()),anytime_rejection=float(anycross.mean()),
                final_interval=interval(int(final.sum()),len(logw)),anytime_interval=interval(int(anycross.sum()),len(logw)),
                detection_delay_blocks={str(i):int(np.sum(delays==i)) for i in range(1,logw.shape[1]+1)},
                noncrossers=int(np.sum(~anycross)),mean_final_log_wealth=float(logw[:,-1].mean()))


def run(*, streams=10000, budgets=(18,24,40,60,100), seed=1701):
    if type(streams) is not int or not 10000 <= streams <= 100000:
        raise ValueError('Use 10000–100000 independent streams')
    if any(type(n) is not int or n < 2 or n > 100 for n in budgets):
        raise ValueError('Invalid independent donor budgets')
    rng=np.random.default_rng(seed)
    records=[]
    scenarios=('iid-null','nonlinear-coupling','rare-state-coupling','low-cell-dropout',
               'shared-capture-noise','batch-confounding','missing-compartment-selection','shared-denominator')
    for n in budgets:
        blocks=n//2
        for scenario in scenarios:
            x=rng.normal(size=(streams,blocks,2)); y=rng.normal(size=x.shape)
            if scenario=='nonlinear-coupling': y=.8*(x*x-1)+.5*y
            elif scenario=='rare-state-coupling':
                rare=rng.binomial(1,.1,size=x.shape); x+=3*rare; y+=3*rare
            elif scenario=='low-cell-dropout':
                y=.8*(x*x-1)+y
                x=rng.binomial(8,1/(1+np.exp(-x)))/8
                y=rng.binomial(8,1/(1+np.exp(-y)))/8
            elif scenario in ('shared-capture-noise','batch-confounding'):
                shared=rng.normal(size=x.shape)*(1 if scenario=='shared-capture-noise' else 3)
                x+=shared; y+=shared
            elif scenario=='missing-compartment-selection':
                # Explicit collider-selected population: accept pairs with matching signs.
                y=np.abs(y)*np.sign(x)
            elif scenario=='shared-denominator':
                total=np.abs(x)+np.abs(y)+.001
                fraction=np.abs(x)/total
                x=fraction-.5; y=.5-fraction
            for critic in ('linear','nonlinear','fixed-rbf'):
                def c(a,b):
                    if critic=='linear': return np.tanh(a*b)
                    if critic=='nonlinear': return np.tanh((a*a-1)*b)
                    return np.exp(-np.square(a-b))-0.5
                h=(c(x[:,:,0],y[:,:,0])+c(x[:,:,1],y[:,:,1])-c(x[:,:,0],y[:,:,1])-c(x[:,:,1],y[:,:,0]))/4
                logw=np.cumsum(np.log1p(.9*h),axis=1)
                records.append(dict(donors=n,scenario=scenario,critic=critic,**summarize(logw)))
                if scenario=='iid-null' and critic=='linear':
                    records.append(dict(donors=n,scenario='invalid-cell-pseudoreplication',critic=critic,
                                        **summarize(logw*64)))
            invalid=np.broadcast_to(np.arange(1,blocks+1)*math.log(1.9),(streams,blocks))
        records.append(dict(donors=n,scenario='invalid-current-block-training',critic='memorized-matches',**summarize(invalid)))
    return dict(schema='ecosystem-simulation-v1',seed=seed,alpha=.05,records=records,
                status='synthetic-diagnostic-only',confirmation='unavailable',
                limitations=['No biological donor inventory, learned-model utility or assay-specific alternative audited',
                             'Confounding/selection/shared-denominator scenarios violate latent-independence interpretations',
                             'Noncrossers remain in detection-delay denominator; no best-critic selection for evidence',
                             'PCA/NB donor-held-out real-data comparison remains an acquisition-gated study'])
