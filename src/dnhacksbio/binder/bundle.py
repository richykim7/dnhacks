"""Portable, content-addressed binder bundle and collector validation."""
from __future__ import annotations
import base64
import io
import json

import gemmi
import pyarrow as pa
import pyarrow.parquet as pq

from .geometry import canonical, digest, evaluate_interface, parse_structure, select_chains

SCHEMA = "binder_bundle.v1"


def make_bundle(raw: bytes, fmt: str, *, target_chains: list[str], binder_chains: list[str],
                candidate_id: str, provenance: dict, scope: dict, source_evidence: list[dict],
                assembly: str = "context unavailable", protocol: dict | None = None) -> dict:
    structure = parse_structure(raw, fmt)
    metrics = evaluate_interface(structure, target_chains, binder_chains, candidate_id=candidate_id)
    target = select_chains(structure, target_chains)
    binder = select_chains(structure, binder_chains)
    # Re-serialize the selected physical model to mmCIF; author and label mapping stays explicit.
    s = (gemmi.read_pdb_string(raw.decode()) if fmt == "pdb" else
         gemmi.make_structure_from_block(gemmi.cif.read_string(raw.decode()).sole_block()))
    while len(s) > 1:
        del s[1]
    complex_cif = s.make_mmcif_document().as_string().encode()
    target_s = s.clone()
    for i in reversed(range(len(target_s[0]))):
        if target_s[0][i].name not in target_chains:
            del target_s[0][i]
    fasta = ""
    for chain in binder_chains:
        seq = "".join(gemmi.find_tabulated_residue(r["name"]).one_letter_code.upper()
                      for r in binder["residues"] if r["chain"] == chain)
        fasta += f">{candidate_id}|{chain}\n{seq}\n"
    sink = io.BytesIO()
    # Explicit schema also makes zero-contact candidates valid Parquet tables.
    contact_schema = pa.schema([(k, pa.int64() if k in {"target_atom", "binder_atom"} else
                                 pa.float64() if k == "distance_angstrom" else pa.string())
                                for k in ("candidate_id", "target_residue", "binder_residue", "target_atom",
                                          "binder_atom", "target_atom_name", "binder_atom_name",
                                          "distance_angstrom", "rule")])
    pq.write_table(pa.Table.from_pylist(metrics["contacts"], schema=contact_schema), sink)
    resolved = protocol or {"engine": "import", "seed": None, "method_version": "binder-interface.v1"}
    blobs = {"source." + fmt: raw, "candidate.cif": complex_cif,
             "target.cif": target_s.make_mmcif_document().as_string().encode(),
             "binder.fasta": fasta.encode(), "residue_map.json": canonical(structure["residues"]),
             "interface_metrics.json": canonical(metrics), "contacts.parquet": sink.getvalue(),
             "protocol.json": canonical(resolved)}
    return {"schema": SCHEMA, "manifest": {"producer": "dnhacksbio.binder", "version": "1",
            "candidate_id": candidate_id, "scope": scope, "provenance": provenance,
            "source_evidence": source_evidence, "assembly": assembly,
            "parent_artifacts": [digest(raw)], "crop_transform": target["crop_transform"],
            "validation_status": "exploratory", "method_version": "binder-interface.v1"},
            "structure": structure, "target_chains": target_chains, "binder_chains": binder_chains,
            "metrics": metrics, "protocol": resolved,
            "files": {name: {"sha256": digest(value), "byte_length": len(value),
                             "base64": base64.b64encode(value).decode()} for name, value in blobs.items()}}


def validate_bundle(raw: bytes, expected_scope: dict | None = None) -> dict:
    if len(raw) > 20 * 1024 * 1024:
        raise ValueError("Binder bundle exceeds byte cap")
    b = json.loads(raw)
    canonical(b)  # Reject NaN/Infinity even in optional metadata.
    if b.get("schema") != SCHEMA:
        raise ValueError("Unsupported binder bundle version")
    m = b["manifest"]
    if m.get("validation_status") != "exploratory" or m.get("method_version") != "binder-interface.v1":
        raise ValueError("Binder bundle cannot assert a statistical verdict")
    if set(m["scope"]) != {"project_id", "run_id", "experiment_id"} or any(
            not isinstance(v, str) or not v for v in m["scope"].values()):
        raise ValueError("Complete binder experiment scope required")
    if expected_scope is not None and m["scope"] != expected_scope:
        raise ValueError("Binder bundle belongs to a different experiment scope")
    p = m["provenance"]
    if p.get("category") not in {"experimental_reference", "prediction", "derived_geometry", "illustration"}:
        raise ValueError("Unknown binder provenance")
    if not p.get("tool") or not p.get("tool_version") or not isinstance(p.get("source_ids"), list):
        raise ValueError("Incomplete producer provenance")
    for evidence in m["source_evidence"]:
        if any(not isinstance(evidence.get(k), str) or not evidence[k].strip() for k in ("doi", "quote", "context")):
            raise ValueError("Evidence requires exact DOI, quote and context")
    if p["category"] != "illustration" and not m["source_evidence"]:
        raise ValueError("Nonillustrative candidates require source evidence")
    decoded = {}
    if len(b["files"]) != 8:
        raise ValueError("Unexpected bundle members")
    for name, ref in b["files"].items():
        value = base64.b64decode(ref["base64"], validate=True)
        if digest(value) != ref["sha256"] or len(value) != ref["byte_length"]:
            raise ValueError("Stale or corrupt bundle member hash")
        decoded[name] = value
    fmt = b["structure"]["format"]
    rebuilt = make_bundle(decoded["source." + fmt], fmt, target_chains=b["target_chains"],
                          binder_chains=b["binder_chains"], candidate_id=m["candidate_id"],
                          provenance=p, scope=m["scope"], source_evidence=m["source_evidence"],
                          assembly=m["assembly"], protocol=b["protocol"])
    # Geometry, mapping, metrics and all derived exports must agree with the immutable source.
    for key in ("structure", "metrics", "files", "manifest"):
        if canonical(b[key]) != canonical(rebuilt[key]):
            raise ValueError(f"Binder {key} disagrees with source coordinates")
    return b


def export_bundle(bundle: dict, directory):
    """Export reviewed bundle files to a new directory, never overwrite source artifacts."""
    from pathlib import Path
    validate_bundle(canonical(bundle))
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=False)
    for name, ref in bundle["files"].items():
        (path / name).write_bytes(base64.b64decode(ref["base64"]))
    (path / "manifest.json").write_bytes(canonical(bundle["manifest"]))
