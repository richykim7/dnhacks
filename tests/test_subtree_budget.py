import asyncio
from concurrent.futures import ThreadPoolExecutor

import pytest

from dnhacksbio.explorer import budget
from dnhacksbio.explorer.control import ControlStore
from test_branch_control import report, ready
from test_runtime import make_explorer, action


def test_shared_actions_reports_and_frozen_restart(tmp_path):
    s = ControlStore(tmp_path)
    s.freeze_budget("r", {"actions": 2})
    s.start("r", 2)
    for _ in range(2):
        op = s.reserve_operation("r", "research")
        s.consume("r")
        s.settle_operation(op, .1)
    assert not s.research_available("r")
    with pytest.raises(budget.BudgetUnavailable):
        s.reserve_operation("r", "research")
    # An empty research grant cannot consume the reserved report allowance.
    op = s.reserve_operation("r", "report")
    s.settle_operation(op, .2)
    assert ControlStore(tmp_path).budgets("r")[0]["actions"] == 2
    with pytest.raises(ValueError, match="frozen"):
        s.freeze_budget("r", {"actions": 3})


def test_fork_reserves_each_child_grant_and_refunds_failed_launch(tmp_path):
    s = ControlStore(tmp_path)
    s.freeze_budget("r", {"actions": 2})
    ready(s, "r")
    d = {"action": "fork", "reason": "Independent questions", "allowance": 1,
         "branches": [{"objective": x, "information_gain": x, "feasibility": "Available"} for x in ("A", "B")]}
    rec = s.decide("r", 1, d)
    assert s.budgets("r")[0]["action_holds"] == {"r~1": 1, "r~2": 1}
    s.start("r~1", 1)
    op = s.reserve_operation("r~1", "research")
    s.settle_operation(op, 2.)
    assert not s.research_available("r~1")
    assert s.research_available("r~2")
    s.launch_state(rec["decision_id"], "r~2", "failed")
    assert "r~2" not in s.budgets("r")[0]["action_holds"]
    assert s.budgets("r")[0]["spent"] == 2.


def test_concurrent_grants_never_overdraw_and_rollback(tmp_path):
    s = ControlStore(tmp_path)
    s.freeze_budget("r", {"actions": 2})
    for rid in ("r~1", "r~2"):
        ready(s, rid)
    d = {"action": "continue", "reason": "Useful preparation", "allowance": 2, "objective": "Check donors"}
    def grant(rid):
        try:
            return s.decide(rid, 1, d)
        except budget.BudgetUnavailable:
            return None
    with ThreadPoolExecutor(2) as pool:
        granted = list(pool.map(grant, ["r~1", "r~2"]))
    assert sum(x is not None for x in granted) == 1
    b = s.budgets("r")[0]
    assert sum(b["action_holds"].values()) == 2
    assert b["spent"] + sum(b["holds"].values()) <= b["contract"]["seconds"]


def test_nested_budget_charges_every_ancestor(tmp_path):
    s = ControlStore(tmp_path)
    s.freeze_budget("r", {"actions": 9})
    s.freeze_budget("r~1", {"actions": 2})
    s.start("r~1~1", 2)
    op = s.reserve_operation("r~1~1", "research")
    s.settle_operation(op, 4)
    assert [b["spent"] for b in s.budgets("r~1~1")] == [4, 4]
    assert [b["actions"] for b in s.budgets("r~1~1")] == [1, 1]
    assert s.settle_operation(op, 4)["charged"] == 4  # idempotent settlement


def test_crash_and_timeout_cannot_refund_or_restart_paid_work(tmp_path):
    s = ControlStore(tmp_path); s.freeze_budget("r", None); s.start("r", 1)
    op = s.reserve_operation("r", "research")
    resumed = ControlStore(tmp_path)
    with pytest.raises(budget.BudgetUnavailable, match="Unsettled"):
        resumed.reserve_operation("r", "report")
    resumed.settle_operation(op, 1, interrupted=True)
    b = resumed.budgets("r")[0]
    assert b["violation"] and b["spent"] == op["seconds"]
    assert not resumed.research_available("r")


def test_zero_shared_actions_forces_report_and_closes_budget(tmp_path, monkeypatch):
    monkeypatch.setitem(budget.DEFAULT_CONTRACT, "actions", 0)
    ex, prompts = make_explorer(tmp_path, monkeypatch, iter([report()]))
    try:
        result = asyncio.run(ex.run_investigation(18))
        assert result["status"] == "completed" and result["steps"] == 0
        assert len(prompts) == 1 and "Research is PAUSED" in prompts[0]
        terminal = ex.control.budgets("study")[0]["terminal"]
        assert terminal["reason"] == "budget_endpoint" and terminal["spent"] > 0
    finally:
        ex.close()


def test_total_limit_across_rounds_preserves_final_report(tmp_path, monkeypatch):
    monkeypatch.setitem(budget.DEFAULT_CONTRACT, "actions", 2)
    ex, _ = make_explorer(tmp_path, monkeypatch, iter([action("checkpoint"), report("continue"), action("reflect"), report()]))
    ex._allocation_fn = lambda _: {"action": "continue", "reason": "Slow start deserves followup", "objective": "Resolve donors", "allowance": 1}
    try:
        assert asyncio.run(ex.run_investigation(1))["steps"] == 2
        b = ex.control.budgets("study")[0]
        assert b["terminal"]["reason"] == "budget_endpoint"
        assert b["spent"] > 0 and not b["active"] and not b["holds"]
        assert ex.control.get("study")["version"] == 2
    finally:
        ex.close()
