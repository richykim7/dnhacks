import copy
import json
import pytest
from dnhacksbio.spindle.bundle import validate
from dnhacksbio.spindle.analysis import analyze_run, analyze_ensemble
from dnhacksbio.explorer.artifacts import collect
from dnhacksbio.explorer.runtime import Journal


def bundle():
    frames = [{'time':t,'poles':[{'id':str(i),'position':p} for i,p in enumerate(points)],'filaments':[]} for t,points in [
        (0, [[-5,0,0],[0,5,0],[5,0,0]]),
        (1, [[-5,0,0],[-4.5,0,0],[5,0,0]]),
        (3, [[-5,0,0],[-4.5,0,0],[5,0,0]]),
        (5, [[0,0,0],[.5,0,0],[.9,0,0]])]]
    return dict(schema_version=1,dimensionality=3,category='illustration',model_id='test',units={'length':'um','time':'s'},radius=[10,10,10],runs=[dict(seed=1,condition='control',frames=frames)])


def test_clustering_dwell_censoring_and_single_collapse():
    b=bundle();validate(json.dumps(b).encode())
    r=analyze_run(b['runs'][0],1,2)
    assert r['pole_counts']==[3,2,2,1]
    assert r['time_to_bipolar_s']==1 and r['bipolar_dwell_s']==2
    assert not r['right_censored']
    censored=analyze_run(b['runs'][0],1,3)
    assert censored['right_censored'] and censored['time_to_bipolar_s'] is None
    report=analyze_ensemble(b,dict(threshold_um=1,dwell_s=2,sensitivity_thresholds_um=[.1,2]))
    assert report['conditions']['control']['simulation_replicates']==1
    assert report['conditions']['control']['replicate_sd_s'] is None
    assert report['threshold_sensitivity']['0.1']==[3]


@pytest.mark.parametrize('mutate',[
    lambda b:b.update(dimensionality=True),
    lambda b:b['units'].update(length='nm'),
    lambda b:b['radius'].__setitem__(0,float('nan')),
    lambda b:b['runs'][0]['frames'][1].update(time=0),
    lambda b:b['runs'][0]['frames'][0]['poles'][1].update(id='0'),
    lambda b:b['runs'][0]['frames'][0].update(filaments=[{'id':'f','pole':'missing','points':[[0,0,0],[1,0,0]]}]),
    lambda b:b['runs'].append(copy.deepcopy(b['runs'][0])),
])
def test_invalid_geometry_and_identity(mutate):
    b=bundle();mutate(b)
    with pytest.raises(ValueError):validate(json.dumps(b).encode())


def test_planar_means_planar():
    b=bundle();b['dimensionality']=2
    validate(json.dumps(b).encode())
    b['runs'][0]['frames'][0]['poles'][0]['position'][2]=.1
    with pytest.raises(ValueError):validate(json.dumps(b).encode())


def test_collector_immutable_geometry_and_provenance(tmp_path):
    output=tmp_path/'output';output.mkdir();journal=Journal(tmp_path/'journal')
    raw=json.dumps(bundle()).encode();(output/'spindle.json').write_bytes(raw)
    entry=dict(kind='filament_trajectory',format='json',path='spindle.json',provenance=dict(category='illustration',source_ids=[],tool='fixture',tool_version='1'))
    (output/'manifest.json').write_text(json.dumps(dict(schema_version=1,artifacts=[entry])))
    artifact=collect(output,journal)[0]
    assert artifact['status']=='available'
    assert journal.read_blob(artifact['storage_key'])==raw
    entry['provenance']['category']='prediction'
    (output/'manifest.json').write_text(json.dumps(dict(schema_version=1,artifacts=[entry])))
    assert collect(output,journal)[0]['status']=='rejected'
    (output/'spindle.json').unlink();(output/'spindle.json').symlink_to(tmp_path/'outside')
    assert collect(output,journal)[0]['status']=='rejected'
