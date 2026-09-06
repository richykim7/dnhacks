"""Separate frozen compartment count representations; CPU PCA baseline.

PCA is a documented simpler-model release, not a validated neural advantage.
Counts use their own measured-library transform, never the TPM FrozenEncoder.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

import numpy as np

from .ecosystem_design import CountData, bags, digest, names, safe_npz


def log_library(counts, library_sizes=None):
    counts = np.asarray(counts, dtype=float)
    if counts.ndim != 2 or not np.isfinite(counts).all() or np.any(counts < 0) or np.any(counts != np.floor(counts)):
        raise ValueError('Nonnegative integer UMI counts required')
    totals = counts.sum(axis=1) if library_sizes is None else np.asarray(library_sizes, dtype=float)
    if totals.shape != (len(counts),) or not np.isfinite(totals).all() or np.any(totals < counts.sum(axis=1)) or np.any(totals != np.floor(totals)) or np.any(totals <= 0) or np.any(totals > 2**53):
        raise ValueError('Invalid measured library size')
    return np.log1p(counts / totals[:, None] * 10000)


@dataclass(frozen=True)
class CompartmentEncoder:
    genes: tuple
    mean: np.ndarray
    projection: np.ndarray
    manifest: dict

    def validate(self):
        names(self.genes, unique=True)
        if self.mean.shape != (len(self.genes),) or self.projection.ndim != 2 or self.projection.shape[0] != len(self.genes) or not self.projection.shape[1]:
            raise ValueError('Invalid encoder dimensions')
        if not np.isfinite(self.mean).all() or not np.isfinite(self.projection).all():
            raise ValueError('Nonfinite encoder')
        if self.manifest.get('schema') != 'ecosystem-pca-v1' or self.manifest.get('transform') != 'log1p-UMI-per-10000':
            raise ValueError('Unsupported count artifact')
        for key in ('compartment', 'assay', 'ontology', 'state_dictionary', 'training_data_hash'):
            names([self.manifest[key]])
        names(self.manifest['training_donors'], unique=True)

    @property
    def identity(self):
        self.validate()
        return digest(dict(genes=self.genes, mean=self.mean.tolist(), projection=self.projection.tolist(), manifest=self.manifest))

    def transform(self, counts, genes, library_sizes=None):
        self.validate()
        if tuple(genes) != self.genes:
            raise ValueError('Exact frozen gene order required; no transductive alignment')
        if self.manifest.get('library_size_rule') == 'measured-all-genes' and library_sizes is None:
            raise ValueError('Frozen measured all-gene offsets required')
        return (log_library(counts, library_sizes) - self.mean) @ self.projection

    def save(self, path):
        self.validate()
        with Path(path).open('wb') as stream:
            np.savez_compressed(stream, genes=np.asarray(self.genes), mean=self.mean, projection=self.projection,
                                manifest=json.dumps(self.manifest, sort_keys=True))

    @classmethod
    def load(cls, path):
        z = safe_npz(path, {'genes', 'mean', 'projection', 'manifest'})
        model = cls(tuple(z['genes'].tolist()), z['mean'], z['projection'], json.loads(str(z['manifest'])))
        model.validate()
        model.mean.flags.writeable = model.projection.flags.writeable = False
        return model


def fit_pca(dataset: CountData, compartment, *, components=32, cells_per_donor=64, seed=0):
    """Fit using equal cells per training donor; bounded covariance, streamed bags."""
    selected, missing = bags(dataset, compartment, min_cells=cells_per_donor,
                             cells_per_donor=cells_per_donor, seed=seed, roles=('training',))
    d = len(dataset.genes)
    if d > 4000 or len(selected) < 2 or type(components) is not int or not 1 <= components <= min(d, len(selected)*cells_per_donor-1):
        raise ValueError('Need >=2 training donors, <=4000 preselected genes and supported PCA rank')
    total = np.zeros(d)
    gram = np.zeros((d, d))
    n = 0
    for rows in selected.values():
        counts = dataset.rows(rows)
        x = log_library(counts, dataset.library_sizes(rows, counts))
        total += x.sum(axis=0)
        gram += x.T @ x
        n += len(x)
    mean = total / n
    cov = gram / n - np.outer(mean, mean)
    _, vectors = np.linalg.eigh(cov)
    projection = vectors[:, -components:][:, ::-1].copy()
    # Resolve sign ambiguity for stable same-environment replay.
    for column in projection.T:
        if column[np.argmax(np.abs(column))] < 0:
            column *= -1
    manifest = dict(schema='ecosystem-pca-v1', transform='log1p-UMI-per-10000',
                    library_size_rule=dataset.manifest.get('library_size_rule', 'sum-supplied-panel'),
                    compartment=compartment, training_donors=sorted(selected), training_data_hash=dataset.identity(),
                    training_sources=dataset.manifest['sources'], cells_per_donor=cells_per_donor, seed=seed,
                    excluded_training_donors=missing, execution={'device': 'cpu', 'numpy_version': np.__version__},
                    model_choice='bounded donor-balanced PCA baseline; neural utility not established',
                    **{k: dataset.manifest[k] for k in ('assay', 'ontology', 'state_dictionary')})
    model = CompartmentEncoder(dataset.genes, mean, projection, manifest)
    model.validate()
    return model


def _check_measurement(dataset, encoder):
    encoder.validate()
    for key in ('assay', 'ontology', 'state_dictionary'):
        if dataset.manifest.get(key) != encoder.manifest[key]:
            raise ValueError('Unreviewed assay/annotation domain shift')
    if dataset.manifest.get('library_size_rule', 'sum-supplied-panel') != encoder.manifest.get('library_size_rule', 'sum-supplied-panel'):
        raise ValueError('Frozen library measurement rule differs')


def profile(dataset, encoder, *, states, min_cells=32, cells_per_donor=64, seed=0, set_encoder=None):
    states = names(states, unique=True)
    _check_measurement(dataset, encoder)
    selected, missing = bags(dataset, encoder.manifest['compartment'], min_cells=min_cells,
                             cells_per_donor=cells_per_donor, seed=seed)
    if set(selected) & set(encoder.manifest['training_donors']):
        raise ValueError('Training/development canonical donor overlap')
    if set_encoder is not None and set(selected) & set(set_encoder.manifest['training_donors']):
        raise ValueError('Set training/development donor overlap')
    result = {}
    for donor, rows in selected.items():
        labels = [dataset.cells[i]['state'] for i in rows]
        if set(labels) - set(states):
            raise ValueError('State outside frozen panel')
        counts = dataset.rows(rows)
        totals = dataset.library_sizes(rows, counts)
        z = encoder.transform(counts, dataset.genes, totals)
        occupancy = np.array([labels.count(s)/len(rows) for s in states])
        # Deterministic disjoint halves measure within-bag instability, never donor n.
        halves = [z[::2], z[1::2]]
        instability = float(np.square(halves[0].mean(0)-halves[1].mean(0)).mean()) if len(rows) > 1 else None
        programs = {}
        for state in states:
            mask = np.array([v == state for v in labels])
            if mask.any():
                expression = log_library(counts[mask], totals[mask]).mean(0)
                programs[state] = [{'gene': dataset.genes[i], 'mean_log_library': float(expression[i])}
                                   for i in np.argsort(-expression, kind='stable')[:10]]
        result[donor] = dict(mean=z.mean(0).tolist(), variance=z.var(0).tolist(), occupancy=occupancy.tolist(),
                             heterogeneity=float(-np.sum(occupancy[occupancy > 0]*np.log(occupancy[occupancy > 0]))),
                             embedding=z.tolist(), representative_programs=programs,
                             sampled_cells=len(rows), subbag_mean_squared_difference=instability)
        if set_encoder is not None:
            result[donor]['learned_set_embedding'] = set_encoder.transform(z, cell_encoder_hash=encoder.identity).tolist()
    return dict(schema='ecosystem-profile-v1', status='development-only', confirmation='unavailable',
                compartment=encoder.manifest['compartment'], population=dataset.manifest['population'],
                assay=dataset.manifest['assay'], states=list(states), donors=result, missing=missing,
                model_hash=encoder.identity, data_hash=dataset.identity(), set_model_hash=set_encoder.identity if set_encoder else None,
                measurement=dict(min_cells=min_cells, cells_per_donor=cells_per_donor, seed=seed,
                                 denominator='within-compartment', state_dictionary=dataset.manifest['state_dictionary']),
                source_manifest=dataset.manifest)


def evaluate_holdout(dataset, encoder, **kwargs):
    """Expose held-out donor coverage and measurement stability, without a power claim."""
    p = profile(dataset, encoder, **kwargs)
    selected, _ = bags(dataset, encoder.manifest['compartment'], min_cells=kwargs.get('min_cells', 32),
                       cells_per_donor=kwargs.get('cells_per_donor', 64), seed=kwargs.get('seed', 0))
    reconstruction = {}
    for donor, rows in selected.items():
        counts = dataset.rows(rows)
        totals = dataset.library_sizes(rows, counts)
        z = encoder.transform(counts, dataset.genes, totals)
        if isinstance(encoder, CompartmentEncoder):
            predicted = z @ encoder.projection.T + encoder.mean
        else:
            logits = z @ encoder.weights[2] + encoder.weights[3]
            rates = np.exp(logits - logits.max(axis=1, keepdims=True))
            predicted = np.log1p(10000*rates[:,:len(encoder.genes)]/rates.sum(axis=1, keepdims=True))
        reconstruction[donor] = float(np.square(predicted-log_library(counts, totals)).mean())
    return dict(status='development-only', model_hash=encoder.identity, data_hash=dataset.identity(),
                donor_log_library_reconstruction_mse=reconstruction,
                eligible_donors=len(p['donors']), unavailable_donors=len(p['missing']),
                mean_subbag_instability=float(np.mean([v['subbag_mean_squared_difference'] for v in p['donors'].values()]))
                    if p['donors'] and all(v['subbag_mean_squared_difference'] is not None for v in p['donors'].values()) else None,
                unseen_study=not bool({s['accession'] for s in dataset.manifest['sources']} &
                                      {s['accession'] for s in encoder.manifest['training_sources']}),
                neural_advantage='not-evaluated')


@dataclass(frozen=True)
class CountNBEncoder:
    """Frozen count autoencoder with training-only negative-binomial dispersion.

    Inference is NumPy-only and has no batch updates, reference fitting or
    cross-compartment inputs. Decoder weights are retained for held-out checks.
    """
    genes: tuple
    weights: tuple
    dispersion: np.ndarray
    manifest: dict

    def validate(self):
        names(self.genes, unique=True)
        d = len(self.genes)
        if self.manifest.get('schema') != 'ecosystem-nb-v2' or self.manifest.get('transform') != 'log1p-UMI-per-10000':
            raise ValueError('Unsupported NB count artifact')
        if len(self.weights) != 4:
            raise ValueError('Expected separate count encoder/decoder weights')
        w, b, v, c = self.weights
        if w.ndim != 2 or w.shape[0] != d or b.shape != (w.shape[1],) or v.shape != (w.shape[1], d+1) or c.shape != (d+1,):
            raise ValueError('Invalid NB dimensions')
        if self.dispersion.shape != (d,) or np.any(self.dispersion <= 0):
            raise ValueError('Invalid training dispersion')
        if not all(np.isfinite(a).all() for a in (*self.weights, self.dispersion)):
            raise ValueError('Nonfinite NB artifact')
        for key in ('compartment', 'assay', 'ontology', 'state_dictionary', 'training_data_hash'):
            names([self.manifest[key]])
        names(self.manifest['training_donors'], unique=True)

    @property
    def identity(self):
        self.validate()
        return digest(dict(genes=self.genes, weights=[a.tolist() for a in self.weights],
                           dispersion=self.dispersion.tolist(), manifest=self.manifest))

    def transform(self, counts, genes, library_sizes=None):
        self.validate()
        if tuple(genes) != self.genes:
            raise ValueError('Exact frozen gene order required')
        w, b, _, _ = self.weights
        if self.manifest.get('library_size_rule') == 'measured-all-genes' and library_sizes is None:
            raise ValueError('Frozen measured all-gene offsets required')
        return np.tanh(log_library(counts, library_sizes) @ w + b)

    def save(self, path):
        self.validate()
        with Path(path).open('wb') as stream:
            np.savez_compressed(stream, genes=np.asarray(self.genes), dispersion=self.dispersion,
                                manifest=json.dumps(self.manifest, sort_keys=True),
                                **{f'weight_{i}': a for i, a in enumerate(self.weights)})

    @classmethod
    def load(cls, path):
        z = safe_npz(path, {'genes','dispersion','manifest',*(f'weight_{i}' for i in range(4))})
        result = cls(tuple(z['genes'].tolist()), tuple(z[f'weight_{i}'] for i in range(4)),
                     z['dispersion'], json.loads(str(z['manifest'])))
        result.validate()
        for a in (*result.weights, result.dispersion): a.flags.writeable = False
        return result


def load_encoder(path):
    # Each concrete loader bounds decompression before accessing array content.
    import zipfile
    if Path(path).stat().st_size > 64*1024**2:
        raise ValueError('Encoder too large')
    with zipfile.ZipFile(path) as z:
        entries = {i.filename for i in z.infolist()}
    return CountNBEncoder.load(path) if 'dispersion.npy' in entries else CompartmentEncoder.load(path)


def fit_nb(dataset, compartment, *, components=32, cells_per_donor=64, seed=0,
           epochs=20, batch_size=256, mask_fraction=.15, lr=.001, device='cpu', lease_path=None,
           max_seconds=7200):
    """Bounded donor-balanced masked NB reconstruction with library-size offsets.

    GPU execution requires the common operator lease path. A process-held flock
    cannot expire while its worker still owns the GPU. No GPU job is launched
    merely by installing this implementation.
    """
    import fcntl
    import time
    import resource
    from contextlib import ExitStack
    import torch
    from .evalue_device import execution

    selected, missing = bags(dataset, compartment, min_cells=cells_per_donor,
                             cells_per_donor=cells_per_donor, seed=seed, roles=('training',))
    if len(selected) < 2 or len(dataset.genes) > 4000 or len(selected)*cells_per_donor > 100000:
        raise ValueError('Training donor/gene/cell pilot limits exceeded')
    if any(type(v) is not int or v < 1 for v in (components,epochs,batch_size)) or components > 64 or epochs > 20 or batch_size > 512:
        raise ValueError('Invalid bounded pilot architecture or schedule')
    if not 0 < mask_fraction < 1 or not np.isfinite(lr) or lr <= 0 or not 0 < max_seconds <= 7200:
        raise ValueError('Invalid training parameters')
    dev, precision, provenance = execution(device, 'float64')
    gpu = str(dev).startswith('cuda')
    if gpu and not lease_path:
        raise ValueError('GPU training requires shared operator-managed lease path')
    with ExitStack() as stack:
        if gpu:
            lock = stack.enter_context(Path(lease_path).open('a+'))
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            torch.cuda.reset_peak_memory_stats(dev)
        started = time.monotonic()
        rng = np.random.default_rng(seed)
        rows = [row for group in selected.values() for row in group]
        losses = []; epoch_metrics = []
        with torch.random.fork_rng(devices=[]):
            torch.random.default_generator.manual_seed(seed)
            encoder = torch.nn.Linear(len(dataset.genes), components).to(device=dev, dtype=precision)
            decoder = torch.nn.Linear(components, len(dataset.genes)+1).to(device=dev, dtype=precision)
            log_theta = torch.nn.Parameter(torch.zeros(len(dataset.genes), device=dev, dtype=precision))
            optimizer = torch.optim.Adam([*encoder.parameters(), *decoder.parameters(), log_theta], lr=lr)
            for epoch in range(epochs):
                order = rng.permutation(rows)
                total = 0.; measured = 0
                for start in range(0,len(order),batch_size):
                    if time.monotonic()-started > max_seconds:
                        raise ValueError('Training pilot time cap reached')
                    counts = dataset.rows(order[start:start+batch_size])
                    x = torch.tensor(counts, device=dev, dtype=precision)
                    totals = dataset.library_sizes(order[start:start+batch_size], counts)
                    logged = torch.tensor(log_library(counts, totals), device=dev, dtype=precision)
                    mask = torch.tensor(rng.random(counts.shape)<mask_fraction, device=dev)
                    if not bool(mask.any()): mask[0,0] = True
                    z = torch.tanh(encoder(logged.masked_fill(mask,0)))
                    # Softmax rates times the measured per-cell library offset.
                    mu = torch.softmax(decoder(z),dim=1)[:,:len(dataset.genes)]*torch.tensor(totals[:,None],device=dev,dtype=precision)
                    mu = mu.clamp_min(1e-10)
                    theta = torch.nn.functional.softplus(log_theta)+1e-4
                    logp = (torch.lgamma(x+theta)-torch.lgamma(theta)-torch.lgamma(x+1)
                            +theta*(torch.log(theta)-torch.log(theta+mu))
                            +x*(torch.log(mu)-torch.log(theta+mu)))
                    loss = -logp[mask].mean()
                    if not bool(torch.isfinite(loss)):
                        raise ValueError('Nonfinite NB training loss')
                    optimizer.zero_grad(); loss.backward(); optimizer.step()
                    total += float(loss.detach())*int(mask.sum()); measured += int(mask.sum())
                    if gpu and torch.cuda.max_memory_reserved(dev) > 32*1024**3:
                        raise ValueError('Training pilot VRAM cap exceeded')
                losses.append(total/measured)
                elapsed = time.monotonic()-started
                epoch_metrics.append(dict(epoch=epoch+1,elapsed_seconds=elapsed,loss=losses[-1],
                                          projected_seconds=elapsed/(epoch+1)*epochs))
                if elapsed/(epoch+1)*epochs > max_seconds:
                    raise ValueError('Projected pilot overrun')
            weights = (encoder.weight.detach().cpu().numpy().T.copy(),encoder.bias.detach().cpu().numpy().copy(),
                       decoder.weight.detach().cpu().numpy().T.copy(),decoder.bias.detach().cpu().numpy().copy())
            theta = (torch.nn.functional.softplus(log_theta)+1e-4).detach().cpu().numpy().copy()
        elapsed = time.monotonic()-started
        manifest = dict(library_size_rule=dataset.manifest.get('library_size_rule', 'sum-supplied-panel'),
                        schema='ecosystem-nb-v2',transform='log1p-UMI-per-10000',compartment=compartment,
                        training_donors=sorted(selected),training_data_hash=dataset.identity(),training_sources=dataset.manifest['sources'],
                        excluded_training_donors=missing,cells_per_donor=cells_per_donor,seed=seed,epochs=epochs,
                        batch_size=batch_size,mask_fraction=mask_fraction,lr=lr,training_loss=losses,epoch_metrics=epoch_metrics,
                        execution=provenance,elapsed_seconds=elapsed,cells_per_second=len(rows)*epochs/max(elapsed,1e-9),
                        host_peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                        peak_gpu_reserved_bytes=torch.cuda.max_memory_reserved(dev) if gpu else 0,
                        utility='unvalidated; compare donor-held-out PCA and fixed-state baselines before selection',
                        **{k:dataset.manifest[k] for k in ('assay','ontology','state_dictionary')})
        result=CountNBEncoder(dataset.genes,weights,theta,manifest)
        result.validate()
        return result


def fit_pseudobulk_pca(dataset, compartment, *, components=32, cells_per_donor=32, seed=1701):
    """Conventional donor pseudobulk PCA baseline using the same sampled cells."""
    selected, _ = bags(dataset, compartment, min_cells=cells_per_donor,
                       cells_per_donor=cells_per_donor, seed=seed, roles=('training',))
    if len(selected) < 2 or len(dataset.genes)>4000 or type(components) is not int or not 1<=components<=64:
        raise ValueError('Pseudobulk PCA needs two training donors and bounded genes/components')
    rows=[]
    for indices in selected.values():
        counts=dataset.rows(indices); totals=dataset.library_sizes(indices,counts)
        rows.append(log_library(counts.sum(0,keepdims=True),[totals.sum()])[0])
    x=np.asarray(rows);mean=x.mean(0)
    _,_,v=np.linalg.svd(x-mean,full_matrices=False)
    dimensions=min(components,len(selected)-1,len(dataset.genes))
    projection=v[:dimensions].T.copy()
    for column in projection.T:
        if column[np.argmax(np.abs(column))]<0: column *= -1
    manifest=dict(schema='ecosystem-pca-v1',transform='log1p-UMI-per-10000',
        library_size_rule=dataset.manifest.get('library_size_rule','sum-supplied-panel'),
        compartment=compartment,training_donors=sorted(selected),training_data_hash=dataset.identity(),
        training_sources=dataset.manifest['sources'],cells_per_donor=cells_per_donor,seed=seed,
        execution={'device':'cpu','numpy_version':np.__version__},model_choice='donor-pseudobulk-PCA-baseline',
        **{k:dataset.manifest[k] for k in ('assay','ontology','state_dictionary')})
    result=CompartmentEncoder(dataset.genes,mean,projection,manifest);result.validate()
    return result


@dataclass(frozen=True)
class FrozenSetAggregator:
    """Permutation-invariant same-compartment pooling; no cross-view inputs."""
    weights: tuple
    mean: np.ndarray
    scale: np.ndarray
    target_mean: np.ndarray
    target_scale: np.ndarray
    manifest: dict

    def validate(self):
        if self.manifest.get('schema')!='ecosystem-set-v1' or len(self.weights)!=4:
            raise ValueError('Invalid set artifact')
        w,b,v,c=self.weights;d=len(self.mean)
        if self.mean.shape!=(d,) or self.scale.shape!=(d,) or np.any(self.scale<=0):
            raise ValueError('Invalid frozen cell standardization')
        if w.ndim!=2 or w.shape[0]!=d or b.shape!=(w.shape[1],) or v.shape!=(w.shape[1],2*d) or c.shape!=(2*d,):
            raise ValueError('Invalid set encoder/decoder dimensions')
        if self.target_mean.shape!=(2*d,) or self.target_scale.shape!=(2*d,) or np.any(self.target_scale<=0):
            raise ValueError('Invalid target reference')
        if not all(np.isfinite(a).all() for a in (*self.weights,self.mean,self.scale,self.target_mean,self.target_scale)):
            raise ValueError('Nonfinite set artifact')
        names(self.manifest['training_donors'],unique=True)
        if len(self.manifest['cell_encoder_hash'])!=64:raise ValueError('Frozen compartment encoder identity required')

    @property
    def identity(self):
        self.validate()
        return digest(dict(weights=[a.tolist() for a in self.weights],mean=self.mean.tolist(),scale=self.scale.tolist(),
            target_mean=self.target_mean.tolist(),target_scale=self.target_scale.tolist(),manifest=self.manifest))

    def transform(self, embeddings, *, cell_encoder_hash):
        self.validate();x=np.asarray(embeddings,dtype=float)
        if cell_encoder_hash!=self.manifest['cell_encoder_hash'] or x.ndim!=2 or x.shape[1]!=len(self.mean) or len(x)<2 or not np.isfinite(x).all():
            raise ValueError('Frozen same-compartment cell embeddings required')
        w,b,_,_=self.weights
        return np.tanh((x-self.mean)/self.scale@w+b).mean(0)

    def save(self,path):
        self.validate()
        with Path(path).open('wb') as stream:
            np.savez_compressed(stream,mean=self.mean,scale=self.scale,target_mean=self.target_mean,target_scale=self.target_scale,
                manifest=json.dumps(self.manifest,sort_keys=True),**{f'weight_{i}':a for i,a in enumerate(self.weights)})

    @classmethod
    def load(cls,path):
        fields={'mean','scale','target_mean','target_scale','manifest',*(f'weight_{i}' for i in range(4))}
        z=safe_npz(path,fields)
        result=cls(tuple(z[f'weight_{i}'] for i in range(4)),z['mean'],z['scale'],z['target_mean'],z['target_scale'],json.loads(str(z['manifest'])))
        result.validate()
        for a in (*result.weights,result.mean,result.scale,result.target_mean,result.target_scale):a.flags.writeable=False
        return result


def fit_set_aggregator(dataset,cell_encoder,*,components=8,cells_per_donor=32,epochs=20,seed=1701):
    """Small CPU set pilot with mean/variance reconstruction and subbag stability."""
    import torch
    import time
    if type(epochs) is not int or not 1<=epochs<=20 or type(components) is not int or not 1<=components<=32 or cells_per_donor<4:
        raise ValueError('Invalid bounded set pilot')
    _check_measurement(dataset, cell_encoder)
    selected,_=bags(dataset,cell_encoder.manifest['compartment'],min_cells=cells_per_donor,
                    cells_per_donor=cells_per_donor,seed=seed,roles=('training',))
    if len(selected)<3:raise ValueError('Set pilot needs at least three training donors')
    encoded=[]
    for rows in selected.values():
        counts=dataset.rows(rows);encoded.append(cell_encoder.transform(counts,dataset.genes,dataset.library_sizes(rows,counts)))
    x=np.stack(encoded);mean=x.reshape(-1,x.shape[-1]).mean(0);scale=x.reshape(-1,x.shape[-1]).std(0);scale[scale<.1]=.1
    target=np.concatenate([x.mean(1),x.var(1)],axis=1)
    target_mean=target.mean(0);target_scale=target.std(0);target_scale[target_scale<.1]=.1
    started=time.monotonic();losses=[]
    with torch.random.fork_rng(devices=[]):
        torch.random.default_generator.manual_seed(seed)
        encoder=torch.nn.Linear(x.shape[-1],components).double();decoder=torch.nn.Linear(components,target.shape[1]).double()
        optimizer=torch.optim.Adam([*encoder.parameters(),*decoder.parameters()],lr=.01)
        inputs=torch.tensor((x-mean)/scale,dtype=torch.float64);targets=torch.tensor((target-target_mean)/target_scale,dtype=torch.float64)
        for _ in range(epochs):
            cell=torch.tanh(encoder(inputs));pooled=cell.mean(1)
            reconstruction=(decoder(pooled)-targets).square().mean()
            stability=(cell[:,::2].mean(1)-cell[:,1::2].mean(1)).square().mean()
            loss=reconstruction+.1*stability
            if not torch.isfinite(loss):raise ValueError('Nonfinite set loss')
            optimizer.zero_grad();loss.backward();optimizer.step()
            losses.append(dict(reconstruction=float(reconstruction.detach()),stability=float(stability.detach())))
        weights=(encoder.weight.detach().numpy().T.copy(),encoder.bias.detach().numpy().copy(),
                 decoder.weight.detach().numpy().T.copy(),decoder.bias.detach().numpy().copy())
    model=FrozenSetAggregator(weights,mean,scale,target_mean,target_scale,
        dict(schema='ecosystem-set-v1',compartment=cell_encoder.manifest['compartment'],cell_encoder_hash=cell_encoder.identity,
             training_donors=sorted(selected),training_data_hash=dataset.identity(),cells_per_donor=cells_per_donor,seed=seed,
             epochs=epochs,losses=losses,elapsed_seconds=time.monotonic()-started,device='cpu',objective='same-compartment donor mean/variance + disjoint-subbag stability'))
    model.validate()
    _,_,vh=np.linalg.svd((target-target_mean)/target_scale,full_matrices=False)
    return model,vh[:min(components,len(selected)-1)].T.copy()


def evaluate_set_aggregator(dataset,cell_encoder,set_encoder,baseline_projection,*,cells_per_donor=32,seed=1701):
    _check_measurement(dataset, cell_encoder)
    selected,missing=bags(dataset,cell_encoder.manifest['compartment'],min_cells=cells_per_donor,
                          cells_per_donor=cells_per_donor,seed=seed,roles=('development',))
    if set(selected)&set(set_encoder.manifest['training_donors']):raise ValueError('Set training/development donor overlap')
    results=[]
    for rows in selected.values():
        counts=dataset.rows(rows);z=cell_encoder.transform(counts,dataset.genes,dataset.library_sizes(rows,counts))
        pooled=set_encoder.transform(z,cell_encoder_hash=cell_encoder.identity)
        target=(np.concatenate([z.mean(0),z.var(0)])-set_encoder.target_mean)/set_encoder.target_scale
        prediction=pooled@set_encoder.weights[2]+set_encoder.weights[3]
        compressed=target@baseline_projection
        split=[set_encoder.transform(part,cell_encoder_hash=cell_encoder.identity) for part in (z[::2],z[1::2])]
        results.append(dict(learned_mse=float(np.square(prediction-target).mean()),
                            summary_pca_mse=float(np.square(compressed@baseline_projection.T-target).mean()),
                            set_subbag_mse=float(np.square(split[0]-split[1]).mean())))
    return dict(eligible_donors=len(selected),unavailable_donors=len(missing),
                means={k:float(np.mean([r[k] for r in results])) for k in results[0]} if results else {},
                interpretation='Exposed development compression/stability only; no association evidence')
