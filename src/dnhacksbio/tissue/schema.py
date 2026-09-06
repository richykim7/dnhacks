"""Bounded tissue schema shared by collection, analysis and rendering."""

from __future__ import annotations
import hashlib
import json
import math

MAX_CELLS = 10000
MAX_VOXELS = 128**3
MAX_FRAMES = 120
MAX_BYTES = 64 * 1024 * 1024


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def digest(value):
    return hashlib.sha256(
        value if isinstance(value, bytes) else canonical(value)
    ).hexdigest()


def finite(value, low=-math.inf, high=math.inf):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not low <= value <= high
    ):
        raise ValueError("Nonfinite or out-of-range numerical value")
    return value


def validate(data):
    if (
        not isinstance(data, dict)
        or data.get("kind") != "tissue_simulation"
        or data.get("schema_version") != 1
    ):
        raise ValueError("Unsupported tissue schema")
    if data.get("category") not in {"illustration", "simulation"}:
        raise ValueError("Tissue category required")
    bounds = data["domain"]["bounds"]
    if len(bounds) != 6 or data["domain"]["units"] != "µm":
        raise ValueError("Expected right-handed xyz micrometer domain")
    if (
        data["domain"].get("axis_order", "xyz") != "xyz"
        or data["domain"].get("handedness", "right") != "right"
    ):
        raise ValueError("Unsupported world coordinate transform")
    for v in bounds:
        finite(v, -1e6, 1e6)
    if any(bounds[i] >= bounds[i + 3] for i in range(3)):
        raise ValueError("Empty domain")
    lo, hi = data["field_range"]
    finite(lo, 0)
    finite(hi, lo + 1e-12)
    conditions = data["conditions"]
    if not 1 <= len(conditions) <= 16:
        raise ValueError("Condition limit")
    condition_ids = set()
    budget = 0
    timeline = None
    for condition in conditions:
        if condition["id"] in condition_ids:
            raise ValueError("Duplicate condition")
        condition_ids.add(condition["id"])
        frames = condition["frames"]
        if not 1 <= len(frames) <= MAX_FRAMES:
            raise ValueError("Frame limit")
        times = [f["time"] for f in frames]
        if timeline is None:
            timeline = times
        elif times != timeline:
            raise ValueError("Paired conditions require identical exact-frame times")
        previous = {}
        last = -1
        for frame in frames:
            finite(frame["time"], 0, 1e6)
            if frame["time"] <= last:
                raise ValueError("Frames not strictly ordered")
            last = frame["time"]
            cells = frame["cells"]
            if not 1 <= len(cells) <= MAX_CELLS:
                raise ValueError("Cell limit")
            ids = set()
            for cell in cells:
                cid = cell["id"]
                if type(cid) is not int or cid < 0 or cid in ids:
                    raise ValueError("Invalid cell ID")
                ids.add(cid)
                if (
                    previous.get(cid, {}).get("state") == "dead"
                    and cell["state"] != "dead"
                ):
                    raise ValueError("Dead cell cannot silently revive")
                if (
                    previous
                    and cid not in previous
                    and cell.get("parent_id") not in previous
                ):
                    raise ValueError("New cell requires known parent")
                if cell["type"] not in {"tumor", "CAF"} or cell["state"] not in {
                    "alive",
                    "dead",
                }:
                    raise ValueError("Unknown cell code")
                if len(cell["position"]) != 3:
                    raise ValueError("Invalid position")
                for i, v in enumerate(cell["position"]):
                    finite(v, bounds[i], bounds[i + 3])
                finite(cell["radius"], 0.01, 1000)
                finite(cell["alanine"], 0, hi)
                if "volume" in cell:
                    volume = finite(cell["volume"], 0.000001)
                    if not math.isclose(
                        volume, 4 * math.pi * cell["radius"] ** 3 / 3, rel_tol=1e-5
                    ):
                        raise ValueError("Cell radius/volume mismatch")
                if cell.get("parent_id") is not None and (
                    type(cell["parent_id"]) is not int or cell["parent_id"] < 0
                ):
                    raise ValueError("Invalid parent ID")
            absent = set(previous) - ids
            if absent != set(frame.get("removed_ids", [])) or any(
                previous[c]["state"] != "dead" for c in absent
            ):
                raise ValueError(
                    "Cell disappearance requires explicit previously dead removal"
                )
            previous = {c["id"]: c for c in cells}
            dims = frame["field"]["dimensions"]
            if len(dims) != 3 or any(
                type(n) is not int or n < 2 or n > 128 for n in dims
            ):
                raise ValueError("Invalid field shape")
            n = math.prod(dims)
            if n > MAX_VOXELS or len(frame["field"]["values"]) != n:
                raise ValueError("Field shape mismatch")
            budget += n * 4 + len(cells) * 128
            if budget > MAX_BYTES:
                raise ValueError("Decoded tissue quota exceeded")
            for v in frame["field"]["values"]:
                finite(v, lo, hi)
    if not isinstance(data.get("provenance"), dict) or not isinstance(
        data.get("analysis"), dict
    ):
        raise ValueError("Missing provenance/analysis")
    if data["category"] == "simulation":
        if data["analysis"].get("analysis_class") != "simulation_sensitivity":
            raise ValueError("Simulation analysis class required")
        for key in ["model", "simulation", "visual_schema"]:
            if not isinstance(data.get(key), dict):
                raise ValueError("Missing reproducibility manifest")
        if data["simulation"].get("completion_status") != "completed":
            raise ValueError("Incomplete simulation cannot be collected")
    return data
