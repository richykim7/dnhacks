"""Versioned, prejoined patient-origin curve contracts. No data acquisition."""
from __future__ import annotations

import hashlib
import json
import numpy as np


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def text(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('Missing identifier/provenance')
    return value


def finite(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not np.isfinite(value):
        raise ValueError('Expected finite number')
    return float(value)


def prepare(document, *, role='development'):
    """Validate one assay/panel; equally weight replicates within plate then plates.

    Selection is an explicit culture ID per canonical donor, never best response.
    Incomplete curves are excluded as whole donors and reported to the caller.
    Confirmation callers must keep this entire object private.
    """
    if document.get('schema')=='pharmacotype.prepared.v1' and role=='development':
        if document.get('role')!='development':raise ValueError('Prepared confirmation is forbidden')
        if document.get('integrity_sha256')!=digest({k:v for k,v in document.items() if k!='integrity_sha256'}):
            raise ValueError('Prepared development integrity mismatch')
        data=dict(document);data['x']=np.asarray(data['x'],float);data['y']=np.asarray(data['y'],float)
        if len(set(data['donors']))!=len(data['donors']) or len(set(data['genes']))!=len(data['genes']):
            raise ValueError('Duplicate prepared identifiers')
        if data['x'].shape!=(len(data['donors']),len(data['genes'])) or data['y'].shape!=(len(data['donors']),sum(len(p['doses']) for p in data['panel'])):
            raise ValueError('Prepared matrix shape mismatch')
        if not np.isfinite(data['y']).all() or np.isinf(data['x']).any():raise ValueError('Invalid prepared values')
        return data
    if document.get('schema') != 'pharmacotype.data.v1' or document.get('role') != role:
        raise ValueError('Wrong schema or data role')
    assay = document['assay']
    for key in ('version', 'technology', 'scale', 'media', 'seeding', 'vehicle_control',
                'positive_control', 'molecular_sampling', 'population', 'source_sha256', 'license'):
        text(assay[key])
    if len(assay['source_sha256']) != 64 or any(c not in '0123456789abcdef' for c in assay['source_sha256']):
        raise ValueError('Source hash required')
    if finite(assay['exposure_hours']) <= 0 or assay['dose_unit'] != 'M':
        raise ValueError('Exposure must be positive; doses must be molar')
    lo, hi = map(finite, assay['response_bounds'])
    if lo >= hi:
        raise ValueError('Invalid assay-specific bounds')
    genes = document['genes']
    if not genes or len(set(genes)) != len(genes):
        raise ValueError('Unique ordered genes required')
    for gene in genes:
        text(gene)
    coordinates = []
    drugs = set()
    for item in document['panel']:
        drug = text(item['compound'])
        text(item['formulation'])
        if drug in drugs:
            raise ValueError('Duplicate compound')
        drugs.add(drug)
        doses = list(map(finite, item['doses']))
        if len(doses) < 2 or doses != sorted(set(doses)) or doses[0] <= 0:
            raise ValueError('Require ordered unique positive molar doses')
        coordinates.extend((drug, d) for d in doses)
    if not coordinates:
        raise ValueError('Empty panel')
    aliases = document['aliases']
    for alias, donor in aliases.items():
        text(alias); text(donor)
        if donor in aliases and aliases[donor] != donor:
            raise ValueError('Aliases must resolve directly to canonical donor')
    selection = document['selected_cultures']
    for donor, culture in selection.items():
        text(donor); text(culture)
        if donor in aliases and aliases[donor] != donor:
            raise ValueError('Selection keys must be canonical')
    seen_cultures, selected, exclusions = set(), {}, []
    for row in document['cultures']:
        origin = text(row['origin'])
        if origin not in aliases:
            raise ValueError('Unresolved donor origin')
        donor = aliases[origin]
        culture = text(row['culture'])
        if culture in seen_cultures:
            raise ValueError('Duplicate culture')
        seen_cultures.add(culture)
        text(row['passage']); text(row['baseline_time'])
        if selection.get(donor) != culture:
            exclusions.append({'donor': donor, 'culture': culture, 'reason': 'not_selected'})
            continue
        if donor in selected:
            raise ValueError('Repeated patient origin')
        selected[donor] = row
    if set(selected) != set(selection):
        raise ValueError('Selection refers to missing donor/culture')
    x, y, ids, variation = [], [], [], []
    for donor in sorted(selected):
        row = selected[donor]
        if len(row['rna']) != len(genes):
            raise ValueError('RNA feature count mismatch')
        expression = [np.nan if v is None else finite(v) for v in row['rna']]
        points, keys = {}, set()
        for well in row['responses']:
            coord = (well['compound'], finite(well['dose']))
            if coord not in coordinates:
                raise ValueError('Unregistered drug/dose; no panel substitution')
            for key in ('plate', 'run', 'pool', 'replicate'):
                text(well[key])
            key = (coord, well['run'], well['plate'], well['replicate'])
            if key in keys:
                raise ValueError('Duplicate technical replicate')
            keys.add(key)
            value = finite(well['value'])
            if not lo <= value <= hi:
                raise ValueError('Response outside frozen assay bounds')
            points.setdefault(coord, {}).setdefault((well['run'], well['plate']), []).append(value)
        if set(points) != set(coordinates):
            exclusions.append({'donor': donor, 'culture': row['culture'], 'reason': 'incomplete_curve'})
            continue
        curve, spread = [], []
        for coord in coordinates:
            plates = points[coord]
            curve.append(float(np.mean([np.mean(v) for v in plates.values()])))
            spread.append(float(np.std([v for values in plates.values() for v in values])))
        ids.append(donor); x.append(expression); y.append(curve); variation.append(spread)
    return {'schema': 'pharmacotype.prepared.v1', 'role': role, 'donors': ids,
            'x': np.asarray(x, dtype=float).reshape(-1, len(genes)),
            'y': np.asarray(y, dtype=float).reshape(-1, len(coordinates)),
            'replicate_sd': variation, 'exclusions': exclusions, 'genes': genes,
            'panel': document['panel'], 'assay': assay, 'source_hash': digest(document),
            'contract_hash': digest({'genes': genes, 'panel': document['panel'], 'assay': {k: v for k, v in assay.items() if k not in {'source_sha256', 'license'}}})}
