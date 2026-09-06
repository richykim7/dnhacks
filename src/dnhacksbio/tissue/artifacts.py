"""Content-addressed frame chunks. Only collector-owned references grant blob access."""

from __future__ import annotations
import json
import struct
from pathlib import Path
from .schema import MAX_BYTES, canonical, digest, validate


def collect_tissue(output: Path, entry: dict, journal):
    from dnhacksbio.explorer.artifacts import read_regular

    raw = read_regular(output, entry["path"], MAX_BYTES)
    if entry.get("sha256") and digest(raw) != entry["sha256"]:
        raise ValueError("Tissue hash mismatch")
    data = validate(json.loads(raw))
    chunks = []
    for condition in data["conditions"]:
        frames = []
        for frame in condition["frames"]:
            cells = canonical(frame["cells"])
            values = frame["field"]["values"]
            field = struct.pack("<" + "f" * len(values), *values)
            cell_key = journal.store_bytes(cells)
            field_key = journal.store_bytes(field)
            refs = [
                dict(
                    storage_key=cell_key,
                    sha256=cell_key,
                    byte_length=len(cells),
                    media_type="application/json",
                ),
                dict(
                    storage_key=field_key,
                    sha256=field_key,
                    byte_length=len(field),
                    media_type="application/octet-stream",
                ),
            ]
            chunks.extend(refs)
            frames.append(
                dict(
                    time=frame["time"],
                    cell_chunk=refs[0],
                    field_chunk=refs[1],
                    cell_count=len(frame["cells"]),
                    field=dict(
                        dimensions=frame["field"]["dimensions"],
                        dtype="float32-le",
                        axis_order="x-fastest",
                        units="mM",
                    ),
                )
            )
        condition["frames"] = frames
    data["chunked"] = True
    key = journal.store_bytes(canonical(data))
    return dict(
        status="available",
        kind="tissue_simulation",
        schema_version=1,
        name=data["name"],
        storage_key=key,
        sha256=key,
        byte_length=len(canonical(data)),
        chunks=chunks,
        provenance=data["provenance"],
        media_type="application/json",
    )


def frame_parts(journal, manifest_key, condition_index, frame_index):
    manifest = json.loads(journal.read_blob(manifest_key))
    if manifest.get("kind") != "tissue_simulation" or not manifest.get("chunked"):
        raise ValueError("Not a chunked tissue artifact")
    if condition_index < 0 or frame_index < 0:
        raise ValueError("Negative frame index")
    frame = manifest["conditions"][condition_index]["frames"][frame_index]
    raw = journal.read_blob(frame["field_chunk"]["storage_key"])
    dims = frame["field"]["dimensions"]
    if len(raw) > MAX_BYTES or len(raw) != dims[0] * dims[1] * dims[2] * 4:
        raise ValueError("Invalid field chunk")
    cells = json.loads(journal.read_blob(frame["cell_chunk"]["storage_key"]))
    return dict(time=frame["time"], cells=cells, field=dict(dimensions=dims)), raw


def read_frame(journal, manifest_key, condition_index, frame_index):
    frame, raw = frame_parts(journal, manifest_key, condition_index, frame_index)
    cells = frame["cells"]
    dims = frame["field"]["dimensions"]
    return dict(
        time=frame["time"],
        cells=cells,
        field=dict(
            dimensions=dims,
            values=list(struct.unpack("<" + "f" * (len(raw) // 4), raw)),
        ),
    )
