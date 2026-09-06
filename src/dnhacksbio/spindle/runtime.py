"""Registered spindle actions bound to the current researcher and immutable journal."""
from __future__ import annotations
import asyncio
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

from .protocol import canonical, digest, prepare_spindle_experiment, scope_key
from .jobs import SpindleStore, TERMINAL
from .scenes import SceneService


def render_scene(request, *, journal, base_url=None):
    root=Path(__file__).resolve().parents[3]
    base_url=base_url or os.environ.get('SPINDLE_SCENE_BASE_URL','http://127.0.0.1:8765')
    from urllib.parse import urlsplit
    u=urlsplit(base_url)
    if u.scheme not in {'http','https'} or u.hostname not in {'localhost','127.0.0.1','::1'} or u.username or u.password:
        raise ValueError('Trusted local workspace URL required')
    with tempfile.TemporaryDirectory(prefix='spindle-capture-') as tmp:
        inp=Path(tmp)/'request.json';out=Path(tmp)/'capture.json'
        manifest=journal.manifest(request['recipe']['scope']['run_id'],request['recipe']['scope']['project_id'])
        inp.write_bytes(canonical({**request,'base_url':base_url,'investigation_id':manifest['investigation_id']}))
        process=subprocess.Popen(['node',str(root/'frontend/scripts/capture-spindle.mjs'),str(inp),str(out)],
            cwd=root/'frontend',stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,start_new_session=True)
        try:
            _,err=process.communicate(timeout=request['render_seconds']+10)
        except subprocess.TimeoutExpired:
            import signal
            os.killpg(process.pid,signal.SIGKILL);process.communicate();raise TimeoutError('Spindle browser capture timed out')
        if process.returncode:raise RuntimeError('Spindle capture failed: '+err.decode(errors='replace')[-1500:])
        if out.stat().st_size>12*1024*1024:raise ValueError('Capture exceeds transport budget')
        result=json.loads(out.read_bytes());result['png']=base64.b64decode(result['png'],validate=True)
        return result


def collect_job(journal,store,receipt,scope):
    status=store.status(receipt,scope)
    if status['state'] not in TERMINAL:return status
    manifest=journal.manifest(scope['run_id'],scope['project_id'])
    run=journal.snapshot(manifest['investigation_id'])['runs'][scope['run_id']]
    def append(kind,payload,tag,producer='runner'):
        return journal.append(scope['run_id'],run['attempt_id'],kind,payload,experiment_id=scope['experiment_id'],
            producer=producer,event_id='spindle-'+digest({'scope':scope,'receipt':receipt,'tag':tag}))
    if status['state']=='completed':
        archive_ref=next(a for a in status['artifacts'] if a['name']=='archive.json')
        archive=json.loads(store.read_blob(receipt,scope,archive_ref['hash']))
        if archive['scope']!=scope:raise ValueError('Native archive scope mismatch')
        raw=store.read_blob(receipt,scope,archive['files']['trajectory.json'])
        from .bundle import validate
        bundle=validate(raw)
        if bundle['category']!='simulation' or bundle['model_id']!=archive['protocol']['model_id']:
            raise ValueError('Native archive trajectory category/model mismatch')
        key=journal.store_bytes(raw)
        append('artifact',{'artifact_id':receipt,'kind':'filament_trajectory','format':'json','status':'available',
            'sha256':key,'storage_key':key,'byte_length':len(raw),'name':'spindle.json',
            'provenance':{'category':'derived_geometry','source_ids':archive['protocol']['source_ids'],
                'tool':'Cytosim','tool_version':archive['build']['solver_commit'],'spec_ref':archive['spec_ref']}},'trajectory','collector')
        metrics_raw=store.read_blob(receipt,scope,archive['files']['metrics.json'])
        metrics_key=journal.store_bytes(metrics_raw)
        append('artifact',{'artifact_id':receipt+'-metrics','kind':'spindle_metrics','format':'json','status':'available',
            'sha256':metrics_key,'storage_key':metrics_key,'byte_length':len(metrics_raw),'name':'Spindle ensemble metrics',
            'provenance':{'category':'derived_geometry','source_ids':archive['protocol']['source_ids'],'tool':'spindle.analysis','tool_version':'1'}},'metrics','collector')
    append('experiment.finished',{'status':status['state'],'exploratory':True,'spindle_receipt':receipt,
        'result':None,'summary':'Provisional mechanics; simulation seeds are not biological samples.'},'finished')
    return status


async def dispatch(journal,project_id,run_id,request,*,renderer=None):
    """No filesystem paths, executable names, or project/run overrides in agent arguments."""
    operation=request['operation'];args=dict(request.get('args',{}))
    if operation=='describe_model':
        from .protocol import describe_model
        return describe_model()
    if operation=='prepare_spindle_experiment':return prepare_spindle_experiment(**args)
    scope={'project_id':project_id,'run_id':run_id,'experiment_id':request['experiment_id']};scope_key(scope)
    store=SpindleStore(journal.directory/'spindle-jobs')
    manifest=journal.manifest(run_id,project_id)
    run=journal.snapshot(manifest['investigation_id'])['runs'].get(run_id,{})
    history=[e for e in run.get('history',[]) if e.get('experiment_id')==scope['experiment_id']]
    if operation=='run_spindle_experiment':
        idem=args['idempotency_key'];protocol=args['protocol'];budget=args['budget']
        prepared=prepare_spindle_experiment(protocol)
        # An experiment identity never changes its numerical hypothesis in place.
        previous=next((e['payload'] for e in history if e['kind']=='experiment.queued'),None)
        if previous and previous.get('spindle_spec_ref')!=prepared['spec_ref']:raise ValueError('New numerical hypothesis requires a new experiment ID')
        parent=request.get('parent_experiment_id')
        if parent and not any(e.get('experiment_id')==parent for e in run.get('history',[])):raise ValueError('Follow-up parent is not owned by this researcher')
        native=os.environ.get('SPINDLE_CYTOSIM_BIN');build=os.environ.get('SPINDLE_CYTOSIM_BUILD')
        if not native or not build:raise RuntimeError('Operator-pinned Cytosim build is not configured')
        if previous:
            with store.connect() as con:old=store._job(con,previous['spindle_receipt'],scope)
            if old['idem']!=idem or old['budget']!=canonical(budget).decode():raise ValueError('Existing experiment retry must keep idempotency key and budget')
            return {'receipt':old['receipt'],'spec_ref':old['spec_hash'],'state':old['state'],'experiment_id':scope['experiment_id']}
        receipt=store.run_spindle_experiment(protocol,scope=scope,idempotency_key=idem,budget=budget)
        journal.append(run_id,run['attempt_id'],'experiment.queued',{'title':args.get('title','Spindle ensemble')[:300],
            'method':'Cytosim 3D · provisional','method_id':'exploratory','spindle_spec_ref':prepared['spec_ref'],
            'spindle_receipt':receipt['receipt'],'parent_experiment_id':parent},experiment_id=scope['experiment_id'],
            event_id='spindle-queued-'+digest(scope))
        req={'journal':str(journal.directory.parent),'scope':scope,'receipt':receipt['receipt'],
             'sim':str(Path(native)/'sim'),'report':str(Path(native)/'report'),'build':build}
        path=store.root/(receipt['receipt']+'.worker.json')
        try:
            with path.open('xb') as out:out.write(canonical(req))
        except FileExistsError:
            return {**receipt,'experiment_id':scope['experiment_id']}
        try:
            process=subprocess.Popen([sys.executable,'-m','dnhacksbio.spindle.runtime',str(path)],
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
            if process is not None:
                from dnhacksbio.explorer.runtime import process_identity
                journal.append(run_id,run['attempt_id'],'spindle.worker.started',{'receipt':receipt['receipt'],'pid':process.pid,'process_identity':process_identity(process.pid)},experiment_id=scope['experiment_id'])
        except OSError:
            store.cancel(receipt['receipt'],scope);collect_job(journal,store,receipt['receipt'],scope);raise
        return {**receipt,'experiment_id':scope['experiment_id']}
    if not history:raise FileNotFoundError('Experiment is not owned by this researcher')
    if operation in {'status','cancel','analyze_spindle_ensemble'}:
        receipt=args['receipt']
        if operation=='cancel':store.cancel(receipt,scope)
        status=collect_job(journal,store,receipt,scope)
        if operation!='analyze_spindle_ensemble':return status
        if status['state']!='completed':raise ValueError('Complete ensemble required')
        archive=json.loads(store.read_blob(receipt,scope,next(a['hash'] for a in status['artifacts'] if a['name']=='archive.json')))
        if args['analysis_plan_ref']!=digest(archive['protocol']['analysis_plan']):raise ValueError('Frozen analysis plan hash required')
        return json.loads(store.read_blob(receipt,scope,archive['files']['metrics.json']))
    service=SceneService(journal,scope)
    if operation=='inspect_scene_capture':return await service.inspect_scene_capture(**args)
    if operation=='export_scene_movie':
        return await asyncio.to_thread(service.export_scene_movie,**args,renderer=renderer or (lambda r:render_scene(r,journal=journal)))
    if operation=='capture_scene':
        return await asyncio.to_thread(service.capture_scene,**args,renderer=renderer or (lambda r:render_scene(r,journal=journal)))
    if operation not in {'open_scene','set_scene_view','record_visual_review'}:raise ValueError('Unknown spindle operation')
    return getattr(service,operation)(**args)


def worker(path):
    from dnhacksbio.explorer.runtime import Journal
    request=json.loads(Path(path).read_bytes());journal=Journal(request['journal'])
    store=SpindleStore(journal.directory/'spindle-jobs')
    try:
        import fcntl
        with (store.root/'worker.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            store.execute(request['receipt'],request['scope'],sim=Path(request['sim']),report=Path(request['report']),
                build_manifest=json.loads(Path(request['build']).read_bytes()))
    except Exception as exc:
        # A preflight failure must not leave an eternally queued receipt. Already
        # claimed work is never stolen or silently restarted by this recovery.
        with store.connect() as con:
            job=store._job(con,request['receipt'],request['scope'])
            if job['state']=='queued':
                reason=f'Worker preflight failed: {type(exc).__name__}: {exc}'
                archive={'schema':'spindle_archive.v1','scope':request['scope'],'protocol':json.loads(job['spec']),
                    'spec_ref':job['spec_hash'],'state':'failed','reason':reason,'files':{},'execution':'not started'}
                key=store._publish(con,request['receipt'],'archive.json',canonical(archive))
                con.execute("UPDATE jobs SET state='failed',updated=? WHERE receipt=?",(time.time(),request['receipt']))
                store._event(con,request['receipt'],{'state':'failed','reason':reason,'archive_sha256':key})
            else:raise
    collect_job(journal,store,request['receipt'],request['scope'])

if __name__=='__main__':worker(sys.argv[1])
