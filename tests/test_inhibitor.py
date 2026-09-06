from pathlib import Path
import math

import pytest

from dnhacksbio.inhibitor import normalize, measure, audit_pose, preparation_audit


def test_reference_geometry_and_identity():
    raw = (Path(__file__).parents[1] / 'frontend/e2e/inhibitor/3vqu.cif').read_bytes()
    g = normalize(raw, 'cif')
    assert len({a['id'] for a in g['atoms']}) == len(g['atoms'])
    a, b = g['atoms'][:2]
    result = measure(g, [a['id'], b['id']])
    assert result['value'] == pytest.approx(math.dist(a['position'], b['position']), abs=.01)
    assert result['coordinate_frame'] == 'canonical'
    ligand = next(r for r in g['residues'] if r['kind'] == 'ligand')
    contacts = audit_pose(g, ligand['id'])
    assert all(c['distance'] <= 4 for c in contacts['contacts'])
    assert preparation_audit(g)['status'] == 'blocked'
    with pytest.raises(ValueError, match='hash mismatch'):
        normalize(raw, 'cif', '0' * 64)
    with pytest.raises(ValueError, match='Unknown atom'):
        measure(g, [a['id'], 'missing'])


def test_empty_structure_rejected():
    with pytest.raises(ValueError, match='No atoms'):
        normalize(b'END\n', 'pdb')


def test_geometry_scope_and_playback(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from dnhacksbio.explorer.runtime import Journal
    from dnhacksbio.webui import data, runtime

    monkeypatch.setattr(data, 'PROCESSED', tmp_path)
    j = Journal(tmp_path)
    j.register('study', 'Geometry test', project='alpha')
    j.register('study~1', 'Geometry test', project='alpha')
    raw = (Path(__file__).parents[1] / 'frontend/e2e/inhibitor/3vqu.cif').read_text()
    blob = j.blob(raw)
    j.append('study', 'a', 'experiment.queued', {'title':'Geometry test'}, experiment_id='exp')
    j.append('study', 'a', 'artifact', {**blob, 'kind':'molecular_structure',
             'format':'cif', 'status':'available'}, producer='collector', experiment_id='exp')
    handler = SimpleNamespace(_project_arg=lambda qs: qs.get('project', [None])[0], _send_json=lambda x:x)
    path = f"study/geometry/{blob['storage_key']}"
    assert runtime.handle(handler, path, {'project':['alpha']})['source_hash'] == blob['storage_key']
    for scoped_path, qs in [(path, {'project':['beta']}), (path, {'through':['0']}),
                            (path.replace('study/', 'study~1/'), {})]:
        with pytest.raises(FileNotFoundError):
            runtime.handle(handler, scoped_path, qs)
