"""Collect only declared, bounded molecular files from a sandbox output directory."""
from __future__ import annotations

import json
import os
import stat
import time
from pathlib import Path
from uuid import uuid4

from .runtime import Journal

MAX_BYTES = 20 * 1024 * 1024
MAX_ATOMS = 100_000


def read_regular(root: Path, relative: str, limit: int) -> bytes:
    """No symlink components; O_NOFOLLOW and fstat guard the final file, too."""
    rel = Path(relative)
    if rel.is_absolute() or not rel.parts or any(p in {"..", "."} for p in rel.parts):
        raise ValueError("Artifact path must be contained and relative")
    current = root
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("Artifact symlinks are not permitted")
    if not current.resolve().is_relative_to(root.resolve()):
        raise ValueError("Artifact escaped output directory")
    fd = os.open(current, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as f:
        info = os.fstat(f.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise ValueError("Artifact must be a regular file within the size limit")
        raw = f.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("Artifact exceeds size limit")
    return raw


def validate_structure(raw: bytes, format: str) -> int:
    # Gemmi performs actual PDB/mmCIF parsing and validates coordinates.
    import gemmi
    text = raw.decode("utf-8")
    if format == "pdb":
        structure = gemmi.read_pdb_string(text)
    elif format == "cif":
        structure = gemmi.make_structure_from_block(gemmi.cif.read_string(text).sole_block())
    else:
        raise ValueError("Unsupported molecular format")
    import math
    count = 0
    for model in structure:
        for chain in model:
            for residue in chain:
                for atom in residue:
                    count += 1
                    if not all(math.isfinite(v) for v in (atom.pos.x, atom.pos.y, atom.pos.z)):
                        raise ValueError("Non-finite atomic coordinates")
                    if count > MAX_ATOMS:
                        raise ValueError("Structure exceeds atom limit")
    if not count:
        raise ValueError("No atoms could be read from structure")
    return count


def collect(output: Path, journal: Journal) -> list[dict]:
    if not (output / "manifest.json").exists() and not (output / "manifest.json").is_symlink():
        return []
    try:
        manifest = json.loads(read_regular(output, "manifest.json", 64 * 1024))
        entries = manifest["artifacts"]
        if manifest.get("schema_version") != 1 or not isinstance(entries, list) or len(entries) > 8:
            raise ValueError("Invalid artifact manifest/version or too many artifacts")
    except Exception as exc:
        return [{"artifact_id": uuid4().hex, "status": "rejected", "failure_reason": str(exc)}]
    artifacts, total = [], 0
    for entry in entries:
        a = {"artifact_id": uuid4().hex, "created_at": time.time(), "status": "rejected"}
        try:
            if isinstance(entry, dict) and entry.get("kind") == "tissue_simulation":
                from dnhacksbio.tissue.artifacts import collect_tissue
                a.update(collect_tissue(output, entry, journal))
                total += sum(c["byte_length"] for c in a["chunks"]) + a["byte_length"]
                if total > 64 * 1024 * 1024:
                    raise ValueError("Experiment artifact quota exceeded")
                artifacts.append(a)
                continue
            if not isinstance(entry, dict) or entry.get("kind") not in {"molecular_structure", "binder_bundle", "filament_trajectory"}:
                raise ValueError("Unsupported artifact kind")
            fmt = entry.get("format")
            prov = entry.get("provenance", {})
            if (prov.get("category") not in {"experimental_reference", "prediction", "derived_geometry", "illustration"}
                    or not isinstance(prov.get("source_ids"), list)
                    or not prov.get("tool") or not prov.get("tool_version")):
                raise ValueError("Artifact provenance incomplete")
            raw = read_regular(output, entry["path"], MAX_BYTES)
            total += len(raw)
            if total > 40 * 1024 * 1024:
                raise ValueError("Experiment artifact quota exceeded")
            if entry["kind"] == "binder_bundle":
                from dnhacksbio.binder.bundle import validate_bundle
                bundle = validate_bundle(raw)
                if prov != bundle["manifest"]["provenance"]:
                    raise ValueError("Binder provenance disagrees with bundle")
                key = journal.store_bytes(raw)
                a.update(status="available", kind="binder_bundle", format="json",
                         media_type="application/json", storage_key=key, sha256=key,
                         byte_length=len(raw), atom_count=len(bundle["structure"]["atoms"]),
                         provenance=prov, name=Path(entry["path"]).name,
                         binder_scope=bundle["manifest"]["scope"])
                artifacts.append(a)
                continue
            if entry["kind"] == "filament_trajectory":
                from ..spindle.bundle import validate
                bundle = validate(raw)
                if fmt != "json" or prov["category"] != ("illustration" if bundle["category"] == "illustration" else "derived_geometry"):
                    raise ValueError("Spindle format/provenance mismatch")
                key = journal.store_bytes(raw)
                a.update(status="available", kind="filament_trajectory", format="json",
                         media_type="application/json", storage_key=key, sha256=key,
                         byte_length=len(raw), provenance=prov, name=Path(entry["path"]).name)
                artifacts.append(a)
                continue
            count = validate_structure(raw, fmt)
            key = journal.store_bytes(raw)
            a.update(status="available", kind="molecular_structure", format=fmt,
                     media_type="chemical/x-pdb" if fmt == "pdb" else "chemical/x-mmcif",
                     storage_key=key, sha256=key, byte_length=len(raw), atom_count=count,
                     provenance=prov, name=Path(entry["path"]).name)
        except Exception as exc:
            a["status"] = "rejected"
            a["failure_reason"] = str(exc)
        artifacts.append(a)
    return artifacts
