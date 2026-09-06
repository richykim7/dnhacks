"""Development pharmacotype operations and receipt-only submission CLI."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import numpy as np
from .pharmacotype_data import prepare
from .pharmacotype_encoder import train, predict, molecular, encode, verify


def profile(document):
    d = prepare(document)
    return {'status': 'development', 'donors': d['donors'], 'curves': d['y'].tolist(),
            'molecular_missing_fraction': np.isnan(d['x']).mean(axis=1).tolist(),
            'replicate_sd': d['replicate_sd'], 'exclusions': d['exclusions'],
            'panel': d['panel'], 'assay': d['assay'], 'source_hash': d['source_hash'],
            'response_logdose_mean': curve_means(d).tolist()}


def curve_means(data):
    """Observed log-dose area divided by observed width, on original response scale."""
    columns, start = [], 0
    for drug in data['panel']:
        doses = np.log(np.asarray(drug['doses']))
        values = data['y'][:, start:start+len(doses)]
        columns.append(np.trapezoid(values, doses, axis=1)/(doses[-1]-doses[0]))
        start += len(doses)
    return np.column_stack(columns)


def _ranks(values):
    _, inverse, counts = np.unique(values, return_inverse=True, return_counts=True)
    return (np.cumsum(counts)-counts/2)[inverse]


def predict_document(document, model):
    """Prediction does not require observed drug responses."""
    verify(model)
    if document.get('schema') == 'pharmacotype.query.v1':
        if document.get('genes') != model['genes'] or document.get('contract_hash') != model['contract_hash']:
            raise ValueError('Query gene/assay contract mismatch')
        ids = document['ids']
        if not ids or len(set(ids)) != len(ids) or not all(isinstance(i,str) and i for i in ids):
            raise ValueError('Unique query identifiers required')
        x = np.asarray(document['rna'], dtype=float)
        if len(x) != len(ids):
            raise ValueError('Query row count mismatch')
    else:
        data = prepare(document); compatible(data, model)
        ids, x = data['donors'], data['x']
    return {'status': 'development_prediction', 'donors': ids,
            'curves': predict(x, model).tolist(), 'model_sha256': model['sha256'],
            'held_out_error': model['metrics'], 'panel': model['panel'],
            'applicability': 'Uncalibrated outside training distribution; no patient benefit probability.'}


def compatible(data, model):
    verify(model)
    if data['contract_hash'] != model['contract_hash']:
        raise ValueError('Frozen gene/panel/assay contract mismatch')


def neighbors(document, query, model, *, modality='molecular', k=5):
    data = prepare(document); compatible(data, model)
    if type(k) is not int or k < 1 or modality not in {'molecular', 'response'}:
        raise ValueError('Invalid neighborhood request')
    transform = (lambda x: molecular(x, model)) if modality == 'molecular' else (lambda x: encode(x, model['response']))
    reference = transform(data['x'] if modality == 'molecular' else data['y'])
    q = transform(np.asarray([query], dtype=float))
    if q.shape != (1, reference.shape[1]) or not np.isfinite(q).all():
        raise ValueError('Invalid query')
    distances = np.linalg.norm(reference-q, axis=1)
    order = sorted(range(len(distances)), key=lambda i: (distances[i], data['donors'][i]))[:k]
    return {'status': 'development', 'modality': modality, 'model_sha256': model['sha256'],
            'applicability': 'Only registered assay; distance is not calibrated biological similarity.',
            'neighbors': [{'donor': data['donors'][i], 'distance': float(distances[i])} for i in order]}


def compare_programs(document, model, genes):
    data = prepare(document); compatible(data, model)
    if not genes or len(set(genes)) != len(genes) or not set(genes) <= set(data['genes']):
        raise ValueError('Require unique measured program genes')
    indices = [data['genes'].index(g) for g in genes]
    x = np.where(np.isnan(data['x']), model['fill'], data['x'])
    scaled = (x-np.asarray(model['molecular']['mean']))/model['molecular']['scale']
    program = scaled[:, indices].mean(1)
    high = program > np.median(program)
    if high.all() or not high.any():
        raise ValueError('Program has no usable contrast')
    ablated = data['x'].copy(); ablated[:, indices] = np.asarray(model['fill'])[indices]
    areas = curve_means(data)
    ranks = _ranks(program)
    correlations = [float(np.corrcoef(ranks, _ranks(col))[0,1]) if np.ptp(col) > 0 else None for col in areas.T]
    return {'status': 'development', 'genes': genes,
            'program_response_area_spearman': correlations, 'model_sha256': model['sha256'],
            'observed_high_minus_low': (data['y'][high].mean(0)-data['y'][~high].mean(0)).tolist(),
            'predicted_minus_ablated': (predict(data['x'], model)-predict(ablated, model)).mean(0).tolist(),
            'limitations': 'Exploratory median split and model ablation; not a causal intervention or confirmed marker.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('prepare-dev', 'profile', 'train', 'predict', 'neighbors', 'compare-programs'):
        p = sub.add_parser(name); p.add_argument('--data', required=True); p.add_argument('--output', required=True)
        if name == 'train':
            p.add_argument('--splits', required=True); p.add_argument('--kind', choices=['identity', 'pca', 'mlp'], default='pca')
            p.add_argument('--seed', type=int, default=0); p.add_argument('--epochs', type=int, default=100)
        if name in {'predict', 'neighbors', 'compare-programs'}:
            p.add_argument('--model', required=True)
        if name == 'neighbors':
            p.add_argument('--query', required=True); p.add_argument('--modality', choices=['molecular', 'response'], default='molecular'); p.add_argument('--k', type=int, default=5)
        if name == 'compare-programs':
            p.add_argument('--genes', required=True, help='Comma-separated frozen program')
    p = sub.add_parser('validate'); p.add_argument('--output', required=True); p.add_argument('--donors', type=int, default=32); p.add_argument('--seed', type=int, default=731)
    p = sub.add_parser('submit'); p.add_argument('--spec', required=True); p.add_argument('--request-id', required=True)
    p.add_argument('--endpoint', default=os.environ.get('DNHACKS_PHARMACOTYPE_ENDPOINT', 'http://127.0.0.1:8797'))
    args = parser.parse_args(argv)
    if args.command == 'submit':
        from .drug_response_experiment import submit
        print(json.dumps(submit(args.spec, args.request_id, endpoint=args.endpoint)))
        return
    read = lambda p: json.loads(Path(p).read_text())
    if args.command == 'validate':
        from .pharmacotype_encoder import validate_native
        with open(args.output, 'x') as stream:
            json.dump(validate_native(donors=args.donors, seed=args.seed), stream, indent=2, allow_nan=False)
        return
    doc = read(args.data)
    if args.command in {'profile', 'prepare-dev'}:
        result = profile(doc)
    elif args.command == 'train':
        result = train(prepare(doc), read(args.splits), kind=args.kind, seed=args.seed, epochs=args.epochs)
    else:
        model = read(args.model)
        if args.command == 'predict':
            result = predict_document(doc, model)
        elif args.command == 'neighbors':
            result = neighbors(doc, read(args.query), model, modality=args.modality, k=args.k)
        else:
            result = compare_programs(doc, model, args.genes.split(','))
    with open(args.output, 'x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False); stream.write('\n')


if __name__ == '__main__':
    main()
