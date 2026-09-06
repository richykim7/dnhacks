"""Operator-owned immutable episodes, prefixes and private review records.

Run under a separate account. File modes limit other users, not unrestricted same-user agents.
No score or review decision is written back to the research journal/database.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from .statistics import split_group


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def belongs(run, ancestor):
    return run == ancestor or run.startswith(ancestor + "~")


class MonitorStore:
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.directory, 0o700)
        self.path = self.directory / "monitor.sqlite3"
        with self.connect() as c:
            c.executescript('''
              CREATE TABLE IF NOT EXISTS episodes(id TEXT PRIMARY KEY, body TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS checkpoints(episode TEXT, version INTEGER, body TEXT NOT NULL,
                PRIMARY KEY(episode,version));
              CREATE TABLE IF NOT EXISTS reviews(id TEXT PRIMARY KEY, body TEXT NOT NULL);
            ''')
        os.chmod(self.path, 0o600)

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

    def enroll(self, *, episode_id, run_id, root_id, group_id, objective, initial_evidence,
               protocol, start_sequence, calibration_unit=False, subgroup="unspecified"):
        required = {"policy_id", "rubric", "verifier_model", "verifier_prompt_version", "corpus_hash",
                    "budget_unit", "terminal_budget", "disclosure_boundary", "sampling_policy"}
        if set(protocol) != required or any(not protocol[k] for k in required):
            raise ValueError("Explicit frozen protocol required")
        if type(protocol["terminal_budget"]) not in (int, float) or not math.isfinite(protocol["terminal_budget"]) or protocol["terminal_budget"] <= 0:
            raise ValueError("Finite positive terminal budget required")
        if not all(isinstance(x, str) and x.strip() for x in (episode_id, run_id, root_id, group_id, objective)):
            raise ValueError("Episode identity and objective required")
        if not belongs(run_id, root_id) or not isinstance(initial_evidence, list):
            raise ValueError("Invalid lineage or initial snapshot")
        if type(start_sequence) is not int or start_sequence < 0:
            raise ValueError("Invalid start cursor")
        body = dict(episode_id=episode_id, run_id=run_id, root_id=root_id, group_id=group_id,
                    objective=objective, initial_evidence=initial_evidence, protocol=protocol,
                    protocol_hash=digest(protocol), start_sequence=start_sequence, calibration_unit=calibration_unit,
                    subgroup=subgroup, partition=split_group(group_id), outcome="unknown", status="open",
                    label_provenance=None, enrolled_at=time.time())
        with self.connect() as c:
            old = c.execute("SELECT body FROM episodes WHERE id=?", (episode_id,)).fetchone()
            if old:
                old = json.loads(old[0])
                if any(old[k] != v for k, v in body.items() if k not in {"enrolled_at", "outcome", "status", "label_provenance"}):
                    raise ValueError("Episode is frozen; cannot refresh endpoint or objective")
                return old
            if calibration_unit:
                all_rows = [json.loads(r[0]) for r in c.execute("SELECT body FROM episodes")]
                if any(e["calibration_unit"] and e["group_id"] == group_id for e in all_rows):
                    raise ValueError("Only one preselected calibration unit per related group")
            c.execute("INSERT INTO episodes VALUES (?,?)", (episode_id, canonical(body)))
        return body

    def episodes(self):
        with self.connect() as c:
            return [json.loads(r[0]) for r in c.execute("SELECT body FROM episodes ORDER BY id")]

    def episode(self, eid):
        with self.connect() as c:
            row = c.execute("SELECT body FROM episodes WHERE id=?", (eid,)).fetchone()
        if not row:
            raise FileNotFoundError("Episode unavailable")
        return json.loads(row[0])

    def checkpoints(self, eid):
        with self.connect() as c:
            return [json.loads(r[0]) for r in c.execute("SELECT body FROM checkpoints WHERE episode=? ORDER BY version", (eid,))]

    def append_checkpoint(self, eid, prefix, *, cost, verifier_score, monitor_statistic=None, threshold=None, error=None, scoring_version=None, verifier_cost=None):
        if type(cost) not in (int, float) or not math.isfinite(cost) or cost < 0:
            raise ValueError("Finite measured cumulative cost required")
        for name, v in [("verifier", verifier_score), ("statistic", monitor_statistic), ("threshold", threshold)]:
            if v is not None and (type(v) not in (int, float) or not math.isfinite(v) or v < 0 or name == "verifier" and v > 1):
                raise ValueError("Invalid private measurement")
        ep = self.episode(eid)
        if ep["status"] != "open":
            raise ValueError("Closed episode cannot acquire new monitor readings")
        if set(prefix) != {"through_sequence", "events", "report", "report_version"}:
            raise ValueError("Invalid prefix envelope")
        seq = prefix["through_sequence"]
        if type(seq) is not int or seq <= ep["start_sequence"]:
            raise ValueError("Checkpoint must follow enrollment")
        if any(e["sequence"] > seq for e in prefix["events"]):
            raise ValueError("Future event in prefix")
        if cost > ep["protocol"]["terminal_budget"]:
            raise ValueError("Checkpoint exceeds fixed endpoint")
        version = prefix["report_version"]
        if type(version) is not int or version < 1:
            raise ValueError("Invalid report version")
        record = dict(episode_id=eid, checkpoint=version, prefix_hash=digest(prefix), prefix=prefix,
                      cumulative_cost=cost, remaining_budget=ep["protocol"]["terminal_budget"] - cost,
                      verifier_score=verifier_score, monitor_statistic=monitor_statistic, threshold=threshold,
                      would_stop=bool(threshold is not None and monitor_statistic is not None and monitor_statistic > threshold),
                      error=error, scoring_version=scoring_version, verifier_cost=verifier_cost or {}, mode="observation_only")
        with self.connect() as c:
            old = c.execute("SELECT body FROM checkpoints WHERE episode=? AND version=?", (eid, version)).fetchone()
            if old:
                old = json.loads(old[0])
                if old != record:
                    raise ValueError("Checkpoint immutable")
                return old
            current = json.loads(c.execute("SELECT body FROM episodes WHERE id=?", (eid,)).fetchone()[0])
            if current["status"] != "open":
                raise ValueError("Closed episode cannot acquire new monitor readings")
            # Serialize comparison with insertion, including concurrent worker calls.
            latest = c.execute("SELECT body FROM checkpoints WHERE episode=? ORDER BY version DESC LIMIT 1", (eid,)).fetchone()
            if latest:
                last = json.loads(latest[0])
                if version <= last["checkpoint"] or seq <= last["prefix"]["through_sequence"] or cost < last["cumulative_cost"]:
                    raise ValueError("Checkpoint/cost must advance monotonically")
            c.execute("INSERT INTO checkpoints VALUES (?,?,?)", (eid, version, canonical(record)))
        return record

    def close(self, eid, *, termination, evidence=None, pending_verification=False, provenance):
        """Only a completed fixed-policy continuation can be a negative example."""
        if not isinstance(provenance, dict) or not provenance.get("assessor") or not provenance.get("artifact_refs"):
            raise ValueError("Final assessment needs assessor and artifact provenance")
        if termination not in {"natural_finish", "budget_endpoint", "infrastructure_failure", "external_cutoff", "cancelled"}:
            raise ValueError("Unknown terminal condition")
        with self.connect() as c:
            row = c.execute("SELECT body FROM episodes WHERE id=?", (eid,)).fetchone()
            if not row:
                raise FileNotFoundError("Episode unavailable")
            ep = json.loads(row[0])
            if ep["status"] == "closed":
                raise ValueError("Outcome is immutable; start a new declared objective")
            qualified = []
            for f in evidence or []:
                if not belongs(f["run_id"], ep["run_id"]):
                    raise ValueError("Evidence outside monitored subtree")
                if f["finding_id"] in ep["initial_evidence"]:
                    continue
                if all(f.get(k) is True for k in ("verified", "relevant", "nonduplicate", "evidence_supported")) and f.get("artifact_refs"):
                    qualified.append(f)
            if qualified:
                outcome, status = "success", "closed"
            elif pending_verification:
                outcome, status = "pending", "adjudicating"
            elif termination in {"natural_finish", "budget_endpoint"}:
                outcome, status = "unsuccessful", "closed"
            else:
                outcome, status = "censored", "closed"
            ep.update(outcome=outcome, status=status, label_provenance={"termination": termination,
                "evidence": qualified, **provenance}, closed_at=time.time())
            c.execute("UPDATE episodes SET body=? WHERE id=?", (canonical(ep), eid))
        return ep

    def associate_review(self, *, receipt, run_id, experiment_id, finding_id, method_id, null,
                         validity_policy, evidence, provenance, disclosure_boundary):
        values = (receipt, run_id, experiment_id, finding_id, method_id, null, validity_policy, disclosure_boundary)
        if not all(isinstance(x, str) and x.strip() for x in values) or not provenance or not isinstance(evidence, dict):
            raise ValueError("Complete immutable evidence association required")
        rid = digest({"receipt": receipt, "finding": finding_id})
        association = dict(receipt=receipt, run_id=run_id, experiment_id=experiment_id, finding_id=finding_id,
                    method_id=method_id, null=null, validity_policy=validity_policy, evidence=evidence,
                    provenance=provenance, disclosure_boundary=disclosure_boundary)
        record = dict(review_id=rid, association=association, decision=None, note=None, disclosed=False)
        with self.connect() as c:
            old = c.execute("SELECT body FROM reviews WHERE id=?", (rid,)).fetchone()
            if old:
                old = json.loads(old[0])
                if old["association"] != association:
                    raise ValueError("Receipt association is immutable")
                return old
            c.execute("INSERT INTO reviews VALUES (?,?)", (rid, canonical(record)))
        return record

    def review(self, rid, decision, note):
        if decision not in {"accepted", "rejected", "unavailable"} or not isinstance(note, str) or not note.strip():
            raise ValueError("Explicit decision and note required")
        with self.connect() as c:
            row = c.execute("SELECT body FROM reviews WHERE id=?", (rid,)).fetchone()
            if not row:
                raise FileNotFoundError("Review unavailable")
            r = json.loads(row[0])
            if r["decision"] and (r["decision"], r["note"]) != (decision, note):
                raise ValueError("Review decision already recorded")
            r.update(decision=decision, note=note)
            c.execute("UPDATE reviews SET body=? WHERE id=?", (canonical(r), rid))
        return r

    def reviews(self, run_id):
        with self.connect() as c:
            rows = [json.loads(r[0]) for r in c.execute("SELECT body FROM reviews")]
        return [r for r in rows if r["association"]["run_id"] == run_id]

    def disclosure_export(self, boundary, *, authorized=False):
        if not authorized:
            raise PermissionError("Explicit operator authorization at the frozen boundary required")
        with self.connect() as c:
            rows = [json.loads(r[0]) for r in c.execute("SELECT body FROM reviews")]
            selected = [r for r in rows if r["association"]["disclosure_boundary"] == boundary and r["decision"]]
            for r in selected:
                r["disclosed"] = True
                c.execute("UPDATE reviews SET body=? WHERE id=?", (canonical(r), r["review_id"]))
        # Export does not mutate research memory, graph, or ordinary feedback.
        return selected

    def export(self):
        result = []
        for ep in self.episodes():
            rows = self.checkpoints(ep["episode_id"])
            result.append({**ep, "scores": [r["verifier_score"] for r in rows],
                           "costs": [r["cumulative_cost"] for r in rows], "histories": rows})
        return result
