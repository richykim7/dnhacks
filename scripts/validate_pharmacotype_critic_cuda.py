"""GPU-only synthetic critic feasibility; never a biological confirmation report."""
import argparse
import fcntl
import json
import time
from pathlib import Path

from dnhacksbio.pharmacotype_data import digest
from dnhacksbio.native_evidence import association_factor
from validate_pharmacotype_adaptive import interval


def sample(torch, generator, count, relation):
    x=torch.randn(count,device='cuda',generator=generator)
    noise=torch.randn(count,device='cuda',generator=generator)
    y=x+.25*noise if relation=='simple' else x.square()+.25*noise if relation=='nonlinear' else noise
    if relation=='heavy_tail_null':
        # Independent t(2) variables using independent chi-square(2) denominators.
        denominator=torch.randn((count,4),device='cuda',generator=generator).square()
        x=x/(denominator[:,:2].mean(1).sqrt())
        y=y/(denominator[:,2:].mean(1).sqrt())
    return torch.stack((x,y),dim=1)


def factors(score, pairs):
    a,b=pairs[::2],pairs[1::2]
    crossed_a=a.clone();crossed_a[:,1]=b[:,1]
    crossed_b=b.clone();crossed_b[:,1]=a[:,1]
    return 1+.9*(score(a)+score(b)-score(crossed_a)-score(crossed_b))/4


def fit(torch, relation, seed, epochs=300):
    torch.manual_seed(seed)
    generator=torch.Generator(device='cuda').manual_seed(seed+1000)
    train=sample(torch,generator,1024,relation)
    validation=sample(torch,generator,256,relation)
    mean=train.mean(0);scale=train.std(0,correction=0).clamp_min(1e-8)
    net=torch.nn.Sequential(torch.nn.Linear(2,32,device='cuda'),torch.nn.Tanh(),
                            torch.nn.Linear(32,32,device='cuda'),torch.nn.Tanh(),
                            torch.nn.Linear(32,1,device='cuda'))
    optimizer=torch.optim.Adam(net.parameters(),lr=.003)
    def logits(rows):return net((rows-mean)/scale).squeeze(1)
    def score(rows):return logits(rows).tanh()
    best=None;best_value=float('-inf');best_epoch=0
    for epoch in range(epochs):
        optimizer.zero_grad()
        order=torch.randperm(len(train),device='cuda',generator=generator)
        rows=train[order]
        if epoch<100:
            crossed=rows.clone();crossed[:,1]=rows[:,1].roll(1)
            loss=(torch.nn.functional.softplus(-logits(rows)).mean()+
                  torch.nn.functional.softplus(logits(crossed)).mean())/2
        else:loss=-factors(score,rows).log().mean()
        if not torch.isfinite(loss):raise ValueError('Nonfinite critic loss')
        loss.backward();optimizer.step()
        with torch.no_grad():value=float(factors(score,validation).log().mean())
        if value>best_value:
            best_value=value;best_epoch=epoch+1
            best={k:v.detach().clone() for k,v in net.state_dict().items()}
    net.load_state_dict(best);net.eval()
    artifact=dict(relation=relation,seed=seed,mean=mean.tolist(),scale=scale.tolist(),
                  weights={k:v.tolist() for k,v in best.items()},epoch=best_epoch,
                  validation_mean_log_factor=best_value)
    artifact['sha256']=digest(artifact)
    return score,artifact


def evaluate(torch,score,relation,*,streams=10000,donors=32):
    generator=torch.Generator(device='cuda').manual_seed(87631)
    wealth=torch.zeros(streams,device='cuda',dtype=torch.float64)
    first=torch.zeros(streams,device='cuda',dtype=torch.int32)
    means=[]
    with torch.no_grad():
        for block in range(donors//2):
            pairs=sample(torch,generator,2*streams,relation)
            factor=factors(score,pairs)
            # Independent scalar production arithmetic on actual scored inputs.
            a,b=pairs[:2];cross_a=a.clone();cross_a[1]=b[1];cross_b=b.clone();cross_b[1]=a[1]
            scores=[float(score(row[None,:])[0]) for row in (a,b,cross_a,cross_b)]
            if abs(float(factor[0])-association_factor(scores))>2e-6:
                raise ValueError('Native factor mismatch')
            wealth+=factor.double().log()
            hits=(first==0)&(wealth>=torch.log(torch.tensor(20.,device='cuda')))
            first[hits]=2*(block+1);means.append(float(factor.mean()))
    final=int((wealth>=torch.log(torch.tensor(20.,device='cuda'))).sum())
    anytime=int((first>0).sum())
    return dict(final_rate=final/streams,final_wilson95=interval(final,streams),
                anytime_rate=anytime/streams,anytime_wilson95=interval(anytime,streams),
                median_detection_donors=float(first[first>0].float().median()) if anytime else None,
                block_factor_mean_range=[min(means),max(means)])


def run(output,*,streams=10000,donors=32):
    import torch
    if not torch.cuda.is_available():raise RuntimeError('CUDA required; no CPU fitting fallback')
    if streams<10000 or donors<2 or donors%2:raise ValueError('At least10000 streams and an even donor budget required')
    design=dict(training='synthetic only; 1024 training and256 validation donors per relation/seed',
                architecture='2-32-32-1 tanh MLP, bounded tanh output',epochs=300,
                optimization='100 logistic initialization epochs then200 native mean-log-factor epochs',
                selection='best external development validation mean log factor, each seed reported separately',
                seeds=[601,602,603],relations=['simple','nonlinear'],streams=streams,donors=donors,
                stake=.9,threshold=20,power_target=.8,
                schedule='externally trained and fully frozen before all evaluation streams')
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    output.with_suffix('.design.json').write_text(json.dumps(design,indent=2)+'\n')
    started=time.monotonic();trials=[]
    with open('/tmp/dnhacks-gpu.lock','a') as lease:
        fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
        torch.cuda.reset_peak_memory_stats()
        for relation in design['relations']:
            for seed in design['seeds']:
                score,artifact=fit(torch,relation,seed)
                result={case:evaluate(torch,score,case,streams=streams,donors=donors)
                        for case in ('iid_null','heavy_tail_null',relation)}
                trials.append(dict(model=artifact,results=result))
        baseline={case:evaluate(torch,lambda rows:(rows[:,0]*rows[:,1]).tanh(),case,streams=streams,donors=donors)
                  for case in ('iid_null','heavy_tail_null','simple','nonlinear')}
        report=dict(schema='pharmacotype.synthetic-critic-feasibility.v1',design=design,trials=trials,
                    bilinear_baseline=baseline,seconds=time.monotonic()-started,device='cuda',torch=torch.__version__,
                    peak_reserved_bytes=torch.cuda.max_memory_reserved(),confirmation_enabled=False,
                    limitations=['Synthetic external training and evaluation, not patient data.',
                                 'No audited fresh PDO denominator or biological utility claim.',
                                 'Experimental MLP critic is not integrated into the private process ledger.'])
        output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps([{'relation':t['model']['relation'],'seed':t['model']['seed'],
                       'power':t['results'][t['model']['relation']]['anytime_rate']} for t in trials]))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True)
    args=parser.parse_args();run(args.output)
