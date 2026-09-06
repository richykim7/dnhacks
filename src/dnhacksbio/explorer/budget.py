"""Shared, prospective subtree allowances. Stored in the controller transaction.

Seconds are summed operation wall time (parallel operations each pay), not CPU-seconds.
Reservations survive process death; ambiguous work is never refunded on restart.
"""
from __future__ import annotations

import json
import math
import time
from uuid import uuid4

from .lineage import ancestors


class BudgetUnavailable(RuntimeError):
    pass


DEFAULT_CONTRACT = dict(version=1, policy_id="parent-allocation-v1", seconds=43200., actions=2880,
                        research_seconds=600., report_seconds=90., report_attempts=3,
                        judge_seconds=90., fork_seconds=10.)


# Version 2 preserves an action horizon without wall-clock cutoffs.
ACTION_CONTRACT = dict(version=2, policy_id="parent-allocation-actions-v1", seconds=None, actions=2880,
                       research_seconds=None, report_seconds=None, report_attempts=3,
                       judge_seconds=None, fork_seconds=None)


def action_only(b):
    return b["contract"]["version"] == 2


def contract(value=None):
    if value and value.get("version") == 2:
        v = dict(ACTION_CONTRACT, **value)
        if set(v) != set(ACTION_CONTRACT) or any(v[k] is not None for k in ("seconds", "research_seconds", "report_seconds", "judge_seconds", "fork_seconds")):
            raise ValueError("Action-only contract cannot contain wall-clock limits")
        if type(v["actions"]) is not int or v["actions"] < 0 or v["report_attempts"] != 3 or not isinstance(v["policy_id"], str) or not v["policy_id"].strip():
            raise ValueError("Invalid action-only contract")
        return v
    v = dict(DEFAULT_CONTRACT, **(value or {}))
    if set(v) != set(DEFAULT_CONTRACT) or v["version"] != 1 or not isinstance(v["policy_id"], str) or not v["policy_id"].strip():
        raise ValueError("Invalid frozen budget contract")
    for k in ("seconds", "research_seconds", "report_seconds", "judge_seconds", "fork_seconds"):
        if type(v[k]) not in (int, float) or not math.isfinite(v[k]) or v[k] <= 0:
            raise ValueError("Budget seconds must be finite and positive")
    if type(v["actions"]) is not int or v["actions"] < 0 or v["report_attempts"] != 3:
        raise ValueError("Invalid action/report allowance")
    if v["seconds"] < v["report_seconds"] * 3:
        raise ValueError("Budget must reserve mandatory reporting")
    return v


def schema(c):
    c.executescript('''
      CREATE TABLE IF NOT EXISTS budgets(id TEXT PRIMARY KEY, body TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS budget_operations(id TEXT PRIMARY KEY, body TEXT NOT NULL);
    ''')


def put(c, b):
    c.execute("INSERT OR REPLACE INTO budgets VALUES (?,?)", (b["run_id"], json.dumps(b, allow_nan=False)))


def scopes(c, rid):
    rows = []
    for aid in ancestors(rid):
        r = c.execute("SELECT body FROM budgets WHERE id=?", (aid,)).fetchone()
        if r:
            rows.append(json.loads(r[0]))
    return rows


def free(b):
    if action_only(b):
        return math.inf
    return max(0., b["contract"]["seconds"] - b["spent"] - sum(b["holds"].values()) - sum(b["active"].values()))


def freeze(c, rid, value):
    v = contract(value)
    old = c.execute("SELECT body FROM budgets WHERE id=?", (rid,)).fetchone()
    if old:
        b = json.loads(old[0])
        if b["contract"] != v:
            raise ValueError("Budget is frozen; restart cannot refresh it")
        return b
    # It is too late to pretend an existing continuation was prospectively budgeted.
    for row in c.execute("SELECT body FROM nodes"):
        n = json.loads(row[0])
        if (n["run_id"] == rid or n["run_id"].startswith(rid + "~")) and (n["total_actions"] or n["report_attempts"] or n["version"]):
            raise ValueError("Cannot enroll a budget after work started")
    for row in c.execute("SELECT body FROM budget_operations"):
        op = json.loads(row[0])
        if op["run_id"] == rid or op["run_id"].startswith(rid + "~"):
            raise ValueError("Cannot enroll a budget after an operation was admitted")
    b = dict(run_id=rid, contract=v, created_at=time.time(), spent=0., actions=0,
             holds={}, action_holds={}, active={}, violation=False, terminal=None)
    put(c, b)
    return b


def hold_reports(c, rids, allowance=0, *, partial=False):
    """Reserve initial research and reports for every child in one transaction."""
    changes = {}
    for rid in rids:
        for base in scopes(c, rid):
            b = changes.setdefault(base["run_id"], base)
            if b["terminal"] or b["violation"]:
                raise BudgetUnavailable("Subtree budget closed or operationally blocked")
            key = rid + ":report"
            if key in b["holds"]:
                continue
            amount = 0. if action_only(b) else b["contract"]["report_seconds"] * 3
            if free(b) + 1e-9 < amount:
                raise BudgetUnavailable("Insufficient shared allowance for mandatory reports")
            b["holds"][key] = amount
    for b in changes.values():
        owned = [rid for rid in rids if b["run_id"] in ancestors(rid) and rid not in b["action_holds"]]
        if not owned:
            continue
        left = b["contract"]["actions"] - b["actions"] - sum(b["action_holds"].values())
        grant = min(allowance, left // len(owned)) if partial else allowance
        if left < grant * len(owned):
            raise BudgetUnavailable("Insufficient shared action grants for children")
        per_node = 0. if action_only(b) else min(b["contract"]["research_seconds"] * grant, max(b["contract"]["research_seconds"], free(b) / (len(owned) + 1)))
        if not action_only(b) and grant and free(b) < b["contract"]["research_seconds"] * len(owned):
            if partial:
                grant, per_node = 0, 0.
            else:
                raise BudgetUnavailable("Insufficient shared research time")
        for rid in owned:
            b["action_holds"][rid] = grant
            b["holds"][rid + ":research"] = per_node
        put(c, b)


def hold_launches(c, rid, count):
    for b in scopes(c, rid):
        amount = 0. if action_only(b) else count * b["contract"]["fork_seconds"]
        if free(b) < amount:
            raise BudgetUnavailable("Insufficient fork launch allowance")
        b["holds"][rid + ":fork"] = amount
        put(c, b)


def release_report(c, rid):
    for b in scopes(c, rid):
        b["holds"].pop(rid + ":report", None)
        b["holds"].pop(rid + ":research", None)
        b["action_holds"].pop(rid, None)
        put(c, b)


def available(c, rid):
    bs = scopes(c, rid)
    return all(not b["terminal"] and not b["violation"]
               and (b["action_holds"].get(rid, 0) if rid in b["action_holds"] else
                    b["contract"]["actions"] - b["actions"] - sum(b["action_holds"].values())) > 0
               and (action_only(b) or (b["holds"].get(rid + ":research", 0.) >= b["contract"]["research_seconds"] if rid in b["action_holds"] else
                    free(b) >= b["contract"]["research_seconds"] + 3 * b["contract"]["report_seconds"] + b["contract"]["judge_seconds"])) for b in bs)


def reserve(c, rid, phase):
    if phase not in {"research", "report", "judge", "fork"}:
        raise ValueError("Unknown budget phase")
    bs = scopes(c, rid)
    if not bs:
        return None
    if any(b["terminal"] or b["violation"] for b in bs):
        raise BudgetUnavailable("Budget closed or blocked")
    key = rid + ":" + phase
    timed = [b for b in bs if not action_only(b)]
    limits = [b["contract"][phase + "_seconds"] for b in timed]
    limits += [b["holds"].get(key, 0.) if phase in {"report", "research", "fork"} else free(b) for b in timed]
    seconds = min(limits) if limits else None
    if (seconds is not None and seconds < .001) or (phase == "research" and (
        any(b["action_holds"].get(rid, 0) <= 0 for b in bs)
        or (timed and seconds < min(b["contract"]["research_seconds"] for b in timed)))):
        raise BudgetUnavailable("Shared subtree allowance exhausted")
    # One in-flight operation per node, including allocation/fork controllers.
    for row in c.execute("SELECT body FROM budget_operations"):
        op = json.loads(row[0])
        if op["run_id"] == rid and op["status"] == "active":
            raise BudgetUnavailable("Unsettled operation requires reconciliation; no automatic retry")
    oid = uuid4().hex
    op = dict(operation_id=oid, run_id=rid, phase=phase, seconds=seconds,
              scopes=[b["run_id"] for b in bs], status="active", started_at=time.time())
    for b in bs:
        if not action_only(b) and phase in {"report", "research", "fork"}:
            b["holds"][key] -= seconds
        if phase == "research":
            b["actions"] += 1
            b["action_holds"][rid] -= 1
        b["active"][oid] = seconds or 0.
        put(c, b)
    c.execute("INSERT INTO budget_operations VALUES (?,?)", (oid, json.dumps(op)))
    return op


def settle(c, oid, elapsed, *, interrupted=False):
    if not oid:
        return
    if not math.isfinite(elapsed) or elapsed < 0:
        raise ValueError("Invalid measured operation cost")
    op = json.loads(c.execute("SELECT body FROM budget_operations WHERE id=?", (oid,)).fetchone()[0])
    if op["status"] != "active":
        return op
    # Cancellation/timeout may leave external compute alive: retain the entire reservation,
    # block further dispatch, and mark the continuation censored rather than claim a valid cap.
    violation = interrupted or (op["seconds"] is not None and elapsed > op["seconds"] + .1)
    charged = max(elapsed, op["seconds"] or 0.) if violation else elapsed
    for b in scopes(c, op["run_id"]):
        b["active"].pop(oid)
        b["spent"] += charged
        if op["phase"] == "research" and not violation and not action_only(b):
            b["holds"][op["run_id"] + ":research"] += max(0., op["seconds"] - charged)
        b["violation"] |= violation
        put(c, b)
    op.update(status="interrupted" if violation else "settled", elapsed=elapsed, charged=charged, ended_at=time.time())
    c.execute("UPDATE budget_operations SET body=? WHERE id=?", (json.dumps(op), oid))
    return op
