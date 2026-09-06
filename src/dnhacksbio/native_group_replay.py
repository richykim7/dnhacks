"""Private finite independent-group replay using the shared canonical donor ledger.

The existing learned_evalue implementation owns the kernel and adaptive schedule.
This module owns only immutable canonical inputs and one atomic full-replay commit.
It does not support appending data or resuming a partially committed critic state.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import platform

import numpy as np

from .experiment_transport import REQUEST_ID
from .native_evidence import PrivateProcessStore, digest, names

METHOD = "protein-group-native-v1"
FIELDS = {"method", "null", "population", "panel_hash", "model_hash", "preprocessing_hash",
          "family", "parent", "sampling", "exclusions", "seed", "max_epochs"}


def runtime_hash():
    import torch
    from . import learned_evalue, expr_encoder, evalues, evalue_device, native_evidence
    return digest({"python": platform.python_version(), "numpy": np.__version__, "torch": torch.__version__,
                   "files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
                             [Path(__file__), *(Path(m.__file__) for m in
                               (learned_evalue, expr_encoder, evalues, evalue_device, native_evidence))]}})


def canonical_inputs(spec, group_a, group_b):
    if not isinstance(spec, dict) or set(spec) != FIELDS or spec["method"] != METHOD:
        raise ValueError("Invalid independent-group specification")
    names([spec[k] for k in ("null", "population", "family", "parent", "sampling")])
    for key in ("panel_hash", "model_hash", "preprocessing_hash"):
        v = spec[key]
        if not isinstance(v, str) or len(v) != 64 or any(c not in "0123456789abcdef" for c in v):
            raise ValueError("Frozen artifact SHA256 required")
    if type(spec["seed"]) is not int or not 0 <= spec["seed"] < 2**32:
        raise ValueError("Invalid seed")
    if type(spec["max_epochs"]) is not int or not 1 <= spec["max_epochs"] <= 500:
        raise ValueError("Invalid training budget")
    groups = []
    if not isinstance(spec["exclusions"], list):
        raise ValueError("Exclusions must be a list")
    seen = set(spec["exclusions"])
    if spec["exclusions"]:
        names(spec["exclusions"], unique=True)
    for group in (group_a, group_b):
        if not isinstance(group, dict) or set(group) != {"donors", "values"}:
            raise ValueError("Canonical donors and frozen measured representations required")
        ids = names(group["donors"], unique=True)
        if set(ids) & seen:
            raise ValueError("Repeated/excluded donor or same-donor tissue in opposite groups")
        seen.update(ids)
        values = np.asarray(group["values"], dtype=float)
        if values.ndim != 2 or len(values) != len(ids) or not 1 <= values.shape[1] <= 16000 or not np.isfinite(values).all():
            raise ValueError("Invalid representations")
        if len(ids) < 48:
            raise ValueError("At least 48 independent pairs required")
        # Seeded identity order fixed independently of observed values and input array order.
        order = sorted(range(len(ids)), key=lambda i: digest([spec["seed"], ids[i]]))
        groups.append({"donors": [ids[i] for i in order], "values": values[order].tolist()})
    if len(groups[0]["values"][0]) != len(groups[1]["values"][0]):
        raise ValueError("Mismatched representation dimensions")
    frozen = {**spec, "exclusions": sorted(spec["exclusions"]), "groups": groups,
              "schedule": "two-burn-in-batches-eight-pairs-finite-v1", "runtime_hash": runtime_hash()}
    return frozen


class PrivateGroupReplayStore(PrivateProcessStore):
    def __init__(self, directory):
        super().__init__(directory)
        with self.connect() as con:
            con.execute("CREATE TABLE IF NOT EXISTS group_results (process TEXT PRIMARY KEY, result TEXT NOT NULL)")

    def register(self, receipt, spec, group_a, group_b):
        if not isinstance(receipt, str) or not REQUEST_ID.fullmatch(receipt):
            raise ValueError("Invalid receipt")
        frozen = canonical_inputs(spec, group_a, group_b)
        key = digest(frozen)
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            old = con.execute("SELECT process FROM aliases WHERE receipt=?", (receipt,)).fetchone()
            if old and old[0] != key:
                raise ValueError("Conflicting receipt retry")
            con.execute("INSERT OR IGNORE INTO processes(id,spec) VALUES (?,?)", (key, json.dumps(frozen, allow_nan=False)))
            con.execute("INSERT OR IGNORE INTO aliases VALUES (?,?)", (receipt, key))
        return {"receipt": receipt, "status": "accepted"}

    def replay(self, receipt, *, before_commit=None):
        from .learned_evalue import learned_two_sample_e, LearnedEConfig, SamplingContract
        with self.connect() as con:
            row = con.execute("SELECT p.id,p.spec FROM processes p JOIN aliases a ON a.process=p.id WHERE a.receipt=?", (receipt,)).fetchone()
            if row is None:
                raise ValueError("Unregistered process")
            key, raw = row
            if con.execute("SELECT 1 FROM group_results WHERE process=?", (key,)).fetchone():
                return
        s = json.loads(raw)
        if digest(s) != key or s.get("method") != METHOD or s["runtime_hash"] != runtime_hash():
            raise ValueError("Wrong method or frozen runtime changed")
        a, b = s["groups"]
        config = LearnedEConfig(batch_pairs=8, burn_in=2, seed=s["seed"], max_epochs=s["max_epochs"],
                               pairing="in_order", device="cpu", hidden=(32, 32))
        result = learned_two_sample_e(a["values"], b["values"], genes=[f"feature-{i}" for i in range(len(a["values"][0]))],
            unit_a=a["donors"], unit_b=b["donors"], config=config,
            sampling=SamplingContract(mode="aggregated", source=key, assumptions=s["sampling"],
                                      unit_namespace="canonical-shared-ledger", input_scale="features"))
        if result.status != "ok":
            raise ValueError("Unavailable scoring schedule")
        report = result.to_dict()
        order = report["metadata"]["pair_order"]
        # Exact sets, not just batch numbers, for every predictably trained critic.
        sets = []
        for update in report["metadata"]["training_updates"]:
            v = update["validation_batch"] - 1
            sets.append({"training": order[:8*v], "validation": order[8*v:8*(v+1)],
                         "scoring": order[8*(v+1):8*(v+2)]})
        report.update(method=METHOD, process=key, unit_sets=sets, config=asdict(config),
                      export_policy="final wealth only; maximum is never an exported e-value")
        # Preserve all input consumption, including burn-in and unused imbalance, conservatively.
        all_ids = a["donors"] + b["donors"]
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            if con.execute("SELECT 1 FROM group_results WHERE process=?", (key,)).fetchone():
                return
            for donor in all_ids:
                if con.execute("SELECT 1 FROM consumed WHERE donor=?", (donor,)).fetchone():
                    raise ValueError("Canonical donor already consumed by another process/modality")
            log_path = report["log_wealth_path"]
            for n in range(1, len(log_path)):
                snapshot = {"unit_sets": sets[n-1], "schedule": s["schedule"], "process": key,
                            "mode": "atomic-finite-replay; no append checkpoint"}
                con.execute("INSERT INTO blocks VALUES (?,?,?,?,?,?)", (key, n-1, digest(snapshot),
                    math.exp(log_path[n]-log_path[n-1]), log_path[n], json.dumps(snapshot)))
            con.executemany("INSERT INTO consumed VALUES (?,?,?)", [(d,key,-1) for d in all_ids])
            con.execute("INSERT INTO group_results VALUES (?,?)", (key,json.dumps(report,allow_nan=False)))
            con.execute("UPDATE processes SET cursor=?,log_wealth=? WHERE id=?", (len(log_path)-1,log_path[-1],key))
            if before_commit:
                before_commit()

    def export(self, receipt):
        with self.connect() as con:
            row = con.execute("SELECT r.result FROM group_results r JOIN aliases a ON a.process=r.process WHERE a.receipt=?", (receipt,)).fetchone()
        if row is None:
            raise ValueError("Process incomplete")
        return json.loads(row[0])
