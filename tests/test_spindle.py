import copy
import json
import pytest
from dnhacksbio.spindle.bundle import validate
from dnhacksbio.spindle.analysis import analyze_run, analyze_ensemble
from dnhacksbio.explorer.artifacts import collect
from dnhacksbio.explorer.runtime import Journal


def bundle():
    frames = [{'time':t,'poles':[{'id':str(i),'position':p} for i,p in enumerate(points)],'filaments':[]} for t,points in [
        (0, [[-5,0,0],[0,5,0],[5,0,0]]),
        (1, [[-5,0,0],[-4.5,0,0],[5,0,0]]),
        (3, [[-5,0,0],[-4.5,0,0],[5,0,0]]),
        (5, [[0,0,0],[.5,0,0],[.9,0,0]])]]
    return dict(schema_version=1,dimensionality=3,category='illustration',model_id='test',units={'length':'um','time':'s'},radius=[10,10,10],runs=[dict(seed=1,condition='control',frames=frames)])


def test_clustering_dwell_censoring_and_single_collapse():
    b=bundle();validate(json.dumps(b).encode())
    r=analyze_run(b['runs'][0],1,2)
    assert r['pole_counts']==[3,2,2,1]
    assert r['time_to_bipolar_s']==1 and r['bipolar_dwell_s']==2
    assert not r['right_censored']
    censored=analyze_run(b['runs'][0],1,3)
    assert censored['right_censored'] and censored['time_to_bipolar_s'] is None
    report=analyze_ensemble(b,dict(threshold_um=1,dwell_s=2,sensitivity_thresholds_um=[.1,2]))
    assert report['conditions']['control']['simulation_replicates']==1
    assert report['conditions']['control']['replicate_sd_s'] is None
    assert report['threshold_sensitivity']['0.1']==[3]


@pytest.mark.parametrize('mutate',[
    lambda b:b.update(dimensionality=True),
    lambda b:b['units'].update(length='nm'),
    lambda b:b['radius'].__setitem__(0,float('nan')),
    lambda b:b['runs'][0]['frames'][1].update(time=0),
    lambda b:b['runs'][0]['frames'][0]['poles'][1].update(id='0'),
    lambda b:b['runs'][0]['frames'][0].update(filaments=[{'id':'f','pole':'missing','points':[[0,0,0],[1,0,0]]}]),
    lambda b:b['runs'].append(copy.deepcopy(b['runs'][0])),
])
def test_invalid_geometry_and_identity(mutate):
    b=bundle();mutate(b)
    with pytest.raises(ValueError):validate(json.dumps(b).encode())


def test_planar_means_planar():
    b=bundle();b['dimensionality']=2
    validate(json.dumps(b).encode())
    b['runs'][0]['frames'][0]['poles'][0]['position'][2]=.1
    with pytest.raises(ValueError):validate(json.dumps(b).encode())


def test_collector_immutable_geometry_and_provenance(tmp_path):
    output=tmp_path/'output';output.mkdir();journal=Journal(tmp_path/'journal')
    raw=json.dumps(bundle()).encode();(output/'spindle.json').write_bytes(raw)
    entry=dict(kind='filament_trajectory',format='json',path='spindle.json',provenance=dict(category='illustration',source_ids=[],tool='fixture',tool_version='1'))
    (output/'manifest.json').write_text(json.dumps(dict(schema_version=1,artifacts=[entry])))
    artifact=collect(output,journal)[0]
    assert artifact['status']=='available'
    assert journal.read_blob(artifact['storage_key'])==raw
    entry['provenance']['category']='prediction'
    (output/'manifest.json').write_text(json.dumps(dict(schema_version=1,artifacts=[entry])))
    assert collect(output,journal)[0]['status']=='rejected'
    (output/'spindle.json').unlink();(output/'spindle.json').symlink_to(tmp_path/'outside')
    assert collect(output,journal)[0]['status']=='rejected'


def protocol():
    from dnhacksbio.spindle.protocol import CYTOSIM_COMMIT,PARAMETERS
    # Upstream tutorial-scale engineering fixture, never a calibrated PDAC preset.
    values={'thermal_energy_pn_um':.0042,'crosslink_diffusion_um2_s':0,'crosslink_length_um':0,'time_step_s':.001,'duration_s':.02,'sampling_interval_s':.01,
        'viscosity_pn_s_um2':.01,'fiber_rigidity_pn_um2':20,'segmentation_um':.5,
        'confine_stiffness_pn_um':100,'core_radius_um':.25,'aster_stiffness_pn_um':500,
        'initial_length_um':1,'growth_um_s':.5,'shrink_um_s':.85,'catastrophe_s_inv':.1,
        'rescue_s_inv':0,'growth_force_pn':1.67,'nucleation_s_inv':1,
        'motor_binding_s_inv':5,'motor_range_um':.02,'motor_unbinding_s_inv':.5,
        'motor_unbinding_force_pn':2,'motor_speed_um_s':-1,'motor_stall_pn':5,'motor_stiffness_pn_um':100}
    assert set(values)==set(PARAMETERS)
    condition={'name':'control','initial_positions_um':[[-2,0,0],[2,0,0]],'fibers_per_aster':4,
               'cortical_motors':0,'crosslink_motors':0,'localization':'uniform'}
    return {'schema':'spindle_protocol.v1','model_id':'cytosim-3d-aster-v1','solver_commit':CYTOSIM_COMMIT,
        'dimensionality':3,'units':{'length':'um','time':'s','force':'pN'},'radius_um':[5,5,5],
        'parameters':{k:{'value':v,'source':'upstream cym/aster_dynamic.cym engineering fixture; explicit testing assumption','status':'assumed'} for k,v in values.items()},
        'seeds':[41],'conditions':[condition,{**condition,'name':'cortical','cortical_motors':8}],
        'analysis_plan':{'threshold_um':1,'dwell_s':.01,'sensitivity_thresholds_um':[.5,2]},
        'source_ids':['https://gitlab.com/f-nedelec/cytosim'], 'scientific_status':'provisional_uncalibrated'}


def test_frozen_protocol_and_deterministic_native_config():
    from dnhacksbio.spindle.protocol import prepare_spindle_experiment
    from dnhacksbio.spindle.cytosim import configuration
    p=protocol();prepared=prepare_spindle_experiment(p)
    assert prepared['estimate']['frames_per_replicate']==3
    assert configuration(p,p['conditions'][0],41)==configuration(p,p['conditions'][0],41)
    changed=copy.deepcopy(p);changed['analysis_plan']['threshold_um']=2
    assert prepare_spindle_experiment(changed)['spec_ref']!=prepared['spec_ref']
    p['parameters']['time_step_s']['value']=.003
    with pytest.raises(ValueError):prepare_spindle_experiment(p)


def test_job_receipt_idempotency_scope_cancel_and_corruption(tmp_path):
    from dnhacksbio.spindle.jobs import SpindleStore
    store=SpindleStore(tmp_path/'jobs');scope={'project_id':'p','run_id':'r','experiment_id':'e'}
    args=dict(protocol=protocol(),scope=scope,idempotency_key='x',budget={'wall_seconds':30,'artifact_bytes':1000000})
    receipt=store.run_spindle_experiment(**args)['receipt']
    assert store.run_spindle_experiment(**args)['receipt']==receipt
    with pytest.raises(FileNotFoundError):store.status(receipt,{**scope,'experiment_id':'other'})
    changed=copy.deepcopy(args);changed['protocol']['seeds']=[42]
    with pytest.raises(ValueError):store.run_spindle_experiment(**changed)
    assert store.cancel(receipt,scope)['state']=='canceled'
    assert store.status(receipt,scope)['state']=='canceled'
    with store.connect() as con:key=store._publish(con,receipt,'test',b'scientific bytes')
    assert store.read_blob(receipt,scope,key)==b'scientific bytes'
    (store.root/'blobs'/key).write_bytes(b'corrupt')
    with pytest.raises(ValueError):store.read_blob(receipt,scope,key)


def test_real_cytosim_pilot_when_operator_build_available(tmp_path):
    import os
    from pathlib import Path
    from dnhacksbio.spindle.protocol import CYTOSIM_COMMIT,digest
    from dnhacksbio.spindle.jobs import SpindleStore
    binary=os.environ.get('SPINDLE_CYTOSIM_BIN')
    if not binary:pytest.skip('Operator-pinned Cytosim CPU build not configured')
    sim=Path(binary)/'sim';report=Path(binary)/'report'
    build={'solver_commit':CYTOSIM_COMMIT,'dimensionality':3,'sim_sha256':digest(sim.read_bytes()),'report_sha256':digest(report.read_bytes())}
    store=SpindleStore(tmp_path/'jobs');scope={'project_id':'p','run_id':'r','experiment_id':'e'}
    receipt=store.run_spindle_experiment(protocol(),scope=scope,idempotency_key='pilot',budget={'wall_seconds':30,'artifact_bytes':1000000})['receipt']
    result=store.execute(receipt,scope,sim=sim,report=report,build_manifest=build)
    assert result['state']=='completed',result
    entry=next(a for a in result['artifacts'] if a['name']=='trajectory.json')
    b=validate(store.read_blob(receipt,scope,entry['hash']))
    assert len(b['runs'])==2
    assert b['runs'][0]['frames'][0]==b['runs'][1]['frames'][0]
    assert any(p['position'][2]!=0 for p in b['runs'][0]['frames'][-1]['poles'])
    with pytest.raises(ValueError):store.execute(receipt,scope,sim=sim,report=report,build_manifest=build)


def test_lossless_chunks_preserve_coordinates_and_reject_corruption():
    from dnhacksbio.spindle.chunks import encode_frame,decode_frame
    frame=bundle()['runs'][0]['frames'][0]
    frame['filaments']=[{'id':'f1','pole':'0','points':[[.12345678901234567,-2,0],[1,0,3.141592653589793]]}]
    metadata,raw=encode_frame(frame)
    assert decode_frame(metadata,raw)==frame
    with pytest.raises(ValueError):decode_frame(metadata,raw[:-1]+b'x')
    broken=copy.deepcopy(metadata);broken['filaments'][0]['offset']=100000
    with pytest.raises(ValueError):decode_frame(broken,raw)


def test_worker_failure_preserves_a_durable_receipt(tmp_path):
    from pathlib import Path
    from dnhacksbio.spindle.protocol import CYTOSIM_COMMIT,digest
    from dnhacksbio.spindle.jobs import SpindleStore
    sim=(tmp_path/'failing-sim');sim.write_text('#!/bin/sh\nexit 7\n');sim.chmod(0o700)
    build={'solver_commit':CYTOSIM_COMMIT,'dimensionality':3,'sim_sha256':digest(sim.read_bytes()),'report_sha256':digest(sim.read_bytes())}
    store=SpindleStore(tmp_path/'jobs');scope={'project_id':'p','run_id':'r','experiment_id':'e'}
    receipt=store.run_spindle_experiment(protocol(),scope=scope,idempotency_key='fail',budget={'wall_seconds':2,'artifact_bytes':1000000})['receipt']
    result=store.execute(receipt,scope,sim=sim,report=sim,build_manifest=build)
    assert result['state']=='failed'
    assert 'exit 7' in result['events'][-1]['reason']
    assert any(a['name']=='archive.json' for a in result['artifacts'])


def test_worker_wall_limit_terminates_process_group(tmp_path):
    import time
    from dnhacksbio.spindle.protocol import CYTOSIM_COMMIT,digest
    from dnhacksbio.spindle.jobs import SpindleStore
    sim=tmp_path/'slow-sim';sim.write_text('#!/bin/sh\nsleep 60\n');sim.chmod(0o700)
    build={'solver_commit':CYTOSIM_COMMIT,'dimensionality':3,'sim_sha256':digest(sim.read_bytes()),'report_sha256':digest(sim.read_bytes())}
    store=SpindleStore(tmp_path/'jobs');scope={'project_id':'p','run_id':'r','experiment_id':'e'}
    receipt=store.run_spindle_experiment(protocol(),scope=scope,idempotency_key='slow',budget={'wall_seconds':1,'artifact_bytes':1000000})['receipt']
    start=time.monotonic();result=store.execute(receipt,scope,sim=sim,report=sim,build_manifest=build)
    assert result['state']=='resource_exhausted' and time.monotonic()-start<5


def test_running_job_cancellation_preserves_archive(tmp_path):
    import time
    from concurrent.futures import ThreadPoolExecutor
    from dnhacksbio.spindle.protocol import CYTOSIM_COMMIT,digest
    from dnhacksbio.spindle.jobs import SpindleStore
    sim=tmp_path/'slow-sim';sim.write_text('#!/bin/sh\nsleep 60\n');sim.chmod(0o700)
    build={'solver_commit':CYTOSIM_COMMIT,'dimensionality':3,'sim_sha256':digest(sim.read_bytes()),'report_sha256':digest(sim.read_bytes())}
    store=SpindleStore(tmp_path/'jobs');scope={'project_id':'p','run_id':'r','experiment_id':'e'}
    receipt=store.run_spindle_experiment(protocol(),scope=scope,idempotency_key='cancel',budget={'wall_seconds':10,'artifact_bytes':1000000})['receipt']
    with ThreadPoolExecutor(max_workers=1) as pool:
        result=pool.submit(store.execute,receipt,scope,sim=sim,report=sim,build_manifest=build)
        deadline=time.monotonic()+3
        while store.status(receipt,scope)['state']=='queued' and time.monotonic()<deadline:time.sleep(.01)
        store.cancel(receipt,scope)
        assert result.result(timeout=4)['state']=='canceled'
