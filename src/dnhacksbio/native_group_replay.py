"""Private finite independent-group replay using the shared canonical donor ledger.

The existing learned_evalue implementation owns the kernel and adaptive schedule.
This module binds canonical inputs, the optional source-frozen linear witness,
and one atomic full-replay commit shared by both routes.
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
FROZEN_METHOD = "protein-group-frozen-linear-v1"
FIELDS = {"method", "null", "population", "panel_hash", "model_hash", "preprocessing_hash",
          "family", "parent", "sampling", "exclusions", "seed", "max_epochs"}
FROZEN_FIELDS = (FIELDS - {"max_epochs"}) | {"witness"}


def validate_witness(witness):
    if not isinstance(witness, dict) or set(witness) != {"coefficients", "intercept", "feature_ids", "artifact_sha256"}:
        raise ValueError("Invalid frozen witness")
    features = names(witness["feature_ids"], unique=True)
    coef = np.asarray(witness["coefficients"], dtype=float)
    if coef.shape != (len(features),) or not 1 <= len(coef) <= 16000 or not np.isfinite(coef).all():
        raise ValueError("Invalid frozen coefficients")
    if isinstance(witness["intercept"], bool) or not isinstance(witness["intercept"], (int, float)) or not math.isfinite(witness["intercept"]):
        raise ValueError("Invalid frozen intercept")
    value = witness["artifact_sha256"]
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("Frozen witness artifact hash required")
    return witness


def witness_from_artifact(path):
    """Read the actual source-fitted module coefficients, never fit on submitted data."""
    path = Path(path)
    with np.load(path, allow_pickle=False) as a:
        witness = {"coefficients": a["module_coefficients"].tolist(),
                   "intercept": float(a["module_intercept"]),
                   "feature_ids": a["symbols"].tolist(),
                   "artifact_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    return validate_witness(witness)


def runtime_hash():
    import torch
    from . import learned_evalue, expr_encoder, evalues, evalue_device, native_evidence
    return digest({"python": platform.python_version(), "numpy": np.__version__, "torch": torch.__version__,
                   "files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
                             [Path(__file__), *(Path(m.__file__) for m in
                               (learned_evalue, expr_encoder, evalues, evalue_device, native_evidence))]}})


def canonical_inputs(spec, group_a, group_b):
    if not isinstance(spec, dict) or spec.get("method") not in {METHOD, FROZEN_METHOD}:
        raise ValueError("Invalid independent-group specification")
    frozen_mode = spec["method"] == FROZEN_METHOD
    if set(spec) != (FROZEN_FIELDS if frozen_mode else FIELDS):
        raise ValueError("Invalid independent-group fields")
    if frozen_mode:
        witness = validate_witness(spec["witness"])
        if digest(witness) != spec["model_hash"]:
            raise ValueError("Frozen witness/model hash mismatch")
    names([spec[k] for k in ("null", "population", "family", "parent", "sampling")])
    for key in ("panel_hash", "model_hash", "preprocessing_hash"):
        v = spec[key]
        if not isinstance(v, str) or len(v) != 64 or any(c not in "0123456789abcdef" for c in v):
            raise ValueError("Frozen artifact SHA256 required")
    if type(spec["seed"]) is not int or not 0 <= spec["seed"] < 2**32:
        raise ValueError("Invalid seed")
    if not frozen_mode and (type(spec["max_epochs"]) is not int or not 1 <= spec["max_epochs"] <= 500):
        raise ValueError("Invalid training budget")
    groups = []
    if not isinstance(spec["exclusions"], list):
        raise ValueError("Exclusions must be a list")
    seen = set(spec["exclusions"])
    if spec["exclusions"]:
        names(spec["exclusions"], unique=True)
    for group in (group_a, group_b):
        if not isinstance(group, dict) or set(group) != ({"donors", "values", "feature_ids"} if frozen_mode else {"donors", "values"}):
            raise ValueError("Canonical donors and frozen measured representations required")
        if frozen_mode and group["feature_ids"] != witness["feature_ids"]:
            raise ValueError("Frozen feature order mismatch")
        ids = names(group["donors"], unique=True)
        if set(ids) & seen:
            raise ValueError("Repeated/excluded donor or same-donor tissue in opposite groups")
        seen.update(ids)
        values = np.asarray(group["values"], dtype=float)
        if values.ndim != 2 or len(values) != len(ids) or not 1 <= values.shape[1] <= 16000 or not np.isfinite(values).all():
            raise ValueError("Invalid representations")
        if len(ids) < 48:
            raise ValueError("At least 48 independent pairs required")
        if frozen_mode and values.shape[1] != len(witness["feature_ids"]):
            raise ValueError("Frozen feature dimension mismatch")
        # Seeded identity order fixed independently of observed values and input array order.
        order = sorted(range(len(ids)), key=lambda i: digest([spec["seed"], ids[i]]))
        groups.append({"donors": [ids[i] for i in order], "values": values[order].tolist()})
        if frozen_mode:
            groups[-1]["feature_ids"] = list(witness["feature_ids"])
    if len(groups[0]["values"][0]) != len(groups[1]["values"][0]):
        raise ValueError("Mismatched representation dimensions")
    frozen = {**spec, "exclusions": sorted(spec["exclusions"]), "groups": groups,
              "schedule": "two-burn-in-batches-eight-pairs-finite-v1", "runtime_hash": runtime_hash()}
    return frozen


def frozen_report(s, key):
    import torch
    from .learned_evalue import _log_payoffs
    from .evalues import from_log
    witness = validate_witness(s["witness"])
    a,b = s["groups"]
    pairs = min(len(a["donors"]), len(b["donors"]))
    order = list(map(list, zip(a["donors"][:pairs], b["donors"][:pairs])))
    coef = torch.tensor(witness["coefficients"], dtype=torch.float64)
    def model(x):
        score = x @ coef + witness["intercept"]
        if not torch.isfinite(score).all():
            raise ValueError("Nonfinite frozen witness output")
        return score
    x,y = (torch.tensor(g["values"][:pairs], dtype=torch.float64) for g in (a,b))
    path = [0.]
    sets = []
    with torch.no_grad():
        for start in range(16, pairs, 8):
            end = min(start+8, pairs)
            logs = _log_payoffs(model, x[start:end], y[start:end], 4.)
            if not torch.isfinite(logs).all():
                raise ValueError("Nonfinite frozen witness payoff")
            path.append(path[-1] + float(logs.sum()))
            sets.append({"training": [], "validation": [], "scoring": order[start:end]})
    # The tested process exports final wealth. No process fits or updates a witness.
    return {"status": "ok", "method": FROZEN_METHOD, "process": key,
            "reason": "", "n_pairs": pairs, "n_batches": math.ceil(pairs/8), "n_scored": len(sets),
            "per_batch": [math.exp(b-a) for a,b in zip(path,path[1:])],
            "null": s["null"], "population": s["population"],
            "log_e_value": path[-1], "e_value": from_log(path[-1]), "log_wealth_path": path,
            "unit_sets": sets, "config": {"burn_in": 2, "batch_pairs": 8, "critic": "externally-frozen-linear"},
            "metadata": {"pair_order": order, "scored_pairs": pairs-16, "burn_in_pairs": order[:16],
                         "training_updates": [], "model_hash": s["model_hash"], "artifact_sha256": witness["artifact_sha256"]},
            "export_policy": "final wealth only; no confirmation-data fitting"}


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
        with self.connect() as con:
            row = con.execute("SELECT p.id,p.spec FROM processes p JOIN aliases a ON a.process=p.id WHERE a.receipt=?", (receipt,)).fetchone()
            if row is None:
                raise ValueError("Unregistered process")
            key, raw = row
            if con.execute("SELECT 1 FROM group_results WHERE process=?", (key,)).fetchone():
                return
        s = json.loads(raw)
        if digest(s) != key or s.get("method") not in {METHOD, FROZEN_METHOD} or s["runtime_hash"] != runtime_hash():
            raise ValueError("Wrong method or frozen runtime changed")
        a, b = s["groups"]
        if s["method"] == FROZEN_METHOD:
            report = frozen_report(s, key)
            sets = report["unit_sets"]
        else:
            report, sets = self._adaptive_report(s, key)
        self._commit_report(key, s, a, b, report, sets, before_commit)

    @staticmethod
    def _adaptive_report(s, key):
        from .learned_evalue import learned_two_sample_e, LearnedEConfig, SamplingContract
        a,b = s["groups"]
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
        return report, sets

    def _commit_report(self, key, s, a, b, report, sets, before_commit):
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
