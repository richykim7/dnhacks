import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from dnhacksbio.explorer.control import ControlStore, validate_report
from test_runtime import action, make_explorer


def report(request="finish"):
    return {"findings": [], "completed_work": ["Inspected data quality"], "unresolved": ["Need sufficient independent donors"],
            "blockers": [], "ruled_out": [], "request": request,
            "next_steps": [] if request == "finish" else [{"objective": "Resolve donor coverage", "information_gain": "Establish feasibility", "prerequisites": "Available metadata", "feasibility": "Metadata already located", "estimated_cost": "One bounded round"}]}


def ready(store, rid):
    store.start(rid, 1, total_nodes=2)
    store.patch(rid, status="reporting")
    return store.save_report(rid, report("continue"))


def test_zero_actions_forces_actual_report_and_no_dispatch(tmp_path, monkeypatch):
    ex, prompts = make_explorer(tmp_path, monkeypatch, iter([report()]))
    try:
        result = asyncio.run(ex.run(0))
        assert result["status"] == "awaiting_parent" and result["steps"] == 0
        assert "Research is PAUSED" in prompts[0]
        assert not any(e["kind"] == "tool.started" for e in ex.journal.events("study"))
        with pytest.raises(RuntimeError, match="paused"):
            ex._delivered.add("agent-runtime")
            asyncio.run(ex._dispatch(action("reflect")))
        assert asyncio.run(ex.run(18))["steps"] == 0
    finally:
        ex.close()


def test_report_repair_is_bounded_and_durable(tmp_path, monkeypatch):
    ex, prompts = make_explorer(tmp_path, monkeypatch, iter([action("run_experiments")] * 3))
    try:
        assert asyncio.run(ex.run(0))["status"] == "reporting_blocked"
        assert len(prompts) == 3
        assert asyncio.run(ex.run(18))["status"] == "reporting_blocked"
        assert ControlStore(tmp_path).get("study")["report_attempts"] == 3
    finally:
        ex.close()


def test_report_model_outage_pauses_without_scientific_failure(tmp_path, monkeypatch):
    ex, _ = make_explorer(tmp_path, monkeypatch, iter([RuntimeError("outage")]))
    try:
        assert asyncio.run(ex.run(0))["status"] == "reporting_blocked"
    finally:
        ex.close()


def test_slow_start_gets_explicit_continuation_then_true_finish(tmp_path, monkeypatch):
    replies = [action("checkpoint"), report("continue"), action("done"), report()]
    ex, _ = make_explorer(tmp_path, monkeypatch, iter(replies))
    decisions = iter([{"action": "continue", "reason": "Useful feasible preparation", "objective": "Resolve donor coverage", "allowance": 1},
                      {"action": "finish", "reason": "Objective sufficiently resolved"}])
    ex._allocation_fn = lambda _: next(decisions)
    try:
        result = asyncio.run(ex.run_investigation(1))
        assert result["status"] == "completed" and result["steps"] == 2
        assert result["report_version"] == 2
    finally:
        ex.close()


def test_duplicate_decision_stale_report_and_no_budget_reset(tmp_path):
    s = ControlStore(tmp_path)
    ready(s, "r")
    d = {"action": "continue", "reason": "Feasible next step", "objective": "Read metadata", "allowance": 2}
    first = s.decide("r", 1, d)
    s.consume("r")
    assert s.decide("r", 1, d) == first
    assert s.get("r")["used"] == 1
    assert s.start("r", 18)["allowance"] == 2
    with pytest.raises(ValueError, match="Conflicting"):
        s.decide("r", 1, dict(d, allowance=3))
    with pytest.raises(ValueError, match="Stale"):
        s.decide("r", 2, d)


def test_concurrent_forks_reserve_tree_capacity_atomically(tmp_path):
    s = ControlStore(tmp_path)
    for rid in ("r~1", "r~2"):
        ready(s, rid)
    d = {"action": "fork", "reason": "Two independent questions", "allowance": 1,
         "branches": [{"objective": x, "information_gain": x, "feasibility": "Available data"} for x in ["A", "B"]]}
    def apply(rid):
        try:
            return s.decide(rid, 1, d)
        except ValueError:
            return None
    with ThreadPoolExecutor(2) as p:
        results = list(p.map(apply, ["r~1", "r~2"]))
    assert sum(x is not None for x in results) == 1
    winner = next(x for x in results if x)
    assert [x["run_id"] for x in winner["children"]] == [winner["run_id"] + "~1", winner["run_id"] + "~2"]
    with pytest.raises(ValueError, match="paused"):
        s.consume(winner["run_id"])


def test_parent_fork_is_executed_without_child_choice(tmp_path, monkeypatch):
    ex, _ = make_explorer(tmp_path, monkeypatch, iter([report("fork")]))
    forks = []
    ex._fork_fn = lambda sid: (forks.append(sid) or SimpleNamespace(session_id="forked-" + str(len(forks))))
    ex._allocation_fn = lambda c: ({"action": "fork", "reason": "Independent feasible questions", "allowance": 1,
        "branches": [{"objective": x, "information_gain": x, "feasibility": "Available"} for x in ["A", "B"]]}
        if c["objective"] == "Original research question" else {"action": "finish", "reason": "Research complete"})
    spawn = ex._spawn_child
    def child(*args):
        c = spawn(*args)
        seq = iter([action("done"), report()])
        async def complete(_): return json.dumps(next(seq))
        c._inject_complete = complete
        monkeypatch.setattr(c, "_turn_message", lambda obs: obs)
        return c
    monkeypatch.setattr(ex, "_spawn_child", child)
    try:
        assert asyncio.run(ex.run_investigation(0))["status"] == "completed"
        assert len(forks) == 2
        assert ex.control.get("study~1")["status"] == "completed"
        assert ex.control.get("study~2")["status"] == "completed"
        record = ex.control.decision(ex.control.get("study")["decision_id"])
        asyncio.run(ex._execute_fork(record))
        assert len(forks) == 2
    finally:
        ex.close()


def test_report_rejects_unreferenced_findings():
    r = report()
    r["findings"] = [{"claim": "A result", "references": []}]
    with pytest.raises(ValueError, match="references"):
        validate_report(r)


def test_concurrent_external_fork_claims_only_launch_once(tmp_path):
    s = ControlStore(tmp_path); ready(s, "r")
    d={"action":"fork","reason":"Independent questions","allowance":1,
       "branches":[{"objective":x,"information_gain":x,"feasibility":"Available"} for x in ["A","B"]]}
    record=s.decide("r",1,d)
    with ThreadPoolExecutor(2) as p:
        granted=list(p.map(lambda _:s.claim_launch(record["decision_id"],"r~1"),[0,1]))
    assert sum(granted) == 1


def test_no_duplicate_concurrent_child_run(tmp_path,monkeypatch):
    ex,_=make_explorer(tmp_path,monkeypatch,iter([]))
    async def scenario():
        entered=asyncio.Event();release=asyncio.Event()
        async def complete(_):
            entered.set();await release.wait();return json.dumps(report())
        ex._inject_complete=complete
        first=asyncio.create_task(ex.run(0));await entered.wait()
        second=await ex.run(0)
        assert second["status"] == "already_running"
        release.set();await first
    try: asyncio.run(scenario())
    finally: ex.close()


def test_checkpoint_trigger_survives_restart_before_reporting(tmp_path,monkeypatch):
    ex,_=make_explorer(tmp_path,monkeypatch,iter([action("checkpoint")]))
    try:
        ex.control.start("study",5)
        asyncio.run(ex.step("Begin"))
        state=ControlStore(tmp_path).get("study")
        assert state["status"] == "reporting" and state["report_reason"] == "voluntary_checkpoint"
        async def complete(_): return json.dumps(report())
        ex._inject_complete=complete
        assert asyncio.run(ex.run(5))["steps"] == 1
    finally: ex.close()


def test_restart_preserves_parent_granted_objective(tmp_path,monkeypatch):
    ex,prompts=make_explorer(tmp_path,monkeypatch,iter([report()]))
    try:
        asyncio.run(ex.run(0))
        ex.control.decide("study",1,{"action":"continue","objective":"Inspect the approved donor manifest",
                                    "reason":"Feasible unresolved data preparation","allowance":1})
        replies=iter([action("done"),report()])
        async def complete(prompt):
            prompts.append(prompt);return json.dumps(next(replies))
        ex._inject_complete=complete;ex._branch_brief=None
        asyncio.run(ex.run(18))
        assert "Inspect the approved donor manifest" in prompts[1]
        assert ex.control.get("study")["total_actions"] == 1
    finally: ex.close()


def _policy_explorer(tmp_path, monkeypatch, *, policy_id=None, actions=12, run_id='policy'):
    from dnhacksbio.explorer.explorer import Explorer
    from dnhacksbio.explorer import budget, embed
    monkeypatch.setattr(embed, 'embed_one', lambda *_: None)
    spec = dict(budget.ACTION_CONTRACT, actions=actions)
    if policy_id is not None:
        spec['policy_id'] = policy_id
    async def unused(_):
        raise AssertionError('No research/model call belongs in this context check')
    ex = Explorer(run_id, 'Original question', db_path=tmp_path/'policy.duckdb', trace_dir=tmp_path,
                  subtree_budget=spec, complete_fn=unused)
    ex.control.start(run_id, 0)
    ex.control.patch(run_id, status='reporting')
    ex.control.save_report(run_id, report('continue'))
    return ex


def test_branching_context_respects_other_branches_action_reservations(tmp_path, monkeypatch):
    from dnhacksbio.explorer.budget import BRANCHING_POLICY_ID
    ex = _policy_explorer(tmp_path, monkeypatch)
    try:
        ex.control.start('policy~1', 8)
        before = ex.control.budgets('policy')
        ctx = ex._allocation_context(ex)
        assert ctx['branching_policy'] == BRANCHING_POLICY_ID
        assert ctx['working_objective'] == 'Original question'
        assert ctx['fork_capacity']['unreserved_actions'] == 4
        assert ctx['fork_capacity']['options'] == [
            {'children': 2, 'max_actions_per_child': 2},
            {'children': 3, 'max_actions_per_child': 1},
        ]
        assert ex.control.budgets('policy') == before
    finally:
        ex.close()


@pytest.mark.parametrize('constraint', ['actions', 'slots', 'depth'])
def test_branching_context_does_not_offer_infeasible_forks(tmp_path, monkeypatch, constraint):
    rid = 'policy' + '~1' * 6 if constraint == 'depth' else 'policy'
    ex = _policy_explorer(tmp_path, monkeypatch, actions=1 if constraint == 'actions' else 12, run_id=rid)
    try:
        if constraint == 'slots':
            with ex.control.connect() as c:
                c.execute('UPDATE trees SET remaining=1 WHERE id=?', ('policy',))
        assert ex._allocation_context(ex)['fork_capacity']['options'] == []
    finally:
        ex.close()


def test_prior_allocations_are_ordered_and_scoped_to_the_current_node(tmp_path, monkeypatch):
    ex = _policy_explorer(tmp_path, monkeypatch)
    try:
        for version, objective in enumerate(['Complete measurement A', 'Resolve condition B'], 1):
            ex.control.decide('policy', version, {'action':'continue', 'reason':'Finish existing work',
                              'objective':objective, 'allowance':1})
            ex.control.patch('policy', status='reporting')
            ex.control.save_report('policy', report('continue'))
        ready(ex.control, 'unrelated')
        ex.control.decide('unrelated', 1, {'action':'continue', 'reason':'Unrelated evidence',
                          'objective':'Do not leak sibling context', 'allowance':1})
        ctx=ex._allocation_context(ex)
        assert ctx['working_objective'] == 'Resolve condition B'
        assert [d['report_version'] for d in ctx['prior_allocations']] == [1,2]
        assert [d['objective'] for d in ctx['prior_allocations']] == ['Complete measurement A','Resolve condition B']
        assert 'Do not leak sibling context' not in json.dumps(ctx)
    finally:
        ex.close()


def test_existing_frozen_policy_does_not_receive_new_allocation_inputs(tmp_path, monkeypatch):
    ex = _policy_explorer(tmp_path, monkeypatch, policy_id='parent-allocation-actions-v1')
    try:
        before=ex.control.budgets('policy')
        ctx=ex._allocation_context(ex)
        assert not {'branching_policy','working_objective','prior_allocations','fork_capacity'} & set(ctx)
        assert ex.control.budgets('policy') == before
    finally:
        ex.close()


def test_versioned_branching_policy_reaches_parent_and_preserves_explicit_decision(tmp_path, monkeypatch):
    from dnhacksbio import llm
    from dnhacksbio.explorer.budget import BRANCHING_POLICY_ID
    ex=_policy_explorer(tmp_path, monkeypatch)
    captured=[]
    decision={'action':'fork','reason':'Two independent feasible questions','allowance':2,
              'branches':[{'objective':x,'information_gain':'Distinct measurement','feasibility':'Inputs available'} for x in ['A','B']]}
    async def allocate(prompt, **kwargs):
        captured.append(prompt)
        return json.dumps(decision)
    monkeypatch.setattr(llm,'acomplete',allocate)
    try:
        actual=asyncio.run(ex._parent_decision(ex))
        assert actual == decision
        ctx=json.loads(captured[0].split('\n')[-1])
        assert ctx['branching_policy'] == BRANCHING_POLICY_ID
        record=ex.control.decide('policy',1,actual)
        assert len(record['children']) == 2
        assert ex.control.get('policy')['status'] == 'forking'
        assert ex.control.budgets('policy')[0]['contract']['actions'] == 12
    finally:
        ex.close()
