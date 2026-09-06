import copy
import json
from pathlib import Path

import pytest

from dnhacksbio.binder import define_interface, evaluate_interface, parse_structure, select_chains, validate_bundle
from dnhacksbio.binder.geometry import canonical


def pdb_atom(serial, name, chain, residue, xyz, element="C", insertion=" ", alt=" ", occ=1):
    return f"ATOM  {serial:5d} {name:>4s}{alt}ALA {chain}{residue:4d}{insertion}   {xyz[0]:8.3f}{xyz[1]:8.3f}{xyz[2]:8.3f}{occ:6.2f}{0:6.2f}          {element:>2s}\n"


def pair(distance=4.5):
    return parse_structure((pdb_atom(1,"CA","A",10,(0,0,0),insertion="B") +
                            pdb_atom(2,"CA","B",1,(distance,0,0))).encode(),"pdb")


def test_exact_contacts_and_insertion_codes():
    s=pair()
    assert s['residues'][0]['insertion_code']=='B'
    r=evaluate_interface(s,['A'],['B'],candidate_id='test')
    assert r['counts']=={'4.0':0,'4.5':1,'5.0':1}
    assert r['contacts'][0]['distance_angstrom']==4.5
    assert r['total_buried_area_angstrom2']>0
    assert r['protocol']['divided_by_two'] is False
    assert r['affinity'] is None
    far=evaluate_interface(pair(20),['A'],['B'],candidate_id='far')
    assert far['counts']['5.0']==0
    assert far['total_buried_area_angstrom2']==pytest.approx(0,abs=1e-10)


def test_chain_trim_retains_source_mapping():
    s=pair();target=select_chains(s,['A'])
    assert target['residues']==s['residues'][:1]
    assert target['atoms'][0]['xyz']==[0,0,0]
    ep=define_interface(target,[target['residues'][0]['id']],[],"competitive interface")
    assert ep['context']=='context unavailable'
    with pytest.raises(ValueError):define_interface(target,['absent'],[],"test")
    with pytest.raises(ValueError):define_interface(target,ep['selected'],ep['selected'],"test")
    with pytest.raises(ValueError):evaluate_interface(s,['A'],['A'],candidate_id='bad')
    with pytest.raises(ValueError):select_chains(s,['Z'])


def test_alternate_conformers_selected_per_residue():
    raw=(pdb_atom(1,'CA','A',1,(0,0,0),alt='A',occ=.8)+
         pdb_atom(2,'CA','A',1,(5,0,0),alt='B',occ=.2)+
         pdb_atom(3,'CB','A',1,(0,1,0),alt='A',occ=.2)+
         pdb_atom(4,'CB','A',1,(5,1,0),alt='B',occ=.8)).encode()
    s=parse_structure(raw,'pdb')
    assert {a['altloc'] for a in s['atoms']}=={'A'}
    assert len(s['omitted_conformers'])==2
    with pytest.raises(ValueError):parse_structure(raw,'pdb',model=-1)
    with pytest.raises(ValueError):parse_structure(b'END\n','pdb')


@pytest.fixture
def bundle():
    return json.loads((Path(__file__).resolve().parents[1]/'frontend/e2e/binder-fixture.json').read_text())


def test_bundle_roundtrip_and_scope(bundle):
    assert validate_bundle(canonical(bundle),bundle['manifest']['scope'])['schema']=='binder_bundle.v1'
    with pytest.raises(ValueError,match='scope'):validate_bundle(canonical(bundle),{'project_id':'other','run_id':'fixture','experiment_id':'exp1'})


@pytest.mark.parametrize('attack',['hash','metric','map','nan','verdict','alias'])
def test_bundle_rejects_corrupt_or_invented_data(bundle,attack):
    if attack=='hash':bundle['files']['candidate.cif']['sha256']='0'*64
    if attack=='metric':bundle['metrics']['clash_count']=0
    if attack=='map':bundle['structure']['residues'][0]['auth_seq_id']=999
    if attack=='nan':bundle['metrics']['affinity']=float('nan')
    if attack=='verdict':bundle['manifest']['validation_status']='validated'
    if attack=='alias':bundle['binder_chains']=['A']
    with pytest.raises(ValueError):validate_bundle(json.dumps(bundle).encode())


def test_receipts_are_idempotent_scoped_and_recoverable(tmp_path):
    from dnhacksbio.binder.jobs import DesignStore, plan_design
    target=select_chains(pair(),['A'])
    # BindCraft cannot represent insertion codes; use a target without one.
    target=parse_structure(pdb_atom(1,'CA','A',10,(0,0,0)).encode(),'pdb')
    ep=define_interface(target,[target['residues'][0]['id']],[],"competition")
    kwargs=dict(lengths=[40,60],seeds=[],candidate_cap=2,gpu_seconds=60,trajectory_cap=2,
                artifact_bytes=10000,environment_sha256='a'*64,weights_sha256='b'*64,
                filters_sha256='c'*64,advanced_sha256='d'*64)
    protocol=plan_design(target,ep,**kwargs)
    store=DesignStore(tmp_path)
    scope={'project_id':'p','run_id':'r','experiment_id':'e'}
    first=store.start_design(protocol,scope=scope,idempotency_key='one')
    assert store.start_design(protocol,scope=scope,idempotency_key='one')==first
    with pytest.raises(ValueError):store.start_design({**protocol,'gpu_seconds':30},scope=scope,idempotency_key='one')
    with pytest.raises(ValueError):store.start_design({**protocol,'gpu_seconds':999999},scope=scope,idempotency_key='bad')
    store.claim(first['receipt'],scope,'owner')
    with pytest.raises(ValueError):store.claim(first['receipt'],scope,'owner')
    restarted=DesignStore(tmp_path)
    events=restarted.collect_candidates(first['receipt'],scope)
    assert [e['state'] for e in events['events']]==['queued','running']
    assert restarted.collect_candidates(first['receipt'],scope,events['cursor'])['events']==[]
    with pytest.raises(FileNotFoundError):restarted.collect_candidates(first['receipt'],{**scope,'project_id':'other'})
    restarted.finish(first['receipt'],scope,'owner','interrupted','Process identity confirms worker exited')
    with pytest.raises(ValueError):restarted.claim(first['receipt'],scope,'replacement')
    other=store.start_design(protocol,scope=scope,idempotency_key='two')
    store.cancel(other['receipt'],scope)
    assert store.collect_candidates(other['receipt'],scope)['state']=='canceled'
    with pytest.raises(ValueError):plan_design(target,ep,**{**kwargs,'seeds':[1]})


def test_collection_only_publishes_validated_bundle(tmp_path,bundle):
    from dnhacksbio.explorer.artifacts import collect
    from dnhacksbio.explorer.runtime import Journal
    output=tmp_path/'output';output.mkdir()
    (output/'binder.json').write_bytes(canonical(bundle))
    manifest={'schema_version':1,'artifacts':[{'kind':'binder_bundle','format':'json','path':'binder.json','provenance':bundle['manifest']['provenance']}]}
    (output/'manifest.json').write_text(json.dumps(manifest))
    journal=Journal(tmp_path/'journal')
    result=collect(output,journal)[0]
    assert result['status']=='available'
    assert validate_bundle(journal.read_blob(result['storage_key']))['schema']=='binder_bundle.v1'
    bundle['metrics']['counts']['4.5']=0
    (output/'binder.json').write_bytes(canonical(bundle))
    assert collect(output,journal)[0]['status']=='rejected'


def test_real_png_bytes_are_attached_to_sdk_observation():
    import asyncio
    import base64
    from dnhacksbio.llm import image_prompt
    raw=(Path(__file__).resolve().parents[1]/'docs/binder-review/r04-interface-close-stage.png').read_bytes()
    async def read():return [m async for m in image_prompt('Inspect the interface',[raw])]
    messages=asyncio.run(read())
    assert len(messages)==1
    content=messages[0]['message']['content']
    assert content[0]=={'type':'text','text':'Inspect the interface'}
    assert content[1]['source']['media_type']=='image/png'
    assert base64.b64decode(content[1]['source']['data'])==raw
    assert image_prompt('unchanged',None)=='unchanged'
    with pytest.raises(ValueError):image_prompt('bad',['/tmp/image.png'])
    with pytest.raises(ValueError):image_prompt('bad',[raw]*3)
    with pytest.raises(ValueError):image_prompt('bad',[b'not png'])

@pytest.fixture
def scene_service(tmp_path, bundle):
    from dnhacksbio.explorer.runtime import Journal
    from dnhacksbio.binder.scenes import SceneService
    scope=bundle['manifest']['scope']
    j=Journal(tmp_path)
    j.register(scope['run_id'],'Interface review',project=scope['project_id'])
    j.append(scope['run_id'],'a','attempt.started',{'original_question':'Interface review'})
    j.append(scope['run_id'],'a','experiment.queued',{'title':'Interface review'},experiment_id=scope['experiment_id'])
    raw=canonical(bundle);key=j.store_bytes(raw)
    j.append(scope['run_id'],'a','artifact',{'artifact_id':'binder','kind':'binder_bundle','status':'available','sha256':key,'storage_key':key},
             experiment_id=scope['experiment_id'],producer='collector')
    return SceneService(j,scope),key


def scene_renderer(request):
    import zlib, struct
    def chunk(kind, data):
        return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data))
    png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b'\0\0\0\0'))+chunk(b'IEND',b'')
    view=request['recipe']['view']
    camera=view['camera'] or {'position':[0,0,10],'target':[0,0,0],'fov':38,'near':.1,'far':2000}
    return {'png':png,'state':{**view,'camera':camera,'bundle_sha256':request['recipe']['bundle_sha256'],
             'viewport':{'width':1,'height':1,'dpr':1},
             'physical_to_scene':{'units':'angstrom','scale':1,'binder_offset':12 if view['preset']=='exploded' else 0,'illustrative':view['preset']=='exploded'}},
            'picked':request['bundle']['structure']['residues'][0]['id']}


def test_scene_scope_cursor_and_stale_revision(scene_service):
    from dnhacksbio.binder.scenes import SceneService
    service,key=scene_service
    with pytest.raises(FileNotFoundError):service.open_scene(key,through=3)
    first=service.open_scene(key)
    second=service.set_scene_view(first['recipe_sha256'],{'preset':'reverse'},note='Check the opposing face')
    assert first['recipe_sha256']!=second['recipe_sha256']
    assert service.open_scene(key,through=first['sequence'])==first
    with pytest.raises(ValueError,match='Stale'):service.set_scene_view(first['recipe_sha256'],{},note='old')
    with pytest.raises(ValueError,match='obsolete'):service.capture_scene(first['recipe_sha256'],scene_renderer)
    other=SceneService(service.journal,{**service.scope,'experiment_id':'other'})
    with pytest.raises(FileNotFoundError):other.open_scene(key)
    capture=service.capture_scene(second['recipe_sha256'],scene_renderer)
    with pytest.raises(FileNotFoundError):service.read_capture(capture['capture_id'],first['sequence'])
    picked=service.pick(capture['capture_id'],recipe_sha256=second['recipe_sha256'],x=0,y=0,renderer=scene_renderer)
    assert picked['residue_id']
    with pytest.raises(ValueError,match='different camera'):service.pick(capture['capture_id'],recipe_sha256=first['recipe_sha256'],x=0,y=0,renderer=scene_renderer)
    def moved(request):
        result=scene_renderer(request);result['state']['camera']={**result['state']['camera'],'position':[1,1,1]};return result
    with pytest.raises(ValueError,match='differs'):service.pick(capture['capture_id'],recipe_sha256=second['recipe_sha256'],x=0,y=0,renderer=moved)


def test_scene_capture_rejects_changes_and_bad_pixels(scene_service):
    service,key=scene_service
    opened=service.open_scene(key)
    def wrong(request):
        result=scene_renderer(request);result['state']['bundle_sha256']='0'*64;return result
    with pytest.raises(ValueError,match='differs'):service.capture_scene(opened['recipe_sha256'],wrong)
    def short(request):
        result=scene_renderer(request);result['png']=b'\x89PNG\r\n\x1a\n';return result
    with pytest.raises(ValueError,match='PNG'):service.capture_scene(opened['recipe_sha256'],short)
    def concurrent(request):
        service.set_scene_view(opened['recipe_sha256'],{'preset':'reverse'},note='Changed during render')
        return scene_renderer(request)
    with pytest.raises(ValueError,match='changed'):service.capture_scene(opened['recipe_sha256'],concurrent)
    assert not any(e['kind']=='artifact' and e['payload'].get('kind')=='scene_capture' for e in service.history())


def test_scene_review_transports_exact_image_and_records_scope(scene_service,monkeypatch):
    service,key=scene_service
    opened=service.open_scene(key);capture=service.capture_scene(opened['recipe_sha256'],scene_renderer)
    async def complete(prompt,**kwargs):
        assert kwargs['images']==[service.journal.read_blob(capture['image_sha256'])]
        assert kwargs['tools_disabled']
        return 'The image is black; no interface can be assessed.'
    monkeypatch.setattr('dnhacksbio.llm.acomplete',complete)
    import asyncio
    review=asyncio.run(service.inspect_scene_capture(capture['capture_id'],question='Is the interface visible?'))
    assert review['scope']==service.scope
    assert service.history()[-1]['kind']=='scene.review'


def test_surface_preserves_source_mapping_and_faces_outward():
    import numpy as np
    from dnhacksbio.binder.surfaces import envelope
    structure=pair();before=copy.deepcopy(structure)
    mesh=envelope(structure,['A'],{'spacing':1.,'max_grid_axis':24})
    vertices=np.array(mesh['positions']);triangles=vertices[np.array(mesh['triangles'])]
    normals=np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0])
    assert np.all(np.einsum('ij,ij->i',normals,triangles.mean(axis=1))>0)
    assert set(mesh['source_atom_ids'])=={structure['atoms'][0]['id']}
    assert np.max(np.abs(np.linalg.norm(vertices,axis=1)-3.1))==pytest.approx(mesh['protocol']['max_vertex_field_residual_angstrom'])
    assert max(mesh['protocol']['grid_shape'])<=24
    assert mesh['protocol']['hausdorff_bound']=='not established'
    assert structure==before
    with pytest.raises(ValueError):envelope(structure,['A'],{'max_grid_axis':128})
    structure['atoms'][0]['element']='XE'
    with pytest.raises(ValueError,match='radius unavailable'):envelope(structure,['A'])


@pytest.mark.parametrize('attack',['position','mapping'])
def test_optional_surface_bundle_rebuild_rejects_rehashed_tampering(attack):
    import base64
    from dnhacksbio.binder.bundle import make_bundle
    from dnhacksbio.binder.geometry import digest
    raw=(pdb_atom(1,'CA','A',1,(0,0,0))+pdb_atom(2,'CA','B',1,(4.5,0,0))).encode()
    b=make_bundle(raw,'pdb',target_chains=['A'],binder_chains=['B'],candidate_id='mesh-test',
      provenance={'category':'illustration','tool':'test','tool_version':'1','source_ids':[]},
      scope={'project_id':'p','run_id':'r','experiment_id':'e'},source_evidence=[],
      surface_options={'spacing':1.5,'max_grid_axis':16})
    assert len(validate_bundle(canonical(b))['files'])==10
    ref=b['files']['surface-target.json'];mesh=json.loads(base64.b64decode(ref['base64']))
    if attack=='position':mesh['positions'][0][0]+=1
    else:mesh['source_atom_ids'][0]=999
    raw=canonical(mesh);ref.update(base64=base64.b64encode(raw).decode(),sha256=digest(raw),byte_length=len(raw))
    with pytest.raises(ValueError,match='source coordinates'):validate_bundle(canonical(b))


def test_scene_representation_requires_available_source_geometry(bundle):
    from dnhacksbio.binder.scenes import validate_view
    from dnhacksbio.binder.surfaces import has_backbone_trace
    with pytest.raises(ValueError,match='precomputed'):validate_view({'representation':'surface'},bundle)
    assert has_backbone_trace(bundle)
    assert validate_view({'representation':'ribbon'},bundle)['representation']=='ribbon'
    assert validate_view({'representation':'ribbon','preset':'reverse'},bundle)['representation']=='atoms'
    bundle['structure']['atoms']=[a for a in bundle['structure']['atoms'] if a['name']!='CA']
    with pytest.raises(ValueError,match='trace unavailable'):validate_view({'representation':'ribbon'},bundle)
