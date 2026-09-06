import asyncio
import json

import pytest

from dnhacksbio.litmap import repair


class FakeSession:
    def __init__(self, responses, prompts):
        self.responses = iter(responses)
        self.prompts = prompts

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        pass

    async def ask(self, prompt):
        self.prompts.append(prompt)
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return json.dumps(response)


def setup_session(monkeypatch, responses):
    prompts = []
    monkeypatch.setattr(repair, "_session", lambda model, cwd: FakeSession(responses, prompts))
    return prompts


def run(failures, validate=lambda raw: None, **kwargs):
    return asyncio.run(repair.repair_claims("A raises B. C lowers D.", failures,
                                           validate=validate, instructions="Closed schema.", **kwargs))


def test_quote_support_requires_order_and_content():
    assert repair.quote_supported("A raises\n B... C lowers D.", "A raises B. C lowers D.")
    assert repair.quote_supported("A raises B […] C lowers", "A raises B. C lowers D.")
    assert not repair.quote_supported("C lowers...A raises", "A raises B. C lowers D.")
    assert not repair.quote_supported("...", "A raises B.")
    assert not repair.quote_supported("A lowers B.", "A raises B.")


def test_retry_uses_validator_feedback_and_preserves_original(monkeypatch):
    prompts = setup_session(monkeypatch, [
        {"results": [{"id": "0", "status": "corrected", "raw": {"quote": "A raises B.", "subject": "wrong"}}]},
        {"results": [{"id": "0", "status": "corrected", "raw": {"quote": "A raises B.", "subject": "A"}}]},
    ])
    failure = {"id": 12, "raw": {"subject": "original"}, "reason": "unknown name"}

    async def validate(raw):
        if raw['subject'] != 'A':
            raise ValueError("Allowed subject: A")

    result = run([failure], validate=validate)
    assert result['accepted'][0]['raw']['subject'] == 'A'
    assert result['accepted'][0]['original'] == failure
    assert failure['raw']['subject'] == 'original'
    assert 'Allowed subject: A' in prompts[1]
    assert result['accepted'][0]['round'] == 2


def test_unsupported_quote_never_reaches_validator(monkeypatch):
    setup_session(monkeypatch, [{"results": [{"id": "0", "status": "corrected", "raw": {"quote": "invented"}}]}] * 2)
    calls = []
    result = run([{'id': 'x', 'raw': {}, 'reason': 'bad'}], validate=lambda raw: calls.append(raw))
    assert not calls and not result['accepted']
    assert 'Quote' in result['unresolved'][0]['reason']


def test_missing_duplicate_and_malformed_results_are_not_lost(monkeypatch):
    setup_session(monkeypatch, [{'results': 'bad'}, {'results': [
        {'id': '0', 'status': 'corrected', 'raw': {'quote': 'A raises B.'}},
        {'id': '0', 'status': 'corrected', 'raw': {'quote': 'A raises B.'}},
    ]}])
    result = run([{'id': 0, 'raw': {}, 'reason': 'x'}, {'id': 1, 'raw': {}, 'reason': 'x'}])
    assert [r['id'] for r in result['unresolved']] == [0, 1]
    assert len(result['audit']) == 2


def test_limitations_cannot_be_silently_rejected(monkeypatch):
    setup_session(monkeypatch, [
        {'results': [{'id': '0', 'status': 'rejected', 'reason': 'No ontology term'}]},
        {'results': [{'id': '0', 'status': 'unresolved', 'reason': 'Schema lacks structural phenotype'}]},
    ])
    result = run([{'id': 3, 'raw': {}, 'reason': 'x'}])
    assert not result['rejected']
    assert result['unresolved'][0]['reason'] == 'Schema lacks structural phenotype'


def test_explicit_nonclaim_rejection_and_service_failure(monkeypatch):
    setup_session(monkeypatch, [{'results': [{'id': '0', 'status': 'rejected', 'rejection_kind': 'nonclaim', 'reason': 'Section heading only'}]}])
    result = run([{'id': 3, 'raw': {}, 'reason': 'x'}])
    assert result['rejected'][0]['reason'] == 'Section heading only'
    setup_session(monkeypatch, [RuntimeError('quota')])
    result = run([{'id': 3, 'raw': {}, 'reason': 'x'}])
    assert 'quota' in result['unresolved'][0]['reason']


def test_groups_bounded_and_ids_unique():
    failures = [{'id': i, 'raw': {}, 'reason': 'same'} for i in range(19)]
    assert [len(group) for group in repair._groups(failures)] == [10, 9]
    with pytest.raises(ValueError, match='unique'):
        run([failures[0], failures[0]])
    with pytest.raises(ValueError, match='positive'):
        run([], max_concurrency=0)


def test_session_disables_all_model_tools(monkeypatch):
    options = []
    monkeypatch.setattr(repair.llm, 'ClaudeSDKClient', lambda opts: options.append(opts))
    repair._session('claude-sonnet-5', '/tmp/empty-repair-test')
    opt = options[-1]
    assert opt.model == 'claude-sonnet-5'
    assert all(option.effort == 'medium' for option in options)
    assert opt.tools == [] and opt.mcp_servers == {} and opt.strict_mcp_config
    assert opt.skills == [] and opt.setting_sources == []
    assert opt.cwd == '/tmp/empty-repair-test'
    assert json.loads(opt.settings)['disableAllHooks']


def test_concurrency_is_bounded_and_outputs_keep_input_order(monkeypatch):
    state = {'active': 0, 'peak': 0}

    class DelayedSession:
        async def __aenter__(self):
            state['active'] += 1
            state['peak'] = max(state['peak'], state['active'])
            return self

        async def __aexit__(self, *exc):
            state['active'] -= 1

        async def ask(self, prompt):
            await asyncio.sleep(0.005)
            records = json.loads(prompt.split('FAILED CLAIMS (ids are local to this group)\n', 1)[1])
            return json.dumps({'results': [{'id': row['id'], 'status': 'corrected',
                                           'raw': {'quote': 'A raises B.'}} for row in records]})

    monkeypatch.setattr(repair, '_session', lambda *args: DelayedSession())
    failures = [{'id': i, 'raw': {}, 'reason': str(i)} for i in range(20)]
    result = run(failures, max_concurrency=2)
    assert state['peak'] == 2 and state['active'] == 0
    assert [r['id'] for r in result['accepted']] == list(range(20))


@pytest.mark.parametrize('count, expected_sessions', [(1, 1), (10, 1), (11, 2), (80, 8)])
def test_unique_failed_terms_use_at_most_ten_records_per_session(monkeypatch, count, expected_sessions):
    sessions = []

    class AcceptSession:
        def __init__(self):
            self.prompts = []
            sessions.append(self)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            pass

        async def ask(self, prompt):
            self.prompts.append(prompt)
            rows = json.loads(prompt.split('FAILED CLAIMS (ids are local to this group)\n', 1)[1])
            return json.dumps({'results': [{'id': row['id'], 'status': 'corrected',
                                           'raw': row['raw']} for row in rows]})

    monkeypatch.setattr(repair, '_session', lambda *args: AcceptSession())
    failures = [{'id': i, 'reason': f"unknown 'TERM{i}'", 'raw': {
        'subject': f'TERM{i}', 'subject_category': 'gene', 'quote': 'A raises B.'}}
        for i in range(count)]
    result = run(failures)
    assert len(sessions) == expected_sessions
    assert all(len(session.prompts) == 1 for session in sessions)
    assert all(len(json.loads(session.prompts[0].split(
        'FAILED CLAIMS (ids are local to this group)\n', 1)[1])) <= 10 for session in sessions)
    assert [row['id'] for row in result['accepted']] == list(range(count))
    assert [row['raw']['subject'] for row in result['accepted']] == [f'TERM{i}' for i in range(count)]
    assert not result['unresolved'] and not result['rejected']
    assert [row['original'] for row in result['accepted']] == failures


def test_quote_first_retry_retrieves_context_only_for_pending_correction(monkeypatch):
    prompts = setup_session(monkeypatch, [
        {'results': [
            {'id': '0', 'status': 'corrected', 'raw': {'quote': 'A raises B.', 'subject': 'A'}},
            {'id': '1', 'status': 'corrected', 'raw': {'quote': 'C lowers D.', 'subject': 'wrong'}}]},
        {'results': [{'id': '1', 'status': 'corrected', 'raw': {'quote': 'C lowers D.', 'subject': 'C'}}]},
    ])
    failures = [{'id': 'accepted-first', 'reason': 'bad A',
                 'raw': {'subject': 'original A', 'quote': 'A raises B.'}},
                {'id': 'pending-second', 'reason': 'bad C',
                 'raw': {'subject': 'original C', 'quote': 'C lowers D.'}}]

    def validate(raw):
        return 'Use canonical subject C' if raw['subject'] == 'wrong' else None

    irrelevant = 'Unrelated background paragraph. ' * 500
    source = irrelevant + '\n\nA raises B. C lowers D. Nearby assay context.\n\n' + irrelevant
    instructions = 'Unique closed schema instructions.'
    result = asyncio.run(repair.repair_claims(source, failures, validate=validate, instructions=instructions))
    assert len(prompts) == 2
    assert source not in prompts[0] and irrelevant not in prompts[0]
    assert instructions in prompts[0] and 'FULL SOURCE' not in prompts[0]
    initial = json.loads(prompts[0].split('FAILED CLAIMS (ids are local to this group)\n', 1)[1])
    assert all('source_context' not in row for row in initial)
    assert [row['raw']['quote'] for row in initial] == ['A raises B.', 'C lowers D.']
    assert source not in prompts[1] and instructions not in prompts[1]
    assert 'FULL SOURCE' not in prompts[1] and 'SCHEMA INSTRUCTIONS' not in prompts[1]
    pending = json.loads(prompts[1].split('FAILED CLAIMS (ids are local to this group)\n', 1)[1])
    assert len(pending) == 1
    assert all('original' not in row and 'original_raw' not in row for row in initial + pending)
    assert result['accepted'][1]['original'] == failures[1]
    assert pending[0]['raw']['subject'] == 'wrong'
    assert pending[0]['validation_errors'] == ['Use canonical subject C']
    assert 'Nearby assay context.' in pending[0]['source_context']
    assert len(pending[0]['source_context']) <= 4000
    assert 'accepted-first' not in prompts[1]
    assert [(r['id'], r['round']) for r in result['accepted']] == [('accepted-first', 1), ('pending-second', 2)]


def test_missing_quote_retrieves_bounded_local_passage_without_full_paper(monkeypatch):
    quote = 'KINASE_X increases TARGET_Y.'
    prompts = setup_session(monkeypatch, [{'results': [
        {'id': '0', 'status': 'corrected', 'raw': {'subject': 'KINASE_X', 'quote': quote}}]}])
    background = 'Unrelated background information. ' * 500
    source = background + '\n\n' + quote + ' This was measured in an assay.\n\n' + background
    failure = {'id': 1, 'reason': 'reader omitted quotation',
               'raw': {'subject': 'KINASE_X', 'object': 'TARGET_Y'}}
    result = asyncio.run(repair.repair_claims(source, [failure], validate=lambda raw: None,
                                            instructions='Closed schema.'))
    rows = json.loads(prompts[0].split('FAILED CLAIMS (ids are local to this group)\n', 1)[1])
    assert quote in rows[0]['source_context']
    assert len(rows[0]['source_context']) <= 4000
    assert background not in prompts[0] and source not in prompts[0]
    assert len(result['accepted']) == 1 and not result['unresolved']


def test_quote_from_another_source_cannot_pass_local_validation(monkeypatch):
    setup_session(monkeypatch, [{'results': [{'id': '0', 'status': 'corrected',
                   'raw': {'quote': 'C lowers D.', 'source_ref': 999}}]}] * 2)
    calls = []
    result = asyncio.run(repair.repair_claims('A raises B.',
        [{'id': 1, 'raw': {'quote': 'A raises B.'}, 'reason': 'bad category'}],
        validate=lambda raw: calls.append(raw), instructions='Closed schema.'))
    assert not calls and not result['accepted']
    assert 'Quote' in result['unresolved'][0]['reason']


def test_ambiguous_perturbation_includes_local_intervention_context(monkeypatch):
    quote = "PIKfyve perturbation increased PtdIns3P."
    source = "We used pharmacological inhibition of PIKfyve. " + quote + "\n\n" + "Unrelated background. " * 400
    prompts = setup_session(monkeypatch, [{"results": [{"id": "0", "status": "corrected",
        "raw": {"quote": quote, "subject": "PIKFYVE", "predicate": "decreases"}}]}])
    failures = [{"id": 1, "reason": "unknown name", "raw": {"quote": quote}}]
    result = asyncio.run(repair.repair_claims(source, failures, validate=lambda raw: None, instructions="Schema"))
    record = json.loads(prompts[0].split("FAILED CLAIMS (ids are local to this group)\n", 1)[1])[0]
    assert "pharmacological inhibition" in record["source_context"]
    assert source not in prompts[0]
    assert len(result["accepted"]) == 1


def test_queued_session_preserves_schema_on_retry_and_source_owner_without_model(monkeypatch):
    from dnhacksbio.litmap import repair_queue

    submitted = []

    async def fake_submit(socket_path, owner, records, instructions):
        submitted.append((socket_path, owner, records, instructions))
        assert len({row['id'] for row in records}) == len(records)
        assert all(row['source_owner'] == owner for row in records)
        assert all('original' not in row and 'original_raw' not in row for row in records)
        return [{'id': row['id'], 'status': 'corrected', 'raw': {
            'quote': row['raw']['quote'],
            'subject': 'wrong' if row['id'] == '1' and len(submitted) == 1 else 'fixed'}}
            for row in records]

    def no_model(*args, **kwargs):
        raise AssertionError('Queue client must not open a model session')

    monkeypatch.setattr(repair_queue, 'submit', fake_submit)
    monkeypatch.setattr(repair.llm, 'Session', no_model)
    monkeypatch.setenv('DNHACKS_REPAIR_SOCKET', '/tmp/test-repair.sock')
    monkeypatch.setenv('DNHACKS_REPAIR_OWNER', 'paper-17')
    failures = [
        {'id': 'already-accepted', 'raw': {'quote': 'A raises B.'}, 'reason': 'name'},
        {'id': 'needs-retry', 'raw': {'quote': 'C lowers D.'}, 'reason': 'name',
         'original_raw': {'quote': 'Old audit-only quotation'}}]
    result = run(failures, validate=lambda raw: 'Use fixed' if raw['subject'] == 'wrong' else None)
    assert len(submitted) == 2
    assert [len(call[2]) for call in submitted] == [2, 1]
    assert [row['id'] for row in submitted[1][2]] == ['1']
    assert all(call[0] == '/tmp/test-repair.sock' and call[1] == 'paper-17' for call in submitted)
    assert [call[3] for call in submitted] == ['Closed schema.', 'Closed schema.']
    assert submitted[1][2][0]['validation_errors'] == ['Use fixed']
    assert [row['id'] for row in result['accepted']] == ['already-accepted', 'needs-retry']
    assert [row['original'] for row in result['accepted']] == failures
