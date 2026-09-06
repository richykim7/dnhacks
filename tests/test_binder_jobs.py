"""Real local-process lifecycle checks; no BindCraft dependencies or GPU are invoked."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from dnhacksbio.binder.bundle import make_bundle
from dnhacksbio.binder.geometry import canonical, digest, parse_structure
from dnhacksbio.binder.jobs import BINDCRAFT_COMMIT, DesignStore
from dnhacksbio.explorer.runtime import process_identity

SCOPE={'project_id':'p','run_id':'r','experiment_id':'e'}
RAW=b'ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 20.00           C\nATOM      2  CA  ALA B   1       4.000   0.000   0.000  1.00 20.00           C\nEND\n'


def protocol(target=None,epitope=None):
    return {'schema':'binder_design_protocol.v1','engine':'BindCraft','commit':BINDCRAFT_COMMIT,
            'target_sha256':digest(target or {}),'epitope_sha256':digest(epitope or {}),
            'lengths':[40,60],'seed_policy':'upstream-random-recorded-in-output',
            'candidate_cap':2,'gpu_seconds':5,'trajectory_cap':2,'artifact_bytes':1000000,
            'simultaneous_jobs':1,'hotspots':'A1',**{k:'a'*64 for k in
            ['environment_sha256','weights_sha256','filters_sha256','advanced_sha256']}}


def start(store,p=None,key='one'):
    return store.start_design(p or protocol(),scope=SCOPE,idempotency_key=key)['receipt']


def test_dead_local_worker_recovery_is_scoped_and_never_reruns(tmp_path):
    store=DesignStore(tmp_path);receipt=start(store)
    child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'])
    try:
        identity=process_identity(child.pid);assert identity
        store.claim(receipt,SCOPE,identity)
        with pytest.raises(ValueError,match='still alive'):store.recover(receipt,SCOPE)
        with pytest.raises(FileNotFoundError):store.recover(receipt,{**SCOPE,'run_id':'other'})
    finally:child.kill();child.wait()
    assert store.recover(receipt,SCOPE)['state']=='interrupted'
    assert store.recover(receipt,SCOPE)['state']=='interrupted'
    assert [e['state'] for e in store.collect_candidates(receipt,SCOPE)['events']]==['queued','running','interrupted']
    with pytest.raises(ValueError,match='already claimed'):store.claim(receipt,SCOPE,process_identity())
    store.claim(start(store,key='explicit-new-run'),SCOPE,process_identity())


def test_recovery_rejects_unverifiable_namespace(tmp_path):
    store=DesignStore(tmp_path);receipt=start(store)
    boot,_,pid,ticks=process_identity().split('|')
    store.claim(receipt,SCOPE,f'{boot}|pid:[different]|{pid}|{ticks}')
    with pytest.raises(ValueError,match='original worker PID namespace'):store.recover(receipt,SCOPE)
    assert store.collect_candidates(receipt,SCOPE)['state']=='running'


@pytest.mark.parametrize('outcome',['completed','failed','canceled','resource_exhausted','interrupted'])
def test_terminal_partial_import_retains_outcome_and_resumes_without_duplicates(tmp_path,outcome):
    store=DesignStore(tmp_path);p=protocol();receipt=start(store,p)
    store.claim(receipt,SCOPE,'owner');store.finish(receipt,SCOPE,'owner',outcome,'Test terminal outcome')
    b=make_bundle(RAW,'pdb',target_chains=['A'],binder_chains=['B'],candidate_id='partial',
                  provenance={'category':'illustration','tool':'fixture','tool_version':'1','source_ids':[]},
                  scope=SCOPE,source_evidence=[],protocol=p)
    raw=canonical(b);review={'source_sha256':b['structure']['source_sha256'],
                            'target_sha256':p['target_sha256'],'policy':'Fixture keeps author chains/numbers; no generator renumbering'}
    before=store.collect_candidates(receipt,SCOPE)['cursor']
    key=store.attach_candidate(receipt,SCOPE,raw,mapping_review=review,rejection_reason='Fixture has a close pair')
    assert store.attach_candidate(receipt,SCOPE,raw,mapping_review=review)==key
    result=DesignStore(tmp_path).collect_candidates(receipt,SCOPE,before)
    assert result['state']==outcome and len(result['events'])==1
    assert result['events'][0]['mapping_review']==review
    assert result['events'][0]['rejection_reason']=='Fixture has a close pair'
    assert store.collect_candidates(receipt,SCOPE,result['cursor'])['events']==[]
    with pytest.raises(ValueError,match='identity mismatch'):
        store.attach_candidate(receipt,SCOPE,raw,mapping_review={**review,'source_sha256':'0'*64})
    b['metrics']['counts']['4.5']=999
    with pytest.raises(ValueError):store.attach_candidate(receipt,SCOPE,canonical(b),mapping_review=review)


@pytest.mark.parametrize('mode,expected',[('success','completed'),('failure','failed'),('large','resource_exhausted'),('setup','interrupted'),('cancel','canceled')])
def test_adapter_terminal_cleanup_and_fast_output_cap(tmp_path,monkeypatch,mode,expected):
    from dnhacksbio.binder import adapter
    target=parse_structure(RAW,'pdb');epitope={'selected':['A:1:']};p=protocol(target,epitope)
    p['artifact_bytes']=2000
    store=DesignStore(tmp_path/'store');receipt=start(store,p)
    source=tmp_path/'target.pdb';source.write_bytes(RAW)
    advanced=tmp_path/'advanced.json';advanced.write_text('{}')
    checkout=tmp_path/'engine';checkout.mkdir()
    # A child retains the inherited GPU lock and ignores TERM. Even an exited leader must be cleaned up.
    (checkout/'bindcraft.py').write_text(f'''import subprocess,sys,json,time
from pathlib import Path
settings=json.loads(Path(sys.argv[sys.argv.index('--settings')+1]).read_text())
root=Path(settings['design_path']);root.mkdir()
child=subprocess.Popen([sys.executable,'-c',"import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(60)"],close_fds=False)
(root/'child.pid').write_text(str(child.pid))
(root/'partial.txt').write_text('x'*{4000 if mode=='large' else 10})
time.sleep({2 if mode=='cancel' else .1})
raise SystemExit({3 if mode=='failure' else 0})
''')
    monkeypatch.setattr(adapter,'check_deployment',lambda *a,**k:None)
    if mode=='setup':(store.root/receipt).mkdir()
    kwargs=dict(checkout=checkout,python=Path(sys.executable),target_pdb=source,target=target,epitope=epitope,
                environment=advanced,weights_manifest=advanced,filters=advanced,advanced=advanced,
                license_reviewed=False,lock_path=tmp_path/'test-gpu.lock')
    if mode=='setup':
        with pytest.raises(FileExistsError):adapter.execute(store,receipt,SCOPE,**kwargs)
    else:
        canceler=None
        if mode=='cancel':
            import threading
            def cancel_when_started():
                deadline=time.monotonic()+5
                while not (store.root/receipt/'outputs/child.pid').exists() and time.monotonic()<deadline:time.sleep(.01)
                store.cancel(receipt,SCOPE)
            canceler=threading.Thread(target=cancel_when_started);canceler.start()
        try:adapter.execute(store,receipt,SCOPE,**kwargs)
        finally:
            if canceler:canceler.join(timeout=6)
        child=int((store.root/receipt/'outputs/child.pid').read_text())
        deadline=time.monotonic()+2
        while Path(f'/proc/{child}/stat').exists() and Path(f'/proc/{child}/stat').read_text().split()[2]!='Z' and time.monotonic()<deadline:
            time.sleep(.01)
        assert not Path(f'/proc/{child}/stat').exists() or Path(f'/proc/{child}/stat').read_text().split()[2]=='Z'
    assert store.collect_candidates(receipt,SCOPE)['state']==expected
    import fcntl
    with kwargs['lock_path'].open('a') as lock:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)


def test_mapped_candidate_budget_is_still_enforced_after_failure(tmp_path):
    store=DesignStore(tmp_path);p=protocol();p['candidate_cap']=1;receipt=start(store,p)
    store.claim(receipt,SCOPE,'owner');store.finish(receipt,SCOPE,'owner','failed','Known engine failure')
    def bundle(candidate):
        return make_bundle(RAW,'pdb',target_chains=['A'],binder_chains=['B'],candidate_id=candidate,
                           provenance={'category':'illustration','tool':'fixture','tool_version':'1','source_ids':[]},
                           scope=SCOPE,source_evidence=[],protocol=p)
    first=bundle('first');review={'source_sha256':first['structure']['source_sha256'],
                                 'target_sha256':p['target_sha256'],'policy':'Exact fixture author mapping'}
    store.attach_candidate(receipt,SCOPE,canonical(first),mapping_review=review)
    with pytest.raises(ValueError,match='budget exhausted'):
        store.attach_candidate(receipt,SCOPE,canonical(bundle('second')),mapping_review=review)
    assert store.collect_candidates(receipt,SCOPE)['state']=='failed'


def test_late_worker_finish_cannot_overwrite_cancel(tmp_path):
    store=DesignStore(tmp_path);receipt=start(store);store.claim(receipt,SCOPE,'owner')
    store.cancel(receipt,SCOPE)
    store.finish(receipt,SCOPE,'owner','completed','Leader exited',preserve_terminal=True)
    assert store.collect_candidates(receipt,SCOPE)['state']=='canceled'
    with pytest.raises(ValueError,match='immutable'):
        store.finish(receipt,SCOPE,'owner','completed','Conflicting explicit outcome')
