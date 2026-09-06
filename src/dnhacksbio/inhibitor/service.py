"""Experiment-scoped receipts and append-only scene actions shared by CLI/HTTP/Explorer."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from uuid import uuid4

from dnhacksbio.explorer.runtime import Journal, process_identity, process_namespace, safe_id
from .science import digest, encode, validate_spec
from .geometry import normalize, measure


@contextmanager
def lock(path):
    with open(path, 'a') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield


def atomic(path, value):
    temp = path.with_name(path.name+'.'+uuid4().hex+'.tmp')
    with open(temp,'wb') as f:
        f.write(encode(value)); f.flush(); os.fsync(f.fileno())
    os.replace(temp,path)


class Workbench:
    def __init__(self, journal: Journal, run: str, experiment: str, project: str | None, through=None):
        safe_id(experiment)
        self.j, self.run, self.experiment, self.project = journal, run, experiment, project
        self.manifest = journal.manifest(run,project)
        self.through = through
        self.directory = journal.directory/'inhibitor'

    def history(self):
        state = self.j.snapshot(self.manifest['investigation_id'],self.through)
        return [e for e in state['runs'].get(self.run,{}).get('history',[]) if e['experiment_id']==self.experiment]

    def event(self, kind, payload, actor='agent', event_id=None):
        if self.through is not None:
            raise ValueError('Playback is read-only')
        return self.j.append(self.run,'inhibitor',kind,{**payload,'actor':actor},experiment_id=self.experiment,
                             producer='collector' if kind=='artifact' else 'inhibitor',event_id=event_id)

    def source(self, key):
        event = next((e for e in self.history() if e['kind']=='artifact' and e['producer']=='collector'
                      and e['payload'].get('storage_key')==key and e['payload'].get('kind')=='molecular_structure'
                      and e['payload'].get('status')=='available'),None)
        if event is None:
            raise FileNotFoundError('Structure absent from this experiment at this cursor')
        return self.j.read_blob(key), event['payload']

    def attach(self, raw, name, kind, fmt, provenance):
        key = self.j.store_bytes(raw)
        artifact = {'artifact_id':key,'storage_key':key,'sha256':key,'name':name,'kind':kind,'format':fmt,
                    'status':'available','byte_length':len(raw),'provenance':provenance}
        self.event('artifact',artifact,event_id=f'inhibitor-artifact-{self.run}-{self.experiment}-{key}')
        return artifact

    def resolve(self, accession, actor, evidence):
        import requests
        if not re.fullmatch(r'[0-9][A-Za-z0-9]{3}',accession):
            raise ValueError('Provide a four-character PDB accession')
        accession = accession.upper()
        url = f'https://files.rcsb.org/download/{accession}.cif'
        response = requests.get(url,timeout=30,stream=True)
        response.raise_for_status()
        chunks, size = [], 0
        for chunk in response.iter_content(65536):
            size += len(chunk)
            if size > 20*1024*1024:
                raise ValueError('Structure download too large')
            chunks.append(chunk)
        raw = b''.join(chunks)
        geometry = normalize(raw,'cif')
        import gemmi
        block = gemmi.cif.read_string(raw.decode()).sole_block()
        if block.find_value('_entry.id').upper() != accession:
            raise ValueError('Retrieved accession mismatch')
        self.event('experiment.queued',{'title':f'{accession} inhibitor investigation','method':'exploratory structure/docking','status':'completed'},actor)
        artifact = self.attach(raw,accession+'.cif','molecular_structure','cif',
                              {'category':'experimental_reference','source_ids':[f'PDB:{accession}',*evidence],
                               'tool':'RCSB','tool_version':'mmCIF','retrieved_at':time.time(), 'url':url,
                               'revision':block.get_mmcif_category('_pdbx_audit_revision_history.'),
                               'construct':block.get_mmcif_category('_entity_poly.'),
                               'sequence_differences':block.get_mmcif_category('_struct_ref_seq_dif.')})
        return {'artifact':artifact,'atom_count':len(geometry['atoms']), 'residues':geometry['residues']}

    def jobs(self):
        result=[]
        for e in self.history():
            if e['kind']!='inhibitor.job':
                continue
            receipt = e['payload']
            p = self.directory/'jobs'/receipt['job_id']/'receipt.json'
            if self.through is None and p.exists():
                receipt=json.loads(p.read_text())
                identity=receipt.get('worker_identity')
                if receipt['status'] in ('queued','running') and identity and identity.split('|')[1]==process_namespace() and process_identity(receipt['pid'])!=identity:
                    receipt={**receipt,'status':'interrupted','error':'Worker exited before committing a complete result'}
                if receipt['status'] in ('queued','running') and time.time()>receipt['created_at']+receipt['spec']['timeout_s']+60:
                    receipt={**receipt,'status':'interrupted','error':'No terminal receipt within the declared budget and publication grace period'}
                progress=p.with_name('progress.json')
                if progress.exists(): receipt={**receipt,'progress':json.loads(progress.read_text())}
            result.append(receipt)
        # The runtime contains immutable receipt events; newest per job wins at playback cursor.
        return list({r['job_id']:r for r in result}.values())

    def start(self,key,spec,actor,idempotency_key):
        raw, artifact = self.source(key)
        if artifact['format']!='cif':
            raise ValueError('Docking preparation requires deposited mmCIF with ligand chemical dictionary')
        validate_spec(spec)
        if not isinstance(idempotency_key,str) or not 1<=len(idempotency_key)<=128:
            raise ValueError('idempotency_key required (1–128 characters)')
        self.directory.mkdir(exist_ok=True)
        request = {'run':self.run,'experiment':self.experiment,'project':self.project,'source_hash':key,'spec':spec}
        job_id=digest(encode({'scope':[self.run,self.experiment,self.project], 'idempotency_key':idempotency_key}))
        directory=self.directory/'jobs'/job_id
        directory.mkdir(parents=True,exist_ok=True)
        with lock(self.directory/'admission.lock'),lock(directory/'lock'):
            receipt_path=directory/'receipt.json'
            if receipt_path.exists():
                receipt=json.loads(receipt_path.read_text())
                if receipt['request_hash']!=digest(encode(request)):
                    raise ValueError('Idempotency key already bound to different inputs')
                return receipt
            if sum(r['status'] in ('queued','running') for r in self.jobs())>=4:
                raise ValueError('At most four pending jobs per experiment; wait or cancel before submitting more')
            receipt={**request,'job_id':job_id,'request_hash':digest(encode(request)),'status':'queued','actor':actor,'created_at':time.time()}
            atomic(receipt_path,receipt)
            self.event('inhibitor.job',receipt,actor)
            # Trusted fixed worker entrypoint; user input never becomes executable code.
            env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'}
            log=open(directory/'worker.log','ab')
            try:
                from dnhacksbio.webui.deployment import lease
                with lease() as fd:
                    if fd is not None: env['DNHACKS_INHIBITOR_LEASE_FD']=str(fd)
                    proc=subprocess.Popen([sys.executable,'-m','dnhacksbio.inhibitor.worker',
                                           str(self.j.directory.parent),job_id],stdout=log,stderr=log,env=env,start_new_session=True,
                                          pass_fds=() if fd is None else (fd,))
            except Exception as exc:
                receipt.update(status='failed',error=f'Worker admission failed: {type(exc).__name__}',finished_at=time.time())
                atomic(receipt_path,receipt)
                self.event('inhibitor.job',receipt,actor)
                raise
            finally:
                log.close()
            receipt.update(pid=proc.pid,worker_identity=process_identity(proc.pid))
            atomic(receipt_path,receipt)
            return receipt

    def cancel(self,job_id,actor):
        if not any(j['job_id']==job_id for j in self.jobs()):
            raise FileNotFoundError('Job outside experiment')
        p=self.directory/'jobs'/job_id
        atomic(p/'cancel.json',{'requested_at':time.time(),'actor':actor})
        return {'status':'cancellation_requested','job_id':job_id}

    def bundles(self):
        return [e['payload'] for e in self.history() if e['kind']=='artifact' and e['producer']=='collector'
                and e['payload'].get('kind')=='inhibitor_bundle']

    def bundle(self,key):
        if not any(b['storage_key']==key for b in self.bundles()):
            raise FileNotFoundError('Bundle outside experiment/cursor')
        return json.loads(self.j.read_blob(key))

    def scenes(self,key):
        self.source(key)
        return [{'sequence':e['sequence'],'recorded_at':e['recorded_at'],**e['payload']} for e in self.history()
                if e['kind']=='scene.changed' and e['payload'].get('source_hash')==key]

    def scene(self,key,patch,expected_revision,actor,note=''):
        raw,artifact=self.source(key)
        geometry=normalize(raw,artifact['format'],key)
        self.directory.mkdir(exist_ok=True)
        with lock(self.directory/'scene.lock'):
            scenes=self.scenes(key)
            own=[s for s in scenes if s['actor']==actor]
            current=own[-1]['recipe'] if own else {'schema_version':1,'source_hash':key,'revision':0,'style':'matte','shot':'pocket',
                 'ligand':next((r['id'] for r in sorted(geometry['residues'],key=lambda r:-len(r['atoms'])) if r['kind']=='ligand'),''),
                 'model':0,'clip':False,'selected':[],'frame':0,'pose':'reference','compare':False,'prepared':False}
            if expected_revision!=current['revision']:
                raise ValueError('Stale scene revision')
            allowed={'style','shot','ligand','model','clip','selected','frame','pose','compare','prepared','camera','bundle','surface'}
            if not isinstance(patch,dict) or set(patch)-allowed:
                raise ValueError('Unknown scene fields')
            recipe={**current,**patch,'revision':current['revision']+1}
            if recipe.get('prepared'):
                recipe['pose']='reference'
            if recipe['style'] not in ('matte','luminous','measurement') or recipe['shot'] not in ('arrival','pocket','oblique'):
                raise ValueError('Unknown scene preset')
            if recipe['frame']!=0:
                raise ValueError('No trajectory attached; frame must be zero')
            if type(recipe['model']) is not int or not 0<=recipe['model']<geometry['model_count']:
                raise ValueError('Unknown model')
            if recipe['ligand'] and not any(r['id']==recipe['ligand'] for r in geometry['residues']):
                raise ValueError('Unknown residue')
            ids={a['id'] for a in geometry['atoms']}
            if recipe.get('bundle'):
                selected_bundle=self.bundle(recipe['bundle'])
                if selected_bundle['source_hash']!=key: raise ValueError('Bundle/source mismatch')
                ids.update(a['id'] for a in selected_bundle['docking_geometry']['atoms'])
            if not isinstance(recipe['selected'],list) or len(recipe['selected'])>3 or any(i not in ids for i in recipe['selected']):
                raise ValueError('Unknown atom selection')
            for boolean in ('clip','compare','prepared','surface'):
                if type(recipe.get(boolean,False)) is not bool:
                    raise ValueError('Scene flags must be booleans')
            if recipe.get('camera'):
                import math
                for k in ('position','target'):
                    v=recipe['camera'].get(k)
                    if not isinstance(v,list) or len(v)!=3 or any(type(x) not in (float,int) or not math.isfinite(x) or abs(x)>1e6 for x in v):
                        raise ValueError('Invalid camera vector')
                if math.dist(recipe['camera']['position'],recipe['camera']['target'])<.01:
                    raise ValueError('Camera is coincident with target')
            if recipe.get('bundle'):
                bundle=self.bundle(recipe['bundle'])
                if bundle['source_hash']!=key or recipe['pose'] not in {p['id'] for p in bundle['poses']+bundle['controls']}:
                    raise ValueError('Unknown pose or mismatched bundle')
                if recipe.get('surface') and not bundle.get('surface'):
                    raise ValueError('No scientific surface in this bundle')
            elif recipe['pose']!='reference' or recipe['prepared'] or recipe.get('surface'):
                raise ValueError('Pose/preparation requires completed bundle')
            if not recipe.get('camera') or ('shot' in patch and 'camera' not in patch):
                import math
                atoms=[a for a in geometry['atoms'] if a['model']==recipe['model']]
                focus=[a for a in atoms if a['residue_id']==recipe['ligand']]
                points=atoms if recipe['shot']=='arrival' else (focus or atoms)
                target=[sum(a['position'][i] for a in points)/len(points) for i in range(3)]
                dist=max(10,max(math.dist(a['position'],target) for a in atoms))*2.8 if recipe['shot']=='arrival' else 25
                offset=[.85,.38,.9] if recipe['shot']=='oblique' else [.2,.22,1.3]
                recipe['camera']={'target':target,'position':[v+offset[i]*dist for i,v in enumerate(target)]}
            event=self.event('scene.changed',{'source_hash':key,'recipe':recipe,'note':str(note)[:2000]},actor)
            return {'recipe':recipe,'sequence':event['sequence']}

    def measurement(self,key,ids,bundle_key=None,pose='reference'):
        raw,artifact=self.source(key)
        geometry=normalize(raw,artifact['format'],key)
        if bundle_key:
            bundle=self.bundle(bundle_key)
            if bundle['source_hash']!=key:
                raise ValueError('Bundle/source mismatch')
            chosen=next((p for p in bundle['poses']+bundle['controls'] if p['id']==pose),None)
            if chosen is None:
                raise ValueError('Unknown pose')
            geometry=bundle['docking_geometry']
            positions=dict(zip(bundle['ligand_atom_names'],chosen['positions']))
            for a in geometry['atoms']:
                if a['residue_id']==bundle['ligand_residue'] and a['name'] in positions:
                    a['position']=positions[a['name']]
        return {**measure(geometry,ids),'pose':pose,'bundle':bundle_key}

    def timeline(self, key):
        """Replay actual receipts; never expand a camera bookmark into invented actions."""
        self.source(key)
        recipes, captures, result = {}, {}, []
        for e in self.history():
            p, kind = e['payload'], e['kind']
            actor = p.get('actor', 'agent')
            if kind == 'scene.capture' and p.get('source_hash') == key:
                captures[p['image_hash']] = p
            relevant = p.get('source_hash') == key
            if kind in ('scene.vision', 'scene.review'):
                relevant = p.get('capture_id') in captures
            if not relevant or kind not in ('scene.changed', 'scene.capture', 'scene.measurement',
                                             'scene.vision', 'scene.review', 'inhibitor.job'):
                continue
            if kind == 'scene.changed':
                recipes[actor] = p['recipe']
                note = p.get('note') or 'Changed the scene'
            elif kind == 'scene.measurement':
                note = f"Measured {p['value']:.3f} {p['units']}"
            elif kind == 'scene.capture':
                note = 'Captured the rendered scene for inspection'
            elif kind == 'scene.vision':
                note = 'Inspected scene pixels'
            elif kind == 'scene.review':
                note = p.get('disposition') or 'Reviewed the visual evidence'
            else:
                note = 'Docking: ' + p['status']
            result.append({'sequence': e['sequence'], 'recorded_at': e['recorded_at'],
                           'actor': actor, 'kind': kind, 'note': note,
                           'recipe': recipes.get(actor), 'details': p})
        return result

    def describe(self,key=None):
        return {'run_id':self.run,'experiment_id':self.experiment,'project_id':self.project,
                'jobs':self.jobs(),'bundles':self.bundles(),'scenes':self.scenes(key) if key else [],
                'timeline':self.timeline(key) if key else [], 'readonly':self.through is not None}

    def compare(self,keys):
        if not isinstance(keys,list) or not 2<=len(keys)<=5 or len(set(keys))!=len(keys):
            raise ValueError('Compare 2–5 distinct completed bundle hashes')
        bundles=[self.bundle(key) for key in keys]
        def compatibility(b):
            spec={k:v for k,v in b['protocol']['spec'].items() if k not in ('seeds','timeout_s','rationale')}
            return {'source':b['source_hash'],'spec':spec,'versions':b['protocol']['versions'],'adapter':b['protocol']['adapter']}
        comparable=all(compatibility(b)==compatibility(bundles[0]) for b in bundles)
        return {'score_comparison_permitted':comparable,
                'exclusion':None if comparable else 'Source, preparation, scoring/search settings or versions differ; no pooled score ranking.',
                'results':[{'bundle':key,'protocol':b['protocol'],'recovery':b['report']['recovery'],
                            'scores':b['report']['scores'],'clusters':b['report'].get('pose_clusters',[])} for key,b in zip(keys,bundles)],
                'independent_units':'Computational sensitivity only; no biological replication'}

    def dispatch(self,args,actor='agent'):
        op=args.get('operation','describe')
        key=args.get('source_hash')
        if self.through is not None and op not in ('describe','bundle','compare'):
            raise ValueError('Playback is read-only')
        if op=='describe': return self.describe(key)
        if op=='resolve': return self.resolve(args['accession'],actor,args.get('evidence_refs',[]))
        if op=='dock': return self.start(key,args['spec'],actor,args['idempotency_key'])
        if op=='cancel': return self.cancel(args['job_id'],actor)
        if op=='set_scene_view': return self.scene(key,args['patch'],args['expected_revision'],actor,args.get('note',''))
        if op=='measure':
            if args.get('capture_id') and not any(e['kind']=='scene.capture' and e['payload']['image_hash']==args['capture_id'] and e['payload']['source_hash']==key and e['payload']['recipe'].get('pose','reference')==args.get('pose','reference') and e['payload']['recipe'].get('bundle')==args.get('bundle') for e in self.history()):
                raise ValueError('Measurement capture does not match this source, bundle and pose')
            value=self.measurement(key,args['atom_ids'],args.get('bundle'),args.get('pose','reference'))
            self.event('scene.measurement',{'source_hash':key,'capture_id':args.get('capture_id'),**value},actor)
            return value
        if op=='bundle': return self.bundle(args['bundle'])
        if op=='compare': return self.compare(args['bundles'])
        if op=='capture_scene':
            from .vision import capture
            return capture(self,key,args['expected_revision'],actor,args.get('viewport',[1600,1000]))
        if op=='record_visual_review':
            capture_id=args['capture_id']
            if not any(e['kind']=='scene.capture' and e['payload']['image_hash']==capture_id for e in self.history()):
                raise FileNotFoundError('Capture outside experiment')
            review={k:str(args.get(k,''))[:4000] for k in ('observations','changes','disposition')}
            if not review['observations']: raise ValueError('Image-grounded observations required')
            return self.event('scene.review',{'capture_id':capture_id,**review},actor)
        raise ValueError('Unknown inhibitor operation')
