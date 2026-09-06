"""Synthetic queue-to-outcome integrations; never invoke a real assessor or research model."""
import asyncio
import copy
import json
import sqlite3
import threading
import time
from types import SimpleNamespace

import pytest

from dnhacksbio.branch_monitoring import receipt_outcomes as adapters
from dnhacksbio.branch_monitoring.outcomes import prepare, adjudicate, workflow
from dnhacksbio.branch_monitoring.store import MonitorStore, canonical, digest
from dnhacksbio.explorer.control import ControlStore
from dnhacksbio.explorer.runtime import Journal
from dnhacksbio.explorer.private_experiments import dispatch, METHODS
from dnhacksbio.experiment_transport import make_server
from test_branch_monitoring import protocol
from test_branch_outcomes import finish
from test_dependency_scoring import registration


def queue_fixture(tmp_path, method, registration):
    if method == 'dependency-chronos-v1':
        from dnhacksbio.dependency_scoring import Store
        from test_dependency_scoring import payload
        q = Store(tmp_path / 'queue'); q.configure(registration)
        return q, payload(registration)
    if method == 'paired-pathway-v1':
        from test_expression_registry import fixture
        from dnhacksbio.registered_expression_scoring import Store
        _, path, reg, payload = fixture(tmp_path)
        reg['cohorts']['c1']['manifest']['confirmation'] = True
        path.write_text(json.dumps(reg))
        q = Store(tmp_path / 'queue'); q.configure(path)
        payload['input']['manifest_sha256'] = digest(reg['cohorts']['c1']['manifest'])
        return q, payload
    from dnhacksbio.drug_response_scoring import Store
    from test_drug_response import protocol as drug_protocol, cohort
    manifest = dict(protocol_id='p1', hypothesis_id='h1', family_id='f1', cohort_id='c1',
                    protocol=drug_protocol(), cohort=cohort())
    path = tmp_path / 'manifest.json'; path.write_text(json.dumps(manifest))
    q = Store(tmp_path / 'queue')
    return q, {'request_id': 'trial', **q.configure(path)}


def setup(tmp_path, q, method):
    trace = tmp_path / 'public'
    j = Journal(trace); j.register('r', 'Synthetic question')
    c = ControlStore(trace); c.freeze_budget('r', {'policy_id': 'pilot-v1', 'actions': 80})
    m = MonitorStore(tmp_path / 'monitor')
    review = dict(review_id='synthetic-review-v1', method_id=method, assumptions='Synthetic assignment fixture',
                  family_policy='One frozen hypothesis; no adaptive confirmation selection',
                  disclosure_boundary='after-frozen-study', confirmation_units_disjoint=True,
                  design_supported=True, selection_frozen=True)
    spec = dict(episode_id='e', run_id='r', root_id='r', group_id='g', objective='Synthetic question',
                initial_evidence=[], protocol=protocol(), start_sequence=0, calibration_unit=True,
                outcome_policy=dict(assessor_model='fake-assessor-v1', prompt_version='subtree-outcome-v1',
                    verification_policy=adapters.POLICY, adjudication_seconds=60, assessment_timeout=2,
                    max_candidates=10, initial_snapshot=[], receipt_sources={method: {
                        'directory': str(q.directory), 'validity_review': review}}))
    prepare(m, j, trace, **spec)
    return m, j, c, trace, spec


def request(j, q, payload, method, *, rid='r~1', receipt='owned', enqueue=True, producer='runner'):
    j.register(rid, 'Synthetic descendant')
    payload = {**payload, 'request_id': receipt}
    event = j.append(rid, 'a', 'private_experiment.requested', {'method_id': method, 'receipt': receipt,
        'request': j.blob(canonical(payload))}, experiment_id=receipt, producer=producer)
    if enqueue:
        q.enqueue(payload)
    return payload, event


async def yes(prompt):
    assert 'validity_review' in prompt and 'null' in prompt
    assert 'monitor_statistic' not in prompt and 'verifier_score' not in prompt
    return canonical(dict(relevant=True, nonduplicate=True, evidence_supported=True, reason='Synthetic supported evidence'))


@pytest.mark.parametrize('method', list(METHODS))
def test_actual_worker_receipt_to_descendant_label_and_private_review(tmp_path, registration, method, monkeypatch):
    q, payload = queue_fixture(tmp_path, method, registration)
    m, j, c, trace, _ = setup(tmp_path, q, method)
    request(j, q, payload, method)
    assert q.process_one()
    finish(c)
    before = j.events('r')
    # Once a worker result exists, neither labeling nor review may score it again.
    monkeypatch.setattr(type(q), 'process_one', lambda *_: pytest.fail('rescore'))
    result = asyncio.run(adjudicate(m, j, trace, 'e', complete_fn=yes))
    assert result['outcome'] == 'success' and result['training_eligible']
    assert result['label_provenance']['evidence'][0]['run_id'] == 'r~1'
    assert before == j.events('r')
    with m.connect() as con:
        review = json.loads(con.execute('SELECT body FROM reviews').fetchone()[0])
    assert review['decision'] is None and review['association']['provenance']['association'] == 'runner-request-and-queue-v1'
    assert asyncio.run(adjudicate(m, j, trace, 'e', complete_fn=yes)) == result


def test_pending_receipt_survives_endpoint_then_completes_without_new_research(tmp_path, registration):
    method = 'dependency-chronos-v1'; q, payload = queue_fixture(tmp_path, method, registration)
    m, j, c, trace, _ = setup(tmp_path, q, method)
    request(j, q, payload, method); end = finish(c)
    assert asyncio.run(adjudicate(m, j, trace, 'e', complete_fn=yes))['outcome'] == 'pending'
    deadline = workflow(m, 'e')['endpoint']['deadline']
    assert q.process_one()
    assert asyncio.run(adjudicate(m, j, trace, 'e', complete_fn=yes))['outcome'] == 'success'
    assert deadline == end['at'] + 60


@pytest.mark.parametrize('failure', ['not_accepted', 'failed', 'mismatched_payload', 'mismatched_hash', 'mismatched_job', 'missing_completion', 'changed_settings', 'late', 'late_acceptance'])
def test_unavailable_is_censored_never_negative(tmp_path, registration, failure):
    method = 'dependency-chronos-v1'; q, payload = queue_fixture(tmp_path, method, registration)
    m, j, c, trace, _ = setup(tmp_path, q, method)
    payload, event = request(j, q, payload, method, enqueue=failure not in {'not_accepted', 'late_acceptance'})
    if failure == 'failed':
        with q.connect() as con: con.execute("UPDATE jobs SET status='failed',error='fixture'")
    elif failure not in {'not_accepted', 'late_acceptance'}:
        assert q.process_one()
    end = finish(c)
    with q.connect() as con:
        if failure == 'mismatched_payload':
            con.execute("UPDATE aliases SET payload=?", (canonical({**payload, 'input': {}}),))
        elif failure == 'mismatched_hash': con.execute("UPDATE aliases SET digest='wrong'")
        elif failure == 'mismatched_job':
            forged = {**payload, 'request_id': 'another-run'}
            con.execute('DROP TRIGGER immutable_completed_job')
            con.execute('DROP TRIGGER immutable_completion_update')
            con.execute('UPDATE jobs SET payload=?,digest=?', (canonical(forged), digest(forged)))
            con.execute('UPDATE completions SET digest=?', (digest(forged),))
        elif failure == 'changed_settings': con.execute("UPDATE settings SET config='{}'")
        elif failure == 'missing_completion':
            con.execute('DROP TRIGGER immutable_completion_delete'); con.execute('DELETE FROM completions')
        elif failure == 'late':
            con.execute('DROP TRIGGER immutable_completion_update')
            con.execute('UPDATE completions SET completed_at=?', (end['at'] + 61,))
    if failure == 'late_acceptance':
        time.sleep(.005); q.enqueue(payload); q.process_one()
    result = asyncio.run(adjudicate(m, j, trace, 'e', complete_fn=yes, now=lambda: end['at'] + 61))
    assert result['outcome'] == 'censored' and not result['training_eligible']
    assert workflow(m, 'e')['attempts'] == 0


def test_aliases_baseline_and_concurrent_restart(tmp_path, registration):
    method = 'dependency-chronos-v1'; q, payload = queue_fixture(tmp_path, method, registration)
    m, j, c, trace, _ = setup(tmp_path, q, method)
    request(j, q, payload, method, receipt='a')
    request(j, q, payload, method, receipt='b', rid='r~2')
    q.process_one(); finish(c)
    calls = []
    async def reject(prompt):
        calls.append(prompt); await asyncio.sleep(.02)
        return canonical(dict(relevant=True, nonduplicate=False, evidence_supported=True, reason='Duplicate fixture'))
    async def concurrent():
        return await asyncio.gather(*(adjudicate(m, j, trace, 'e', complete_fn=reject) for _ in range(2)))
    asyncio.run(concurrent())
    assert len(calls) == 1
    assert asyncio.run(adjudicate(MonitorStore(m.directory), j, trace, 'e', complete_fn=reject))['outcome'] == 'unsuccessful'
    assert len(calls) == 1


def test_existing_queue_identity_cannot_become_new_finding(tmp_path, registration):
    method = 'dependency-chronos-v1'; q, payload = queue_fixture(tmp_path, method, registration)
    q.enqueue(payload); q.process_one()
    m, j, c, trace, _ = setup(tmp_path, q, method)
    request(j, q, payload, method); finish(c)
    result = asyncio.run(adjudicate(m, j, trace, 'e', complete_fn=yes))
    assert result['outcome'] == 'unsuccessful' and workflow(m, 'e')['attempts'] == 0


def test_foreign_and_future_requests_do_not_supply_success(tmp_path, registration):
    method = 'dependency-chronos-v1'; q, payload = queue_fixture(tmp_path, method, registration)
    m, j, c, trace, _ = setup(tmp_path, q, method)
    request(j, q, payload, method, rid='other', receipt='foreign')
    finish(c)
    request(j, q, payload, method, receipt='future')
    q.process_one()
    assert asyncio.run(adjudicate(m, j, trace, 'e', complete_fn=yes))['outcome'] == 'unsuccessful'


def test_completion_is_atomic_immutable_and_restart_does_not_timestamp_again(tmp_path, registration):
    method = 'dependency-chronos-v1'; q, payload = queue_fixture(tmp_path, method, registration)
    q.enqueue(payload); q.process_one()
    with q.connect() as con:
        before = con.execute('SELECT * FROM completions').fetchall()
    for sql in ("UPDATE jobs SET status='running'", "UPDATE completions SET completed_at=0", 'DELETE FROM completions'):
        with pytest.raises(sqlite3.IntegrityError):
            with q.connect() as con: con.execute(sql)
    q = type(q)(q.directory)
    assert not q.process_one()
    with q.connect() as con: assert con.execute('SELECT * FROM completions').fetchall() == before


def test_runner_submission_uses_real_http_and_receipt_only(tmp_path, registration, monkeypatch):
    method = 'dependency-chronos-v1'; q, payload = queue_fixture(tmp_path, method, registration)
    m, j, c, trace, _ = setup(tmp_path, q, method)
    server = make_server(q, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    monkeypatch.setenv(METHODS[method][1], f'http://127.0.0.1:{server.server_port}')
    fake = SimpleNamespace(_delivered={METHODS[method][0]}, _skill_snapshots={METHODS[method][0]: {}}, journal=j)
    fake._event = lambda kind, body, **kw: j.append('r', 'a', kind, body, **kw)
    try:
        public = asyncio.run(dispatch(fake, dict(method_id=method, spec=payload['spec'], input=payload['input'])))
        assert set(json.loads(public)) == {'receipt', 'status'}
        assert json.loads(public)['receipt'] != payload['request_id']
        q.process_one(); finish(c)
        assert asyncio.run(adjudicate(m, j, trace, 'e', complete_fn=yes))['outcome'] == 'success'
        assert 'e_value' not in canonical(j.events('r'))
    finally:
        server.shutdown(); server.server_close(); thread.join()


def test_independent_queue_locations_share_policy_but_preserve_episode_provenance(tmp_path, registration):
    episodes = []
    for directory in ('one', 'two'):
        root = tmp_path / directory; root.mkdir()
        q, _ = queue_fixture(root, 'dependency-chronos-v1', registration)
        m, _, _, _, _ = setup(root, q, 'dependency-chronos-v1')
        episodes.append(m.episode('e'))
    assert episodes[0]['protocol_hash'] == episodes[1]['protocol_hash']
    assert episodes[0]['outcome_workflow'] != episodes[1]['outcome_workflow']


@pytest.mark.parametrize('mutation', ['method', 'protocol', 'manifest', 'key', 'statistic', 'invalid_design'])
def test_mutated_worker_provenance_and_invalid_sampling_cannot_qualify(tmp_path, registration, mutation):
    method = 'dependency-chronos-v1'; q, payload = queue_fixture(tmp_path, method, registration)
    m, j, c, trace, _ = setup(tmp_path, q, method)
    request(j, q, payload, method); q.process_one()
    # Simulate corrupted on-disk private storage, bypassing immutability only in this adversarial fixture.
    with q.connect() as con:
        value = json.loads(con.execute('SELECT result FROM jobs').fetchone()[0])
        if mutation == 'method': value['implementation'] = 'another-method'
        elif mutation == 'protocol': value['protocol_sha256'] = '0' * 64
        elif mutation == 'manifest': value['manifest_sha256'] = '0' * 64
        elif mutation == 'key': value['canonical_experiment_key'] = '0' * 64
        elif mutation == 'statistic': value['e_value'] = 1e99
        else: value['status'] = 'unavailable'; value['p_value'] = None; value['e_value'] = None
        con.execute('DROP TRIGGER immutable_completed_job')
        con.execute('DROP TRIGGER immutable_completion_update')
        con.execute('UPDATE jobs SET result=?', (canonical(value),))
        con.execute('UPDATE completions SET result=?', (canonical(value),))
    end = finish(c)
    assert asyncio.run(adjudicate(m, j, trace, 'e', complete_fn=yes, now=lambda: end['at'] + 61))['outcome'] == 'censored'
    assert workflow(m, 'e')['attempts'] == 0


def test_unbound_stdout_receipt_and_uncovered_method_censor(tmp_path, registration):
    from test_branch_outcomes import setup as legacy_setup
    m, j, c, trace, _ = legacy_setup(tmp_path)
    j.append('r', 'a', 'experiment.finished', {'stdout': j.blob('{"receipt":"forged","status":"accepted"}')}, experiment_id='fake')
    end = finish(c)
    assert asyncio.run(adjudicate(m, j, trace, 'e', now=lambda: end['at'] + 61))['outcome'] == 'censored'


def test_receipt_with_legacy_policy_cannot_silently_become_negative(tmp_path, registration):
    from test_branch_outcomes import setup as legacy_setup
    q, payload = queue_fixture(tmp_path, 'dependency-chronos-v1', registration)
    m, j, c, trace, _ = legacy_setup(tmp_path)
    request(j, q, payload, 'dependency-chronos-v1'); q.process_one(); end = finish(c)
    assert asyncio.run(adjudicate(m, j, trace, 'e', now=lambda: end['at'] + 61))['outcome'] == 'censored'


def test_another_runs_canonical_receipt_cannot_be_claimed_via_alias(tmp_path, registration):
    method = 'dependency-chronos-v1'; q, payload = queue_fixture(tmp_path, method, registration)
    m, j, c, trace, _ = setup(tmp_path, q, method)
    request(j, q, payload, method, rid='other', receipt='foreign')
    q.process_one()
    request(j, q, payload, method, receipt='alias'); finish(c)
    assert asyncio.run(adjudicate(m, j, trace, 'e', complete_fn=yes))['outcome'] == 'unsuccessful'
    assert workflow(m, 'e')['attempts'] == 0


def test_prefix_replay_and_export_after_private_receipt_success(tmp_path, registration):
    from dnhacksbio.branch_monitoring.worker import score_pending
    from test_branch_control import report
    method = 'dependency-chronos-v1'; q, payload = queue_fixture(tmp_path, method, registration)
    m, j, c, trace, _ = setup(tmp_path, q, method)
    request(j, q, payload, method)
    j.append('r', 'a', 'tool.ended', {'action': 'private_experiment', 'observation': j.blob('{"receipt":"owned","status":"accepted"}')})
    j.append('r', 'a', 'checkpoint.report', {'version': 1, 'report': report(),
        'budget_scopes': [{'run_id': 'r', 'actions': 0, 'spent': 0}]})
    q.process_one(); finish(c)
    assert asyncio.run(adjudicate(m, j, trace, 'e', complete_fn=yes))['outcome'] == 'success'
    async def prefix(prompt):
        assert 'e_value' not in prompt and 'table_sha256' not in prompt
        assert 'Synthetic supported evidence' not in prompt and 'synthetic-review-v1' not in prompt
        return '{"score":0.4}'
    assert asyncio.run(score_pending(m, j, complete_fn=prefix))['recorded'] == 1
    export = m.export()[0]
    assert export['training_eligible'] is True and export['scores'] == [.4]
    assert export['outcome'] == 'success'


def test_registered_action_uses_controller_budget_and_cannot_dispatch_when_paused(tmp_path, registration, monkeypatch):
    from test_runtime import make_explorer, action
    from test_branch_control import report
    method = 'dependency-chronos-v1'; q, payload = queue_fixture(tmp_path, method, registration)
    server = make_server(q, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    monkeypatch.setenv(METHODS[method][1], f'http://127.0.0.1:{server.server_port}')
    replies = iter([action('get_skill', {'name': 'dependency-experiment'}),
                    action('private_experiment', dict(method_id=method, spec=payload['spec'], input=payload['input'])),
                    action('done'), report()])
    ex, _ = make_explorer(tmp_path / 'runtime', monkeypatch, replies)
    try:
        assert asyncio.run(ex.run(3))['status'] == 'awaiting_parent'
        with ex.control.connect() as con:
            operations = [json.loads(r[0]) for r in con.execute('SELECT body FROM budget_operations')]
        assert sum(o['phase'] == 'research' for o in operations) == 3
        assert all(o['status'] != 'active' for o in operations)
        with q.connect() as con: assert con.execute('SELECT count(*) FROM jobs').fetchone()[0] == 1
        with pytest.raises(RuntimeError, match='paused'):
            asyncio.run(ex._dispatch(action('private_experiment', dict(method_id=method, spec=payload['spec'], input=payload['input']))))
        with q.connect() as con: assert con.execute('SELECT count(*) FROM jobs').fetchone()[0] == 1
    finally:
        ex.close(); server.shutdown(); server.server_close(); thread.join()


def test_lost_acknowledgement_reconciles_without_resubmission(tmp_path, registration, monkeypatch):
    from dnhacksbio.explorer import private_experiments
    method = 'dependency-chronos-v1'; q, payload = queue_fixture(tmp_path, method, registration)
    m, j, c, trace, _ = setup(tmp_path, q, method)
    monkeypatch.setenv(METHODS[method][1], 'http://operator-fixture.invalid')
    calls = []
    def lost(body, endpoint):
        calls.append(body); q.enqueue(body)
        raise RuntimeError('PRIVATE-NETWORK-DETAIL')
    monkeypatch.setattr(private_experiments, 'send_payload', lost)
    fake = SimpleNamespace(_delivered={METHODS[method][0]}, _skill_snapshots={METHODS[method][0]: {}}, journal=j)
    fake._event = lambda kind, body, **kw: j.append('r', 'a', kind, body, **kw)
    public = asyncio.run(dispatch(fake, dict(method_id=method, spec=payload['spec'], input=payload['input'])))
    assert 'PRIVATE-NETWORK-DETAIL' not in public
    q.process_one(); finish(c)
    assert asyncio.run(adjudicate(m, j, trace, 'e', complete_fn=yes))['outcome'] == 'success'
    assert len(calls) == 1 and not any(e['kind'] == 'private_experiment.acknowledged' for e in j.events('r'))


def test_disclosure_policy_cannot_disagree_with_episode(tmp_path, registration):
    method = 'dependency-chronos-v1'; q, _ = queue_fixture(tmp_path, method, registration)
    m, j, c, trace, spec = setup(tmp_path, q, method)
    spec['episode_id'] = 'new'; spec['group_id'] = 'new'
    spec['outcome_policy']['receipt_sources'][method]['validity_review']['disclosure_boundary'] = 'during-research'
    with pytest.raises(ValueError, match='disclosure boundary'):
        prepare(m, j, trace, **spec)
    with m.connect() as con:
        assert con.execute("SELECT count(*) FROM episodes WHERE id='new'").fetchone()[0] == 0


def test_live_routing_before_endpoint_is_private_and_never_assesses_or_labels(tmp_path, registration, monkeypatch):
    from dnhacksbio import llm
    method = 'dependency-chronos-v1'; q, payload = queue_fixture(tmp_path, method, registration)
    m, j, c, trace, _ = setup(tmp_path, q, method)
    request(j, q, payload, method)
    assert adapters.route(m, j, trace, 'e')['pending'] == 1
    q.process_one()
    public = j.events('r'); episode = m.episode('e'); state = workflow(m, 'e')
    monkeypatch.setattr(llm, 'acomplete', lambda *a, **k: pytest.fail('Live routing invoked a model'))
    assert adapters.route(m, j, trace, 'e')['routed'] == 1
    assert adapters.route(MonitorStore(m.directory), j, trace, 'e')['routed'] == 1
    with m.connect() as con:
        assert con.execute('SELECT count(*) FROM reviews').fetchone()[0] == 1
        review = json.loads(con.execute('SELECT body FROM reviews').fetchone()[0])
    m.review(review['review_id'], 'rejected', 'PRIVATE HUMAN OPINION')
    assert m.episode('e') == episode and workflow(m, 'e') == state and j.events('r') == public
    finish(c)
    # Human review is separate; it is not a success label or input to the frozen assessor.
    async def assessor(prompt):
        assert 'PRIVATE HUMAN OPINION' not in prompt
        return await yes(prompt)
    assert asyncio.run(adjudicate(m, j, trace, 'e', complete_fn=assessor))['outcome'] == 'success'
    with m.connect() as con: assert con.execute('SELECT count(*) FROM reviews').fetchone()[0] == 1


def test_operator_route_cli_does_not_load_a_model_or_write_public_state(tmp_path, registration):
    import subprocess
    import sys
    method = 'dependency-chronos-v1'; q, payload = queue_fixture(tmp_path, method, registration)
    m, j, c, trace, _ = setup(tmp_path, q, method)
    request(j, q, payload, method); q.process_one()
    before = j.events('r')
    proc = subprocess.run([sys.executable, '-m', 'dnhacksbio.branch_monitoring', 'route',
                           '--state', str(m.directory), '--trace-dir', str(trace), '--episode-id', 'e'],
                          capture_output=True, text=True, timeout=10)
    assert proc.returncode == 0, proc.stderr
    assert not proc.stdout and before == j.events('r')
    assert m.episode('e')['outcome'] == 'unknown'
    with m.connect() as con: assert con.execute('SELECT count(*) FROM reviews').fetchone()[0] == 1


def test_request_order_does_not_let_alias_hide_later_canonical_candidate(tmp_path, registration):
    method = 'dependency-chronos-v1'; q, payload = queue_fixture(tmp_path, method, registration)
    m, j, c, trace, _ = setup(tmp_path, q, method)
    alias, _ = request(j, q, payload, method, receipt='alias', rid='r~1', enqueue=False)
    request(j, q, payload, method, receipt='canonical', rid='r~2')
    q.enqueue(alias)  # Concurrent requests can reach the queue in a different order than the journal.
    q.process_one(); finish(c)
    result = asyncio.run(adjudicate(m, j, trace, 'e', complete_fn=yes))
    assert result['outcome'] == 'success'
    assert result['label_provenance']['evidence'][0]['finding_id'] == 'canonical'
    assert workflow(m, 'e')['attempts'] == 1
