"""Bounded structural inspection. Coordinates are Å; no affinity or statistical verdict."""
from __future__ import annotations

import hashlib
import json
import math

import gemmi
import numpy as np

MAX_ATOMS = 6000
RADII = {"C": 1.70, "N": 1.55, "O": 1.52, "S": 1.80, "P": 1.80, "F": 1.47,
         "Cl": 1.75, "Br": 1.85, "I": 1.98, "H": 1.20, "D": 1.20}


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value) -> str:
    return hashlib.sha256(value if isinstance(value, bytes) else canonical(value)).hexdigest()


def parse_structure(raw: bytes, fmt: str, *, model: int = 0, altloc: str = "highest-occupancy") -> dict:
    if len(raw) > 20 * 1024 * 1024 or fmt not in {"pdb", "cif"}:
        raise ValueError("Unsupported format or structure exceeds byte limit")
    if altloc != "highest-occupancy":
        raise ValueError("Unsupported alternate-conformer policy")
    s = (gemmi.read_pdb_string(raw.decode()) if fmt == "pdb" else
         gemmi.make_structure_from_block(gemmi.cif.read_string(raw.decode()).sole_block()))
    if type(model) is not int or model < 0 or model >= len(s):
        raise ValueError("Requested model unavailable")
    atoms, residues, omitted = [], [], []
    seen = set()
    for chain in s[model]:
        for res in chain:
            rid = json.dumps([chain.name, res.seqid.num, res.seqid.icode.strip(), res.subchain,
                              res.label_seq], separators=(",", ":"))
            if rid in seen:
                raise ValueError("Ambiguous duplicate residue identity")
            seen.add(rid)
            # Choose one residue-level conformer; never mix A and B side chains.
            occupancies = {}
            for atom in res:
                if not all(math.isfinite(v) for v in (atom.pos.x, atom.pos.y, atom.pos.z, atom.occ)):
                    raise ValueError("Non-finite coordinates or occupancy")
                if atom.altloc != "\x00":
                    occupancies[atom.altloc] = occupancies.get(atom.altloc, 0) + atom.occ
            chosen = min(occupancies, key=lambda a: (-occupancies[a], a)) if occupancies else "\x00"
            residue = {"id": rid, "chain": chain.name, "auth_seq_id": res.seqid.num,
                       "insertion_code": res.seqid.icode.strip(), "label_asym_id": res.subchain,
                       "label_seq_id": res.label_seq, "name": res.name, "altloc": chosen.strip("\x00")}
            names = set()
            for atom in res:
                if atom.altloc not in {"\x00", chosen}:
                    omitted.append({"residue": rid, "atom": atom.name, "altloc": atom.altloc})
                    continue
                if atom.name in names:
                    raise ValueError("Duplicate atom identity within selected conformer")
                names.add(atom.name)
                atoms.append({"id": len(atoms), "residue_id": rid, "name": atom.name,
                              "element": atom.element.name, "xyz": [atom.pos.x, atom.pos.y, atom.pos.z],
                              "occupancy": atom.occ, "altloc": atom.altloc.strip("\x00")})
                if len(atoms) > MAX_ATOMS:
                    raise ValueError("Interface inspection atom cap exceeded")
            if names:
                residues.append(residue)
    if not atoms:
        raise ValueError("No atoms in selected model")
    return {"source_sha256": digest(raw), "format": fmt, "model": model, "units": "angstrom",
            "atoms": atoms, "residues": residues, "altloc_policy": altloc,
            "omitted_conformers": omitted, "missing_atoms": "not reconstructed",
            "assembly_ids": [a.name for a in s.assemblies]}


def select_chains(structure: dict, chains: list[str]) -> dict:
    available = {r["chain"] for r in structure["residues"]}
    if not chains or len(set(chains)) != len(chains) or not set(chains) <= available:
        raise ValueError("Invalid or absent chain selection")
    residues = [r for r in structure["residues"] if r["chain"] in chains]
    ids = {r["id"] for r in residues}
    return {**structure, "residues": residues,
            "atoms": [a for a in structure["atoms"] if a["residue_id"] in ids],
            "crop_transform": {"rotation": [[1, 0, 0], [0, 1, 0], [0, 0, 1]], "translation": [0, 0, 0]}}


def define_interface(target: dict, selected: list[str], excluded: list[str], competition: str) -> dict:
    ids = {r["id"] for r in target["residues"]}
    if (not selected or len(set(selected)) != len(selected) or not set(selected + excluded) <= ids
            or set(selected) & set(excluded) or not competition.strip()):
        raise ValueError("Invalid epitope, exclusion or competition context")
    return {"schema": "binder_epitope.v1", "target_sha256": digest(target),
            "selected": sorted(selected), "excluded": sorted(set(excluded)),
            "competition": competition, "accessible_area": None,
            "context": target.get("context", "context unavailable")}


def _sasa(atoms: list[dict], probe: float, samples: int) -> float:
    if not atoms:
        return 0.0
    if any(a["element"] not in RADII for a in atoms):
        raise ValueError("SASA radius unavailable for an element")
    xyz = np.array([a["xyz"] for a in atoms])
    radii = np.array([RADII[a["element"]] + probe for a in atoms])
    k = np.arange(samples)
    z = 1 - 2 * (k + 0.5) / samples
    phi = k * math.pi * (3 - math.sqrt(5))
    sphere = np.column_stack((np.cos(phi) * np.sqrt(1-z*z), np.sin(phi) * np.sqrt(1-z*z), z))
    area = 0.0
    for i, (center, radius) in enumerate(zip(xyz, radii)):
        distance = np.linalg.norm(xyz - center, axis=1)
        near = (distance < radii + radius) & (np.arange(len(atoms)) != i)
        points = center + sphere * radius
        exposed = np.ones(samples, dtype=bool)
        for other, r in zip(xyz[near], radii[near]):
            exposed &= np.sum((points - other)**2, axis=1) >= r*r
        area += float(exposed.mean()) * 4 * math.pi * radius**2
    return area


def evaluate_interface(structure: dict, target_chains: list[str], binder_chains: list[str],
                       *, candidate_id: str, probe: float = 1.4, samples: int = 256) -> dict:
    if set(target_chains) & set(binder_chains):
        raise ValueError("Target and binder chain sets overlap")
    if probe != 1.4 or samples not in {128, 256, 512, 1024}:
        raise ValueError("Unsupported SASA protocol")
    target = [a for a in select_chains(structure, target_chains)["atoms"] if a["element"] not in {"H", "D"}]
    binder = [a for a in select_chains(structure, binder_chains)["atoms"] if a["element"] not in {"H", "D"}]
    if not target or not binder:
        raise ValueError("Both partners need heavy atoms")
    contacts = []
    xyz = np.array([a["xyz"] for a in binder])
    for a in target:
        distances = np.linalg.norm(xyz - a["xyz"], axis=1)
        for index in np.flatnonzero(distances <= 5.0):
            b = binder[index]
            contacts.append({"candidate_id": candidate_id, "target_residue": a["residue_id"],
                             "binder_residue": b["residue_id"], "target_atom": a["id"],
                             "binder_atom": b["id"], "target_atom_name": a["name"],
                             "binder_atom_name": b["name"], "distance_angstrom": float(distances[index]),
                             "rule": "interchain-heavy-atom-distance.v1"})
            if len(contacts) > 100_000:
                raise ValueError("Contact quota exceeded")
    missing = []
    try:
        sasa_t, sasa_b = _sasa(target, probe, samples), _sasa(binder, probe, samples)
        sasa_c = _sasa(target + binder, probe, samples)
        buried = max(0.0, sasa_t + sasa_b - sasa_c)
    except ValueError as exc:
        sasa_t = sasa_b = sasa_c = buried = None
        missing.append(str(exc))
    return {"protocol": {"id": "binder-interface.v1", "contact_cutoff_angstrom": 4.5,
                         "sensitivity_cutoffs_angstrom": [4.0, 5.0], "clash_cutoff_angstrom": 2.0,
                         "sasa_method": "Shrake-Rupley Fibonacci approximation",
                         "probe_radius_angstrom": probe, "sphere_samples": samples,
                         "radii_angstrom": RADII, "buried_area_formula": "SASA(target)+SASA(binder)-SASA(complex)",
                         "divided_by_two": False},
            "contacts": contacts, "counts": {str(c): sum(r["distance_angstrom"] <= c for r in contacts)
                                                for c in (4.0, 4.5, 5.0)},
            "clash_count": sum(r["distance_angstrom"] < 2.0 for r in contacts),
            "sasa_target_angstrom2": sasa_t, "sasa_binder_angstrom2": sasa_b,
            "sasa_complex_angstrom2": sasa_c, "total_buried_area_angstrom2": buried,
            "missingness": missing, "confidence": None, "affinity": None,
            "context": "context unavailable", "status": "exploratory"}
