import copy
import math

import numpy as np
import pytest

from dnhacksbio.native_evidence import KERNEL, PrivateProcessStore, association_factor, frozen_scores


def test_adaptive_scores_before_training_and_recovers(tmp_path,monkeypatch):
    import json
    from dnhacksbio import native_evidence as core
    declaration=spec();declaration['schedule']=core.ADAPTIVE_SCHEDULE
    declaration['weights']=[[0.]]
    store=PrivateProcessStore(tmp_path);store.register('adaptive',declaration)
    first=[[1.],[-1.]];second=[[2.],[-2.]]
    store.advance('adaptive',0,['a','b'],first,first)
    assert store.export('adaptive')['blocks'][0]['factor']==1.
    expected=core.past_block_update([[0.]],first,first)
    original=core.past_block_update
    def checked(weights,x,y):
        assert x==second and y==second and weights==expected
        return original(weights,x,y)
    monkeypatch.setattr(core,'past_block_update',checked)
    def crash():raise RuntimeError('after score and snapshot, before commit')
    with pytest.raises(RuntimeError):store.advance('adaptive',1,['c','d'],second,second,before_commit=crash)
    assert store.export('adaptive')['cursor']==1
    store=PrivateProcessStore(tmp_path)
    store.advance('adaptive',1,['c','d'],second,second)
    assert store.export('adaptive')['blocks'][1]['factor']==pytest.approx(association_factor(frozen_scores(second,second,expected)))
    store.advance('adaptive',1,['c','d'],second,second)
    assert store.export('adaptive')['cursor']==2
    with store.connect() as con:
        state=json.loads(con.execute('SELECT snapshot FROM blocks WHERE number=1').fetchone()[0])
    assert state['critic']==expected and state['optimizer']['learning_rate']==.001
    assert state['next_critic']==original(expected,second,second)
    uninterrupted=PrivateProcessStore(tmp_path/'uninterrupted')
    uninterrupted.register('alias',declaration)
    monkeypatch.setattr(core,'past_block_update',original)
    uninterrupted.advance('alias',0,['a','b'],first,first)
    uninterrupted.advance('alias',1,['c','d'],second,second)
    assert uninterrupted.export('alias')==store.export('adaptive')


def spec():
    return dict(kernel=KERNEL, null='independence-of-measured-views', population='synthetic-iid', panel='synthetic',
                model_hashes=['a'*64, 'b'*64], qc_hash='c'*64, data_hash='d'*64, crosswalk_hash='e'*64,
                acquisition_hash='f'*64, family='f1', parent='p1', sampling='independent donor pairs',
                exclusions=['training-1'], weights=[[1.0]], stake=0.9, eligible_donors=['a','b','c','d'],
                reuse_policy='globally-disjoint-canonical-donors-v1', schedule='fully-frozen-v1')


def test_kernel_symmetry_bounds():
    assert association_factor([1,1,-1,-1]) == 1.9
    assert association_factor([-1,-1,1,1]) == pytest.approx(0.1)
    assert association_factor([.5,.5,.5,.5]) == 1
    rng = np.random.default_rng(19)
    for _ in range(100):
        x, y = rng.normal(size=(2,3)), rng.normal(size=(2,4))
        w = rng.normal(size=(3,4))
        f = association_factor(frozen_scores(x,y,w))
        swapped = association_factor(frozen_scores(x,y[::-1],w))
        assert f + swapped == pytest.approx(2)
        assert .1 <= f <= 1.9
    for scores in ([2,0,0,0], [np.nan,0,0,0], [0,0]):
        with pytest.raises(ValueError): association_factor(scores)
    for stake in (-1,1,np.nan):
        with pytest.raises(ValueError): association_factor([0]*4, stake)


def test_alias_crash_retry_and_restart(tmp_path):
    s = PrivateProcessStore(tmp_path)
    s.register('r1', spec()); s.register('alias', spec())
    x = [[1.],[-1.]]
    def crash(): raise RuntimeError('simulated power loss')
    with pytest.raises(RuntimeError):
        s.advance('r1',0,['a','b'],x,x,before_commit=crash)
    assert s.export('alias')['cursor'] == 0
    s.advance('r1',0,['a','b'],x,x)
    s = PrivateProcessStore(tmp_path)
    s.advance('alias',0,['a','b'],x,x)
    s.advance('alias',1,['c','d'],x,x)
    state = s.export('r1')
    assert state['cursor'] == 2
    assert len(state['blocks']) == 2
    assert state['log_wealth'] == pytest.approx(2*math.log(association_factor(frozen_scores(x,x,[[1.]]))))
    with pytest.raises(ValueError): s.advance('alias',0,['a','b'],[[0.],[0.]],x)
    with pytest.raises(ValueError): s.advance('alias',3,['e','f'],x,x)
    changed = spec(); changed['stake'] = .5
    with pytest.raises(ValueError): s.register('alias', changed)
    s.register('new-hypothesis', changed)
    with pytest.raises(ValueError): s.advance('new-hypothesis',0,['a','b'],x,x)


def test_replay_equals_uninterrupted(tmp_path):
    a,b = PrivateProcessStore(tmp_path/'a'), PrivateProcessStore(tmp_path/'b')
    for s in (a,b): s.register('r', spec())
    x,y = [[1.],[2.]], [[3.],[4.]]
    for number, donors in enumerate((['a','b'],['c','d'])):
        a.advance('r',number,donors,x,y)
        b.advance('r',number,donors,x,y)
        b = PrivateProcessStore(tmp_path/'b')
        b.advance('r',number,donors,x,y)
    assert a.export('r') == b.export('r')


def test_invalid_contracts(tmp_path):
    store = PrivateProcessStore(tmp_path)
    for field,value in [('schedule','current-block-training'), ('eligible_donors',['a','a']),
                        ('eligible_donors',['training-1','a']), ('weights',[[float('nan')]]),
                        ('model_hashes',['x']), ('reuse_policy','reset-on-new-receipt')]:
        s=copy.deepcopy(spec()); s[field]=value
        with pytest.raises(ValueError): store.register('r',s)


def test_independent_null_streams():
    # Kernel calibration diagnostic, not biological power/release validation.
    rng=np.random.default_rng(765)
    x=rng.normal(size=(10000,50,2)); y=rng.normal(size=(10000,50,2))
    c11=np.tanh(x[:,:,0]*y[:,:,0]); c22=np.tanh(x[:,:,1]*y[:,:,1])
    c12=np.tanh(x[:,:,0]*y[:,:,1]); c21=np.tanh(x[:,:,1]*y[:,:,0])
    logw=np.cumsum(np.log1p(.9*(c11+c22-c12-c21)/4),axis=1)
    assert np.mean(logw.max(axis=1)>=math.log(20)) < .06
    assert np.mean(logw[:,-1]>=math.log(20)) < .06
