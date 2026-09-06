"""Strict, bounded scientific display trajectory contract."""
from __future__ import annotations
import json
import math

MAX_POINTS = 2_000_000

def vector(value, *, positive=False, planar=False):
    if (not isinstance(value, list) or len(value) != 3
        or any(type(x) not in (int, float) or not math.isfinite(x) for x in value)
        or (positive and any(x <= 0 for x in value)) or (planar and value[2] != 0)):
        raise ValueError('Invalid spatial coordinates')

def validate(raw: bytes) -> dict:
    if len(raw) > 20 * 1024 * 1024:
        raise ValueError('Trajectory exceeds artifact budget')
    b = json.loads(raw)
    if (not isinstance(b, dict) or b.get('schema_version') != 1
        or type(b.get('dimensionality')) is not int or b['dimensionality'] not in (2, 3)
        or b.get('category') not in ('illustration', 'simulation')
        or b.get('units') != {'length': 'um', 'time': 's'}
        or not isinstance(b.get('model_id'), str) or not b['model_id']):
        raise ValueError('Invalid spindle manifest, dimensionality or units')
    vector(b.get('radius'), positive=True)
    runs = b.get('runs')
    if not isinstance(runs, list) or not 1 <= len(runs) <= 128:
        raise ValueError('Invalid ensemble size')
    points = 0
    keys = set()
    for run in runs:
        if (not isinstance(run, dict) or type(run.get('seed')) is not int
            or not isinstance(run.get('condition'), str) or not run['condition']):
            raise ValueError('Invalid replicate identity')
        key = (run['seed'], run['condition'])
        if key in keys:
            raise ValueError('Duplicate simulation replicate')
        keys.add(key)
        frames = run.get('frames')
        if not isinstance(frames, list) or not 1 <= len(frames) <= 2000:
            raise ValueError('Invalid frame count')
        previous = -1
        for frame in frames:
            t = frame.get('time')
            if type(t) not in (int, float) or not math.isfinite(t) or t <= previous:
                raise ValueError('Physical time must be finite, nonnegative and strictly increasing')
            previous = t
            poles = frame.get('poles')
            if not isinstance(poles, list) or not 1 <= len(poles) <= 32:
                raise ValueError('Invalid centrosome count')
            ids = set()
            for pole in poles:
                identifier = pole.get('id')
                if not isinstance(identifier, str) or not identifier or identifier in ids:
                    raise ValueError('Invalid or duplicate pole identity')
                ids.add(identifier)
                vector(pole.get('position'), planar=b['dimensionality'] == 2)
            fibers = frame.get('filaments')
            if not isinstance(fibers, list):
                raise ValueError('Missing filament geometry')
            fiber_ids = set()
            for fiber in fibers:
                identifier = fiber.get('id')
                if (not isinstance(identifier, str) or not identifier or identifier in fiber_ids
                    or fiber.get('pole') not in ids):
                    raise ValueError('Invalid filament ownership or identity')
                fiber_ids.add(identifier)
                vertices = fiber.get('points')
                if not isinstance(vertices, list) or len(vertices) < 2:
                    raise ValueError('Incomplete filament geometry')
                points += len(vertices)
                if points > MAX_POINTS:
                    raise ValueError('Trajectory exceeds display budget')
                for p in vertices:
                    vector(p, planar=b['dimensionality'] == 2)
    return b
