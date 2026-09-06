"""Device-resident fitting; no host-side PCA, ridge or critic feature expansion."""
import platform
import time


def fit(data, splits, ix, *, kind, latent, seed, epochs, ridge, missing_tolerance, device):
    import numpy as np
    import torch
    from .pharmacotype_encoder import seal

    started=time.monotonic()
    if device=='cuda':
        if not torch.cuda.is_available():raise RuntimeError('CUDA unavailable; no CPU fallback')
        torch.cuda.reset_peak_memory_stats()
    torch.manual_seed(seed)
    x=torch.as_tensor(data['x'],dtype=torch.float64,device=device)
    y=torch.as_tensor(data['y'],dtype=torch.float64,device=device)
    if not torch.isfinite(y).all() or torch.isinf(x).any():raise ValueError('Invalid training values')
    fill=torch.nanmean(x[ix[0]],dim=0)
    if not torch.isfinite(fill).all():raise ValueError('Training feature entirely missing')
    if (torch.isnan(x).double().mean(dim=1)>missing_tolerance).any():raise ValueError('Missing features exceed frozen tolerance')
    x=torch.where(torch.isnan(x),fill,x)

    def portable(t):return t.detach().cpu().tolist()

    def view(values, view_seed):
        torch.manual_seed(view_seed)
        train=values[ix[0]]
        mean=train.mean(dim=0);scale=train.std(dim=0,correction=0).clamp_min(1e-8)
        z=(values-mean)/scale
        artifact=dict(kind=kind,mean=portable(mean),scale=portable(scale))
        if kind=='identity':return z,artifact
        if kind=='pca':
            _,_,vt=torch.linalg.svd(z[ix[0]],full_matrices=False)
            w=vt[:min(latent,len(vt))].T
            artifact['weights']=portable(w)
            return z@w,artifact
        # Float32 neural optimization, with float64 PCA/ridge for stable baselines.
        z=z.float()
        encoder=torch.nn.Linear(z.shape[1],latent,device=device)
        decoder=torch.nn.Linear(latent,z.shape[1],device=device)
        parameters=[*encoder.parameters(),*decoder.parameters()]
        optimizer=torch.optim.Adam(parameters,lr=.001)
        best=None;best_loss=float('inf');stale=0;view_started=time.monotonic()
        for epoch in range(epochs):
            if time.monotonic()-view_started>300:raise TimeoutError('View training exceeded five-minute cap')
            optimizer.zero_grad()
            masked=z[ix[0]].masked_fill(torch.rand_like(z[ix[0]])<.15,0)
            loss=(decoder(torch.tanh(encoder(masked)))-z[ix[0]]).square().mean()
            if not torch.isfinite(loss):raise ValueError('Nonfinite neural training loss')
            loss.backward();optimizer.step()
            with torch.no_grad():value=float((decoder(torch.tanh(encoder(z[ix[1]])))) .sub(z[ix[1]]).square().mean())
            if value<best_loss-1e-8:
                best_loss=value;stale=0;used=epoch+1
                best=[p.detach().clone() for p in parameters]  # Remains on device.
            else:stale+=1
            if stale>=15:break
        with torch.no_grad():
            for p,saved in zip(parameters,best):p.copy_(saved)
            encoded=torch.tanh(encoder(z)).double()
        artifact.update(weights=portable(encoder.weight.T),bias=portable(encoder.bias),
                        decoder=portable(decoder.weight.T),decoder_bias=portable(decoder.bias),
                        epochs=used,validation_reconstruction_mse=best_loss,optimizer='Adam',device=device)
        return encoded,artifact

    zx,ex=view(x,seed);zy,ey=view(y,seed+1)
    design=torch.cat((zx,torch.ones((len(zx),1),dtype=zx.dtype,device=device)),dim=1)
    penalty=torch.eye(design.shape[1],dtype=design.dtype,device=device)*ridge;penalty[-1,-1]=0
    train_design=design[ix[0]]
    coef=torch.linalg.solve(train_design.T@train_design+penalty,train_design.T@y[ix[0]])
    torch.manual_seed(seed)
    a=zx[ix[0]].float();b=zy[ix[0]].float();crossed=b.roll(1,dims=0)
    cw=torch.nn.Parameter(torch.randn((a.shape[1],b.shape[1]),device=device)*.001)
    optimizer=torch.optim.Adam([cw],lr=.001)
    critic_started=time.monotonic()
    for _ in range(epochs):
        if time.monotonic()-critic_started>300:raise TimeoutError('Critic training exceeded five-minute cap')
        optimizer.zero_grad()
        matched=torch.tanh(((a@cw)*b).sum(dim=1))
        unmatched=torch.tanh(((a@cw)*crossed).sum(dim=1))
        loss=((matched-1).square().mean()+(unmatched+1).square().mean())/2+.01*cw.square().mean()
        if not torch.isfinite(loss):raise ValueError('Nonfinite critic loss')
        loss.backward();optimizer.step()
    metrics={name+'_curve_rmse':float((design[indices]@coef-y[indices]).square().mean().sqrt())
             for name,indices in zip(('validation','test'),ix[1:])}
    resources={'torch':torch.__version__,'device':device,'fitting_device':device,'host_critic_features':False}
    if device=='cuda':
        torch.cuda.synchronize()
        resources.update(peak_allocated_bytes=torch.cuda.max_memory_allocated(),peak_reserved_bytes=torch.cuda.max_memory_reserved())
    return seal(dict(schema='pharmacotype.model.v1',kind=kind,genes=data['genes'],panel=data['panel'],
        contract_hash=data['contract_hash'],source_hash=data['source_hash'],development_donors=data['donors'],
        splits=splits,fill=portable(fill),missing_tolerance=missing_tolerance,molecular=ex,response=ey,
        predictor=portable(coef),critic=portable(cw),seed=seed,epochs_cap=epochs,ridge=ridge,latent=latent,
        backend='torch',resource_metrics=resources,metrics=metrics,training_seconds=time.monotonic()-started,
        software={'python':platform.python_version(),'numpy':np.__version__,'torch':torch.__version__},
        limitations='Development only; no clinical probability, mechanism, synergy or confirmation. Test split must not select models.'))
