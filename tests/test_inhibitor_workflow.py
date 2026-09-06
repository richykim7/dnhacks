from pathlib import Path
import json
from types import SimpleNamespace

import pytest

from dnhacksbio.explorer.runtime import Journal
from dnhacksbio.inhibitor.service import Workbench
from dnhacksbio.inhibitor.science import validate_spec


@pytest.fixture
def workbench(tmp_path):
    j=Journal(tmp_path);j.register('study','Scoped inhibitor experiment',project='alpha')
    w=Workbench(j,'study','recovery','alpha')
    w.event('experiment.queued',{'title':'Recovery'})
    a=w.attach((Path(__file__).parents[1]/'frontend/e2e/inhibitor/3vqu.cif').read_bytes(),
               '3VQU','molecular_structure','cif',{'category':'experimental_reference'})
    return w,a['storage_key']


def spec():
    return dict(spec_version=1,chain='A',ligand_sequence='909',ligand_name='O22',rationale='Test dry-receptor protocol',
                water_policy='exclude',cofactor_policy='reject',assembly='deposited-chain',protonation='meeko-standard-templates',
                repair_policy='reject',altloc='A',margin_angstrom=5,seeds=[17,29,41],pose_count=5,exhaustiveness=4,timeout_s=600)


def test_actor_revisions_and_cursor(workbench):
    w,key=workbench
    first=w.scene(key,{'shot':'arrival'},0,'agent')
    user=w.scene(key,{'shot':'oblique'},0,'user')
    second=w.scene(key,{'shot':'pocket'},1,'agent')
    assert user['recipe']['revision']==1 and second['recipe']['revision']==2
    assert len(w.scenes(key))==3
    with pytest.raises(ValueError,match='Stale'): w.scene(key,{},1,'agent')
    replay=Workbench(w.j,w.run,w.experiment,w.project,first['sequence'])
    assert len(replay.scenes(key))==1
    with pytest.raises(ValueError,match='read-only'): replay.dispatch({'operation':'set_scene_view'})
    with pytest.raises(FileNotFoundError): Workbench(w.j,w.run,'other',w.project).source(key)
    with pytest.raises(FileNotFoundError): Workbench(w.j,w.run,w.experiment,'other')
    assert first['recipe']['camera']!=second['recipe']['camera']


def test_capture_countercheck_must_match(workbench):
    w,key=workbench
    with pytest.raises(ValueError,match='capture does not match'):
        w.dispatch({'operation':'measure','source_hash':key,'atom_ids':[],'capture_id':'fake'})
    from dnhacksbio.inhibitor.vision import capture
    with pytest.raises(ValueError,match='Stale'): capture(w,key,7,'agent',[1600,1000])
    with pytest.raises(ValueError,match='Viewport'): capture(w,key,0,'agent',[99999,99999])


def test_admission_idempotency_and_cancel(workbench,monkeypatch):
    w,key=workbench
    calls=[]
    def spawn(*a,**kw): calls.append(a);return SimpleNamespace(pid=123456789)
    monkeypatch.setattr('dnhacksbio.inhibitor.service.subprocess.Popen',spawn)
    a=w.start(key,spec(),'agent','unique')
    b=w.start(key,spec(),'agent','unique')
    assert a==b and len(calls)==1
    with pytest.raises(ValueError,match='different inputs'): w.start(key,{**spec(),'exhaustiveness':8},'agent','unique')
    assert w.cancel(a['job_id'],'user')['status']=='cancellation_requested'
    with pytest.raises(FileNotFoundError): w.cancel('outside','user')
    assert json.loads((w.directory/'jobs'/a['job_id']/'cancel.json').read_text())['actor']=='user'


@pytest.mark.parametrize('patch',[{'seeds':[True]},{'timeout_s':99999},{'margin_angstrom':float('nan')},
                                 {'repair_policy':'silent-delete'},{'water_policy':'guess'},{'exclude_additives':'all'}])
def test_invalid_protocol(patch):
    with pytest.raises(ValueError): validate_spec({**spec(),**patch})


def test_surface_coordinates_and_atom_identity():
    pytest.importorskip('scipy',reason='Install the inhibitor extra for scientific surface tests')
    from dnhacksbio.inhibitor.surface import accessible_surface
    g={'source_hash':'x','coordinate_frame':'canonical','atoms':[
        {'id':'a','kind':'polymer','element':'C','radius':1.7,'position':[0,0,0],'residue_id':'r'},
        {'id':'b','kind':'ligand','element':'C','radius':1.7,'position':[4,0,0],'residue_id':'l'}]}
    s=accessible_surface(g,'l')
    assert len(s['positions'])==len(s['triangle_atom_ids'])*3
    assert set(s['triangle_atom_ids'])=={'a'}
    import math
    assert all(math.dist(p,[0,0,0])==pytest.approx(3.1,abs=.06) for p in s['positions'])


def test_timeline_has_receipts_and_keeps_source_actor_cursor_scope(workbench):
    w,key=workbench
    first=w.scene(key,{'shot':'arrival'},0,'agent','Locate reference')
    w.event('scene.capture',{'source_hash':key,'image_hash':'image-a','recipe':first['recipe']})
    w.event('scene.vision',{'capture_id':'image-a','observation':'Visible reference'})
    w.event('scene.vision',{'capture_id':'outside','observation':'Must stay outside'})
    w.event('scene.measurement',{'source_hash':key,'value':2.7,'units':'Å','atom_ids':['a','b']})
    w.scene(key,{'shot':'oblique'},0,'user','User exploration')
    timeline=w.describe(key)['timeline']
    assert [e['kind'] for e in timeline]==['scene.changed','scene.capture','scene.vision','scene.measurement','scene.changed']
    assert timeline[3]['note']=='Measured 2.700 Å'
    assert timeline[2]['details']['observation']=='Visible reference'
    assert timeline[2]['recipe']==first['recipe']
    assert timeline[-1]['actor']=='user'
    historic=Workbench(w.j,w.run,w.experiment,w.project,first['sequence'])
    assert len(historic.describe(key)['timeline'])==1
