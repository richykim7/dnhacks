"""Native scientist action scope, durable records, real publication and instruction gates."""
import asyncio
import copy
import json
from types import SimpleNamespace

import pytest

from dnhacksbio.binder.geometry import canonical,digest
from dnhacksbio.binder.runtime import BinderRuntime,dispatch
from dnhacksbio.binder.jobs import DesignStore
from dnhacksbio.explorer.runtime import Journal

RAW=b'ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 20.00           C\nATOM      2  CA  ALA B   1       4.000   0.000   0.000  1.00 20.00           C\nEND\n'
SCOPE={'project_id':'p','run_id':'r','experiment_id':'e'}
EVIDENCE=[{'doi':'fixture-only','quote':'Illustrative test atoms','context':'Software fixture, no biological evidence'}]


@pytest.fixture
def native(tmp_path):
    journal=Journal(tmp_path);journal.register('r','Inspect fixture',project='p')
    journal.append('r','a','attempt.started',{'original_question':'Inspect fixture'})
    journal.append('r','a','experiment.queued',{'title':'Fixture'},experiment_id='e')
    source=journal.store_bytes(RAW)
    journal.append('r','a','artifact',{'artifact_id':'source','kind':'molecular_structure','format':'pdb',
        'status':'available','sha256':source,'storage_key':source,'provenance':{'category':'illustration'}},
        experiment_id='e',producer='collector')
    def call(operation,**args):
        return asyncio.run(dispatch(journal,'p','r',{'operation':operation,'experiment_id':'e','args':args}))
    return journal,source,call


def prepare(native):
    _,source,call=native
    target=call('prepare_target',source_ref=source,chains=['A'],source_evidence=EVIDENCE,construct_policy='Fixture chain A only')
    epitope=call('define_interface',target_ref=target['artifact_sha256'],selected=[target['data']['residues'][0]['id']],
                 excluded=[],competition='Illustrative patch; not ligand competition evidence')
    protocol=call('plan_design',target_ref=target['artifact_sha256'],epitope_ref=epitope['artifact_sha256'],
                  lengths=[40,60],seeds=[],candidate_cap=2,gpu_seconds=60,trajectory_cap=2,artifact_bytes=1000000,
                  environment_sha256='a'*64,weights_sha256='b'*64,filters_sha256='c'*64,advanced_sha256='d'*64)
    return target,epitope,protocol


def test_native_target_protocol_receipt_never_launches_and_reuses_terminal_state(native,monkeypatch):
    journal,_,call=native
    monkeypatch.setattr('subprocess.Popen',lambda *a,**k:pytest.fail('Native queue must not launch inference'))
    target,epitope,protocol=prepare(native)
    assert protocol['data']['protocol']['target_sha256']==digest(target['data'])
    before=journal.snapshot('r')['sequence']
    first=call('start_design',protocol_ref=protocol['artifact_sha256'],idempotency_key='one')
    assert first['state']=='queued'
    assert call('start_design',protocol_ref=protocol['artifact_sha256'],idempotency_key='one')==first
    assert len([e for e in journal.events('r',before) if e['kind']=='binder.job'])==1
    call('cancel',receipt=first['receipt'])
    assert call('start_design',protocol_ref=protocol['artifact_sha256'],idempotency_key='one')['state']=='canceled'
    assert journal.snapshot('r',before)['sequence']==before
    assert not any(e['kind']=='experiment.finished' for e in journal.events('r'))


def test_native_inputs_and_guidance_are_bound_to_current_researcher(native):
    journal,source,call=native
    with pytest.raises(ValueError,match='argument fields'):call('prepare_target',source_ref=source,structure_path='/not-allowed')
    with pytest.raises(ValueError,match='requires operation'):
        asyncio.run(dispatch(journal,'p','r',{'operation':'open_scene','experiment_id':'e','project_id':'other','args':{}}))
    with pytest.raises(FileNotFoundError):
        asyncio.run(dispatch(journal,'p','r',{'operation':'open_scene','experiment_id':'other','args':{'bundle_sha256':source}}))
    journal.append('r','a','experiment.queued',{'title':'Other'},experiment_id='other')
    with pytest.raises(FileNotFoundError,match='scope'):
        asyncio.run(dispatch(journal,'p','r',{'operation':'prepare_target','experiment_id':'other',
            'args':{'source_ref':source,'chains':['A'],'source_evidence':EVIDENCE,'construct_policy':'No borrowed artifact'}}))
    from dnhacksbio.explorer.explorer import Explorer
    explorer=object.__new__(Explorer);explorer._degraded=False;explorer._delivered={'agent-runtime'}
    explorer.journal=journal;explorer.manifest={'project_id':'p'};explorer.run_id='r'
    explorer.control=SimpleNamespace(get=lambda _:None)
    action={'action':'binder','args':{'operation':'evaluate_interface','experiment_id':'e','args':{'bundle_sha256':source}}}
    assert 'get_skill binder-interface' in asyncio.run(explorer._dispatch(action))
    explorer._delivered.add('binder-interface')
    assert 'error' in json.loads(asyncio.run(explorer._dispatch(action)))
    from dnhacksbio.explorer.skills import snapshot
    guide=snapshot('binder-interface')
    assert len(guide['files'])==2 and 'inspect_scene_capture' in guide['content']


def test_import_preserves_illustration_and_scoped_scene_identity(native):
    journal,source,call=native
    imported=call('import_candidate',source_ref=source,target_chains=['A'],binder_chains=['B'],
                  candidate_id='illustrative',source_evidence=[])
    bundle=json.loads(journal.read_blob(imported['bundle_sha256']))
    assert bundle['manifest']['provenance']['category']=='illustration'
    assert bundle['manifest']['scope']==SCOPE
    assert call('evaluate_interface',bundle_sha256=imported['bundle_sha256'])['metrics']['counts']['4.5']==1
    scene=call('open_scene',bundle_sha256=imported['bundle_sha256'],preset='interface-close')
    revision=call('set_scene_view',recipe_sha256=scene['recipe_sha256'],view={'preset':'reverse'},note='Inspect the opposite side')
    assert revision['view']['preset']=='reverse'
    with pytest.raises(ValueError,match='argument fields'):call('capture_scene',recipe_sha256=revision['recipe_sha256'],base_url='https://example.com')
    with pytest.raises(FileNotFoundError):call('open_scene',bundle_sha256=source)


def test_late_partial_collection_publishes_exact_bundle_once(native):
    journal,source,call=native;_,_,protocol=prepare(native)
    receipt=call('start_design',protocol_ref=protocol['artifact_sha256'],idempotency_key='one')['receipt']
    store=DesignStore(journal.directory/'binder-jobs');store.claim(receipt,SCOPE,'owner')
    store.finish(receipt,SCOPE,'owner','failed','Fixture engine failed')
    from dnhacksbio.binder.bundle import make_bundle
    bundle=make_bundle(RAW,'pdb',target_chains=['A'],binder_chains=['B'],candidate_id='partial',scope=SCOPE,
                      provenance={'category':'illustration','source_ids':[source],'tool':'fixture','tool_version':'1'},
                      source_evidence=[],protocol=protocol['data']['protocol'])
    raw=canonical(bundle);review={'source_sha256':digest(RAW),'target_sha256':protocol['data']['protocol']['target_sha256'],
                                'policy':'Fixture identity mapping; not generated design evidence'}
    key=store.attach_candidate(receipt,SCOPE,raw,mapping_review=review,rejection_reason='Illustrative failure')
    result=call('collect_candidates',receipt=receipt)
    assert result['state']=='failed'
    call('collect_candidates',receipt=receipt)
    artifacts=[e for e in journal.events('r') if e['kind']=='artifact' and e['payload'].get('sha256')==key]
    assert len(artifacts)==1 and artifacts[0]['payload']['rejection_reason']=='Illustrative failure'
    assert journal.read_blob(key)==raw
    assert call('collect_candidates',receipt=receipt,after=result['cursor'])['events']==[]


def test_comparison_rebuilds_sources_and_checks_full_target_mapping(native):
    journal,source,call=native
    first=call('import_candidate',source_ref=source,target_chains=['A'],binder_chains=['B'],candidate_id='first',source_evidence=[])
    second=call('import_candidate',source_ref=source,target_chains=['A'],binder_chains=['B'],candidate_id='second',source_evidence=[])
    result=call('compare',bundle_sha256s=[first['bundle_sha256'],second['bundle_sha256']])
    assert result['data']['rows'][0]['contacts']==1
    assert result['data']['rows'][0]['affinity'] is None
    from dnhacksbio.binder.tools import compare
    a=json.loads(journal.read_blob(first['bundle_sha256']));b=json.loads(journal.read_blob(second['bundle_sha256']))
    b['metrics']['counts']['4.5']=999
    with pytest.raises(ValueError,match='source coordinates'):compare([a,b])
    with pytest.raises(ValueError,match='distinct'):call('compare',bundle_sha256s=[first['bundle_sha256']]*2)


@pytest.mark.parametrize('fail',[False,True])
def test_native_image_review_transports_png_and_accounts_usage_even_on_failure(native,monkeypatch,fail):
    journal,source,call=native
    imported=call('import_candidate',source_ref=source,target_chains=['A'],binder_chains=['B'],candidate_id='image-test',source_evidence=[])
    opened=call('open_scene',bundle_sha256=imported['bundle_sha256'])
    from test_binder import scene_renderer
    capture=asyncio.run(dispatch(journal,'p','r',{'operation':'capture_scene','experiment_id':'e',
        'args':{'recipe_sha256':opened['recipe_sha256']}},renderer=scene_renderer))
    png=journal.read_blob(capture['image_sha256'])
    async def observe(prompt,**kwargs):
        assert kwargs['images']==[png] and kwargs['tools_disabled']
        kwargs['capture']['messages']=[{'type':'ResultMessage','usage':{'input_tokens':12,'output_tokens':7}}]
        if fail:raise Exception('Fixture provider quota failure after usage')
        return 'Fixture-only observation; not scientific evidence'
    monkeypatch.setattr('dnhacksbio.llm.acomplete',observe)
    from dnhacksbio.explorer.explorer import Explorer
    explorer=object.__new__(Explorer);explorer._degraded=False;explorer._delivered={'agent-runtime','binder-interface'}
    explorer.journal=journal;explorer.manifest={'project_id':'p'};explorer.run_id='r'
    costs=[];explorer.control=SimpleNamespace(get=lambda _:None,cost=lambda *a:costs.append(a))
    result=json.loads(asyncio.run(explorer._dispatch({'action':'binder','args':{'operation':'inspect_scene_capture',
        'experiment_id':'e','args':{'capture_id':capture['capture_id'],'question':'Fixture image check'}}})))
    assert costs==[('r','research',0.,{'input_tokens':12,'output_tokens':7})]
    assert ('error' in result)==fail
    if not fail:assert result['image_sha256']==capture['image_sha256']
    else:
        assert 'Visual observation unavailable' in result['error']
        assert not any(e['kind']=='scene.review' for e in journal.events('r'))


def test_compare_rejects_valid_but_different_target_residue_metadata(native):
    journal,source,call=native
    from dnhacksbio.binder.bundle import make_bundle
    from dnhacksbio.binder.tools import compare
    kwargs={'target_chains':['A'],'binder_chains':['B'],'scope':SCOPE,'source_evidence':[],
            'provenance':{'category':'illustration','source_ids':[],'tool':'fixture','tool_version':'1'}}
    first=make_bundle(RAW,'pdb',candidate_id='a',**kwargs)
    second=make_bundle(RAW.replace(b'ALA A',b'GLY A'),'pdb',candidate_id='b',**kwargs)
    with pytest.raises(ValueError,match='target coordinates/mapping'):compare([first,second])


def test_binder_guide_cannot_be_used_as_an_audited_method():
    from dnhacksbio.explorer.explorer import Explorer
    explorer=object.__new__(Explorer)
    events=[];explorer._event=lambda *args,**kwargs:events.append(args)
    result=asyncio.run(explorer._act_run_experiments({'experiments':[
        {'method_id':'binder-interface','code':'raise AssertionError("must not run")'}]}))
    assert 'use method_id exploratory' in result
    assert events[0][0]=='policy.rejected'
