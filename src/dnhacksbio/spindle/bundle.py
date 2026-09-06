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

def validate(raw: bytes, *, scientific=False) -> dict:
    # The worker validates the full archive before separately bounding its display.
    if len(raw) > (200 if scientific else 20) * 1024 * 1024:
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
                if points > (20_000_000 if scientific else MAX_POINTS):
                    raise ValueError('Trajectory exceeds display budget')
                for p in vertices:
                    vector(p, planar=b['dimensionality'] == 2)
            motors=frame.get('cortical_motors',[])
            if not isinstance(motors,list) or len(motors)>1000:raise ValueError('Invalid cortical motor count')
            motor_ids=set()
            for motor in motors:
                if not isinstance(motor,dict) or set(motor)!={'id','position','force_pn','filament','abscissa_um'}:
                    raise ValueError('Invalid cortical motor fields')
                if not isinstance(motor['id'],str) or not motor['id'] or motor['id'] in motor_ids:
                    raise ValueError('Invalid cortical motor identity')
                motor_ids.add(motor['id']);vector(motor['position'],planar=b['dimensionality']==2)
                if motor['filament'] is None:
                    if motor['force_pn'] is not None or motor['abscissa_um'] is not None:raise ValueError('Unbound motor has invented bound measurements')
                else:
                    if motor['filament'] not in fiber_ids:raise ValueError('Unknown motor-bound filament')
                    vector(motor['force_pn'],planar=b['dimensionality']==2)
                    if type(motor['abscissa_um']) not in (int,float) or not math.isfinite(motor['abscissa_um']):raise ValueError('Invalid motor abscissa')
    sampling=b.get('display_sampling')
    if sampling is not None:
        if (not isinstance(sampling,dict) or sampling.get('schema')!='spindle_display_sampling.v1'
            or not isinstance(sampling.get('source_trajectory_sha256'),str)
            or len(sampling['source_trajectory_sha256'])!=64
            or any(c not in '0123456789abcdef' for c in sampling['source_trajectory_sha256'])
            or not isinstance(sampling.get('method'),str)
            or not isinstance(sampling.get('source_frame_counts'),list)
            or not isinstance(sampling.get('source_frame_indices'),list)
            or len(sampling['source_frame_counts'])!=len(runs)
            or len(sampling['source_frame_indices'])!=len(runs)):
            raise ValueError('Invalid display sampling manifest')
        for run,count,indices in zip(runs,sampling['source_frame_counts'],sampling['source_frame_indices']):
            if (type(count) is not int or not 1<=count<=2000 or not isinstance(indices,list)
                or len(indices)!=len(run['frames']) or not indices or indices[0]!=0 or indices[-1]!=count-1
                or any(type(n) is not int or not 0<=n<count or (i and n<=indices[i-1]) for i,n in enumerate(indices))):
                raise ValueError('Invalid source frame mapping')
    return b
