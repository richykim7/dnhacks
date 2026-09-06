#!/usr/bin/env python3
"""GPU canonical-kernel sample-budget feasibility; never a model release certificate."""
import argparse
import fcntl
import hashlib
import json
import math
from pathlib import Path
from statistics import NormalDist
import time

EFFECT = .4
BUDGETS = (48,60,96,128,160,192,256,384,512)


def gaussian_oracle_power(pairs, effect=EFFECT, alpha=.05):
    """Optimal level-alpha directional test, known variance, for this Gaussian scenario."""
    if pairs < 1 or effect < 0 or not 0 < alpha < 1:
        raise ValueError("Invalid Gaussian planning parameters")
    normal=NormalDist()
    return normal.cdf(effect*math.sqrt(pairs/2)-normal.inv_cdf(1-alpha))


def interval(k,n):
    z=NormalDist().inv_cdf(.975);p=k/n;den=1+z*z/n
    center=(p+z*z/(2*n))/den
    half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [max(0.,center-half),min(1.,center+half)]


def run():
    import torch
    from dnhacksbio.learned_evalue import _log_payoffs
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA required; no CPU sweep fallback")
    torch.cuda.set_per_process_memory_fraction(16*1024**3/torch.cuda.get_device_properties(0).total_memory)
    start=time.monotonic();n=10000;out=[]
    class Witness:
        def __call__(self,x):return x*(EFFECT/2)
    for pairs in BUDGETS:
        scored=pairs-16
        row={"pairs":pairs,"scored_pairs":scored,
             "gaussian_oracle_using_all_pairs":gaussian_oracle_power(pairs),
             "gaussian_oracle_using_scored_pairs":gaussian_oracle_power(scored)}
        for case,shift in (("null",0.),("effect",EFFECT)):
            gen=torch.Generator(device="cuda").manual_seed(12000+pairs+(0 if case=="null" else 1000))
            x=torch.randn((n,scored,1),device="cuda",generator=gen,dtype=torch.float64)+shift/2
            y=torch.randn((n,scored,1),device="cuda",generator=gen,dtype=torch.float64)-shift/2
            log=_log_payoffs(Witness(),x,y,4.).reshape(n,scored).cumsum(1)
            final=int((log[:,-1]>=math.log(20)).sum())
            anytime=int((log.max(1).values>=math.log(20)).sum())
            row[case]={"streams":n,"final_rate":final/n,"final_ci95":interval(final,n),
                       "anytime_rate":anytime/n,"anytime_ci95":interval(anytime,n)}
        out.append(row)
    return {"schema":"ProteinPowerFeasibility-v1","minimum_effect":EFFECT,"alpha":.05,
            "witness":"oracle g(x)=0.2x; not saved protein model","kernel":"learned_evalue._log_payoffs",
            "burn_in_pairs":16,"results":out,"device":torch.cuda.get_device_name(),
            "torch":torch.__version__,"seconds":time.monotonic()-start,
            "peak_cuda_bytes":torch.cuda.max_memory_allocated(),
            "code_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "model_specific_release_certificate":False}


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--output",required=True);a=p.parse_args()
    with open("/tmp/dnhacks-gpu.lock","a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        report=run()
        with open(a.output,"x") as stream:json.dump(report,stream,indent=2,allow_nan=False)
