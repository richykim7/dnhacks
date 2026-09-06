"""Immutable experiment-scoped scene actions, image captures and visual observations."""
from __future__ import annotations

import asyncio
import copy
import fcntl
import json
import math
import struct
from contextlib import contextmanager
from uuid import uuid4

from .bundle import validate
from .protocol import canonical, digest


def validate_view(view: dict, bundle: dict) -> dict:
    if not isinstance(view,dict) or set(view)-{'shot','treatment','selected','camera','run','frame','trails','compare'}:
        raise ValueError('Unsupported scene fields; scientific coordinates are read-only')
    result={'shot':'oblique','treatment':'luminous','selected':None,'camera':None,
            'run':0,'frame':0,'trails':True,'compare':None,**view}
    if result['shot'] not in {'front','oblique','detail'} or result['treatment'] not in {'luminous','fine'}:
        raise ValueError('Unsupported spindle composition')
    if type(result['trails']) is not bool:raise ValueError('Trails must be boolean')
    for name in ('run','compare'):
        value=result[name]
        if name=='compare' and value is None:continue
        if type(value) is not int or not 0<=value<len(bundle['runs']):raise ValueError('Unknown simulation replicate')
    frames=bundle['runs'][result['run']]['frames']
    if type(result['frame']) is not int or not 0<=result['frame']<len(frames):raise ValueError('Unknown saved physical frame')
    if result['selected'] is not None and result['selected'] not in {p['id'] for p in frames[result['frame']]['poles']}:
        raise ValueError('Unknown centrosome ID')
    c=result['camera']
    if c is not None:
        if not isinstance(c,dict) or set(c)-{'position','target','fov','near','far','up','quaternion','projection'}:
            raise ValueError('Unsupported camera')
        for key in ('position','target'):
            if not isinstance(c.get(key),list) or len(c[key])!=3 or any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>10000 for v in c[key]):
                raise ValueError('Finite camera position and target required')
        if math.dist(c['position'],c['target'])<.01:raise ValueError('Camera position equals target')
        for k,default,lo,hi in [('fov',40,15,80),('near',.1,.01,100),('far',300,1,10000)]:
            v=c.get(k,default)
            if type(v) not in (float,int) or not math.isfinite(v) or not lo<=v<=hi:raise ValueError('Invalid camera lens')
        if c.get('far',300)<=c.get('near',.1):raise ValueError('Invalid clipping interval')
        if c.get('projection','PerspectiveCamera')!='PerspectiveCamera':raise ValueError('Unsupported projection')
        if 'up' in c and c['up']!=[0,1,0]:raise ValueError('Only fixed world-up is supported')
        if 'quaternion' in c:
            q=c['quaternion']
            if not isinstance(q,list) or len(q)!=4 or any(type(v) not in (float,int) or not math.isfinite(v) for v in q):raise ValueError('Invalid quaternion')
    canonical(result)
    return result


def same_state(a,b):
    """Camera reconstruction may differ by floating-point roundoff, not a visible pose change."""
    if type(a) in (float,int) and type(b) in (float,int):
        return math.isfinite(a) and math.isfinite(b) and math.isclose(a,b,rel_tol=0,abs_tol=1e-8)
    if isinstance(a,dict) and isinstance(b,dict):
        return a.keys()==b.keys() and all(same_state(a[k],b[k]) for k in a)
    if isinstance(a,list) and isinstance(b,list):
        return len(a)==len(b) and all(same_state(x,y) for x,y in zip(a,b))
    return a==b


class SceneService:
    """Trusted local runtime service. No arbitrary shaders, remote URLs or source writes."""
    def __init__(self,journal,scope:dict):
        if set(scope)!={'project_id','run_id','experiment_id'} or any(not isinstance(v,str) or not v for v in scope.values()):
            raise ValueError('Complete scene experiment scope required')
        self.journal=journal;self.scope=dict(scope);self._bundles={}
        self.manifest=journal.manifest(scope['run_id'],scope['project_id'])

    @contextmanager
    def locked(self):
        with (self.journal.directory/'spindle-scenes.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            yield

    def history(self,through=None):
        run=self.journal.snapshot(self.manifest['investigation_id'],through)['runs'].get(self.scope['run_id'],{})
        return [e for e in run.get('history',[]) if e.get('experiment_id')==self.scope['experiment_id']]

    def bundle(self,key,through=None):
        if not any(e['kind']=='artifact' and e['producer']=='collector' and e['payload'].get('kind')=='filament_trajectory'
                   and e['payload'].get('status')=='available' and e['payload'].get('sha256')==key
                   for e in self.history(through)):
            raise FileNotFoundError('Spindle artifact unavailable in this experiment at this cursor')
        if key not in self._bundles:self._bundles[key]=validate(self.journal.read_blob(key))
        return copy.deepcopy(self._bundles[key])

    def _append(self,kind,payload,event_id=None):
        state=self.journal.snapshot(self.manifest['investigation_id'])
        run=state['runs'][self.scope['run_id']]
        return self.journal.append(self.scope['run_id'],run['attempt_id'],kind,payload,
                                   experiment_id=self.scope['experiment_id'],producer='collector' if kind=='artifact' else 'scene-service',
                                   event_id=event_id)

    def _recipe(self,key,through=None):
        for e in self.history(through):
            if e['kind']=='scene.recipe' and e['payload']['recipe']['sha256']==key:
                recipe=json.loads(self.journal.read_blob(key))
                if recipe['scope']!=self.scope or recipe.get('adapter')!='spindle@1':raise ValueError('Recipe scope mismatch')
                return recipe
        raise FileNotFoundError('Recipe unavailable at this cursor')

    def _latest(self,scene_id):
        return next((e['payload']['recipe']['sha256'] for e in reversed(self.history())
                     if e['kind']=='scene.recipe' and e['payload']['scene_id']==scene_id),None)

    def _save_recipe(self,recipe,note):
        if len([e for e in self.history() if e['kind']=='scene.recipe'])>=128:
            raise ValueError('Experiment scene action budget exhausted')
        raw=canonical(recipe);key=self.journal.store_bytes(raw)
        event=self._append('scene.recipe',{'scene_id':recipe['scene_id'],'bundle_sha256':recipe['bundle_sha256'],
                                         'view':recipe['view'],'note':note[:2000],'actor':'agent',
                                         'recipe':{'sha256':key,'storage_key':key,'byte_length':len(raw)}})
        return {'scene_id':recipe['scene_id'],'recipe_sha256':key,'sequence':event['sequence'],'view':recipe['view']}

    def open_scene(self,bundle_sha256,*,preset='oblique',through=None,note='Inspect saved spindle trajectory'):
        bundle=self.bundle(bundle_sha256,through)
        scene_id=digest({'scope':self.scope,'bundle_sha256':bundle_sha256,'adapter':'spindle@1'})
        with self.locked():
            old=self._latest(scene_id)
            if old:
                # Historical reads never silently return a future recipe.
                visible=[e for e in self.history(through) if e['kind']=='scene.recipe' and e['payload']['scene_id']==scene_id]
                if visible:
                    e=visible[-1];return {'scene_id':scene_id,'recipe_sha256':e['payload']['recipe']['sha256'],
                                          'sequence':e['sequence'],'view':e['payload']['view']}
                if through is not None:raise FileNotFoundError('Scene not opened at this historical cursor')
            if through is not None:raise FileNotFoundError('Scene not opened at this historical cursor')
            recipe={'schema':'scene_recipe.v1','adapter':'spindle@1','scene_id':scene_id,'scope':self.scope,
                    'bundle_sha256':bundle_sha256,'parent_recipe':None,'frame':0,
                    'timeline':'manual saved physical samples; scene actions are separate', 'interpolation':'none', 'coordinate_transform':{'units':'um','scale':1},
                    'view':validate_view({'shot':preset},bundle)}
            return self._save_recipe(recipe,note)

    def set_scene_view(self,recipe_sha256,view,*,note):
        if not isinstance(note,str) or not note.strip():raise ValueError('Concise scene action note required')
        with self.locked():
            old=self._recipe(recipe_sha256)
            if self._latest(old['scene_id'])!=recipe_sha256:raise ValueError('Stale scene recipe; refresh before changing view')
            if 'shot' in view and 'camera' not in view:view={**view,'camera':None}
            resolved=validate_view({**old['view'],**view},self.bundle(old['bundle_sha256']))
            recipe={**old,'view':resolved,'parent_recipe':recipe_sha256}
            return self._save_recipe(recipe,note)

    def capture_scene(self,recipe_sha256,renderer,*,viewport=(1600,1000),render_seconds=30):
        if len(viewport)!=2 or any(type(v) is not int for v in viewport) or not 320<=viewport[0]<=1920 or not 320<=viewport[1]<=1080:
            raise ValueError('Capture viewport outside bounds')
        if type(render_seconds) is not int or not 1<=render_seconds<=60:raise ValueError('Invalid render-time budget')
        recipe=self._recipe(recipe_sha256);bundle=self.bundle(recipe['bundle_sha256'])
        if self._latest(recipe['scene_id'])!=recipe_sha256:raise ValueError('Cannot capture obsolete scene revision')
        captures=[e for e in self.history() if e['kind']=='artifact' and e['payload'].get('kind')=='scene_capture']
        if len(captures)>=16:raise ValueError('Experiment capture quota exhausted')
        result=renderer({'recipe':recipe,'bundle':bundle,'viewport':list(viewport),'render_seconds':render_seconds})
        png=result['png'];state=result['state']
        if not isinstance(png,bytes) or not 33<=len(png)<=8*1024*1024 or png[:8]!=b'\x89PNG\r\n\x1a\n':
            raise ValueError('Renderer did not return bounded PNG bytes')
        width,height=struct.unpack('>II',png[16:24])
        if not 1<=width<=1920 or not 1<=height<=1080:raise ValueError('Rendered PNG dimensions exceed capture bounds')
        if state.get('bundle_sha256')!=recipe['bundle_sha256'] or any(state.get(k)!=recipe['view'][k] for k in ('shot','treatment','selected','run','frame','trails','compare')):
            raise ValueError('Rendered state differs from requested source/view')
        checked=validate_view({k:state.get(k) for k in ('shot','treatment','selected','camera','run','frame','trails','compare')},bundle)
        if checked['camera'] is None or checked['camera']!=state['camera']:
            raise ValueError('Capture requires a valid actual camera')
        if state.get('physical_to_scene')!={'units':'um','scale':1,'interpolation':'none'}:
            raise ValueError('Capture physical transform does not match preset')
        if state.get('viewport',{}).get('dpr')!=1 or any(abs(state['viewport'].get(k,0)-v)>1 for k,v in zip(('width','height'),(width,height))):
            raise ValueError('Capture viewport differs from PNG dimensions')
        requested_camera=recipe['view'].get('camera')
        if requested_camera and any(not same_state(state['camera'].get(k),v) for k,v in requested_camera.items() if k not in {'quaternion','zoom'}):
            raise ValueError('Rendered camera differs from requested pose')
        frame=bundle['runs'][recipe['view']['run']]['frames'][recipe['view']['frame']]
        if state.get('physical_time_s')!=frame['time'] or state.get('poles')!=frame['poles']:
            raise ValueError('Captured physical frame differs from saved trajectory')
        compare=recipe['view']['compare']
        if compare is not None:
            other=bundle['runs'][compare]['frames'];nearest=min(range(len(other)),key=lambda i:abs(other[i]['time']-frame['time']))
            comparison=state.get('comparison',{})
            if comparison.get('physical_time_s')!=other[nearest]['time'] or comparison.get('poles')!=other[nearest]['poles']:
                raise ValueError('Comparison is not synchronized to nearest saved physical time')
            if not same_state(comparison.get('camera'),state['camera']):raise ValueError('Comparison cameras differ')
        canonical(state)
        with self.locked():
            if self._latest(recipe['scene_id'])!=recipe_sha256:raise ValueError('Scene changed while capture rendered')
            if sum(e['kind']=='artifact' and e['payload'].get('kind')=='scene_capture' for e in self.history())>=16:
                raise ValueError('Experiment capture quota exhausted')
            key=self.journal.store_bytes(png)
            snapshot={'schema':'scene_capture.v1','adapter':'spindle@1','scope':self.scope,'recipe_sha256':recipe_sha256,
                      'bundle_sha256':recipe['bundle_sha256'],'image_sha256':key,'state':state,
                      'image_size':[width,height],'render_viewport':list(viewport)}
            snapshot_raw=canonical(snapshot);capture_id=self.journal.store_bytes(snapshot_raw)
            event=self._append('artifact',{'artifact_id':uuid4().hex,'kind':'scene_capture','status':'available',
                        'name':f"{recipe['view']['shot']} · agent scene capture",'media_type':'image/png',
                        'sha256':key,'storage_key':key,'byte_length':len(png),'capture_id':capture_id,
                        'snapshot':{'sha256':capture_id,'storage_key':capture_id,'byte_length':len(snapshot_raw)},
                        'recipe_sha256':recipe_sha256,'bundle_sha256':recipe['bundle_sha256'],
                        'provenance':{'category':'derived_geometry','source_ids':[recipe['bundle_sha256']],
                                      'tool':'spindle scene capture','tool_version':'1'}})
            return {'capture_id':capture_id,'image_sha256':key,'recipe_sha256':recipe_sha256,'sequence':event['sequence'],'state':state}

    def read_capture(self,capture_id,through=None):
        if not any(e['kind']=='artifact' and e['producer']=='collector' and e['payload'].get('kind')=='scene_capture'
                   and e['payload'].get('status')=='available' and e['payload'].get('capture_id')==capture_id for e in self.history(through)):
            raise FileNotFoundError('Capture unavailable in this experiment at this cursor')
        snapshot=json.loads(self.journal.read_blob(capture_id))
        if snapshot['scope']!=self.scope or snapshot.get('adapter')!='spindle@1':raise ValueError('Capture scope mismatch')
        return snapshot

    async def inspect_scene_capture(self,capture_id,*,question,through=None):
        from dnhacksbio.llm import acomplete
        if not isinstance(question,str) or not 1<=len(question)<=2000:raise ValueError('Bounded visual question required')
        snapshot=self.read_capture(capture_id,through)
        png=self.journal.read_blob(snapshot['image_sha256'])
        note=await asyncio.wait_for(acomplete(
            'Inspect this exact spindle image. Describe visible pole IDs, occlusion, depth and comparison balance. '
            'Do not infer motor forces, clustering statistics, chromosome accuracy or viability from pixels. Question: '+question,
            images=[png],tools_disabled=True,max_turns=1,max_attempts=1,max_output_tokens=768,effort='low'),timeout=90)
        review={'schema':'visual_review.v1','scope':self.scope,'capture_id':capture_id,
                'image_sha256':snapshot['image_sha256'],'recipe_sha256':snapshot['recipe_sha256'],
                'observation':note,'status':'visual observation, not scientific verification'}
        raw=canonical(review);key=self.journal.store_bytes(raw)
        event=self._append('scene.review',{'capture_id':capture_id,'bundle_sha256':snapshot['bundle_sha256'],
                                         'observation':note,'review':{'sha256':key,'storage_key':key,'byte_length':len(raw)}})
        return {**review,'review_sha256':key,'sequence':event['sequence']}


    def record_visual_review(self,review_sha256,*,observed_defects,changes,disposition):
        if disposition not in {'revise','accepted','incomplete'}:raise ValueError('Invalid review disposition')
        if not any(e['kind']=='scene.review' and e['payload'].get('review',{}).get('sha256')==review_sha256 for e in self.history()):
            raise FileNotFoundError('Image-bearing observation required before a visual verdict')
        review=json.loads(self.journal.read_blob(review_sha256))
        self.read_capture(review['capture_id'])
        for items in (observed_defects,changes):
            if not isinstance(items,list) or len(items)>20 or any(not isinstance(x,str) or not 1<=len(x)<=2000 for x in items):raise ValueError('Bounded review details required')
        record={**review,'parent_review':review_sha256,'observed_defects':observed_defects,'changes':changes,'disposition':disposition}
        raw=canonical(record);key=self.journal.store_bytes(raw)
        event=self._append('scene.review',{'capture_id':review['capture_id'],'observation':disposition,
            'review':{'sha256':key,'storage_key':key,'byte_length':len(raw)}})
        return {'review_sha256':key,'sequence':event['sequence'],'disposition':disposition}
