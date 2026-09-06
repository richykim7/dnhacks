"""Reproducible CPTAC development import; never imports a confirmation cohort."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import urllib.request

import numpy as np
import pandas as pd

from .protein_design import digest, validate

BASE = "https://cptac-pancancer-data.s3.us-west-2.amazonaws.com/data_freeze_v1.2_reorganized"
ROLES = {"TRAIN": ["BRCA", "COAD"], "VALIDATION": ["LUAD"], "DEV": ["PDAC"]}
PROCESSING = ("Published gene-level log2 reference-intensity normalized tumor abundance; "
              "pooled identification/reference construction and upstream cohort fitting are unaudited. "
              "Development only; not independent sequential confirmation inputs.")


def file_hash(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def acquire(directory):
    """Fixed allowlist, bounded atomic downloads, and immutable receipt hashes."""
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    receipts = []
    for cohort in sum(ROLES.values(), []):
        for kind, suffix in (("proteomics", "proteomics_gene_abundance_log2_reference_intensity_normalized_Tumor"),
                             ("meta", "meta")):
            path = root / f"{cohort}_{kind}.txt"
            url = f"{BASE}/{cohort}/{cohort}_{suffix}.txt"
            if not path.exists():
                partial = path.with_suffix(".part")
                with urllib.request.urlopen(url, timeout=120) as source, partial.open("xb") as target:
                    size = 0
                    while chunk := source.read(1024 * 1024):
                        size += len(chunk)
                        if size > 100 * 1024 * 1024:
                            raise ValueError("Source exceeds development download budget")
                        target.write(chunk)
                partial.rename(path)
            receipts.append({"cohort": cohort, "kind": kind, "url": url,
                             "sha256": file_hash(path), "bytes": path.stat().st_size})
    return receipts


def read_matrix(path):
    with Path(path).open(newline="") as stream:
        header = next(csv.reader(stream, delimiter="\t"))
    if len(header[1:]) != len(set(header[1:])):
        raise ValueError("Duplicate donor columns; harmonize before import")
    frame = pd.read_csv(path, sep="\t", index_col=0, na_values=["NA", ""], low_memory=False)
    if frame.index.has_duplicates:
        raise ValueError("Duplicate feature rows require reviewed protein-group mapping")
    # Preserve exact release identifiers. Never arbitrarily pick the first isoform/version.
    frame.index = frame.index.astype(str)
    values = frame.apply(pd.to_numeric, errors="raise").T
    if np.isinf(values.to_numpy()).any():
        raise ValueError("Infinite protein abundance")
    return values


def build(directory, *, max_features=2000):
    root = Path(directory)
    receipts = acquire(root)
    frames = {c: read_matrix(root / f"{c}_proteomics.txt") for c in sum(ROLES.values(), [])}
    all_donors = [str(d) for f in frames.values() for d in f.index]
    if len(all_donors) != len(set(all_donors)):
        raise ValueError("Cross-cohort donor alias/overlap requires canonical mapping")
    training = pd.concat([frames[c] for c in ROLES["TRAIN"]], join="outer")
    coverage = training.notna().mean()
    # TRAIN only, coverage descending then exact identifier: no validation/PDAC selection.
    features = sorted((f for f in coverage.index if coverage[f] >= .8),
                      key=lambda f: (-coverage[f], f))[:max_features]
    if len(features) < max_features:
        raise ValueError("Insufficient training-covered features")
    cohorts, summaries = {}, {}
    for role, names in ROLES.items():
        rows = []
        for name in names:
            frame = frames[name].reindex(columns=features)
            meta = pd.read_csv(root / f"{name}_meta.txt", sep="\t", index_col=0).drop(index="data_type", errors="ignore")
            if meta.index.has_duplicates or set(frame.index) - set(meta.index):
                raise ValueError("Donor metadata mapping incomplete or duplicated")
            grade_counts = {"G1": 0, "G2": 0, "G3": 0, "unknown": 0}
            for donor, values in frame.iterrows():
                grade_text = str(meta.loc[donor].get("Histologic_Grade", "unknown"))
                grade = next((g for g in ("G1", "G2", "G3") if grade_text == g or grade_text.startswith(g + " ")), None)
                grade_counts[grade or "unknown"] += 1
                mask = values.notna().to_numpy()
                rows.append({"donor_id": str(donor), "specimen_id": "unavailable:published-case-only",
                    "aliquot_id": "unavailable", "run_id": "unavailable", "batch": name,
                    "reference": "published-reference-intensity", "histology": name,
                    "tissue": "primary_tumor", "treatment": "unknown", "grade": grade,
                    "context": grade or "unknown", "qc": {"pass": bool(mask.mean() >= .8),
                        "basis": "fixed measured-panel coverage; raw assay QC unaudited"},
                    "values": [float(v) if m else None for v, m in zip(values, mask)], "mask": mask.tolist()})
            summaries[name] = {"records": len(frame), "exact_features_in_release": len(frames[name].columns),
                "metadata_joined": len(frame), "grades": grade_counts,
                "grade_pairs_ceiling": min(grade_counts["G1"] + grade_counts["G2"], grade_counts["G3"]),
                "raw_coverage": float(frames[name].notna().mean().mean()),
                "selected_coverage": float(frame.notna().mean().mean()),
                "coverage_pass_donors": int((frame.notna().mean(axis=1) >= .8).sum()),
                "untreated_eligibility": "unverified in downloaded metadata"}
        sources = [r for r in receipts if r["cohort"] in names]
        cohort = {"schema": "ProteinObservation-v1", "role": role, "cohort_id": "+".join(names),
            "donor_namespace": "CPTAC-case-id", "accession": "LinkedOmics-CPTAC-pan-cancer",
            "release": "data_freeze_v1.2", "license": "public download; data-specific redistribution terms unaudited",
            "access": "open HTTPS", "assay": "CPTAC-reference-intensity",
            "processing_dependencies": PROCESSING, "source_sha256": digest(sources),
            "processing_sha256": digest({"processing": PROCESSING, "selection": features}),
            "scale": "log2_abundance", "feature_ids": features, "observations": rows}
        validate(cohort, discovery=True)
        cohorts[role] = cohort
    report = {"schema": "ProteinDevelopmentAudit-v2", "roles": ROLES, "files": receipts,
              "cohorts": summaries, "selected_features": len(features), "feature_sha256": digest(features),
              "donor_ids_disjoint": True, "identity_limit": "case IDs joined, specimen/aliquot/run crosswalk not supplied",
              "selection": "TRAIN coverage >= .8, descending coverage and exact feature ID, first 2000",
              "confirmation": "unavailable; no confirmation numerical inputs accessed"}
    return cohorts, report


def write_json(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, allow_nan=False, indent=2)
        stream.write("\n")
