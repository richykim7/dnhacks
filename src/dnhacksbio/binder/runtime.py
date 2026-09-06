"""Scientist-facing binder actions bound to the current researcher and journal artifacts."""
from __future__ import annotations

import asyncio
import json
import os
import re

from .bundle import make_bundle, validate_bundle
from .geometry import canonical, define_interface, digest
from .jobs import DesignStore, plan_design
from .scenes import SceneService
from .tools import compare, prepare_target, propose_followup

FIELDS = {
    'prepare_target': {'source_ref','chains','source_evidence','construct_policy'},
    'define_interface': {'target_ref','selected','excluded','competition'},
    'plan_design': {'target_ref','epitope_ref','lengths','seeds','candidate_cap','gpu_seconds',
                    'trajectory_cap','artifact_bytes','environment_sha256','weights_sha256','filters_sha256','advanced_sha256'},
    'start_design': {'protocol_ref','idempotency_key'},
    'collect_candidates': {'receipt','after'}, 'cancel': {'receipt'}, 'recover': {'receipt'},
    'import_candidate': {'source_ref','target_chains','binder_chains','candidate_id','source_evidence','protocol_ref','surface_options'},
    'evaluate_interface': {'bundle_sha256'},
    'compare': {'bundle_sha256s'},
    'propose_followup': {'bundle_sha256s','question','evidence'},
    'open_scene': {'bundle_sha256','preset','through','note'},
    'set_scene_view': {'recipe_sha256','view','note'},
    'capture_scene': {'recipe_sha256','viewport','render_seconds'},
    'inspect_scene_capture': {'capture_id','question','through'},
    'pick': {'capture_id','recipe_sha256','x','y','through','render_seconds'},
}


class BinderRuntime:
    def __init__(self,journal,project_id,run_id,experiment_id):
        self.scope={'project_id':project_id,'run_id':run_id,'experiment_id':experiment_id}
        self.service=SceneService(journal,self.scope)
        self.journal=journal
        if not any(e['kind']=='experiment.queued' for e in self.service.history()):
            raise FileNotFoundError('Experiment is not owned by this researcher')

    def artifact(self,key,kind):
        event=next((e for e in self.service.history() if e['kind']=='artifact' and e['producer']=='collector'
                    and e['payload'].get('kind')==kind and e['payload'].get('status')=='available'
                    and e['payload'].get('sha256')==key),None)
        if event is None:raise FileNotFoundError('Artifact unavailable in this exact experiment scope')
        raw=self.journal.read_blob(key)
        if digest(raw)!=key:raise ValueError('Stored artifact hash mismatch')
        return raw,event['payload']

    def record(self,kind,data,sources):
        raw=canonical({'schema':kind+'.v1','scope':self.scope,'data':data})
        if len(raw)>20*1024*1024:raise ValueError('Binder record exceeds byte cap')
        key=self.journal.store_bytes(raw)
        self.service._append('artifact',{'artifact_id':'binder-'+key,'kind':kind,'format':'json','status':'available',
            'sha256':key,'storage_key':key,'byte_length':len(raw),'name':kind.replace('_',' '),
            'provenance':{'category':'derived_geometry','source_ids':sources,'tool':'binder.runtime','tool_version':'1'}},
            event_id='binder-record-'+digest({'scope':self.scope,'key':key}))
        return {'artifact_sha256':key,'kind':kind,'data':data,'status':'exploratory'}

    def data(self,key,kind):
        raw,_=self.artifact(key,kind);record=json.loads(raw)
        if record.get('schema')!=kind+'.v1' or record.get('scope')!=self.scope:
            raise ValueError('Binder record schema/scope mismatch')
        return record['data']

    def publish_bundle(self,raw,*,receipt=None,rejection_reason=None,mapping_review=None):
        bundle=validate_bundle(raw,self.scope);key=self.journal.store_bytes(raw)
        event_id='binder-candidate-'+digest({'scope':self.scope,'key':key,'receipt':receipt})
        self.service._append('artifact',{'artifact_id':event_id,'kind':'binder_bundle','format':'json','status':'available',
            'sha256':key,'storage_key':key,'byte_length':len(raw),'name':bundle['manifest']['candidate_id'],
            'atom_count':len(bundle['structure']['atoms']),'provenance':bundle['manifest']['provenance'],
            'design_receipt':receipt,'rejection_reason':rejection_reason,'mapping_review':mapping_review},event_id=event_id)
        return {'bundle_sha256':key,'candidate_id':bundle['manifest']['candidate_id'],'status':'exploratory'}

    def bundles(self,keys):
        if not isinstance(keys,list) or not 1<=len(keys)<=8 or len(set(keys))!=len(keys):
            raise ValueError('Choose 1–8 distinct available bundle hashes')
        return [self.service.bundle(key) for key in keys]

    def collect(self,store,receipt,after=0):
        result=store.collect_candidates(receipt,self.scope,after)
        for event in result['events']:
            if event.get('bundle_sha256'):
                key=event['bundle_sha256']
                if not isinstance(key,str) or not re.fullmatch('[a-f0-9]{64}',key):raise ValueError('Invalid stored candidate identity')
                raw=(store.root/key).read_bytes()
                if digest(raw)!=key:raise ValueError('Candidate store hash mismatch')
                self.publish_bundle(raw,receipt=receipt,rejection_reason=event.get('rejection_reason'),
                                    mapping_review=event.get('mapping_review'))
            self.service._append('binder.job',{'receipt':receipt,**event},
                event_id='binder-job-'+digest({'scope':self.scope,'receipt':receipt,'cursor':event['cursor']}))
        return result


async def dispatch(journal,project_id,run_id,request,*,renderer=None,usage_capture=None):
    """Agent arguments cannot choose host paths, executable names, stores or run/project scope."""
    if not isinstance(request,dict) or set(request)-{'operation','experiment_id','args'}:
        raise ValueError('Binder action requires operation, owned experiment_id and args')
    operation=request['operation'];args=request.get('args',{})
    if operation not in FIELDS or not isinstance(args,dict) or set(args)-FIELDS[operation]:
        raise ValueError('Unsupported binder operation or argument fields')
    args=dict(args);runtime=BinderRuntime(journal,project_id,run_id,request['experiment_id'])
    service=runtime.service
    if operation in {'prepare_target','import_candidate'}:
        source_ref=args.pop('source_ref');raw,artifact=runtime.artifact(source_ref,'molecular_structure')
        fmt=artifact.get('format')
        if operation=='prepare_target':
            target=await asyncio.to_thread(prepare_target,raw,fmt,structure_sha256=source_ref,**args)
            return runtime.record('binder_target',target,[source_ref])
        protocol_ref=args.pop('protocol_ref',None)
        if protocol_ref:args['protocol']=runtime.data(protocol_ref,'binder_protocol')['protocol']
        provenance={'category':artifact['provenance']['category'],'source_ids':[source_ref],
                    'tool':'binder.import','tool_version':'1'}
        bundle=await asyncio.to_thread(make_bundle,raw,fmt,scope=runtime.scope,provenance=provenance,**args)
        return await asyncio.to_thread(runtime.publish_bundle,canonical(bundle))
    if operation=='define_interface':
        key=args.pop('target_ref');target=runtime.data(key,'binder_target')
        return runtime.record('binder_epitope',define_interface(target,**args),[key])
    if operation=='plan_design':
        target_ref=args.pop('target_ref');epitope_ref=args.pop('epitope_ref')
        target=runtime.data(target_ref,'binder_target');epitope=runtime.data(epitope_ref,'binder_epitope')
        protocol=plan_design(target,epitope,**args)
        return runtime.record('binder_protocol',{'protocol':protocol,'target_ref':target_ref,'epitope_ref':epitope_ref},
                              [target_ref,epitope_ref])
    if operation in {'start_design','collect_candidates','cancel','recover'}:
        store=DesignStore(journal.directory/'binder-jobs')
        if operation=='start_design':
            record=runtime.data(args['protocol_ref'],'binder_protocol')
            # Resolve each pinned input through the current owner's records before queuing.
            target=runtime.data(record['target_ref'],'binder_target');epitope=runtime.data(record['epitope_ref'],'binder_epitope')
            protocol=record['protocol']
            if digest(target)!=protocol['target_sha256'] or digest(epitope)!=protocol['epitope_sha256']:
                raise ValueError('Protocol input identity mismatch')
            receipt=store.start_design(protocol,scope=runtime.scope,idempotency_key=args['idempotency_key'])
            collected=runtime.collect(store,receipt['receipt'])
            return {**receipt,'state':collected['state'],
                    'execution':'This action never launches inference; queued receipts require an operator launch'}
        receipt=args['receipt']
        if operation in {'cancel','recover'}:getattr(store,operation)(receipt,runtime.scope)
        return await asyncio.to_thread(runtime.collect,store,receipt,args.get('after',0))
    if operation=='evaluate_interface':
        bundle=service.bundle(args['bundle_sha256'])
        return {'bundle_sha256':args['bundle_sha256'],'metrics':bundle['metrics'],'status':'exploratory'}
    if operation in {'compare','propose_followup'}:
        keys=args.pop('bundle_sha256s');bundles=runtime.bundles(keys)
        result=await asyncio.to_thread(compare,bundles) if operation=='compare' else propose_followup(bundles,**args)
        if operation=='compare':
            for row,key in zip(result['rows'],keys):row['bundle_sha256']=key
        return runtime.record('binder_comparison' if operation=='compare' else 'binder_followup',result,keys)
    if operation=='inspect_scene_capture':return await service.inspect_scene_capture(**args,usage_capture=usage_capture)
    if operation in {'capture_scene','pick'}:
        if renderer is None:
            from .render import browser_renderer
            renderer=browser_renderer(os.environ.get('BINDER_SCENE_BASE_URL','http://127.0.0.1:8765'),
                                      service.manifest['investigation_id'])
        return await asyncio.to_thread(getattr(service,operation),**args,renderer=renderer)
    return getattr(service,operation)(**args)
