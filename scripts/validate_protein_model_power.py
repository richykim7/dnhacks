#!/usr/bin/env python3
"""CUDA source-fitted protein-space simulation through frozen actual witnesses."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import runpy
import time
import numpy as np
import torch
from dnhacksbio.learned_evalue import _log_payoffs

MITOTIC={"NUAK1","PPP1R12A","PPP1CB","GSK3B","PLK4","ATM","ATR","KIFC1"}


def module_sd(loadings,residual,indices):
    return (loadings[indices].mean(0).square().sum()+residual[indices].sum()/len(indices)**2).sqrt()


def run(inputs,model,streams,budgets,artifact):
    if not torch.cuda.is_available():raise RuntimeError("CUDA required")
    torch.cuda.set_per_process_memory_fraction(16*1024**3/torch.cuda.get_device_properties(0).total_memory)
    start=time.monotonic()
    helpers=runpy.run_path(str(Path(__file__).with_name("evaluate_protein_external.py")))
    percentile=helpers["percentile"]
    with np.load(model,allow_pickle=False) as a:
        selected=a["selected"].tolist();symbols=a["symbols"].tolist()
        kernel_source=torch.as_tensor(a["kernel_source"],device="cuda")
        alpha=torch.as_tensor(a["kernel_alpha"],device="cuda")
    with np.load(inputs,allow_pickle=False) as a:train=torch.as_tensor(a["train"][:,selected],device="cuda")
    mask=torch.isfinite(train);coverage=mask.float().mean(0)
    mean=torch.nanmean(train,0);std=torch.nanmean((train-mean).square(),0).sqrt().clamp_min(1e-6)
    z=torch.nan_to_num((train-mean)/std)
    _,s,vt=torch.linalg.svd(z-z.mean(0),full_matrices=False)
    loadings=vt[:32].T*(s[:32]/(len(z)-1)**.5)
    residual=(z.var(0,correction=1)-loadings.square().sum(1)).clamp_min(1e-4)
    indices=[i for i,symbol in enumerate(symbols) if symbol in MITOTIC]
    if len(indices)<2:raise ValueError("Insufficient measured mitotic panel")
    scale=module_sd(loadings,residual,indices)
    coverage[indices]=1
    def scores(standardized,observed):
        raw=standardized*std+mean
        ranks=percentile(torch.where(observed,raw,torch.nan))
        kernel=torch.exp(-torch.cdist(ranks,kernel_source).square()/len(symbols))@alpha
        module=standardized[:,indices].mean(1)/scale
        return torch.stack((kernel,module),1)
    source_scores=scores(z,mask)
    score_scale=source_scores.std(0,correction=0).clamp_min(1e-6)
    def generate(count,shift,gen):
        base=torch.randn((count,32),device="cuda",generator=gen)@loadings.T
        base+=torch.randn((count,len(symbols)),device="cuda",generator=gen)*residual.sqrt()
        base[:,indices]+=shift*scale
        observed=torch.rand(base.shape,device="cuda",generator=gen)<coverage
        return scores(base,observed)/score_scale
    def pairs(count,effect,gen):
        aa=[];bb=[]
        for offset in range(0,count,512):
            n=min(512,count-offset)
            aa.append(generate(n,effect/2,gen));bb.append(generate(n,-effect/2,gen))
        return torch.cat(aa),torch.cat(bb)
    gen=torch.Generator(device="cuda").manual_seed(830001)
    ca,cb=pairs(2048,.4,gen)
    stakes=torch.tensor([0,.125,.25,.5,1.,2.],device="cuda")
    class Identity:
        def __call__(self,x):return x
    calibration=torch.stack([_log_payoffs(Identity(),ca*v,cb*v,4.).reshape(-1,2).mean(0) for v in stakes])
    chosen=stakes[calibration.argmax(0)]
    coefficients=torch.zeros_like(mean)
    coefficients[indices]=chosen[1]/(len(indices)*scale*score_scale[1]*std[indices])
    frozen={"mean":mean,"std":std,"loadings":loadings,"residual":residual,
            "coverage":coverage,"score_scale":score_scale,"stakes":chosen,
            "module_coefficients":coefficients,"module_intercept":-(coefficients*mean).sum()}
    with open(artifact,"xb") as f:
        np.savez_compressed(f,**{k:v.cpu().numpy() for k,v in frozen.items()},
                            module_indices=np.asarray(indices),symbols=np.asarray(symbols,dtype=str))
    records=[]
    for budget in budgets:
        scored=budget-16
        if scored<1:raise ValueError("Insufficient pairs")
        for case,effect in (("null",0.),("effect",.4)):
            final=torch.zeros(2,device="cuda",dtype=torch.int64);anytime=final.clone()
            gen=torch.Generator(device="cuda").manual_seed(920000+budget+(10000 if effect else 0))
            for offset in range(0,streams,32):
                n=min(32,streams-offset)
                a,b=pairs(n*scored,effect,gen)
                logs=_log_payoffs(Identity(),a*chosen,b*chosen,4.).reshape(n,scored,2).cumsum(1)
                final+=(logs[:,-1]>=np.log(20)).sum(0)
                anytime+=(logs.max(1).values>=np.log(20)).sum(0)
            records.append({"pairs":budget,"scored_pairs":scored,"case":case,"streams":streams,
                            "final_rejections":final.tolist(),"anytime_rejections":anytime.tolist()})
    return {"schema":"ProteinModelPower-v1","effect":.4,"views":["frozen_rank_kernel","fixed_measured_module"],
            "stakes":chosen.tolist(),"calibration_mean_log":calibration.tolist(),"results":records,
            "module_symbols":[symbols[i] for i in indices],"latent_module_sd":float(scale),
            "inputs_sha256":hashlib.sha256(Path(inputs).read_bytes()).hexdigest(),
            "model_sha256":hashlib.sha256(Path(model).read_bytes()).hexdigest(),
            "generator_witness_sha256":hashlib.sha256(Path(artifact).read_bytes()).hexdigest(),
            "script_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "device":torch.cuda.get_device_name(),"torch":torch.__version__,
            "seconds":time.monotonic()-start,"peak_cuda_bytes":torch.cuda.max_memory_allocated(),
            "release_certificate":False}


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for k in ("inputs","model","output"):p.add_argument("--"+k,required=True)
    p.add_argument("--streams",type=int,default=256)
    p.add_argument("--budgets",type=int,nargs="+",default=[60,192,384]);a=p.parse_args()
    with open("/tmp/dnhacks-gpu.lock","a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        report=run(a.inputs,a.model,a.streams,a.budgets,str(Path(a.output).with_suffix(".npz")))
        with open(a.output,"x") as f:json.dump(report,f,indent=2,allow_nan=False)
