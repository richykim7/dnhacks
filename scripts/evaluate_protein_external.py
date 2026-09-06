#!/usr/bin/env python3
"""CUDA-only frozen CPTAC-to-Fudan prediction; external labels are not an input."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import time

import numpy as np
import torch

MODULES = {"mitotic": ["NUAK1", "PPP1R12A", "PPP1CB", "GSK3B", "PLK4", "ATM", "ATR", "KIFC1"],
           "stress_redox": ["NFE2L2", "CPEB1", "NQO1", "HMOX1", "GPX4"],
           "integrin_fak": ["ITGB1", "ITGA5", "PTK2"]}


def percentile(x):
    mask = torch.isfinite(x)
    sorted_x, order = torch.sort(torch.where(mask, x, torch.inf), dim=1, stable=True)
    n,p = x.shape
    starts = torch.ones((n,p), dtype=torch.bool, device=x.device)
    starts[:,1:] = sorted_x[:,1:] != sorted_x[:,:-1]
    groups = starts.cumsum(1)-1
    count = torch.zeros_like(x).scatter_add_(1,groups,torch.ones_like(x))
    ranks = torch.arange(1,p+1,device=x.device,dtype=x.dtype).expand(n,p)
    sums = torch.zeros_like(x).scatter_add_(1,groups,ranks)
    average = (sums/count.clamp_min(1)).gather(1,groups)
    out = torch.empty_like(x).scatter_(1,order,average)/(mask.sum(1,keepdim=True)+1)
    return torch.where(mask,out,.5)


def ridge(source, target, y):
    mean = source.mean(0)
    scale = source.std(0,correction=0).clamp_min(1e-6)
    x, z = (source-mean)/scale, (target-mean)/scale
    counts = torch.bincount(y.long(), minlength=2)
    if (counts==0).any():
        raise ValueError("Both source grades required")
    weights = len(y)/(2*counts[y.long()])
    intercept_mean = (x*weights[:,None]).sum(0)/weights.sum()
    x, z = x-intercept_mean, z-intercept_mean
    wx = x*weights.sqrt()[:,None]
    response = (2*y-1)*weights.sqrt()
    dual = torch.linalg.solve(wx@wx.T+torch.eye(len(y),device=x.device),response)
    coef = wx.T@dual
    return z@coef, {"mean":mean,"scale":scale,"intercept_mean":intercept_mean,"coef":coef}


def run(inputs, output):
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA required; CPU fitting is disabled")
    output = Path(output)
    output.mkdir(parents=True,exist_ok=False)
    start = time.monotonic()
    torch.cuda.set_per_process_memory_fraction(16*1024**3/torch.cuda.get_device_properties(0).total_memory)
    torch.manual_seed(0)
    with np.load(inputs,allow_pickle=False) as archive:
        symbols = archive["symbols"].tolist()
        train, dev, ext = (torch.as_tensor(archive[k],device="cuda") for k in ("train","development","external"))
        y = torch.as_tensor(archive["development_y"],device="cuda",dtype=torch.float32)
        donor_ids = archive["external_ids"].copy()
    coverage = torch.isfinite(train).float().mean(0)
    eligible = coverage>=.8
    module_set = set(sum(MODULES.values(),[]))
    selected = [i for i,s in enumerate(symbols) if s in module_set]
    for i in torch.argsort(coverage,descending=True,stable=True).tolist():
        if i not in selected and bool(eligible[i]):
            selected.append(i)
        if len(selected)>=2000:
            break
    selected.sort()
    if len(selected)<32:
        raise ValueError("Insufficient training feature coverage")
    train,dev,ext = (t[:,selected] for t in (train,dev,ext))
    selected_symbols = [symbols[i] for i in selected]
    tr_rank, dev_rank, ext_rank = (percentile(t) for t in (train,dev,ext))
    center = tr_rank.mean(0)
    _,_,vt = torch.linalg.svd(tr_rank-center,full_matrices=False)
    components = vt[:32]
    valid = y>=0
    y=y[valid]
    def modules(x):
        cols=[]
        for genes in MODULES.values():
            ids=[i for i,s in enumerate(selected_symbols) if s in genes]
            cols.append(x[:,ids].mean(1) if ids else torch.full((len(x),),.5,device=x.device))
        return torch.stack(cols,dim=1)
    views = {"rank_pca":((dev_rank-center)@components.T,(ext_rank-center)@components.T),
             "rank_linear":(dev_rank,ext_rank), "fixed_modules":(modules(dev_rank),modules(ext_rank)),
             "missingness":((~torch.isfinite(dev)).float(),(~torch.isfinite(ext)).float())}
    weights={"selected":np.asarray(selected),"symbols":np.asarray(selected_symbols),
             "pca_center":center.cpu().numpy(),"pca_components":components.cpu().numpy()}
    scores={}
    for name,(source,target) in views.items():
        score, model = ridge(source[valid],target,y)
        scores[name]=score.cpu().numpy()
        weights.update({name+"_"+k:v.cpu().numpy() for k,v in model.items()})
    source=dev_rank[valid]
    k=torch.exp(-torch.cdist(source,source).square()/len(selected))
    cross=torch.exp(-torch.cdist(ext_rank,source).square()/len(selected))
    counts=torch.bincount(y.long(),minlength=2)
    sw=(len(y)/(2*counts[y.long()])).sqrt()
    alpha=torch.linalg.solve(k*sw[:,None]*sw[None,:]+torch.eye(len(y),device="cuda"),(2*y-1)*sw)*sw
    scores["rank_kernel"]=(cross@alpha).cpu().numpy()
    weights.update(kernel_source=source.cpu().numpy(),kernel_alpha=alpha.cpu().numpy())
    np.savez_compressed(output/"model.npz",**weights)
    np.savez_compressed(output/"predictions.npz",donors=donor_ids,**scores,
                        coverage=torch.isfinite(ext).float().mean(1).cpu().numpy())
    torch.cuda.synchronize()
    report={"device":torch.cuda.get_device_name(),"torch":torch.__version__,"seed":0,
            "source_grade_donors":len(y),"external_tumors":len(ext),"selected_genes":len(selected),
            "seconds":time.monotonic()-start,"peak_cuda_bytes":torch.cuda.max_memory_allocated(),
            "inputs_sha256":hashlib.sha256(Path(inputs).read_bytes()).hexdigest(),
            "code_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "model_sha256":hashlib.sha256((output/"model.npz").read_bytes()).hexdigest(),
            "predictions_sha256":hashlib.sha256((output/"predictions.npz").read_bytes()).hexdigest(),
            "module_measured_symbols":{k:[s for s in v if s in selected_symbols] for k,v in MODULES.items()},
            "external_labels_accessed":False,"primary_view":"rank_pca","penalty":1.,
            "assay_scope":"explicit exploratory cross-assay rank transfer; original abundance artifacts incompatible"}
    (output/"training.json").write_text(json.dumps(report,indent=2))


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--inputs",required=True);p.add_argument("--output",required=True)
    a=p.parse_args()
    with open("/tmp/dnhacks-gpu.lock","a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        run(a.inputs,a.output)
