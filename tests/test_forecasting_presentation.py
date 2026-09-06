"""Saved replay presentation preserves analytical commitments and provenance."""
import json
from hashlib import sha256
import pytest
from dnhacksbio.webui import forecasting

@pytest.fixture
def artifacts(monkeypatch,tmp_path):
    scenario={'id':'dated','nodes':[],'claims':[],'evidence':[],'candidates':[]}
    digest=sha256(json.dumps(scenario,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    forecasts=[{'candidate_id':f'c{i}','score':40-i} for i in range(40)]
    run={'scenario_id':'dated','scenario_sha256':digest,'origin':'computed','forecasts':forecasts,'events':[{'seq':0,'type':'forecast_recorded','payload':{'forecasts':forecasts}}],'revisions':[{'revision':0,'forecasts':forecasts}]}
    outcomes={'scenario_id':'dated','outcomes':[{'candidate_id':'c2','observed':True,'evidence_ids':['future']}],'evidence':[{'id':'future','title':'Later publication'}]}
    paths=[tmp_path/'historical.json',tmp_path/'run.json',tmp_path/'report.json']
    for path,value in [(paths[0],scenario),(paths[1],run),(tmp_path/'outcomes.json',outcomes),(paths[2],{'models':{'baseline':{'overall':{'average_precision':.2},'ranking':[1,2],'metadata':{'budget':'fixed'}}}})]:path.write_text(json.dumps(value))
    monkeypatch.setattr(forecasting,'_paths',lambda:tuple(paths))
    return paths,run

def test_presenter_keeps_frozen_ranks_and_full_download(artifacts):
    paths,original=artifacts
    packet=forecasting.demo_packet()
    assert packet['run']['forecasts']==original['forecasts'][:30]
    assert packet['run']['forecast_count']==40
    assert packet['run']['revisions'][0]['forecasts']==original['forecasts'][:30]
    assert packet['future_evidence'][0]['id']=='future'
    assert packet['scenario']['evidence']==[]
    assert packet['report']['models']['baseline']=={'overall':{'average_precision':.2},'metadata':{'budget':'fixed'}}
    assert forecasting.saved_run()==original
    assert json.loads(paths[1].read_text())==original

def test_changed_graph_requires_matching_run(artifacts):
    paths,_=artifacts
    scenario=json.loads(paths[0].read_text());scenario['nodes']=[{'id':'new'}];paths[0].write_text(json.dumps(scenario))
    packet=forecasting.demo_packet()
    assert packet['status']=='preparing'
    assert 'run' not in packet and 'future_evidence' not in packet

def test_unrelated_outcomes_rejected(artifacts):
    paths,_=artifacts
    paths[0].with_name('outcomes.json').write_text(json.dumps({'scenario_id':'other'}))
    with pytest.raises(ValueError,match='Later outcomes'):forecasting.demo_packet()

def test_missing_replay_reports_preparation(artifacts):
    paths,_=artifacts;paths[1].unlink()
    assert forecasting.demo_packet()['status']=='preparing'


def test_model_presenter_keeps_evaluation_separate(artifacts, monkeypatch, tmp_path):
    paths, _ = artifacts
    monkeypatch.setattr(forecasting, 'ROOT', tmp_path)
    base = tmp_path / 'demo/forecasting/reasoning/civic-model'
    base.mkdir(parents=True)
    comparison = {'scenario_id': 'dated', 'origin': 'model', 'conditions': {}}
    (base / 'comparison.json').write_text(json.dumps(comparison))
    assert forecasting.reasoning_packet() == {'status': 'ready', 'comparison': comparison, 'evaluation': None, 'study': None}
    evaluation = {'evaluation_status': 'no_positive_cohort', 'models': {}}
    (base / 'evaluation.json').write_text(json.dumps(evaluation))
    packet = forecasting.reasoning_packet()
    assert packet['evaluation'] == evaluation
    assert 'evaluation' not in packet['comparison']


def test_study_progress_does_not_require_or_expose_unsealed_evaluation(artifacts, monkeypatch, tmp_path):
    paths, _ = artifacts
    scenario = json.loads(paths[0].read_text())
    monkeypatch.setenv('DNHACKS_FORECAST_STUDY', str(tmp_path))
    manifest = {'historical_packet_sha256': forecasting._digest(scenario), 'candidate_count': 40,
                'budget': {'output_tokens': 6000}, 'queries': [{'query_id': 'q1', 'file': 'q1.json'}, {'query_id': 'q2', 'file': 'q2.json'}]}
    (tmp_path / 'manifest.json').write_text(json.dumps(manifest))
    (tmp_path / 'q1.json').write_text(json.dumps({'query_id': 'q1'}))
    (tmp_path / 'q2.json').write_text('{')
    (tmp_path / 'evaluation.json').write_text(json.dumps({'coverage': {'complete_queries': 1}}))
    packet = forecasting.study_packet(scenario)
    assert packet == {'status': 'running', 'planned_queries': 2, 'saved_queries': 1, 'planned_candidates': 40, 'requested_output_tokens': 6000}
    (tmp_path / 'sealed.json').write_text('{}')
    assert forecasting.study_packet(scenario)['evaluation']['coverage']['complete_queries'] == 1
    scenario['nodes'] = [{'id': 'changed'}]
    assert forecasting.study_packet(scenario) is None
