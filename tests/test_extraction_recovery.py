"""Integration checks for replay, source-backed repair, and extraction accounting."""
import asyncio
import copy

import pytest

from dnhacksbio.litmap import extract, repair
from dnhacksbio.litmap.schema import DeferralError


TEXT = 'EGFR increases KRAS activity. Cells were human epithelial cells.'


def claim(**changes):
    raw = {'subject': 'EGFR', 'subject_category': 'gene', 'predicate': 'increases',
           'object': 'KRAS', 'object_category': 'gene', 'object_aspect': 'activity',
           'quote': 'EGFR increases KRAS activity.'}
    raw.update(changes)
    return raw


@pytest.fixture(autouse=True)
def local_grounding(monkeypatch):
    def ground(surface, namespaces=None):
        names = {'EGFR': 'HGNC:3236', 'KRAS': 'HGNC:6407'}
        return {'curie': names[surface], 'label': surface, 'kind': 'entity'} if surface in names else None
    monkeypatch.setattr(extract.G, 'ground_curie', ground)
    monkeypatch.setattr(extract.G, 'resolve_process', lambda *args: None)
    monkeypatch.setattr(extract.G, 'process_candidates', lambda *args: [])
    monkeypatch.setattr(extract.G, 'entity_candidates', lambda *args, **kwargs: [])
    monkeypatch.setattr(extract.G, 'resolve_context_value', lambda *args: None)


def replay(raw, **kwargs):
    return asyncio.run(extract.extract_paper(TEXT, source_ref=17, source_label='Test2020',
        field='Cancer biology', direction_pass=False, raw_extraction=raw, **kwargs))


def test_replay_avoids_reader_and_preserves_input(monkeypatch):
    monkeypatch.setattr(extract.llm, 'Session', lambda **kw: pytest.fail('Reader must not run'))
    raw = {'claims': [claim()]}
    original = copy.deepcopy(raw)
    result = replay(raw)
    assert result['stats']['kept'] == 1 and result['stats']['repair_attempted'] == 0
    assert result['claims'][0].evidence[0].source_ref == 17
    assert raw == original


def test_failed_raw_and_reader_deferred_repaired_once_each(monkeypatch):
    observed = []
    async def fix(text, failures, *, validate, **kwargs):
        observed.extend(failures)
        corrected = claim()
        assert await validate(corrected) is None
        return {'accepted': [{'id': f['id'], 'raw': copy.deepcopy(corrected), 'original': f} for f in failures],
                'rejected': [], 'unresolved': [], 'audit': []}
    monkeypatch.setattr(repair, 'repair_claims', fix)
    result = replay({'claims': [claim(subject='misspelled')],
                     'deferred': [{'reason': 'Unable to represent', 'quote': TEXT}]})
    assert [f['id'] for f in observed] == ['claim:0', 'reader:0']
    assert result['stats']['repair_attempted'] == 2
    assert result['stats']['repaired'] == result['stats']['kept'] == 2
    assert result['stats']['deferred'] == 0
    assert all(c.evidence[0].extractor == extract.llm.SONNET for c in result['claims'])


def test_unresolved_is_single_failure_not_diagnostic_fanout(monkeypatch):
    async def fix(text, failures, **kwargs):
        return {'accepted': [], 'rejected': [], 'audit': [],
                'unresolved': [{'id': f['id'], 'original': f, 'last_raw': f['raw'],
                                'reason': 'No faithful representation'} for f in failures]}
    monkeypatch.setattr(repair, 'repair_claims', fix)
    result = replay({'claims': [claim(subject='unknown')]})
    assert result['stats']['deferred'] == 1
    assert result['deferrals'][0].raw['subject'] == 'unknown'
    assert result['deferrals'][0].reason == 'No faithful representation'


def test_context_warning_does_not_become_deferral():
    result = replay({'claims': [claim(context={'not_a_slot': {'value': 'x'}})]}, repair=False)
    assert result['stats']['kept'] == 1
    assert result['stats']['warnings'] == 1
    assert result['stats']['deferred'] == 0


def test_initial_unsupported_quote_is_not_retained():
    result = replay({'claims': [claim(quote='Invented result.')]}, repair=False)
    assert result['stats']['kept'] == 0
    assert result['stats']['deferred'] == 1
    assert 'quote' in result['deferrals'][0].reason.lower()


def test_repair_validator_supplies_category_and_source_errors(monkeypatch):
    async def fix(text, failures, *, validate, **kwargs):
        assert 'category' in (await validate(claim(subject_category='invented_category'))).lower()
        assert 'quote' in (await validate(claim(quote='Invented result.'))).lower()
        return {'accepted': [], 'rejected': [], 'unresolved': [], 'audit': []}
    monkeypatch.setattr(repair, 'repair_claims', fix)
    replay({'claims': [claim(subject_category='invented_category')]})


def test_strict_unknown_category_and_cross_owner_grounding():
    with pytest.raises(DeferralError, match='category'):
        extract._entity('EGFR', None, 'unknown_category')
    with pytest.raises(DeferralError, match='outside owner'):
        extract._entity('EGFR', None, 'chemical')


def test_resolution_keys_separate_owner_and_species():
    human = extract._resolution_key('migration', 'process', '9606')
    mouse = extract._resolution_key('migration', 'process', '10090')
    pathology = extract._resolution_key('migration', 'pathological_process', '9606')
    assert len({human, mouse, pathology}) == 3


def test_direction_failure_is_repaired_during_replay(monkeypatch):
    class AuditSession:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *exc):
            pass
        async def ask(self, prompt):
            return '{"wrong_sign": [0], "swapped": [], "unsure": []}'
    monkeypatch.setattr(extract.llm, 'Session', lambda **kwargs: AuditSession())
    async def fix(text, failures, *, validate, **kwargs):
        assert len(failures) == 1 and 'wrong_sign' in failures[0]['reason']
        corrected = claim()
        assert await validate(corrected) is None
        return {'accepted': [{'id': failures[0]['id'], 'raw': corrected, 'original': failures[0]}],
                'rejected': [], 'unresolved': [], 'audit': []}
    monkeypatch.setattr(repair, 'repair_claims', fix)
    result = asyncio.run(extract.extract_paper(TEXT, source_ref=17, field='Cancer biology',
        raw_extraction={'claims': [claim(predicate='decreases')]}, direction_pass=True))
    assert result['stats']['kept'] == 1
    assert result['stats']['repaired'] == 1
    assert result['claims'][0].spine.predicate == 'increases'


def test_fabricated_experiment_is_never_stored():
    result = replay({'claims': [claim(experiment={'unit': 'cells', 'n': 900,
        'effect': '900-fold increase', 'quote': 'A fabricated assay showed a 900-fold increase in 900 cells.'})]}, repair=False)
    assert not result['experiments'], 'A real claim quote must not validate a fabricated experiment quote'


def test_repair_cannot_guess_integer_experiment_reference(monkeypatch):
    async def fix(text, failures, *, validate, **kwargs):
        error = await validate(claim(experiment=0))
        assert error and 'experiment' in error.lower()
        assert await validate(claim()) is None
        return {'accepted': [], 'rejected': [], 'unresolved': [], 'audit': []}
    monkeypatch.setattr(repair, 'repair_claims', fix)
    replay({'claims': [claim(subject='unknown')],
            'experiments': [{'quote': 'EGFR increases KRAS activity.', 'readout': 'activity'}]})


def test_completed_paper_audit_is_atomic_and_survives_later_failure(monkeypatch, tmp_path):
    import json
    from pathlib import Path
    from dnhacksbio.litmap import corpus_build
    from dnhacksbio.litmap.ingest import Document

    audit_dir = tmp_path / 'run1'
    published = asyncio.Event()
    replacements = []
    real_replace = Path.replace

    def inspect_replace(path, target):
        if path.name.endswith('.json.tmp'):
            assert json.loads(path.read_text())['source_ref'] == 1
            assert not target.exists()
            replacements.append((path.name, target.name))
        return real_replace(path, target)

    monkeypatch.setattr(Path, 'replace', inspect_replace)

    class Progress:
        def emit(self, stage, status, message, **kwargs):
            if status == 'progress':
                assert json.loads((audit_dir / '1.json').read_text())['stats']['kept'] == 1
                published.set()

    async def fake_extract(text, *, source_ref, **kwargs):
        if source_ref == 2:
            await asyncio.wait_for(published.wait(), timeout=2)
            assert (audit_dir / '1.json').is_file()
            raise RuntimeError('later paper failed')
        return {'claims': [{}], 'experiments': [], 'deferrals': [], 'stats': {'kept': 1},
                'repair_audit': {'accepted': [{'id': 'claim:0'}]}, 'warnings': []}

    monkeypatch.setattr(extract, 'extract_paper', fake_extract)
    docs = [Document(ref=i, label=f'Test{i}', ext='txt', path='', text=TEXT, n_chars=len(TEXT))
            for i in (1, 2)]
    results = asyncio.run(corpus_build._extract_with_progress(docs, 2, Progress(), audit_dir=audit_dir))
    assert results[2]['claims'] == []
    assert json.loads((audit_dir / '1.json').read_text())['repair']['accepted'] == [{'id': 'claim:0'}]
    assert replacements == [('1.json.tmp', '1.json')]
    assert not list(audit_dir.glob('*.tmp'))


def test_distinct_audit_runs_do_not_mix_stale_refs(monkeypatch, tmp_path):
    import json
    from dnhacksbio.litmap import corpus_build
    from dnhacksbio.litmap.ingest import Document

    class Progress:
        def emit(self, *args, **kwargs):
            pass

    async def fake_extract(text, *, source_ref, **kwargs):
        return {'claims': [], 'experiments': [], 'deferrals': [], 'stats': {'raw': source_ref}}

    monkeypatch.setattr(extract, 'extract_paper', fake_extract)
    def build_run(dirname, refs):
        docs = [Document(ref=i, label=str(i), ext='txt', path='', text=TEXT, n_chars=len(TEXT)) for i in refs]
        asyncio.run(corpus_build._extract_with_progress(docs, 2, Progress(), audit_dir=tmp_path / dirname))
    build_run('older', [1, 2])
    older = (tmp_path / 'older' / '1.json').read_bytes()
    build_run('newer', [1])
    assert sorted(p.name for p in (tmp_path / 'newer').iterdir()) == ['1.json']
    assert (tmp_path / 'older' / '1.json').read_bytes() == older
    assert json.loads((tmp_path / 'older' / '2.json').read_text())['source_ref'] == 2


def test_repair_validation_suggests_supplement_category(monkeypatch):
    async def fix(text, failures, *, validate, **kwargs):
        error = await validate(claim(object='mitochondrial respiration', object_category='process', object_aspect=''))
        assert 'mitochondrial respiration' in error
        assert 'cellular_phenotype' in error
        return {'accepted': [], 'rejected': [], 'unresolved': [], 'audit': []}
    monkeypatch.setattr(repair, 'repair_claims', fix)
    replay({'claims': [claim(subject='unknown')]})
