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
    assert [len(group) for group in repair._groups(failures)] == [8, 8, 3]
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
            return json.dumps({'results': [{'id': '0', 'status': 'corrected', 'raw': {'quote': 'A raises B.'}}]})

    monkeypatch.setattr(repair, '_session', lambda *args: DelayedSession())
    failures = [{'id': i, 'raw': {}, 'reason': str(i)} for i in range(6)]
    result = run(failures, max_concurrency=2)
    assert state['peak'] == 2 and state['active'] == 0
    assert [r['id'] for r in result['accepted']] == list(range(6))
