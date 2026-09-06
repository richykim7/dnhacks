"""Synthetic measured-protein invariants. No biological or calibration claims."""
import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from dnhacksbio.protein_design import audit, digest, validate
from dnhacksbio.protein_encoder import ProteinEncoder, fit
from dnhacksbio.protein_experiment import EvidenceUnavailable, Store, availability
from dnhacksbio.protein_tools import compare, neighbors, profile, sites


def cohort(role="DEV", prefix="d", n=6, p=4):
    return {"schema": "ProteinObservation-v1", "role": role, "cohort_id": prefix,
            "donor_namespace": "synthetic", "accession": "synthetic", "release": "v1",
            "license": "synthetic", "access": "synthetic", "assay": "label_free",
            "processing_dependencies": "independent synthetic observations", "scale": "linear_abundance",
            "source_sha256": digest(prefix), "processing_sha256": digest("identity"),
            "feature_ids": [f"P{j}" for j in range(p)],
            "observations": [{"donor_id": f"{prefix}{i}", "specimen_id": f"s{i}", "aliquot_id": f"a{i}",
                "run_id": f"r{i}", "batch": "b", "reference": "none", "histology": "other" if role in {"TRAIN", "VALIDATION"} else "PDAC",
                "tissue": "primary_tumor", "context": "A" if i % 2 else "B", "treatment": "untreated",
                "grade": "G1" if i % 2 else "G3", "qc": {"pass": True},
                "values": [float(i+j+1) for j in range(p)], "mask": [True]*p,
                "sites": [{"accession": "P0", "isoform": None, "position": 12, "residue": "S",
                           "localization_confidence": 0.9, "parent_protein_coverage": 0.5, "value": 1.0}]}
                for i in range(n)]}


PANEL = {"version": "synthetic-v1", "feature_ids": ["P0", "P1", "unmeasured"],
         "modules": {"synthetic": ["P0", "unmeasured"]}}


def test_measured_profiles_sites_and_comparison():
    c = cohort()
    p = profile(c, PANEL, "label_free")
    assert p["status"] == "exploratory"
    assert p["rows"][0]["values"] == [1, np.log2(3), None]
    assert p["rows"][0]["mask"] == [True, True, False]
    assert p["rows"][0]["modules"]["synthetic"]["measured"] == 1
    out = compare(c, "A", "B", PANEL)
    assert out["features"][-1]["difference_A_minus_B"] is None
    out = sites(c, ["P0", "missing"])
    assert out["sites"][0]["resolution"] == "unresolved"
    assert out["unmeasured_proteins"] == ["missing"]
    c["observations"][0]["sites"][0]["isoform"] = "P0-1"
    assert sites(c, ["P0"])["sites"][0]["resolution"] == "localized"
    assert sites(c, ["P0"], 0.95)["sites"][0]["resolution"] == "unresolved"


@pytest.mark.parametrize("mutation", [
    lambda c: c["observations"].append(copy.deepcopy(c["observations"][0])),
    lambda c: c["observations"][0]["values"].__setitem__(0, float("nan")),
    lambda c: c["observations"][0]["mask"].__setitem__(0, False),
    lambda c: c["observations"][0].__setitem__("grade", "favorable-subtype"),
    lambda c: c.__setitem__("source_sha256", "missing"),
    lambda c: c.__setitem__("scale", "TPM"),
])
def test_invalid_provenance_or_measurements(mutation):
    c = cohort(); mutation(c)
    with pytest.raises(ValueError):
        validate(c)


def test_private_audit_threshold_and_role():
    c = cohort("CONFIRM", n=96)
    panel = {"version": "v1", "feature_ids": ["P0"]}
    assert audit(c, panel)["current_48_pair_policy_met"]
    c["observations"][0]["grade"] = None
    assert not audit(c, panel)["current_48_pair_policy_met"]
    for op in (lambda: profile(c, panel, "label_free"), lambda: compare(c, "A", "B", panel),
               lambda: sites(c, ["P0"])):
        with pytest.raises(ValueError, match="Confirmation"):
            op()
    assert audit(c, panel)["evidence_status"] == "unavailable"


def test_training_frozen_roundtrip_and_neighbor_provenance(tmp_path):
    t, v = cohort("TRAIN", "train"), cohort("VALIDATION", "val")
    enc = fit(t, v, latent=2)
    path = tmp_path / "encoder.npz"
    enc.save(path)
    restored = ProteinEncoder.load(path)
    dev = cohort()
    np.testing.assert_allclose(enc.transform(dev), restored.transform(dev))
    before = enc.sha256
    shifted = copy.deepcopy(dev)
    shifted["observations"][0]["values"][0] = 1e6
    out = enc.transform(shifted)
    np.testing.assert_allclose(enc.transform(dev)[1:], out[1:])
    assert enc.sha256 == before
    p = profile(dev, PANEL, "label_free", enc)
    nn = neighbors(p, dev, 2, panel=PANEL, encoder=enc)
    assert all(r["donor_key"] not in {n["donor_key"] for n in r["neighbors"]} for r in nn["rows"])
    with pytest.raises(ValueError, match="Assay"):
        enc.transform(dev | {"assay": "shared_reference"})
    with pytest.raises(ValueError, match="identical"):
        neighbors(p, dev, 2, panel=PANEL)
    # Tampering with even a finite weight must be detected before transformation.
    with np.load(path, allow_pickle=False) as data:
        arrays = {k: data[k] for k in data.files}
    arrays["center"][0] += 1
    np.savez(tmp_path / "tampered.npz", **arrays)
    with pytest.raises(ValueError, match="integrity"):
        ProteinEncoder.load(tmp_path / "tampered.npz")


def test_disjoint_training_and_training_only_selection():
    t, v = cohort("TRAIN", "train"), cohort("VALIDATION", "val")
    overlapping = copy.deepcopy(v)
    overlapping["observations"][0]["donor_id"] = t["observations"][0]["donor_id"]
    with pytest.raises(ValueError, match="overlap"):
        fit(t, overlapping, latent=2)
    with pytest.raises(ValueError, match="entire cohort"):
        fit(t, v | {"cohort_id": t["cohort_id"]}, latent=2)
    for r in t["observations"]:
        r["mask"][-1] = False; r["values"][-1] = None
    enc = fit(t, v, latent=2)
    assert "P3" not in enc.metadata["feature_ids"]
    v["observations"][0]["values"][0] = 1e7
    other = fit(t, v, latent=2)
    np.testing.assert_array_equal(enc.arrays["center"], other.arrays["center"])
    np.testing.assert_array_equal(enc.arrays["components"], other.arrays["components"])


def test_denoising_roundtrip(tmp_path):
    torch = pytest.importorskip("torch")
    previous = torch.get_num_threads()
    try:
        torch.set_num_threads(1)
        enc = fit(cohort("TRAIN", "tr", n=3, p=2000), cohort("VALIDATION", "va", n=3, p=2000),
                  kind="denoising", latent=32, epochs=1)
        assert np.isfinite(enc.metadata["validation_masked_mse"])
        enc.save(tmp_path / "ae.npz")
        restored = ProteinEncoder.load(tmp_path / "ae.npz")
        np.testing.assert_allclose(enc.transform(cohort(p=2000)), restored.transform(cohort(p=2000)))
    finally:
        torch.set_num_threads(previous)


def test_native_cannot_be_enabled_by_asserted_gates(tmp_path):
    store = Store(tmp_path / "private")
    assert availability()["status"] == "unavailable"
    with pytest.raises(EvidenceUnavailable):
        store.configure({"privacy": True, "power": 1, "eligible_pairs": 100})
    for receipt in ("original", "reordered-alias", "new-release"):
        with pytest.raises(EvidenceUnavailable):
            store.enqueue({"request_id": receipt, "spec": {}, "input": {}})
    with store.connect() as con:
        assert con.execute("select count(*) from jobs").fetchone()[0] == 0


def test_audit_cli_private_file_and_discovery_cli(tmp_path):
    root = Path(__file__).resolve().parents[1]
    env = os.environ | {"PYTHONPATH": str(root / "src")}
    c, p, out = tmp_path / "cohort.json", tmp_path / "panel.json", tmp_path / "audit.json"
    c.write_text(json.dumps(cohort("CONFIRM"))); p.write_text(json.dumps(PANEL))
    result = subprocess.run([sys.executable, str(root / "scripts/audit_protein_cohort.py"),
                             "--cohort", str(c), "--panel", str(p), "--output", str(out)],
                            env=env, capture_output=True, text=True)
    assert result.returncode == 0 and result.stdout == ""
    assert out.stat().st_mode & 0o777 == 0o600
    c.write_text(json.dumps(cohort()))
    result = subprocess.run([sys.executable, str(root / "scripts/protein_tool.py"), "profile",
                             "--cohort", str(c), "--panel", str(p)], env=env, capture_output=True, text=True)
    assert result.returncode == 0
    assert json.loads(result.stdout)["status"] == "exploratory"
