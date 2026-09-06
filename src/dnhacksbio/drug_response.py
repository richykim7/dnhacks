"""Fixed observed-dose inhibition area and unit-level stratified randomization test.

Operator-only numerical implementation. No causal or synergy-evidence claim.
"""
from __future__ import annotations

from collections import defaultdict
from itertools import permutations, product
import math
import numpy as np

from .evalues import p_to_e

VERSION = "biomarker_auc.v1"
PROTOCOL_FIELDS = {"version", "drug", "exposure_hours", "biomarker", "dose_min_molar",
    "dose_max_molar", "input_scale", "normalization", "clipping", "aggregation",
    "missing_coverage", "direction", "permutations", "seed", "min_units", "assumptions"}
ROW_FIELDS = {"unit_id", "plate_id", "replicate_id", "dose_molar", "viability", "biomarker"}


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Expected finite number")
    return float(value)


def validate_protocol(p):
    if not isinstance(p, dict) or set(p) != PROTOCOL_FIELDS:
        raise ValueError("Invalid protocol fields")
    expected = {"version": VERSION, "normalization": "vehicle_normalized",
        "clipping": "reject", "aggregation": "mean_replicates_then_plates_then_donor",
        "missing_coverage": "reject", "direction": "two-sided"}
    if any(p[k] != v for k, v in expected.items()):
        raise ValueError("Unsupported protocol")
    for k in ("drug", "biomarker", "assumptions"):
        if not isinstance(p[k], str) or not p[k].strip():
            raise ValueError("Missing protocol declaration")
    if p["input_scale"] not in {"fraction", "percent"}:
        raise ValueError("Declare viability scale")
    if not 0 < number(p["dose_min_molar"]) < number(p["dose_max_molar"]):
        raise ValueError("Invalid dose range")
    if math.log(p["dose_max_molar"]) <= math.log(p["dose_min_molar"]):
        raise ValueError("Dose range too narrow for log integration")
    if number(p["exposure_hours"]) <= 0:
        raise ValueError("Invalid exposure")
    if p["permutations"] != "exact" and (type(p["permutations"]) is not int or p["permutations"] != 9999):
        raise ValueError("Use exact or 9999 permutations")
    if type(p["seed"]) is not int or not 0 <= p["seed"] < 2**32:
        raise ValueError("Invalid seed")
    if type(p["min_units"]) is not int or not 3 <= p["min_units"] <= 10000:
        raise ValueError("Invalid minimum units")


def prepare(cohort, protocol):
    """Collapse complete curves through the frozen hierarchy; aliases share one donor."""
    validate_protocol(protocol)
    if not isinstance(cohort, dict) or set(cohort) != {"rows", "units", "source"}:
        raise ValueError("Invalid cohort")
    if not isinstance(cohort["source"], str) or not cohort["source"].strip():
        raise ValueError("Source provenance required")
    units = cohort["units"]
    if not isinstance(units, dict) or not units or len(units) > 10000:
        raise ValueError("Invalid unit registry")
    donors = {}
    for uid, meta in units.items():
        if not isinstance(uid, str) or not uid or not isinstance(meta, dict) or set(meta) != {"donor_id", "stratum"}:
            raise ValueError("Invalid unit mapping")
        if any(not isinstance(v, str) or not v for v in meta.values()):
            raise ValueError("Missing donor/stratum")
        donor = meta["donor_id"]
        if donor in donors and donors[donor] != meta["stratum"]:
            raise ValueError("Donor crosses assay strata")
        donors[donor] = meta["stratum"]
    rows = cohort["rows"]
    if not isinstance(rows, list) or not 1 <= len(rows) <= 1000000:
        raise ValueError("Invalid rows")
    curves, biomarkers = defaultdict(dict), {}
    seen_units = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != ROW_FIELDS:
            raise ValueError("Invalid row fields")
        uid = row["unit_id"]
        if not isinstance(uid, str) or uid not in units:
            raise ValueError("Unregistered unit")
        seen_units.add(uid)
        for field in ("plate_id", "replicate_id"):
            if not isinstance(row[field], str) or not row[field]:
                raise ValueError("Missing nested observation identity")
        donor = units[uid]["donor_id"]
        bio = number(row["biomarker"])
        if donor in biomarkers and biomarkers[donor] != bio:
            raise ValueError("Inconsistent donor biomarker")
        biomarkers[donor] = bio
        dose, viability = number(row["dose_molar"]), number(row["viability"])
        if protocol["input_scale"] == "percent":
            viability /= 100
        if not 0 <= viability <= 1 or not protocol["dose_min_molar"] <= dose <= protocol["dose_max_molar"]:
            raise ValueError("Out-of-range dose or viability; no clipping")
        # Same donor/plate/replicate through another alias is a duplicate, never fresh data.
        key = (donor, row["plate_id"], row["replicate_id"])
        if dose in curves[key]:
            raise ValueError("Duplicate donor/plate/replicate/dose")
        curves[key][dose] = viability
    if seen_units != set(units):
        raise ValueError("Registered units missing observations")
    plates = defaultdict(list)
    lo, hi = protocol["dose_min_molar"], protocol["dose_max_molar"]
    for (donor, plate, _), points in sorted(curves.items()):
        doses = sorted(points)
        if len(doses) < 2 or doses[0] != lo or doses[-1] != hi:
            raise ValueError("Incomplete dose coverage; no extrapolation")
        x = np.log(doses)
        area = 1 - float(np.trapezoid([points[d] for d in doses], x)) / float(x[-1] - x[0])
        plates[donor, plate].append(area)
    donor_areas = defaultdict(list)
    for (donor, _), areas in sorted(plates.items()):
        donor_areas[donor].append(math.fsum(areas) / len(areas))
    ids = sorted(donor_areas)
    if len(ids) < protocol["min_units"]:
        raise ValueError("Insufficient independent donors")
    return {"unit_ids": ids, "biomarker": [biomarkers[d] for d in ids],
        "inhibition_area": [math.fsum(donor_areas[d]) / len(donor_areas[d]) for d in ids],
        "strata": [donors[d] for d in ids], "n_rows": len(rows), "n_curves": len(curves),
        "n_plates": len(plates), "exclusions": []}


def ranks(values):
    values = np.asarray(values, dtype=float)
    order = np.argsort(values, kind="stable")
    result = np.empty(len(values), dtype=float)
    start = 0
    while start < len(values):
        end = start + 1
        while end < len(values) and values[order[end]] == values[order[start]]:
            end += 1
        result[order[start:end]] = (start + end - 1) / 2
        start = end
    return result - result.mean()


def score(cohort, protocol):
    prepared = prepare(cohort, protocol)
    x, y = ranks(prepared["biomarker"]), ranks(prepared["inhibition_area"])
    denominator = float(np.linalg.norm(x) * np.linalg.norm(y))
    if denominator == 0:
        raise ValueError("Constant biomarker or response")
    effect = float(x @ y / denominator)
    groups = [np.array([i for i, s in enumerate(prepared["strata"]) if s == label])
              for label in sorted(set(prepared["strata"]))]
    space = math.prod(math.factorial(len(g)) for g in groups)
    if space <= 1:
        raise ValueError("No exchangeable units")
    observed = abs(effect)
    extreme = 0
    if protocol["permutations"] == "exact":
        if space > 100000:
            raise ValueError("Exact permutation budget exceeded")
        for choices in product(*(permutations(g.tolist()) for g in groups)):
            permuted = y.copy()
            for g, indices in zip(groups, choices):
                permuted[g] = y[list(indices)]
            extreme += abs(float(x @ permuted / denominator)) >= observed - 1e-12
        count, p = space, extreme / space
    else:
        rng = np.random.default_rng(protocol["seed"])
        count = protocol["permutations"]
        for _ in range(count):
            permuted = y.copy()
            for g in groups:
                permuted[g] = rng.permutation(y[g])
            extreme += abs(float(x @ permuted / denominator)) >= observed - 1e-12
        p = (1 + extreme) / (count + 1)
    return {"method": VERSION, "effect": effect, "p": p, "e": p_to_e(p),
        "null": "biomarker-response independence within frozen assay strata",
        "validity": "Requires declared donor independence, exchangeability and preselection",
        "assumptions": protocol["assumptions"], "n_units": len(x), "permutations": count,
        "extreme": extreme, "seed": protocol["seed"], "numpy_version": np.__version__,
        "prepared": prepared, "protocol": protocol, "source": cohort["source"]}
