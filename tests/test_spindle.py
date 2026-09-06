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
    for field in ('time','poles','filaments'):
        assert b['runs'][0]['frames'][0][field]==b['runs'][1]['frames'][0][field]
    assert b['runs'][0]['frames'][0]['cortical_motors']==[]
    assert len(b['runs'][1]['frames'][0]['cortical_motors'])==8
    # A native placement regression previously left fixed motors at the origin.
    from dnhacksbio.spindle.cytosim import export_run
    run_dir=store.root/'runs'/receipt/'41-1'
    anchors=run_dir/'motor-anchors.txt'
    lines=anchors.read_text().splitlines()
    for i,line in enumerate(lines):
        if line.strip() and not line.lstrip().startswith('%'):
            row=line.split();row[2:5]=['0','0','0'];lines[i]=' '.join(row);break
    anchors.write_text('\n'.join(lines)+'\n')
    with pytest.raises(ValueError,match='prescribed surface'):
        export_run(run_dir,protocol(),protocol()['conditions'][1],41)

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


def spindle_scene(tmp_path):
    from dnhacksbio.spindle.scenes import SceneService
    from dnhacksbio.spindle.protocol import canonical
    j=Journal(tmp_path);scope={'project_id':'p','run_id':'r','experiment_id':'e'}
    j.register('r','Spindle review',project='p');j.append('r','a','attempt.started',{'original_question':'Spindle review'})
    j.append('r','a','experiment.queued',{'title':'Spindle review'},experiment_id='e')
    raw=canonical(bundle());key=j.store_bytes(raw)
    j.append('r','a','artifact',{'artifact_id':'spindle','kind':'filament_trajectory','status':'available','sha256':key,'storage_key':key},experiment_id='e',producer='collector')
    return SceneService(j,scope),key


def spindle_renderer(request):
    import struct,zlib
    def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data))
    png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',320,320,8,2,0,0,0))+chunk(b'IDAT',zlib.compress((b'\0'+b'\0'*960)*320))+chunk(b'IEND',b'')
    view=request['recipe']['view'];frame=request['bundle']['runs'][view['run']]['frames'][view['frame']]
    return {'png':png,'state':{**view,'camera':view['camera'] or {'position':[0,0,30],'target':[0,0,0],'fov':40,'near':.1,'far':300},
        'physical_time_s':frame['time'],'poles':frame['poles'],'viewport':{'width':320,'height':320,'dpr':1},
        'physical_to_scene':{'units':'um','scale':1,'interpolation':'none'},'bundle_sha256':request['recipe']['bundle_sha256']}}


def test_scene_scoping_revisions_pixels_and_saved_time(tmp_path,monkeypatch):
    import asyncio
    from dnhacksbio.spindle.scenes import SceneService
    service,key=spindle_scene(tmp_path);first=service.open_scene(key)
    second=service.set_scene_view(first['recipe_sha256'],{'frame':2,'selected':'0'},note='Inspect stable two-pole interval')
    with pytest.raises(ValueError,match='obsolete'):service.capture_scene(first['recipe_sha256'],spindle_renderer)
    with pytest.raises(FileNotFoundError):SceneService(service.journal,{**service.scope,'experiment_id':'other'}).open_scene(key)
    captured=service.capture_scene(second['recipe_sha256'],spindle_renderer)
    with pytest.raises(FileNotFoundError):service.read_capture(captured['capture_id'],first['sequence'])
    async def pixels(prompt,**kwargs):
        assert kwargs['images']==[service.journal.read_blob(captured['image_sha256'])]
        return 'Test transport received the PNG; test does not certify visual quality.'
    monkeypatch.setattr('dnhacksbio.llm.acomplete',pixels)
    viewed=asyncio.run(service.inspect_scene_capture(captured['capture_id'],question='Are pole IDs readable?'))
    assert service.record_visual_review(viewed['review_sha256'],observed_defects=['Mock renderer'],changes=[],disposition='incomplete')['disposition']=='incomplete'
    def wrong(r):
        result=spindle_renderer(r);result['state']['physical_time_s']=100;return result
    with pytest.raises(ValueError,match='physical frame'):service.capture_scene(second['recipe_sha256'],wrong)
    with pytest.raises(ValueError):service.set_scene_view(second['recipe_sha256'],{'frame':999},note='Invalid future')


def test_runtime_collects_native_result_only_in_owning_experiment(tmp_path):
    # No native launch: completed archive receipt fixture tests publication and idempotency.
    from dnhacksbio.spindle.runtime import collect_job
    from dnhacksbio.spindle.jobs import SpindleStore
    from dnhacksbio.spindle.protocol import canonical
    service,_=spindle_scene(tmp_path/'journal');store=SpindleStore(tmp_path/'jobs');scope=service.scope
    receipt=store.run_spindle_experiment(protocol(),scope=scope,idempotency_key='collect',budget={'wall_seconds':30,'artifact_bytes':1000000})['receipt']
    with store.connect() as con:
        native=bundle();native.update(category='simulation',model_id=protocol()['model_id'])
        key=store._publish(con,receipt,'trajectory.json',canonical(native))
        metrics=store._publish(con,receipt,'metrics.json',b'{}')
        store._publish(con,receipt,'archive.json',canonical({'scope':scope,'files':{'trajectory.json':key,'metrics.json':metrics},'protocol':protocol(),'build':{'solver_commit':'fixture'},'spec_ref':'fixture'}))
        con.execute("UPDATE jobs SET state='completed' WHERE receipt=?",(receipt,))
    collect_job(service.journal,store,receipt,scope);n=len(service.history());collect_job(service.journal,store,receipt,scope)
    assert len(service.history())==n
    with pytest.raises(FileNotFoundError):collect_job(service.journal,store,receipt,{**scope,'experiment_id':'other'})


def test_runtime_launch_retry_does_not_create_an_orphan_job(tmp_path,monkeypatch):
    import asyncio
    from dnhacksbio.spindle.runtime import dispatch
    from dnhacksbio.spindle.jobs import SpindleStore
    service,_=spindle_scene(tmp_path)
    monkeypatch.setenv('SPINDLE_CYTOSIM_BIN','/operator/bin');monkeypatch.setenv('SPINDLE_CYTOSIM_BUILD','/operator/build.json')
    calls=[];monkeypatch.setattr('dnhacksbio.spindle.runtime.subprocess.Popen',lambda *a,**kw:calls.append(a))
    request={'operation':'run_spindle_experiment','experiment_id':'new','args':{'protocol':protocol(),'idempotency_key':'one','budget':{'wall_seconds':30,'artifact_bytes':1000000}}}
    first=asyncio.run(dispatch(service.journal,'p','r',request));second=asyncio.run(dispatch(service.journal,'p','r',request))
    assert first['receipt']==second['receipt'] and len(calls)==1
    request['args']['idempotency_key']='changed'
    with pytest.raises(ValueError,match='retry'):asyncio.run(dispatch(service.journal,'p','r',request))
    store=SpindleStore(service.journal.directory/'spindle-jobs')
    with store.connect() as con:assert con.execute('SELECT COUNT(*) FROM jobs').fetchone()[0]==1


def test_runtime_worker_preflight_failure_is_durable(tmp_path):
    from dnhacksbio.spindle.runtime import worker
    from dnhacksbio.spindle.jobs import SpindleStore
    service,_=spindle_scene(tmp_path/'journal');store=SpindleStore(service.journal.directory/'spindle-jobs')
    receipt=store.run_spindle_experiment(protocol(),scope=service.scope,idempotency_key='no-build',budget={'wall_seconds':1,'artifact_bytes':1000000})['receipt']
    path=tmp_path/'worker.json';path.write_text(json.dumps({'journal':str(service.journal.directory.parent),'scope':service.scope,
        'receipt':receipt,'sim':str(tmp_path/'sim'),'report':str(tmp_path/'report'),'build':str(tmp_path/'missing-build.json')}))
    worker(path)
    state=store.status(receipt,service.scope)
    assert state['state']=='failed' and 'preflight failed' in state['events'][-1]['reason']
    assert any(a['name']=='archive.json' for a in state['artifacts'])
    assert any(e['kind']=='experiment.finished' and e['payload']['status']=='failed' for e in service.history())


def test_pending_native_queue_is_bounded(tmp_path):
    from dnhacksbio.spindle.jobs import SpindleStore
    store=SpindleStore(tmp_path);scope={'project_id':'p','run_id':'r','experiment_id':'e'}
    for i in range(4):store.run_spindle_experiment(protocol(),scope=scope,idempotency_key=str(i),budget={'wall_seconds':1,'artifact_bytes':10000})
    with pytest.raises(ValueError,match='queue is full'):store.run_spindle_experiment(protocol(),scope=scope,idempotency_key='extra',budget={'wall_seconds':1,'artifact_bytes':10000})


def test_motor_fields_are_scoped_finite_and_lossless():
    from dnhacksbio.spindle.chunks import encode_frame,decode_frame
    b=bundle();f=b['runs'][0]['frames'][0]
    f['filaments']=[{'id':'f','pole':'0','points':[[0,0,0],[1,0,0]]}]
    f['cortical_motors']=[{'id':'m','position':[0,1,0],'filament':'f','force_pn':[.12345678901234567,0,0],'abscissa_um':.5}]
    validate(json.dumps(b).encode())
    metadata,raw=encode_frame(f)
    assert decode_frame(metadata,raw)==f
    f['cortical_motors'][0]['filament']='missing'
    with pytest.raises(ValueError,match='filament'):validate(json.dumps(b).encode())
    f['cortical_motors'][0]['filament']=None
    with pytest.raises(ValueError,match='Unbound'):validate(json.dumps(b).encode())


def test_failed_vision_cannot_create_a_visual_verdict(tmp_path,monkeypatch):
    import asyncio
    import dnhacksbio.llm
    service,key=spindle_scene(tmp_path)
    opened=service.open_scene(key)
    capture=service.capture_scene(opened['recipe_sha256'],spindle_renderer,viewport=[320,320])
    async def unavailable(*args,**kwargs):raise RuntimeError('Provider quota exhausted')
    monkeypatch.setattr(dnhacksbio.llm,'acomplete',unavailable)
    with pytest.raises(RuntimeError,match='no observation recorded'):
        asyncio.run(service.inspect_scene_capture(capture['capture_id'],question='Check visibility'))
    assert any(e['kind']=='scene.review.failed' for e in service.history())
    assert not any(e['kind']=='scene.review' for e in service.history())
