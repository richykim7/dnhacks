"""Development ecosystem operations and receipt-only private registration.

Private release requires an operator-reviewed design and immutable observations.
No first-release spatial confirmation or paired comparison; critic schedules
are implemented by the shared private core.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

import numpy as np

from .ecosystem_design import CountData, digest, names
from .ecosystem_encoder import CompartmentEncoder, fit_pca, fit_nb, load_encoder, FrozenSetAggregator, profile, evaluate_holdout
from .experiment_transport import QueueStore, REQUEST_ID, send_payload, serve
from .native_evidence import KERNEL, PrivateProcessStore


def vectors(p):
    if p.get('schema') != 'ecosystem-profile-v1' or p.get('status') != 'development-only':
        raise ValueError('Exposed development profile required')
    # Coverage and whole-tissue composition never enter the critic representation.
    return {d: np.asarray(v['mean'] + v['variance'] + v['occupancy'], dtype=float) for d, v in p['donors'].items()}


def couple(left, right):
    if left['compartment'] == right['compartment'] or left['population'] != right['population'] or left['assay'] != right['assay']:
        raise ValueError('Two separately defined compartments in one assay population required')
    x, y = vectors(left), vectors(right)
    donors = sorted(x.keys() & y.keys())
    if len(donors) < 3:
        raise ValueError('At least three complete development donors required')
    a, b = np.array([x[d] for d in donors]), np.array([y[d] for d in donors])
    a -= a.mean(0); b -= b.mean(0)
    denom = np.sqrt((a*a).sum(0)[:, None]*(b*b).sum(0)[None, :])
    correlations = np.divide(a.T@b, denom, out=np.zeros(denom.shape), where=denom > 0)
    return dict(status='development-only', null='exploratory measured-state association; no calibrated evidence',
                donors=donors, n_donors=len(donors), correlations=correlations.tolist(),
                constant_feature_pairs=(denom == 0).tolist(),
                missing_left=sorted(y.keys()-x.keys()), missing_right=sorted(x.keys()-y.keys()),
                profile_hashes=[digest(left), digest(right)],
                interpretation='Association cannot establish flux, ligand transfer, signaling direction or treatment causality')


def compare(left, right):
    keys = ('compartment', 'assay', 'states', 'model_hash', 'measurement')
    if any(left[k] != right[k] for k in keys):
        raise ValueError('Comparison requires the same frozen representation and measurement')
    x, y = vectors(left), vectors(right)
    if set(x) & set(y):
        raise ValueError('Paired or overlapping donors require another reviewed contract')
    if min(len(x), len(y)) < 2:
        raise ValueError('At least two independently sampled donors per population required')
    a, b = np.array(list(x.values())), np.array(list(y.values()))
    return dict(status='development-only', n_donors=[len(x), len(y)], populations=[left['population'], right['population']],
                mean_difference=(a.mean(0)-b.mean(0)).tolist(), profile_hashes=[digest(left), digest(right)],
                interpretation='Exploratory measured distribution contrast; no two-sample evidence adapter enabled')


def spatial_profile(document):
    """Summarize segmented-cell neighborhoods within preselected donor sections.

    Inputs are exposed development coordinates with frozen external states.
    GeoMx regions and mixed spots cannot masquerade as individual cells.
    """
    if document.get('role') != 'development' or document.get('resolution') != 'segmented-single-cell':
        raise ValueError('Development segmented single cells required; mixed spots/GeoMx unsupported')
    for key in ('assay', 'segmentation_hash', 'coordinate_units', 'specimen_rule'):
        names([document[key]])
    if document['specimen_rule'] != 'one-preselected-section-per-donor':
        raise ValueError('Explicit single-section donor rule required')
    radius = document['radius']
    if not isinstance(radius, (int, float)) or not np.isfinite(radius) or radius <= 0:
        raise ValueError('Positive frozen distance radius required')
    left, right = names(document['compartments'], unique=True)
    names(document['states'], unique=True)
    cells = document['cells']
    names([c['cell_id'] for c in cells], unique=True)
    grouped = {}
    for c in cells:
        names([c[k] for k in ('donor', 'section', 'compartment', 'state')])
        if c['state'] not in document['states'] or c.get('identity_reviewed') is not True:
            raise ValueError('Unreviewed donor or state')
        xy = np.asarray(c['xy'], dtype=float)
        if xy.shape != (2,) or not np.isfinite(xy).all():
            raise ValueError('Invalid measured coordinates')
        grouped.setdefault(c['donor'], []).append(c)
    result = {}
    for donor, rows in grouped.items():
        if len({c['section'] for c in rows}) != 1:
            raise ValueError('Multiple sections cannot increase donor n')
        a = [c for c in rows if c['compartment'] == left]
        b = [c for c in rows if c['compartment'] == right]
        if not a or not b:
            result[donor] = {'status': 'unavailable-compartment'}
            continue
        if len(a)*len(b) > 10_000_000:
            raise ValueError('Neighborhood operation exceeds development work bound')
        xy = np.array([c['xy'] for c in b])
        occupancy = []
        for c in a:
            near = np.sum((xy-np.array(c['xy']))**2, axis=1) <= radius**2
            occupancy.append([sum(near[i] and b[i]['state'] == s for i in range(len(b)))/int(near.sum())
                              for s in document['states']] if near.any() else None)
        measured = [o for o in occupancy if o is not None]
        result[donor] = dict(neighborhoods_with_coverage=len(measured), anchors=len(a),
                            mean_state_occupancy=np.mean(measured, axis=0).tolist() if measured else None,
                            within_donor_sd=np.std(measured, axis=0).tolist() if measured else None)
    return dict(status='development-only', confirmation='unavailable', donors=result, source_hash=digest(document),
                uncertainty='Within-donor neighborhood dispersion; no independent-cell confidence interval')


class EcosystemQueue(QueueStore):
    """Operator config is immutable; submission validates only public syntax.

    Unknown registrations are durably accepted, then fail privately. Otherwise
    data-dependent configuration could leak eligibility through HTTP status.
    """
    worker_module = 'dnhacksbio.ecosystem_experiments'

    def validate_payload(self, payload):
        if not isinstance(payload, dict) or set(payload) != {'request_id', 'registration'}:
            raise ValueError('Only immutable registration reference accepted')
        if not isinstance(payload['request_id'], str) or not REQUEST_ID.fullmatch(payload['request_id']):
            raise ValueError('Invalid request ID')
        r = payload['registration']
        if not isinstance(r, str) or len(r) != 64 or any(c not in '0123456789abcdef' for c in r):
            raise ValueError('Invalid registration hash')

    def configure(self, document):
        """Operator-only: frozen observations and signed-off gate evidence.

        Gate booleans are not scientific validation: operator reviews the
        referenced artifacts before enabling this process in private storage.
        """
        def valid_hash(value):
            return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)
        gates = document['gates']
        for key in ('identity', 'access', 'sampling', 'transfer', 'selection', 'privacy', 'novelty'):
            gate = gates[key]
            if gate.get('approved') is not True or not gate.get('reviewer') or not valid_hash(gate.get('artifact_sha256')):
                raise ValueError('Private release gate unavailable')
        power = gates['power']
        if power.get('null_streams', 0) < 10000 or power.get('alpha') != 0.05 or power.get('power_lower_bound', 0) < 0.8 or not valid_hash(power.get('artifact_sha256')) or not np.isfinite(power.get('power_lower_bound')) or power['power_lower_bound'] > 1:
            raise ValueError('Predeclared power gate unavailable')
        spec = document['spec']
        if spec['null'] != 'independence-of-measured-malignant-and-fibroblast-states' or spec['population'] != 'untreated-primary-human-PDAC':
            raise ValueError('First-release null/population unsupported')
        if spec['kernel'] != KERNEL or len(spec['eligible_donors']) != power['available_donors']:
            raise ValueError('Power budget does not match independent donor inventory')
        if len(spec['eligible_donors'])//2 * math.log(1.9) < -math.log(.05):
            raise ValueError('Donor budget cannot reach the registered threshold even at maximal factors')
        observations = document['observations']
        if digest(observations) != spec['data_hash'] or [o['donor'] for o in observations] != spec['eligible_donors']:
            raise ValueError('Immutable observation identity/order mismatch')
        # Validate the process contract without creating a scoring transition.
        ledger = Path(document['ledger_directory'])
        if not ledger.is_absolute():
            raise ValueError('Explicit shared private ledger directory required')
        private = PrivateProcessStore(ledger)
        registration = digest(document)
        private.register('config-'+registration, spec)
        value = json.dumps({'registration': registration, 'document': document}, sort_keys=True, allow_nan=False)
        with self.connect() as con:
            con.execute('BEGIN IMMEDIATE')
            old = con.execute('SELECT config FROM settings WHERE id=1').fetchone()
            if old and old[0] != value:
                raise ValueError('Queue configuration is immutable; use a separate private queue')
            con.execute('INSERT OR IGNORE INTO settings VALUES (1,?)', (value,))
        return registration

    def export_private(self, receipt):
        with self.connect() as con:
            row = con.execute('SELECT j.status,j.result,j.error FROM jobs j JOIN aliases a ON a.canonical=j.receipt WHERE a.receipt=?', (receipt,)).fetchone()
        if row is None:
            raise ValueError('Unknown receipt')
        return dict(status=row[0], result=json.loads(row[1]) if row[1] else None, error=row[2])

    def _score_one(self, receipt):
        try:
            with self.connect() as con:
                payload = json.loads(con.execute('SELECT payload FROM jobs WHERE receipt=?', (receipt,)).fetchone()[0])
                config = json.loads(con.execute('SELECT config FROM settings WHERE id=1').fetchone()[0])
            if payload['registration'] != config['registration']:
                raise ValueError('Unknown private registration')
            document = config['document']
            store = PrivateProcessStore(document['ledger_directory'])
            store.register(receipt, document['spec'])
            observations = document['observations']
            for i in range(0, len(observations)-1, 2):
                block = observations[i:i+2]
                store.advance(receipt, i//2, [o['donor'] for o in block], [o['x'] for o in block], [o['y'] for o in block])
            result = json.dumps(store.export(receipt), allow_nan=False)
            with self.connect() as con:
                con.execute("UPDATE jobs SET status='complete',result=?,error=NULL WHERE receipt=?", (result, receipt))
        except Exception:
            with self.connect() as con:
                con.execute("UPDATE jobs SET status='failed',error='private_scoring_failed' WHERE receipt=?", (receipt,))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    subs = p.add_subparsers(dest='verb', required=True)
    prep = subs.add_parser('prepare'); prep.add_argument('--input', required=True); prep.add_argument('--output', required=True)
    train = subs.add_parser('train'); train.add_argument('--input', required=True); train.add_argument('--output', required=True)
    train.add_argument('--compartment', required=True); train.add_argument('--components', type=int, default=32)
    train.add_argument('--method', choices=['pca','nb'], default='pca'); train.add_argument('--device', default='cpu')
    train.add_argument('--lease-path'); train.add_argument('--epochs',type=int,default=20)
    train.add_argument('--cells-per-donor', type=int, default=64); train.add_argument('--seed', type=int, default=0)
    for verb in ('profile', 'evaluate'):
        sub = subs.add_parser(verb); sub.add_argument('--input', required=True); sub.add_argument('--model', required=True)
        sub.add_argument('--set-model'); sub.add_argument('--states', required=True); sub.add_argument('--cells-per-donor', type=int, default=64)
        sub.add_argument('--min-cells', type=int, default=32); sub.add_argument('--seed', type=int, default=0)
    for verb in ('couple', 'compare'):
        sub = subs.add_parser(verb); sub.add_argument('--left', required=True); sub.add_argument('--right', required=True)
    sp = subs.add_parser('spatial-profile'); sp.add_argument('--input', required=True)
    register = subs.add_parser('register'); register.add_argument('--registration', required=True)
    register.add_argument('--request-id', required=True); register.add_argument('--endpoint', required=True)
    for verb in ('configure-private', 'serve-private', 'score-one', 'export-private'):
        sub = subs.add_parser(verb); sub.add_argument('--state', required=True)
        if verb == 'configure-private': sub.add_argument('--input', required=True)
        if verb in ('score-one', 'export-private'): sub.add_argument('--receipt', required=True)
        if verb == 'serve-private':
            sub.add_argument('--host', default='127.0.0.1'); sub.add_argument('--port', type=int, default=8797)
    args = p.parse_args(argv)
    read = lambda path: json.loads(Path(path).read_text())
    try:
        if args.verb == 'prepare':
            doc = read(args.input)
            data = CountData(*(np.asarray(doc[k], dtype=np.int64) for k in ('data', 'indices', 'indptr')),
                             tuple(doc['genes']), doc['cells'], doc['manifest'])
            # Prevent truncation of fractional source counts during integer conversion.
            if any(not np.array_equal(np.asarray(doc[k]), getattr(data, k)) for k in ('data', 'indices', 'indptr')):
                raise ValueError('Raw CSR arrays must be integers')
            data.save(args.output); result = {'data_hash': data.identity(), 'status': 'prepared-development-or-training'}
        elif args.verb == 'train':
            fn = fit_pca if args.method == 'pca' else fit_nb
            extra = {} if args.method == 'pca' else dict(device=args.device, lease_path=args.lease_path, epochs=args.epochs)
            model = fn(CountData.load(args.input, roles=('training',)), args.compartment,
                       components=args.components, cells_per_donor=args.cells_per_donor, seed=args.seed, **extra)
            model.save(args.output); result = {'model_hash': model.identity, 'status': 'unvalidated-development-model'}
        elif args.verb in ('profile', 'evaluate'):
            fn = profile if args.verb == 'profile' else evaluate_holdout
            result = fn(CountData.load(args.input, roles=('development',)), load_encoder(args.model),
                        states=args.states.split(','), min_cells=args.min_cells, cells_per_donor=args.cells_per_donor, seed=args.seed,
                        set_encoder=FrozenSetAggregator.load(args.set_model) if args.set_model else None)
        elif args.verb in ('couple', 'compare'):
            result = (couple if args.verb == 'couple' else compare)(read(args.left), read(args.right))
        elif args.verb == 'spatial-profile': result = spatial_profile(read(args.input))
        elif args.verb == 'register':
            payload = {'request_id': args.request_id, 'registration': args.registration}
            EcosystemQueue.validate_payload(None, payload)
            result = send_payload(payload, args.endpoint)
        else:
            store = EcosystemQueue(args.state)
            if args.verb == 'configure-private': result = {'registration': store.configure(read(args.input))}
            elif args.verb == 'serve-private': serve(store, args.host, args.port); return 0
            elif args.verb == 'score-one': store.score_one(args.receipt); return 0
            else: result = store.export_private(args.receipt)
        print(json.dumps(result, allow_nan=False))
        return 0
    except (ValueError, KeyError, TypeError, OSError, RuntimeError):
        print('Ecosystem operation unavailable; check the declared inputs and operator setup.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
