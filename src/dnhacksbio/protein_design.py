"""Measured protein schemas and operator-only eligibility audit (no acquisition)."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def load(path):
    with Path(path).open() as stream:
        return json.load(stream)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def sha(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def validate(cohort, *, discovery=False):
    """Reject ambiguous donor selections; masked values must be null, never inferred RNA."""
    if not isinstance(cohort, dict) or cohort.get("schema") != "ProteinObservation-v1":
        raise ValueError("Expected ProteinObservation-v1")
    if cohort.get("role") not in {"TRAIN", "VALIDATION", "DEV", "CONFIRM"}:
        raise ValueError("Declare data role")
    if discovery and cohort["role"] == "CONFIRM":
        raise ValueError("Confirmation observations are unavailable to discovery")
    for key in ("cohort_id", "donor_namespace", "accession", "release", "license", "access",
                "assay", "processing_dependencies"):
        if not nonempty(cohort.get(key)):
            raise ValueError(f"Missing {key}")
    if cohort.get("scale") not in {"linear_abundance", "log2_abundance", "log2_ratio"}:
        raise ValueError("Unsupported measured protein scale")
    if not sha(cohort.get("source_sha256")) or not sha(cohort.get("processing_sha256")):
        raise ValueError("Source and processing SHA256 required")
    features = cohort.get("feature_ids")
    if not isinstance(features, list) or not features or not all(map(nonempty, features)) or len(set(features)) != len(features):
        raise ValueError("Unique ordered feature identifiers required")
    rows = cohort.get("observations")
    if not isinstance(rows, list) or not rows:
        raise ValueError("No observations")
    donors = set()
    for row in rows:
        for key in ("donor_id", "specimen_id", "aliquot_id", "run_id", "batch", "reference",
                    "histology", "tissue", "context"):
            if not nonempty(row.get(key)):
                raise ValueError(f"Missing observation {key}")
        if row["donor_id"] in donors:
            raise ValueError("Select one tumor per canonical donor before import; aliases/replicates are not units")
        donors.add(row["donor_id"])
        if row.get("treatment") not in {"untreated", "treated", "unknown"}:
            raise ValueError("Declare treatment eligibility")
        if row.get("grade") not in {None, "G1", "G2", "G3", "unknown"}:
            raise ValueError("Use audited grading crosswalk G1/G2/G3, or unknown")
        if not isinstance(row.get("qc"), dict) or type(row["qc"].get("pass")) is not bool:
            raise ValueError("Assay QC required")
        values, mask = row.get("values"), row.get("mask")
        if not isinstance(values, list) or not isinstance(mask, list) or len(values) != len(features) or len(mask) != len(features):
            raise ValueError("Feature/value/mask shape mismatch")
        for value, measured in zip(values, mask):
            if type(measured) is not bool:
                raise ValueError("Mask must contain booleans")
            if not measured:
                if value is not None:
                    raise ValueError("Unmeasured values must be null")
            elif type(value) not in {int, float} or not math.isfinite(value):
                raise ValueError("Measured values must be finite")
            elif cohort["scale"] == "linear_abundance" and value < 0:
                raise ValueError("Negative linear abundance")
        if not isinstance(row.get("sites", []), list):
            raise ValueError("Sites must be a list")
        for site in row.get("sites", []):
            if not isinstance(site, dict) or not {"accession", "isoform", "position", "residue", "localization_confidence", "parent_protein_coverage", "value"} <= set(site):
                raise ValueError("Complete measured site fields required")
            if not nonempty(site.get("accession")) or not nonempty(site.get("residue")) or site["residue"] not in {"S", "T", "Y"}:
                raise ValueError("Invalid phosphosite identity")
            if site.get("isoform") is not None and not nonempty(site["isoform"]):
                raise ValueError("Invalid isoform")
            if site.get("position") is not None and (type(site["position"]) is not int or site["position"] < 1):
                raise ValueError("Invalid residue position")
            for field in ("localization_confidence", "parent_protein_coverage"):
                v = site.get(field)
                if type(v) not in {int, float} or not math.isfinite(v) or not 0 <= v <= 1:
                    raise ValueError(f"Invalid site {field}")
            if site.get("value") is not None and (type(site["value"]) not in {int, float} or not math.isfinite(site["value"])):
                raise ValueError("Invalid site abundance")
    return cohort


def donor_keys(cohort):
    return [digest([cohort["donor_namespace"], r["donor_id"]]) for r in cohort["observations"]]


def panel_ids(panel):
    ids = panel.get("feature_ids")
    if not nonempty(panel.get("version")) or not isinstance(ids, list) or not ids or not all(map(nonempty, ids)) or len(set(ids)) != len(ids):
        raise ValueError("Versioned panel of unique feature identifiers required")
    return ids


def audit(cohort, panel, *, min_coverage=0.8):
    """PRIVATE report: never call this on CONFIRM from an agent-facing service."""
    validate(cohort)
    ids = panel_ids(panel)
    if not 0 < min_coverage <= 1:
        raise ValueError("Invalid coverage threshold")
    positions = {f: i for i, f in enumerate(cohort["feature_ids"])}
    rows = cohort["observations"]
    tumor = [r for r in rows if r["tissue"] == "primary_tumor"]
    eligible = [r for r in tumor if r["histology"] == "PDAC" and r["treatment"] == "untreated"]
    graded = [r for r in eligible if r["grade"] in {"G1", "G2", "G3"}]
    measured = [r for r in graded if r["qc"]["pass"] and
                sum(f in positions and r["mask"][positions[f]] for f in ids) / len(ids) >= min_coverage]
    groups = {"G1/G2": sum(r["grade"] in {"G1", "G2"} for r in measured),
              "G3": sum(r["grade"] == "G3" for r in measured)}
    return {"visibility": "operator_private", "schema": "ProteinEligibility-v1",
            "cohort_sha256": digest(cohort), "panel_sha256": digest(panel),
            "counts": {"records": len(rows), "unique_tumor_donors": len(tumor),
                       "untreated_pdac": len(eligible), "compatible_grade": len(graded),
                       "eligible_measured_panel": len(measured), "groups": groups},
            "min_coverage": min_coverage, "pair_budget_available": min(groups.values()),
            "current_48_pair_policy_met": min(groups.values()) >= 48,
            "evidence_status": "unavailable",
            "unresolved": ["independent sampling and preprocessing review", "untouched cohort history",
                           "external histology interpretation", "shared canonical donor ledger",
                           "deployment-enforced privacy", "resource and null/power release gates"]}
