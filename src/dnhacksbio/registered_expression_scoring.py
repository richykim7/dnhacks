"""Operator-frozen pathway registry adapter for the shared private experiment queue."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re

from .experiment_transport import QueueStore, serve
from .expression_experiment import REQUEST_ID

METHOD = 'paired-pathway-v1'
SPEC_FIELDS = {'schema_version', 'method', 'protocol_id', 'hypothesis', 'family_id'}
PROTOCOL_FIELDS = {'input_scale', 'assignment', 'assignment_justification', 'min_pairs', 'min_targets',
                   'direction', 'exact_limit', 'seed', 'organism', 'endpoint', 'dose', 'time', 'exclusions',
                   'aggregation', 'mapping', 'resource_id', 'cohort_id', 'hypothesis', 'family_id', 'count_effects'}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def strict(value, fields):
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError('Invalid fields')


def identifier(value):
    if not isinstance(value, str) or not REQUEST_ID.fullmatch(value):
        raise ValueError('Invalid identifier')


def validate_payload(payload):
    strict(payload, {'request_id', 'spec', 'input'})
    identifier(payload['request_id'])
    spec = payload['spec']
    strict(spec, SPEC_FIELDS)
    if type(spec['schema_version']) is not int or spec['schema_version'] != 2 or spec['method'] != METHOD:
        raise ValueError('Unsupported method/schema')
    for key in ('protocol_id', 'family_id'):
        identifier(spec[key])
    if not isinstance(spec['hypothesis'], str) or not 1 <= len(spec['hypothesis'].strip()) <= 4000:
        raise ValueError('Invalid hypothesis')
    strict(payload['input'], {'cohort_id', 'manifest_sha256'})
    identifier(payload['input']['cohort_id'])
    if not isinstance(payload['input']['manifest_sha256'], str) or not re.fullmatch('[a-f0-9]{64}', payload['input']['manifest_sha256']):
        raise ValueError('Invalid manifest hash')


class Store(QueueStore):
    worker_module = 'dnhacksbio.registered_expression_scoring'

    def configure(self, registry_path):
        from .expression_design import load_arrays, validate_arrays
        source = Path(registry_path).resolve()
        if source.stat().st_size > 4 * 1024**2:
            raise ValueError('Registry too large')
        registry = json.loads(source.read_text())
        strict(registry, {'schema_version', 'protocols', 'resources', 'cohorts'})
        if type(registry['schema_version']) is not int or registry['schema_version'] != 1:
            raise ValueError('Invalid registry version')
        for section in ('protocols', 'resources', 'cohorts'):
            if not isinstance(registry[section], dict) or not registry[section]:
                raise ValueError('Empty registry')
            for key in registry[section]:
                identifier(key)
        seen_units = {}
        for cohort in registry['cohorts'].values():
            strict(cohort, {'path', 'manifest'})
            manifest = cohort['manifest']
            strict(manifest, {'data_sha256', 'source', 'release', 'organism', 'input_scale', 'unit_namespace',
                             'aliases_resolved', 'discovery_units', 'confirmation', 'aggregation', 'mapping'})
            if manifest['aliases_resolved'] is not True or type(manifest['confirmation']) is not bool:
                raise ValueError('Unresolved aliases or invalid confirmation declaration')
            if not isinstance(manifest['discovery_units'], list) or any(not isinstance(u, str) or not u.strip() for u in manifest['discovery_units']):
                raise ValueError('Invalid overlap declaration')
            for key in ('source', 'release', 'organism', 'unit_namespace', 'aggregation', 'mapping'):
                if not isinstance(manifest[key], str) or not manifest[key].strip():
                    raise ValueError('Missing provenance')
            path = (source.parent / cohort['path']).resolve()
            with path.open('rb') as stream:
                raw = stream.read(48 * 1024**2 + 1)
            if sha(raw) != manifest['data_sha256']:
                raise ValueError('Dataset hash mismatch')
            arrays = load_arrays(raw)
            validate_arrays(arrays, manifest['input_scale'])
            for unit in set(arrays['unit_ids']):
                key = (manifest['unit_namespace'], unit)
                if key in seen_units and seen_units[key] != manifest['data_sha256']:
                    raise ValueError('Overlapping registered cohorts')
                seen_units[key] = manifest['data_sha256']
            if set(arrays['unit_ids']) & set(manifest['discovery_units']):
                raise ValueError('Discovery/confirmation donor overlap')
            frozen = self.directory / (sha(raw) + '.npz')
            if not frozen.exists():
                with frozen.open('xb') as stream:
                    stream.write(raw)
                os.chmod(frozen, 0o600)
            if sha(frozen.read_bytes()) != sha(raw):
                raise ValueError('Frozen data changed')
            cohort['path'] = str(frozen)
            cohort['manifest_sha256'] = sha(canonical(manifest).encode())
        for resource in registry['resources'].values():
            strict(resource, {'organism', 'source', 'release', 'mapping', 'weights'})
            import math
            if any(not isinstance(resource[k], str) or not resource[k].strip() for k in ('organism', 'source', 'release', 'mapping')):
                raise ValueError('Invalid resource provenance')
            if not isinstance(resource['weights'], dict) or not resource['weights'] or any(not isinstance(g, str) or not g.strip() or type(w) not in (float, int) or not math.isfinite(w) for g, w in resource['weights'].items()):
                raise ValueError('Invalid weights')
        for protocol in registry['protocols'].values():
            strict(protocol, PROTOCOL_FIELDS)
            for key in PROTOCOL_FIELDS - {'min_pairs', 'min_targets', 'direction', 'exact_limit', 'seed', 'count_effects'}:
                if not isinstance(protocol[key], str) or not protocol[key].strip():
                    raise ValueError('Invalid protocol text')
            for key, low, high in [('min_pairs', 2, 10000), ('min_targets', 1, 100000), ('exact_limit', 1, 1048576), ('seed', 0, 2**32-1)]:
                if type(protocol[key]) is not int or not low <= protocol[key] <= high:
                    raise ValueError('Invalid protocol integer')
            if type(protocol['direction']) is not int or protocol['direction'] not in (-1, 1) or type(protocol['count_effects']) is not bool:
                raise ValueError('Invalid protocol option')
            resource = registry['resources'][protocol['resource_id']]
            manifest = registry['cohorts'][protocol['cohort_id']]['manifest']
            if protocol['input_scale'] not in {'TPM', 'counts'} or protocol['count_effects'] and protocol['input_scale'] != 'counts':
                raise ValueError('Invalid count effects scale')
            for key in ('organism', 'mapping'):
                if resource[key] != protocol[key] or manifest[key] != protocol[key]:
                    raise ValueError('Incompatible organism/mapping')
            for key in ('input_scale', 'aggregation'):
                if manifest[key] != protocol[key]:
                    raise ValueError('Incompatible preparation')
            if protocol['min_targets'] > len(resource['weights']):
                raise ValueError('Impossible coverage')
        import importlib.metadata
        software = {name: importlib.metadata.version(name) for name in ('numpy',)}
        if any(p['count_effects'] for p in registry['protocols'].values()):
            from .count_expression import PYDESEQ2_VERSION
            for name in ('pydeseq2', 'scipy', 'pandas', 'anndata', 'formulaic', 'formulaic-contrasts'):
                software[name] = importlib.metadata.version(name)
            if software['pydeseq2'] != PYDESEQ2_VERSION:
                raise ValueError('Unsupported PyDESeq2')
        implementation = {name: sha((Path(__file__).parent / name).read_bytes()) for name in
                          ('registered_expression_scoring.py', 'expression_design.py', 'pathway_evalue.py', 'count_expression.py', 'evalues.py')}
        value = canonical({'registry': registry, 'software': software, 'implementation': implementation})
        with self.connect() as con:
            con.execute('BEGIN IMMEDIATE')
            previous = con.execute('SELECT config FROM settings WHERE id=1').fetchone()
            if previous and previous[0] != value:
                raise ValueError('Settings frozen; use a new queue')
            con.execute('INSERT OR IGNORE INTO settings VALUES (1, ?)', (value,))

    def experiment_key(self, payload):
        # Only the frozen cohort/protocol is scientific identity; aliases cannot add evidence.
        with self.connect() as con:
            registry = json.loads(con.execute('SELECT config FROM settings WHERE id=1').fetchone()[0])['registry']
        protocol, cohort, resource = self.resolve(payload, registry)
        scientific = {k: v for k, v in protocol.items() if k not in {'cohort_id', 'resource_id', 'hypothesis', 'family_id'}}
        return sha(canonical({'data': cohort['manifest']['data_sha256'], 'protocol': scientific, 'resource': resource}).encode())

    def validate_payload(self, payload):
        validate_payload(payload)
        with self.connect() as con:
            row = con.execute('SELECT config FROM settings WHERE id=1').fetchone()
        if not row:
            raise ValueError('Queue not configured')
        self.resolve(payload, json.loads(row[0])['registry'])

    def enqueue(self, payload):
        # Keep rejected method-specific attempts private as well as accepted aliases.
        try:
            self.validate_payload(payload)
        except Exception:
            try:
                value = canonical(payload)
                if len(value.encode()) <= 96 * 1024**2:
                    receipt = payload.get('request_id', '') if isinstance(payload, dict) else ''
                    receipt = receipt if isinstance(receipt, str) else ''
                    with self.connect() as con:
                        con.execute('INSERT INTO submissions (receipt,digest,payload,outcome) VALUES (?, ?, ?, ?)',
                                    (receipt, sha(value.encode()), value, 'rejected_validation'))
            except (TypeError, ValueError):
                pass
            raise ValueError('Invalid registered expression submission') from None
        return super().enqueue(payload)

    @staticmethod
    def resolve(payload, registry):
        protocol = registry['protocols'][payload['spec']['protocol_id']]
        cohort = registry['cohorts'][protocol['cohort_id']]
        if payload['input'] != {'cohort_id': protocol['cohort_id'], 'manifest_sha256': cohort['manifest_sha256']}:
            raise ValueError('Cohort mismatch')
        if any(payload['spec'][k] != protocol[k] for k in ('hypothesis', 'family_id')):
            raise ValueError('Specification conflicts with frozen protocol')
        return protocol, cohort, registry['resources'][protocol['resource_id']]

    def _score_one(self, receipt):
        try:
            import importlib.metadata
            from .expression_design import load_arrays
            from .pathway_evalue import score_pathway
            with self.connect() as con:
                payload = json.loads(con.execute("SELECT payload FROM jobs WHERE receipt=? AND status='running'", (receipt,)).fetchone()[0])
                config = json.loads(con.execute('SELECT config FROM settings WHERE id=1').fetchone()[0])
            for name, pinned in config['software'].items():
                if importlib.metadata.version(name) != pinned:
                    raise ValueError('Software changed')
            for name, digest in config['implementation'].items():
                if sha((Path(__file__).parent / name).read_bytes()) != digest:
                    raise ValueError('Implementation changed')
            protocol, cohort, resource = self.resolve(payload, config['registry'])
            raw = Path(cohort['path']).read_bytes()
            if sha(raw) != cohort['manifest']['data_sha256']:
                raise ValueError('Frozen data changed')
            arrays = load_arrays(raw)
            result = score_pathway(arrays, protocol, resource)
            result.update({'experiment_key': self.experiment_key(payload), 'spec': payload['spec'], 'manifest': cohort['manifest'],
                           'manifest_sha256': cohort['manifest_sha256'], 'protocol': protocol,
                           'protocol_sha256': sha(canonical(protocol).encode()), 'resource_sha256': sha(canonical(resource).encode()),
                           'software': config['software'], 'implementation': config['implementation'], 'confirmation': cohort['manifest']['confirmation']})
            if protocol['count_effects']:
                from .count_expression import paired_count_effects
                try:
                    result['count_effects'] = paired_count_effects(arrays)
                except Exception as exc:
                    result['count_effects'] = {'status': 'unavailable', 'reason': type(exc).__name__}
            with self.connect() as con:
                con.execute("UPDATE jobs SET status='completed', result=? WHERE receipt=? AND status='running'", (canonical(result), receipt))
        except Exception as exc:
            with self.connect() as con:
                con.execute("UPDATE jobs SET status='failed', error=? WHERE receipt=? AND status='running'", (type(exc).__name__, receipt))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    run = commands.add_parser('serve')
    run.add_argument('--registry', required=True)
    run.add_argument('--host', default='127.0.0.1')
    run.add_argument('--port', type=int, default=8793)
    score = commands.add_parser('score-one')
    score.add_argument('--receipt', required=True)
    export = commands.add_parser('export')
    export.add_argument('--output', required=True)
    for sub in (run, score, export):
        sub.add_argument('--state', required=True)
    args = parser.parse_args(argv)
    store = Store(args.state)
    if args.command == 'serve':
        store.configure(args.registry)
        serve(store, args.host, args.port)
    elif args.command == 'score-one':
        store.score_one(args.receipt)
    else:
        with store.connect() as con:
            rows = con.execute('SELECT receipt, canonical, payload FROM aliases ORDER BY rowid').fetchall()
            jobs = con.execute('SELECT receipt, status, result, error FROM jobs ORDER BY rowid').fetchall()
            submissions = con.execute('SELECT receipt, outcome, received_at FROM submissions ORDER BY id').fetchall()
        value = {'submissions': [{'receipt': r, 'outcome': o, 'received_at': t} for r, o, t in submissions], 'attempts': [{'receipt': r, 'canonical': c, 'payload': json.loads(p)} for r, c, p in rows],
                 'experiments': [{'receipt': r, 'status': s, 'result': json.loads(v) if v else None, 'error': e} for r, s, v, e in jobs]}
        with open(args.output, 'w', opener=lambda p, f: os.open(p, f, 0o600)) as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(canonical(value) + '\n')


if __name__ == '__main__':
    main()
