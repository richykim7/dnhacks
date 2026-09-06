"""Frozen separate-view PCA/compact reconstruction encoders and ridge predictor.

All model selection uses declared development splits. JSON artifacts avoid pickle.
"""
from __future__ import annotations

import copy
import platform
import time
import numpy as np
from .pharmacotype_data import digest


def seal(model):
    model = copy.deepcopy(model)
    model.pop('sha256', None)
    return {**model, 'sha256': digest(model)}


def verify(model):
    if model.get('schema') != 'pharmacotype.model.v1' or seal(model)['sha256'] != model.get('sha256'):
        raise ValueError('Model integrity failure')


def _fill(x, fill, tolerance):
    x = np.asarray(x, float)
    if x.ndim != 2 or x.shape[1] != len(fill) or np.isinf(x).any():
        raise ValueError('Invalid molecular shape/values')
    if (np.isnan(x).mean(axis=1) > tolerance).any():
        raise ValueError('Missing features exceed frozen tolerance')
    return np.where(np.isnan(x), fill, x)


def encode(x, artifact):
    z = (np.asarray(x) - artifact['mean']) / artifact['scale']
    if artifact['kind'] == 'identity':
        return z
    z = z @ np.asarray(artifact['weights'])
    return np.tanh(z + artifact['bias']) if artifact['kind'] == 'mlp' else z


def fit_view(train, validation, *, kind, latent, seed, epochs):
    mean = train.mean(0)
    scale = np.maximum(train.std(0), 1e-8)
    z, v = (train - mean) / scale, (validation - mean) / scale
    a = {'kind': kind, 'mean': mean.tolist(), 'scale': scale.tolist()}
    if kind == 'identity':
        return a
    if kind == 'pca':
        _, _, vt = np.linalg.svd(z, full_matrices=False)
        a['weights'] = vt[:min(latent, len(vt))].T.tolist()
        return a
    rng = np.random.default_rng(seed)
    w = rng.normal(0, .1, (z.shape[1], latent)); b = np.zeros(latent)
    decoder = rng.normal(0, .1, (latent, z.shape[1])); db = np.zeros(z.shape[1])
    best, loss_best, stale = None, float('inf'), 0
    for epoch in range(epochs):
        # Masked reconstruction; training fill/scaling never sees validation values.
        masked = z * (rng.random(z.shape) > .15)
        h = np.tanh(masked @ w + b)
        delta = 2 * (h @ decoder + db - z) / z.size
        dh = (delta @ decoder.T) * (1 - h*h)
        w -= .02 * masked.T @ dh; b -= .02 * dh.sum(0)
        decoder -= .02 * h.T @ delta; db -= .02 * delta.sum(0)
        loss = float(np.mean((np.tanh(v @ w + b) @ decoder + db - v)**2))
        if loss < loss_best - 1e-8:
            loss_best, stale = loss, 0
            best = (w.copy(), b.copy(), decoder.copy(), db.copy(), epoch + 1)
        else:
            stale += 1
        if stale >= 15:
            break
    w, b, decoder, db, used = best
    a.update(weights=w.tolist(), bias=b.tolist(), decoder=decoder.tolist(),
             decoder_bias=db.tolist(), epochs=used, validation_reconstruction_mse=loss_best)
    return a


def train(data, splits, *, kind='pca', latent=8, seed=0, epochs=100, ridge=1., missing_tolerance=.1):
    if data['role'] != 'development' or kind not in {'pca', 'identity', 'mlp'}:
        raise ValueError('Development training only')
    if not 0 <= missing_tolerance < 1 or not 1 <= epochs <= 500 or not 1 <= latent <= 128 or not np.isfinite(ridge) or ridge <= 0:
        raise ValueError('Invalid bounded training configuration')
    groups = [splits.get(k, []) for k in ('train', 'validation', 'test')]
    flattened = sum(groups, [])
    if any(len(g) < 2 for g in groups) or len(set(flattened)) != len(flattened) or set(flattened) != set(data['donors']):
        raise ValueError('Exhaustive disjoint canonical-donor splits required (>=2 each)')
    ix = [[data['donors'].index(d) for d in group] for group in groups]
    x, y = data['x'], data['y']
    fill = np.nanmean(x[ix[0]], axis=0)
    if not np.isfinite(fill).all():
        raise ValueError('Training feature entirely missing')
    x = _fill(x, fill, missing_tolerance)
    started = time.monotonic()
    ex = fit_view(x[ix[0]], x[ix[1]], kind=kind, latent=latent, seed=seed, epochs=epochs)
    ey = fit_view(y[ix[0]], y[ix[1]], kind=kind, latent=latent, seed=seed+1, epochs=epochs)
    zx, zy = encode(x, ex), encode(y, ey)
    design = np.column_stack((zx[ix[0]], np.ones(len(ix[0]))))
    penalty = np.eye(design.shape[1]) * ridge; penalty[-1, -1] = 0
    coef = np.linalg.solve(design.T @ design + penalty, design.T @ y[ix[0]])
    # Bounded cross-modal bilinear critic, development matched vs crossed pairs.
    rng = np.random.default_rng(seed)
    a, b = zx[ix[0]], zy[ix[0]]
    crossed = np.roll(b, 1, axis=0)
    features = np.concatenate([np.einsum('ni,nj->nij', a, q).reshape(len(a), -1) for q in (b, crossed)])
    labels = np.r_[np.ones(len(a)), -np.ones(len(a))]
    cw = rng.normal(0, .001, features.shape[1])
    for _ in range(epochs):
        score = np.tanh(features @ cw)
        gradient = features.T @ ((score-labels)*(1-score**2)) / len(score) + .01*cw
        cw -= .01 * np.clip(gradient, -10, 10)
    metrics = {}
    for name, indices in zip(('validation', 'test'), ix[1:]):
        predicted = np.column_stack((zx[indices], np.ones(len(indices)))) @ coef
        metrics[name + '_curve_rmse'] = float(np.sqrt(np.mean((predicted-y[indices])**2)))
    return seal({'schema': 'pharmacotype.model.v1', 'kind': kind, 'genes': data['genes'],
        'panel': data['panel'], 'contract_hash': data['contract_hash'], 'source_hash': data['source_hash'],
        'development_donors': data['donors'], 'splits': splits, 'fill': fill.tolist(),
        'missing_tolerance': missing_tolerance, 'molecular': ex, 'response': ey,
        'predictor': coef.tolist(), 'critic': cw.reshape(zx.shape[1], zy.shape[1]).tolist(),
        'seed': seed, 'epochs_cap': epochs, 'ridge': ridge, 'latent': latent,
        'metrics': metrics, 'training_seconds': time.monotonic()-started,
        'software': {'python': platform.python_version(), 'numpy': np.__version__},
        'limitations': 'Development only; no clinical probability, mechanism, synergy or confirmation. Test split must not select models.'})


def molecular(x, model):
    verify(model)
    return encode(_fill(x, model['fill'], model['missing_tolerance']), model['molecular'])


def predict(x, model):
    z = molecular(x, model)
    return np.column_stack((z, np.ones(len(z)))) @ model['predictor']


def critic(x, y, model):
    return np.tanh(np.asarray(x) @ np.asarray(model['critic']) @ np.asarray(y))


def validate_native(*, streams=10000, donors=32, seed=731):
    """Synthetic stress diagnostics for a prespecified frozen one-dimensional critic.

    Invalid controls intentionally violate the null/filtration/independent-unit
    contract. These simulations cannot certify any real assay or its power.
    """
    from .native_evidence import association_factor
    if type(streams) is not int or not 10000 <= streams <= 100000 or type(donors) is not int or not 4 <= donors <= 256 or donors % 2:
        raise ValueError('Require 10000..100000 streams and even donor budget 4..256')
    rng = np.random.default_rng(seed)
    cases = {}
    def interval(count):
        # Two-sided 95% Wilson interval for independent Bernoulli stream outcomes.
        p = count/streams; z = 1.959963984540054; den = 1+z*z/streams
        middle = (p+z*z/(2*streams))/den
        half = z*np.sqrt(p*(1-p)/streams+z*z/(4*streams**2))/den
        return [float(middle-half), float(middle+half)]
    for case in ('iid_null', 'heavy_tail_null', 'simple_alternative', 'nonlinear_alternative',
                 'shared_control_invalid', 'current_block_training_invalid', 'pseudoreplication_invalid'):
        x = rng.normal(size=(streams,donors))
        y = rng.normal(size=x.shape)
        if case == 'heavy_tail_null':
            x, y = rng.standard_t(1, size=x.shape), rng.standard_t(1, size=x.shape)
        elif case in {'simple_alternative', 'pseudoreplication_invalid'}:
            if case == 'simple_alternative': y = x + .3*y
        elif case == 'nonlinear_alternative':
            y = x*x + .3*y
            x = x*x  # Frozen development-selected nonlinear feature, not fitted here.
        elif case == 'shared_control_invalid':
            # Independent underlying modalities with a common normalization/control effect.
            common = rng.normal(0,3,size=x.shape); x += common; y += common
        a,b,c,d = x[:,::2],x[:,1::2],y[:,::2],y[:,1::2]
        scores = np.stack([np.tanh(a*c),np.tanh(b*d),np.tanh(a*d),np.tanh(b*c)],axis=-1)
        if case == 'current_block_training_invalid':
            # Memorizing a current block supplies maximal matched/crossed separation.
            scores[:] = [1,1,-1,-1]
        if case == 'pseudoreplication_invalid':
            scores[:] = scores[:,:1,:]  # Reuse the same two donors as if fresh.
        factors = np.fromiter((association_factor(row,.9) for row in scores.reshape(-1,4)),
                              dtype=float,count=streams*(donors//2)).reshape(streams,-1)
        path = np.cumsum(np.log(factors),axis=1)
        crossed = path >= np.log(20)
        final, anytime = int(crossed[:,-1].sum()), int(crossed.any(axis=1).sum())
        first = np.argmax(crossed,axis=1)*2+2
        cases[case] = {'final_rejection_rate':final/streams,'final_95ci':interval(final),
            'anytime_rejection_rate':anytime/streams,'anytime_95ci':interval(anytime),
            'median_donors_to_detection_among_detected':float(np.median(first[crossed.any(axis=1)])) if anytime else None,
            'actual_unique_donors':2 if case == 'pseudoreplication_invalid' else donors,
            'valid_null':case in {'iid_null','heavy_tail_null'},
            'invalid_control':case.endswith('_invalid')}
    return {'schema':'pharmacotype.synthetic-validation.v1','seed':seed,'streams_per_case':streams,
            'nominal_donor_budget':donors,'kernel':'native-two-view-four-term-v1',
            'software':{'python':platform.python_version(),'numpy':np.__version__},'alpha':.05,'stake':.9,'cases':cases,
            'limitations':'Synthetic frozen critic only; nonlinear case uses a prespecified squared feature. No PDO power or release approval.'}
