"""Read-only presentation of saved forecasting artifacts; never used as scorer input."""
from __future__ import annotations
import json
from hashlib import sha256
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

def _paths():
    base = ROOT / 'demo/forecasting'
    scenario = Path(os.environ.get('DNHACKS_FORECAST_SCENARIO', base / 'scenarios/civic-2018-2022/historical.json'))
    run = Path(os.environ.get('DNHACKS_FORECAST_RUN', base / 'runs/civic-2018-2022-greedy.json'))
    report = Path(os.environ.get('DNHACKS_FORECAST_REPORT', base / 'reports/civic-2018-2022.json'))
    return scenario, run, report

def _read(path: Path):
    return json.loads(path.read_text())

def _digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()

def _forecasts(rows):
    return rows[:30]

def demo_packet():
    scenario_path, run_path, report_path = _paths()
    if not scenario_path.exists() or not run_path.exists():
        return {'status': 'preparing', 'message': 'The historical replay is being prepared.'}
    scenario, run = _read(scenario_path), _read(run_path)
    if run.get('scenario_id') != scenario['id']:
        raise ValueError('Saved run and historical scenario do not match.')
    digest = _digest(scenario)
    if run.get('scenario_sha256') and run['scenario_sha256'] != digest:
        return {'status': 'preparing', 'message': 'The historical graph changed; its matching replay is being prepared.'}
    outcomes = _read(scenario_path.with_name('outcomes.json'))
    if outcomes['scenario_id'] != scenario['id']:
        raise ValueError('Later outcomes and historical scenario do not match.')
    events = []
    for event in run.get('events', []):
        event = dict(event)
        payload = dict(event.get('payload', {}))
        if 'forecasts' in payload:
            payload['forecasts'] = _forecasts(payload['forecasts'])
        event['payload'] = payload
        events.append(event)
    revisions = []
    for revision in run.get('revisions', []):
        revision = dict(revision)
        revision['forecasts'] = _forecasts(revision.get('forecasts', []))
        revisions.append(revision)
    presented_run = {key: value for key, value in run.items() if key not in ('comparisons', 'events', 'revisions', 'forecasts')}
    presented_run.update(events=events, revisions=revisions, forecasts=_forecasts(run['forecasts']), forecast_count=len(run['forecasts']))
    report = _read(report_path) if report_path.exists() else {}
    if 'models' in report:
        report = {**report, 'models': {name: {key: value for key, value in result.items() if key in ('overall', 'macro', 'metadata')} for name, result in report['models'].items()}}
    return {'status': 'ready', 'scenario': scenario, 'run': presented_run,
            'outcomes': outcomes['outcomes'], 'future_evidence': outcomes.get('evidence', []),
            'report': report,
            'artifact_url': '/api/forecasting/run',
            'presentation': {'forecast_limit': 30, 'description': 'Top ranks for playback; the full saved run is downloadable.'}}

def saved_run():
    return _read(_paths()[1])


def reasoning_packet():
    """The separate outcome evaluation is added only to completed model replays."""
    base = ROOT / 'demo/forecasting/reasoning/civic-model'
    path = base / 'comparison.json'
    if not path.exists():
        return {'status': 'preparing'}
    comparison = _read(path)
    scenario = _read(_paths()[0])
    if comparison['scenario_id'] != scenario['id']:
        raise ValueError('Model replay and historical scenario do not match.')
    if comparison.get('provenance', {}).get('historical_packet_sha256') not in (None, _digest(scenario)):
        return {'status': 'preparing'}
    evaluation_path = base / 'evaluation.json'
    return {'status': 'ready', 'comparison': comparison,
            'evaluation': _read(evaluation_path) if evaluation_path.exists() else None}
