import copy
import pytest
from dnhacksbio.spindle.display import display_stream
from dnhacksbio.spindle.protocol import digest


def bundle():
    frames = [{'time': t, 'poles': [{'id': 'C1', 'position': [t, 0, 0]}],
               'filaments': [{'id': 'F1', 'pole': 'C1', 'points': [[t, 0, 0], [t, 1, 0]]}],
               'cortical_motors': [{'id': 'M1', 'position': [5, 0, 0], 'filament': 'F1', 'force_pn': [1, 0, 0], 'abscissa_um': .5}]}
              for t in range(9)]
    return {'schema_version': 1, 'dimensionality': 3, 'category': 'simulation', 'model_id': 'test',
            'units': {'length': 'um', 'time': 's'}, 'radius': [5, 5, 5],
            'runs': [{'seed': 1, 'condition': 'control', 'frames': frames}]}


def test_display_sampling_preserves_source_and_every_selected_entity():
    full = bundle(); before = copy.deepcopy(full)
    assert display_stream(full) is full
    shown = display_stream(full, max_points=6)
    assert shown['display_sampling']['source_frame_indices'] == [[0, 4, 8]]
    assert shown['display_sampling']['source_trajectory_sha256'] == digest(full)
    assert full == before
    assert shown['runs'][0]['frames'] == [full['runs'][0]['frames'][i] for i in [0, 4, 8]]
    with pytest.raises(ValueError, match='First/last'):
        display_stream(full, max_points=3)


def test_source_mapping_rejects_missing_or_reordered_frames():
    from dnhacksbio.spindle.bundle import validate
    from dnhacksbio.spindle.protocol import canonical
    shown = display_stream(bundle(), max_points=6)
    for indices in [[0, 8, 4], [1, 4, 8], [0, 4, 9]]:
        damaged = copy.deepcopy(shown)
        damaged['display_sampling']['source_frame_indices'][0] = indices
        with pytest.raises(ValueError, match='source frame'):
            validate(canonical(damaged))


def test_native_athermal_job_keeps_full_chunks_and_metrics_when_display_is_sampled(tmp_path, monkeypatch):
    import json
    import os
    from pathlib import Path
    from test_spindle import protocol
    from dnhacksbio.spindle import display
    from dnhacksbio.spindle.jobs import SpindleStore
    from dnhacksbio.spindle.protocol import CYTOSIM_COMMIT
    binary = os.environ.get('SPINDLE_CYTOSIM_BIN')
    if not binary:
        pytest.skip('Operator-pinned Cytosim build required')
    p = protocol()
    p['parameters']['thermal_energy_pn_um']['value'] = 0
    p['parameters']['duration_s']['value'] = .04
    original = display.display_stream
    def bounded_display(full):
        cap = sum(len(f['points']) for run in full['runs'] for frame in (run['frames'][0], run['frames'][-1]) for f in frame['filaments'])
        return original(full, max_points=cap)
    monkeypatch.setattr(display, 'display_stream', bounded_display)
    build = {'solver_commit': CYTOSIM_COMMIT, 'dimensionality': 3,
             **{name+'_sha256': digest((Path(binary)/name).read_bytes()) for name in ('sim','report')}}
    store = SpindleStore(tmp_path/'jobs'); scope = {'project_id':'p','run_id':'r','experiment_id':'sampled'}
    receipt = store.run_spindle_experiment(p, scope=scope, idempotency_key='sampled', budget={'wall_seconds':30,'artifact_bytes':2000000})['receipt']
    result = store.execute(receipt, scope, sim=Path(binary)/'sim', report=Path(binary)/'report', build_manifest=build)
    assert result['state'] == 'completed', result
    def read(name):
        key = next(a['hash'] for a in result['artifacts'] if a['name'] == name)
        return json.loads(store.read_blob(receipt, scope, key))
    shown = read('trajectory.json'); chunks = read('chunks/index.json'); metrics = read('metrics.json')
    assert shown['display_sampling']['source_frame_counts'] == [5,5]
    assert all(len(r['frames']) == 2 for r in shown['runs'])
    assert all(len(r['frames']) == 5 for r in chunks['runs'])
    assert all(len(r['pole_counts']) == 5 for r in metrics['runs'])

    from dnhacksbio.spindle.chunks import decode_frame
    restored = {k:v for k,v in shown.items() if k not in {'runs','display_sampling'}}
    restored['runs'] = []
    for run in chunks['runs']:
        frames = []
        for frame in run['frames']:
            key = next(a['hash'] for a in result['artifacts'] if a['name'] == 'chunks/' + frame['path'])
            frames.append(decode_frame(frame, store.read_blob(receipt, scope, key)))
        restored['runs'].append({'seed':run['seed'],'condition':run['condition'],'frames':frames})
    assert digest(restored) == shown['display_sampling']['source_trajectory_sha256']
