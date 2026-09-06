"""Frozen, source-linked numerical protocols, separate from visual scene recipes."""
from __future__ import annotations
import hashlib
import json
import math
import re

CYTOSIM_COMMIT = '0780e265cb6a2bb3536c6f89d2143ba9bb016ff0'
# Numerical guardrails, not biological estimates or calibration intervals.
PARAMETERS = {
    'thermal_energy_pn_um': (0, .1), 'crosslink_diffusion_um2_s': (0,100),
    'crosslink_length_um': (0,1),
    'time_step_s': (1e-5, .02), 'duration_s': (.01, 600),
    'sampling_interval_s': (.001, 60), 'viscosity_pn_s_um2': (.001, 10),
    'fiber_rigidity_pn_um2': (.01, 100), 'segmentation_um': (.05, 2),
    'confine_stiffness_pn_um': (1, 1000), 'core_radius_um': (.05, 2),
    'aster_stiffness_pn_um': (1, 2000), 'initial_length_um': (.1, 10),
    'growth_um_s': (0, 5), 'shrink_um_s': (.001, 10),
    'catastrophe_s_inv': (0, 10), 'rescue_s_inv': (0, 10),
    'growth_force_pn': (.01, 50), 'nucleation_s_inv': (0, 10),
    'motor_binding_s_inv': (0, 100), 'motor_range_um': (.001, 1),
    'motor_unbinding_s_inv': (0, 100), 'motor_unbinding_force_pn': (.01, 50),
    'motor_speed_um_s': (-10, -.001), 'motor_stall_pn': (.01, 50),
    'motor_stiffness_pn_um': (.01, 1000),
}


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value) -> str:
    return hashlib.sha256(value if isinstance(value, bytes) else canonical(value)).hexdigest()


def scope_key(scope: dict) -> str:
    if (not isinstance(scope, dict) or set(scope) != {'project_id','run_id','experiment_id'}
        or any(not isinstance(v,str) or not 1 <= len(v) <= 160 for v in scope.values())):
        raise ValueError('Complete project/run/experiment scope required')
    return canonical(scope).decode()


def bounded(value, low, high):
    return type(value) in (int,float) and math.isfinite(value) and low <= value <= high


def validate_protocol(p: dict) -> dict:
    if not isinstance(p,dict) or p.get('schema') != 'spindle_protocol.v1':
        raise ValueError('Unsupported spindle protocol')
    if p.get('model_id') != 'cytosim-3d-aster-v1' or p.get('solver_commit') != CYTOSIM_COMMIT:
        raise ValueError('Unsupported solver/model version; planar reproduction is a separate model')
    if p.get('dimensionality') != 3 or p.get('units') != {'length':'um','time':'s','force':'pN'}:
        raise ValueError('Cytosim model requires explicit 3D and um/s/pN units')
    params = p.get('parameters',{})
    if set(params) != set(PARAMETERS):
        raise ValueError('Complete parameter set required')
    for name,(low,high) in PARAMETERS.items():
        parameter=params[name]
        if (not isinstance(parameter,dict) or set(parameter) != {'value','source','status'}
            or not bounded(parameter['value'],low,high)
            or parameter['status'] not in {'assumed','measured','fitted'}
            or not isinstance(parameter['source'],str) or not parameter['source'].strip()):
            raise ValueError(f'Invalid value/provenance for {name}')
    v={k:x['value'] for k,x in params.items()}
    steps=v['duration_s']/v['time_step_s'];sample=v['sampling_interval_s']/v['time_step_s']
    if (not math.isclose(steps,round(steps),abs_tol=1e-7) or not math.isclose(sample,round(sample),abs_tol=1e-7)
        or not 1 <= sample <= steps or int(round(steps)) % int(round(sample))):
        raise ValueError('Duration and sampling must divide into complete timesteps')
    if steps > 100_000 or steps/sample > 1000:
        raise ValueError('Pilot step/frame budget exceeded')
    radius=p.get('radius_um')
    if not isinstance(radius,list) or len(radius)!=3 or any(not bounded(x,2,50) for x in radius):
        raise ValueError('Invalid ellipsoid semiaxes')
    seeds=p.get('seeds')
    if (not isinstance(seeds,list) or not 1 <= len(seeds) <= 16
        or any(type(s) is not int or not 1 <= s < 2**31 for s in seeds) or len(set(seeds))!=len(seeds)):
        raise ValueError('Distinct explicit simulation seeds required')
    conditions=p.get('conditions')
    if not isinstance(conditions,list) or not 2 <= len(conditions) <= 4:
        raise ValueError('Two to four declared control/perturbation conditions required')
    names=set()
    for c in conditions:
        if not isinstance(c,dict) or set(c) != {'name','initial_positions_um','fibers_per_aster','cortical_motors','crosslink_motors','localization'}:
            raise ValueError('Invalid condition fields')
        if not isinstance(c['name'],str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',c['name']) or c['name'] in names:
            raise ValueError('Condition name must be unique')
        names.add(c['name'])
        points=c['initial_positions_um']
        if not isinstance(points,list) or not 2 <= len(points) <= 8:
            raise ValueError('Two to eight centrosomes required')
        for point in points:
            if (not isinstance(point,list) or len(point)!=3 or any(not bounded(x,-50,50) for x in point)
                or sum((x/r)**2 for x,r in zip(point,radius)) >= .8**2):
                raise ValueError('Initial centrosomes must be inside the cell with margin')
        if any(math.dist(a,b) < 2*v['core_radius_um'] for i,a in enumerate(points) for b in points[:i]):
            raise ValueError('Initial centrosome cores overlap')
        for key,cap in [('fibers_per_aster',128),('cortical_motors',1000),('crosslink_motors',1000)]:
            if type(c[key]) is not int or not (4 if key=='fibers_per_aster' else 0) <= c[key] <= cap:
                raise ValueError('Filament/motor count exceeds pilot budget')
        if c['localization'] not in {'uniform','positive_x_crescent'}:
            raise ValueError('Unsupported cortical localization')
    plan=p.get('analysis_plan',{})
    if (set(plan) != {'threshold_um','dwell_s','sensitivity_thresholds_um'}
        or not bounded(plan['threshold_um'],.01,10) or not bounded(plan['dwell_s'],v['sampling_interval_s'],v['duration_s'])
        or not isinstance(plan['sensitivity_thresholds_um'],list) or len(plan['sensitivity_thresholds_um'])>8
        or any(not bounded(x,.01,10) for x in plan['sensitivity_thresholds_um'])):
        raise ValueError('Freeze bounded clustering threshold, dwell and sensitivity before execution')
    if not isinstance(p.get('source_ids'),list) or not p['source_ids'] or any(not isinstance(x,str) or not x for x in p['source_ids']):
        raise ValueError('Model source references required')
    if p.get('scientific_status') != 'provisional_uncalibrated':
        raise ValueError('This adapter does not establish calibration or biological validity')
    canonical(p)
    return p


def prepare_spindle_experiment(protocol: dict) -> dict:
    p=validate_protocol(json.loads(canonical(protocol)))
    v={k:x['value'] for k,x in p['parameters'].items()}
    return {'protocol':p,'spec_ref':digest(p),'estimate':{
        'replicates':len(p['seeds'])*len(p['conditions']),
        'steps_per_replicate':round(v['duration_s']/v['time_step_s']),
        'frames_per_replicate':1+round(v['duration_s']/v['sampling_interval_s']),
        'wall_time':'unmeasured; enforced by declared worker budget'},'status':'prepared'}
