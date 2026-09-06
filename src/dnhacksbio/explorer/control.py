"""Durable checkpoints and atomic parent grants. Contains ordinary research state only."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .lineage import root, depth, child
from . import budget

REPORT_FIELDS = {"findings", "completed_work", "unresolved", "blockers", "ruled_out", "request", "next_steps"}
REPORT_PROMPT = """Research is PAUSED. Produce your own checkpoint report from your existing context.
No tools, new research, or forks are permitted. Return exactly one JSON object with:
findings: list of {claim: string, references: list of existing experiment/artifact/source IDs};
completed_work, unresolved, blockers, ruled_out: lists of strings;
request: continue, fork, or finish;
next_steps: list of {objective, information_gain, prerequisites, feasibility, estimated_cost}, all strings.
An unfinished result, justified preparation, or useful falsification is acceptable. Cite actual work;
do not invent findings. This report requests allocation; only the parent authorizes work.
"""


def encoded(value):
    return json.dumps(value, sort_keys=True, allow_nan=False, separators=(",", ":"))


def validate_report(value, max_chars=24000):
    if not isinstance(value, dict) or set(value) != REPORT_FIELDS:
        raise ValueError("Report must contain exactly the documented fields")
    for k in ("completed_work", "unresolved", "blockers", "ruled_out"):
        if not isinstance(value[k], list) or any(not isinstance(s, str) for s in value[k]):
            raise ValueError(f"{k} must be a list of strings")
    if value["request"] not in {"continue", "fork", "finish"}:
        raise ValueError("Invalid report request")
    if not isinstance(value["findings"], list):
        raise ValueError("findings must be a list")
    for f in value["findings"]:
        if not isinstance(f, dict) or set(f) != {"claim", "references"} or not isinstance(f["claim"], str):
            raise ValueError("Each finding needs claim and references")
        if not isinstance(f["references"], list) or not f["references"] or any(not isinstance(r, str) or not r.strip() for r in f["references"]):
            raise ValueError("Each finding needs existing evidence references")
    if not isinstance(value["next_steps"], list):
        raise ValueError("next_steps must be a list")
    for s in value["next_steps"]:
        if not isinstance(s, dict) or set(s) != {"objective", "information_gain", "prerequisites", "feasibility", "estimated_cost"} or any(not isinstance(v, str) or not v.strip() for v in s.values()):
            raise ValueError("Each next step needs objective, information_gain, prerequisites, feasibility, estimated_cost")
    if value["request"] != "finish" and not value["next_steps"]:
        raise ValueError("Further work requires a next step")
    if max_chars is not None and len(encoded(value)) > max_chars:
        raise ValueError("Report exceeds 24000 characters")
    return value


def validate_decision(value, max_actions=18, max_branches=3):
    if not isinstance(value, dict) or value.get("action") not in {"continue", "fork", "finish", "prune"}:
        raise ValueError("Parent must choose continue, fork, finish, or prune")
    if not isinstance(value.get("reason"), str) or not value["reason"].strip():
        raise ValueError("Parent decision needs an evidence-based reason")
    allowed = {"action", "reason", "objective", "allowance", "branches"}
    if set(value) - allowed:
        raise ValueError("Unexpected parent decision field")
    if value["action"] in {"continue", "fork"}:
        if type(value.get("allowance")) is not int or (value["allowance"] < 1 or (max_actions is not None and value["allowance"] > max_actions)):
            raise ValueError("Invalid action allowance")
    if value["action"] == "continue" and (not isinstance(value.get("objective"), str) or not value["objective"].strip()):
        raise ValueError("Continuation needs a concrete objective")
    if value["action"] == "fork":
        bs = value.get("branches")
        if not isinstance(bs, list) or (len(bs) < 2 or (max_branches is not None and len(bs) > max_branches)):
            raise ValueError("Fork needs two or three distinct subquestions")
        for b in bs:
            if not isinstance(b, dict) or set(b) != {"objective", "information_gain", "feasibility"} or any(not isinstance(s, str) or not s.strip() for s in b.values()):
                raise ValueError("Each fork needs objective, information_gain and feasibility")
        if len({b["objective"].strip().casefold() for b in bs}) != len(bs):
            raise ValueError("Duplicate fork objectives")
    return value


class ControlStore:
    def __init__(self, directory):
        self.path = Path(directory) / "runtime" / "control.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as c:
            budget.schema(c)
            c.executescript("""
              CREATE TABLE IF NOT EXISTS nodes(id TEXT PRIMARY KEY, body TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS trees(id TEXT PRIMARY KEY, remaining INTEGER NOT NULL);
              CREATE TABLE IF NOT EXISTS decisions(id TEXT PRIMARY KEY, body TEXT NOT NULL);
            """)

    @contextmanager
    def connect(self):
        c = sqlite3.connect(self.path, timeout=20)
        try:
            c.execute("PRAGMA synchronous=FULL")
            c.execute("BEGIN IMMEDIATE")
            with c:
                yield c
        finally:
            c.close()

    @staticmethod
    def _get(c, run_id):
        r = c.execute("SELECT body FROM nodes WHERE id=?", (run_id,)).fetchone()
        return json.loads(r[0]) if r else None

    @staticmethod
    def _put(c, state):
        c.execute("INSERT OR REPLACE INTO nodes VALUES (?,?)", (state["run_id"], encoded(state)))

    def get(self, run_id):
        with self.connect() as c:
            return self._get(c, run_id)

    def start(self, run_id, allowance, total_nodes=None):
        if type(allowance) is not int or allowance < 0:
            raise ValueError("Nonnegative integer allowance required")
        with self.connect() as c:
            s = self._get(c, run_id)
            if s is None:
                s = dict(run_id=run_id, status="working", allowance=allowance, used=0,
                         total_actions=0, version=0, report=None, rounds=0, report_attempts=0,
                         session_id=None, costs={"research_seconds": 0., "report_seconds": 0., "judge_seconds": 0., "input_tokens": 0, "output_tokens": 0})
                budget.hold_reports(c, [run_id], allowance, partial=True)
                self._put(c, s)
            c.execute("INSERT OR IGNORE INTO trees VALUES (?,?)", (root(run_id),
                      total_nodes if total_nodes is not None else (72 if budget.scopes(c, run_id) else -1)))
            return s

    def unlimited(self, run_id):
        return not self.budgets(run_id) and self.remaining(run_id) == -1

    def patch(self, run_id, **values):
        with self.connect() as c:
            s = self._get(c, run_id)
            s.update(values)
            self._put(c, s)
            return s

    def cost(self, run_id, category, seconds, usage=None):
        with self.connect() as c:
            s = self._get(c, run_id)
            s["costs"][category + "_seconds"] += max(0., seconds)
            for k in ("input_tokens", "output_tokens"):
                s["costs"][k] += (usage or {}).get(k, 0) or 0
            self._put(c, s)

    def consume(self, run_id):
        with self.connect() as c:
            s = self._get(c, run_id)
            if s["status"] != "working" or s["used"] >= s["allowance"]:
                raise ValueError("Research paused: report and parent authorization required")
            s["used"] += 1
            s["total_actions"] += 1
            self._put(c, s)
            return s

    def save_report(self, run_id, report):
        validate_report(report, max_chars=None if self.unlimited(run_id) else 24000)
        with self.connect() as c:
            s = self._get(c, run_id)
            if s["status"] != "reporting":
                raise ValueError("Not reporting")
            budget.release_report(c, run_id)
            s.update(status="awaiting_parent", report=report, version=s["version"] + 1)
            self._put(c, s)
            return s

    def decide(self, run_id, version, decision, *, branch_cap=96, rounds_cap=6, depth_cap=6):
        uncapped = self.unlimited(run_id)
        validate_decision(decision, max_actions=None if uncapped else 18, max_branches=None if uncapped else 3)
        did = hashlib.sha256(f"{run_id}:{version}".encode()).hexdigest()
        with self.connect() as c:
            old = c.execute("SELECT body FROM decisions WHERE id=?", (did,)).fetchone()
            if old:
                old = json.loads(old[0])
                if old["decision"] != decision:
                    raise ValueError("Conflicting duplicate parent decision")
                return old
            s = self._get(c, run_id)
            if not s or s["status"] != "awaiting_parent" or s["version"] != version:
                raise ValueError("Stale or unreported child")
            action = decision["action"]
            record = dict(decision_id=did, run_id=run_id, report_version=version, decision=decision,
                          status="applied", children=[])
            if action == "continue":
                if not uncapped and (s["rounds"] >= rounds_cap or s["total_actions"] + decision["allowance"] > branch_cap):
                    raise ValueError("Continuation exceeds operational cap; revise allocation")
                budget.hold_reports(c, [run_id], decision["allowance"])
                if not budget.available(c, run_id):
                    raise budget.BudgetUnavailable("No research allowance remains")
                s.update(status="working", allowance=decision["allowance"], used=0,
                         rounds=s["rounds"] + 1, report_attempts=0, report_reason="allowance_exhausted", objective=decision["objective"])
            elif action == "fork":
                n = len(decision["branches"])
                left = c.execute("SELECT remaining FROM trees WHERE id=?", (root(run_id),)).fetchone()[0]
                if not uncapped and (depth(run_id) >= depth_cap or left < n):
                    raise ValueError("Fork exceeds depth or tree capacity; revise allocation")
                budget.hold_launches(c, run_id, n)
                budget.hold_reports(c, [child(run_id, i + 1) for i in range(n)], decision["allowance"])
                if not all(budget.available(c, child(run_id, i + 1)) for i in range(n)):
                    raise budget.BudgetUnavailable("No research allowance remains for children")
                if left >= 0:
                    c.execute("UPDATE trees SET remaining=remaining-? WHERE id=?", (n, root(run_id)))
                s["status"] = "forking"
                record["status"] = "reserved"
                record["children"] = [dict(run_id=child(run_id, i + 1), spec=b, status="reserved", session_id=None)
                                      for i, b in enumerate(decision["branches"])]
                # A node transfers its grant; it cannot continue alongside descendants.
            else:
                s["status"] = "completed" if action == "finish" else "pruned"
            s["decision_id"] = did
            self._put(c, s)
            c.execute("INSERT INTO decisions VALUES (?,?)", (did, encoded(record)))
            return record

    def decision(self, did):
        with self.connect() as c:
            r = c.execute("SELECT body FROM decisions WHERE id=?", (did,)).fetchone()
            return json.loads(r[0]) if r else None

    def launch_state(self, did, run_id, status, session_id=None):
        with self.connect() as c:
            r = json.loads(c.execute("SELECT body FROM decisions WHERE id=?", (did,)).fetchone()[0])
            item = next(x for x in r["children"] if x["run_id"] == run_id)
            item.update(status=status, session_id=session_id or item["session_id"])
            if status == "failed":
                budget.release_report(c, run_id)
            r["status"] = "executed" if all(x["status"] == "launched" for x in r["children"]) else "partial"
            c.execute("UPDATE decisions SET body=? WHERE id=?", (encoded(r), did))
            return r

    def claim_launch(self, did, run_id):
        """Only one concurrent controller can perform the external SDK fork."""
        with self.connect() as c:
            r = json.loads(c.execute("SELECT body FROM decisions WHERE id=?", (did,)).fetchone()[0])
            item = next(x for x in r["children"] if x["run_id"] == run_id)
            if item["status"] != "reserved":
                return False
            item["status"] = "launching"
            c.execute("UPDATE decisions SET body=? WHERE id=?", (encoded(r), did))
            return True

    def remaining(self, run_id):
        with self.connect() as c:
            r = c.execute("SELECT remaining FROM trees WHERE id=?", (root(run_id),)).fetchone()
            return r[0] if r else -1


    def freeze_budget(self, run_id, contract):
        with self.connect() as c:
            return budget.freeze(c, run_id, contract)

    def budgets(self, run_id):
        with self.connect() as c:
            return budget.scopes(c, run_id)

    def research_available(self, run_id):
        with self.connect() as c:
            return budget.available(c, run_id)

    def reserve_operation(self, run_id, phase):
        with self.connect() as c:
            return budget.reserve(c, run_id, phase)

    def settle_operation(self, op, elapsed, interrupted=False):
        with self.connect() as c:
            return budget.settle(c, op["operation_id"] if op else None, elapsed, interrupted=interrupted)

    def release_reporting(self, run_id):
        with self.connect() as c:
            budget.release_report(c, run_id)

    def finalize_budgets(self, run_id):
        """Trusted, durable endpoint after all owned work settles; no label is public."""
        import time
        with self.connect() as c:
            nodes = [json.loads(r[0]) for r in c.execute("SELECT body FROM nodes")]
            result = []
            for b in budget.scopes(c, run_id):
                if b["terminal"]:
                    result.append(b)
                    continue
                owned = [n for n in nodes if n["run_id"] == b["run_id"] or n["run_id"].startswith(b["run_id"] + "~")]
                if not owned or b["active"]:
                    continue
                statuses = {n["status"] for n in owned}
                if statuses - {"completed", "pruned", "failed", "cancelled", "reporting_blocked", "fork_blocked"}:
                    continue
                if b["violation"] or statuses & {"failed", "reporting_blocked", "fork_blocked"}:
                    reason = "infrastructure_failure"
                elif "cancelled" in statuses:
                    reason = "cancelled"
                elif "pruned" in statuses:
                    reason = "external_cutoff"
                elif any(n.get("terminal_reason") == "budget_endpoint" for n in owned):
                    reason = "budget_endpoint"
                else:
                    reason = "natural_finish"
                b["holds"] = {}
                b["action_holds"] = {}
                b["terminal"] = dict(reason=reason, at=time.time(), spent=b["spent"], actions=b["actions"])
                budget.put(c, b)
                result.append(b)
            return result
