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
