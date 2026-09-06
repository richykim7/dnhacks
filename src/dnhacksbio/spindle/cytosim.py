"""Pinned Cytosim configuration and checked frame/ownership export.

This new 3D model uses stock objects. Symmetric minus-end crosslinkers are a
provisional motor hypothesis, not a calibrated HSET molecule or paper-57 reproduction.
"""
from __future__ import annotations
import math
import re
from pathlib import Path
from .protocol import validate_protocol


def cortical_positions(radius,condition):
    positions=[]
    for i in range(condition['cortical_motors']):
        z=1-2*(i+.5)/condition['cortical_motors'];a=i*math.pi*(3-math.sqrt(5))
        direction=[math.sqrt(1-z*z)*math.cos(a),math.sqrt(1-z*z)*math.sin(a),z]
        if condition['localization']=='positive_x_crescent':
            direction[0]=abs(direction[0])+1
            norm=math.sqrt(sum(x*x for x in direction));direction=[x/norm for x in direction]
        positions.append([x*r for x,r in zip(direction,radius)])
    return positions


def configuration(protocol: dict, condition: dict, seed: int) -> str:
    p=validate_protocol(protocol)
    if condition not in p['conditions'] or seed not in p['seeds']:
        raise ValueError('Run not in frozen protocol')
    v={k:x['value'] for k,x in p['parameters'].items()}
    def block(command, fields):
        return command+'\n{\n'+''.join(f'    {k} = {value}\n' for k,value in fields.items())+'}\n\n'
    s=block('set simul system',{'time_step':v['time_step_s'],'viscosity':v['viscosity_pn_s_um2'],'random_seed':seed,'kT':v['thermal_energy_pn_um']})
    s+=block('set space cell',{'shape':'ellipse'})
    s+=block('new cell',{'diameter':', '.join(str(2*r) for r in p['radius_um'])})
    s+=block('set fiber microtubule',{
        'rigidity':v['fiber_rigidity_pn_um2'],'segmentation':v['segmentation_um'],
        'confine':f"inside, {v['confine_stiffness_pn_um']}, cell",'activity':'classic',
        'growing_speed':v['growth_um_s'],'growing_force':v['growth_force_pn'],
        'shrinking_speed':-v['shrink_um_s'],'catastrophe_rate':v['catastrophe_s_inv'],
        'rescue_rate':v['rescue_s_inv'],'min_length':v['initial_length_um'],'persistent':0})
    s+=block('set solid core',{})
    fiber_spec=f"( plus_end=grow; length={v['initial_length_um']}; )"
    s+=block('set aster star',{'stiffness':f"{v['aster_stiffness_pn_um']}, {v['aster_stiffness_pn_um']}",
                             'nucleate':f"{v['nucleation_s_inv']}, microtubule, {fiber_spec}"})
    for pos in condition['initial_positions_um']:
        s+=block('new star',{'solid':'core','radius':v['core_radius_um'],
                            'point1':f"center, {v['core_radius_um']}",
                            'fibers':f"{condition['fibers_per_aster']}, microtubule, {fiber_spec}",
                            'position':' '.join(map(str,pos))})
    s+=block('set hand minus_motor',{'binding_rate':v['motor_binding_s_inv'],
        'binding_range':v['motor_range_um'],'unbinding_rate':v['motor_unbinding_s_inv'],
        'unbinding_force':v['motor_unbinding_force_pn'],'activity':'move',
        'unloaded_speed':v['motor_speed_um_s'],'stall_force':v['motor_stall_pn']})
    s+=block('set single cortical',{'hand':'minus_motor','stiffness':v['motor_stiffness_pn_um'],'activity':'fixed'})
    # Explicit equal-area unit-sphere directions mapped to ellipsoid; this is NOT
    # uniform ellipsoid surface-area density. Record the placement semantics.
    for pos in cortical_positions(p['radius_um'],condition):
        s+=block('new cortical',{'position':' '.join(f'{x:.17g}' for x in pos),'placement':'anywhere'})
    s+=block('set couple crosslink',{'hand1':'minus_motor','hand2':'minus_motor',
        'stiffness':v['motor_stiffness_pn_um'],'diffusion':v['crosslink_diffusion_um2_s'],'length':v['crosslink_length_um']})
    if condition['crosslink_motors']:
        s+=block(f"new {condition['crosslink_motors']} crosslink",{'position':'inside'})
    steps=round(v['duration_s']/v['time_step_s']);frames=round(v['duration_s']/v['sampling_interval_s'])
    s+=block(f'run {steps} system',{'nb_frames':frames})
    return s


def read_report(path: Path) -> dict[int,list[list[str]]]:
    frames={};frame=None
    for line in path.read_text().splitlines():
        line=line.strip()
        if line.startswith('% frame'):
            frame=int(line.split()[-1])
            if frame in frames:raise ValueError('Duplicate report frame')
            frames[frame]=[]
        elif line and not line.startswith('%'):
            if frame is None:raise ValueError('Report lacks frame boundary')
            row=line.split()
            try:
                if any(not math.isfinite(float(x)) for x in row):raise ValueError('Nonfinite report')
            except ValueError as exc:raise ValueError('Malformed solver report') from exc
            frames[frame].append(row)
    if not frames:raise ValueError('Empty solver report')
    return frames


def export_run(directory: Path, protocol: dict, condition: dict, seed: int) -> dict:
    asters=read_report(directory/'asters.txt');fibers=read_report(directory/'fibers.txt');owners=read_report(directory/'owners.txt')
    anchors=read_report(directory/'motor-anchors.txt');links=read_report(directory/'motor-links.txt')
    if set(anchors)!=set(asters) or set(links)!=set(asters):raise ValueError('Motor report frame mismatch')
    if set(asters)!=set(fibers) or set(asters)!=set(owners):raise ValueError('Solver reports have different frame boundaries')
    v={k:x['value'] for k,x in protocol['parameters'].items()}
    expected=1+round(v['duration_s']/v['sampling_interval_s'])
    if sorted(asters)!=list(range(expected)):raise ValueError('Incomplete trajectory; cannot invent final frame')
    times={}
    for name in ['asters.txt','fibers.txt','owners.txt','motor-anchors.txt','motor-links.txt']:
        text=(directory/name).read_text()
        observed=[float(x) for x in re.findall(r'% time ([+0-9.eE-]+)',text)]
        if len(observed)!=expected or any(not math.isclose(t,i*v['sampling_interval_s'],rel_tol=0,abs_tol=5.1e-7) for i,t in enumerate(observed)):
            raise ValueError('Recorded solver clock disagrees with prescribed sampling')
        times[name]=observed
    if any(clock!=times['asters.txt'] for clock in times.values()):
        raise ValueError('Solver reports use different physical clocks')
    result=[]
    for index in range(expected):
        poles=[]
        for row in asters[index]:
            if len(row)!=5:raise ValueError('Aster report must contain 3D coordinates')
            poles.append({'id':'C'+row[1],'position':list(map(float,row[2:5]))})
        owner_map={}
        for row in owners[index]:
            if len(row)!=13:raise ValueError('Unsupported fiber ownership report')
            owner_map[row[1]]='C'+row[-1]
        geometry={}
        for row in fibers[index]:
            if len(row)!=5:raise ValueError('Fiber report must contain 3D coordinates and curvature')
            geometry.setdefault(row[0],[]).append(list(map(float,row[1:4])))
        ids={x['id'] for x in poles}
        if len(poles)!=len(condition['initial_positions_um']) or set(geometry)!=set(owner_map) or any(x not in ids for x in owner_map.values()):
            raise ValueError('Missing pole or unresolved exported filament ownership')
        attached={}
        for row in links[index]:
            if len(row)!=11 or row[1] in attached:raise ValueError('Invalid native bound motor report')
            attached[row[1]]={'force_pn':list(map(float,row[5:8])),'filament':'F'+row[8],'abscissa_um':float(row[9])}
        motors=[]
        prescribed=cortical_positions(protocol['radius_um'],condition)
        for row in anchors[index]:
            if len(row)!=7:raise ValueError('Invalid native motor anchor report')
            identity=int(row[1])
            if not 1<=identity<=len(prescribed) or math.dist(list(map(float,row[2:5])),prescribed[identity-1])>1e-5:
                raise ValueError('Native cortical anchor differs from prescribed surface position')
            binding=attached.pop(row[1],None)
            if (row[5]!='0') != (binding is not None):raise ValueError('Native motor binding state mismatch')
            if binding and (binding['filament']!='F'+row[5] or row[5] not in geometry):raise ValueError('Native motor filament mismatch')
            motors.append({'id':'M'+row[1],'position':list(map(float,row[2:5])),
                **(binding or {'force_pn':None,'filament':None,'abscissa_um':None})})
        if attached or len(motors)!=condition['cortical_motors']:raise ValueError('Missing native cortical motors')
        result.append({'time':times['asters.txt'][index],'poles':poles,'cortical_motors':motors,
            'filaments':[{'id':'F'+key,'pole':owner_map[key],'points':points} for key,points in geometry.items()]})
    return {'seed':seed,'condition':condition['name'],'frames':result}
