"""Exploratory measured-protein operations; no confirmation or ToolResult verdicts."""
from __future__ import annotations

import argparse
import json
import numpy as np

from .protein_design import digest, donor_keys, load, panel_ids, validate
from .protein_encoder import ProteinEncoder, matrix


def profile(cohort, panel, assay, encoder=None):
    validate(cohort, discovery=True)
    features = panel_ids(panel)
    if assay != cohort["assay"]:
        raise ValueError("Requested assay does not match observations")
    x, mask = matrix(cohort, features)
    embedding = encoder.transform(cohort).tolist() if encoder else None
    modules = panel.get("modules", {})
    if not isinstance(modules, dict) or any(not members or not set(members) <= set(features) for members in modules.values()):
        raise ValueError("Module members must belong to the frozen panel")
    rows = []
    keys = donor_keys(cohort)
    for i, row in enumerate(cohort["observations"]):
        summaries = {}
        for name, members in modules.items():
            indices = [features.index(f) for f in members]
            observed = [j for j in indices if mask[i, j]]
            summaries[name] = {"mean_observed": float(x[i, observed].mean()) if observed else None,
                               "measured": len(observed), "total": len(indices)}
        rows.append({"donor_key": keys[i], "context": row["context"],
                     "values": [float(v) if m else None for v, m in zip(x[i], mask[i])],
                     "mask": mask[i].tolist(), "coverage": float(mask[i].mean()), "qc": row["qc"],
                     "modules": summaries, "embedding": embedding[i] if embedding else None})
    return {"schema": "ProteinProfile-v1", "status": "exploratory", "role": cohort["role"],
            "cohort_sha256": digest(cohort), "source_sha256": cohort["source_sha256"],
            "processing_sha256": cohort["processing_sha256"], "panel_sha256": digest(panel),
            "model_sha256": encoder.sha256 if encoder else None,
            "preprocessing_sha256": encoder.metadata["preprocessing_sha256"] if encoder else digest({
                "scale": cohort["scale"], "transform": "log2(1+x) if linear; otherwise identity"}),
            "assay": assay, "scale": "log2_abundance" if cohort["scale"] == "linear_abundance" else cohort["scale"],
            "feature_ids": features, "rows": rows,
            "limitations": "Missingness is measured coverage, not abundance change. No occupancy, kinase activity, glycan or causal claim."}


def neighbors(query_profile, reference_cohort, k, *, panel, encoder=None):
    if query_profile.get("schema") != "ProteinProfile-v1" or query_profile.get("status") != "exploratory" or query_profile.get("role") not in {"TRAIN", "VALIDATION", "DEV"}:
        raise ValueError("Exploratory query profile required")
    if type(k) is not int or k < 1:
        raise ValueError("k must be positive")
    reference = profile(reference_cohort, panel, query_profile["assay"], encoder)
    for key in ("panel_sha256", "model_sha256", "preprocessing_sha256", "scale"):
        if query_profile[key] != reference[key]:
            raise ValueError("Profiles require identical frozen feature/model/transform definitions")
    matches = []
    for row in query_profile["rows"]:
        ranked = []
        for ref in reference["rows"]:
            if row["donor_key"] == ref["donor_key"]:
                continue
            if encoder:
                distance = float(np.linalg.norm(np.asarray(row["embedding"]) - ref["embedding"]))
                n = sum(a and b for a, b in zip(row["mask"], ref["mask"]))
            else:
                shared = [j for j, (a, b) in enumerate(zip(row["mask"], ref["mask"])) if a and b]
                if not shared:
                    continue
                distance = float(np.sqrt(np.mean([(row["values"][j]-ref["values"][j])**2 for j in shared])))
                n = len(shared)
            ranked.append({"donor_key": ref["donor_key"], "distance": distance, "shared_measured_features": n})
        ranked.sort(key=lambda r: (r["distance"], r["donor_key"]))
        matches.append({"donor_key": row["donor_key"], "neighbors": ranked[:k]})
    return {"status": "exploratory", "query_sha256": digest(query_profile),
            "reference_sha256": digest(reference), "model_sha256": reference["model_sha256"],
            "source_sha256": reference["source_sha256"], "processing_sha256": reference["processing_sha256"],
            "preprocessing_sha256": reference["preprocessing_sha256"], "panel_sha256": reference["panel_sha256"],
            "distance": "embedding Euclidean" if encoder else "RMS over jointly measured features",
            "rows": matches}


def compare(cohort, context_A, context_B, panel):
    if context_A == context_B:
        raise ValueError("Distinct external contexts required")
    p = profile(cohort, panel, cohort["assay"])
    groups = [[r for r in p["rows"] if r["context"] == c] for c in (context_A, context_B)]
    if any(not g for g in groups):
        raise ValueError("Both contexts need observed donors")
    features = []
    for j, feature in enumerate(p["feature_ids"]):
        values = [[r["values"][j] for r in g if r["mask"][j]] for g in groups]
        means = [float(np.mean(v)) if v else None for v in values]
        features.append({"feature_id": feature, "mean_A": means[0], "mean_B": means[1],
                         "difference_A_minus_B": means[0]-means[1] if all(m is not None for m in means) else None,
                         "measured_donors": [len(v) for v in values],
                         "missing_fraction": [1-len(v)/len(g) for v, g in zip(values, groups)]})
    return {"status": "exploratory", "profile_sha256": digest(p), "source_sha256": p["source_sha256"],
            "processing_sha256": p["processing_sha256"], "panel_sha256": p["panel_sha256"],
            "model_sha256": None, "preprocessing_sha256": p["preprocessing_sha256"],
            "contexts": [context_A, context_B], "n_donors": [len(g) for g in groups],
            "features": features, "interpretation": "Descriptive association; missingness and assay batches may explain contrasts"}


def sites(cohort, proteins, localization_threshold=0.75):
    validate(cohort, discovery=True)
    if not 0 <= localization_threshold <= 1 or not proteins or not all(isinstance(p, str) and p for p in proteins):
        raise ValueError("Protein identifiers and localization threshold required")
    result = []
    for key, row in zip(donor_keys(cohort), cohort["observations"]):
        for site in row.get("sites", []):
            if site["accession"] in proteins:
                resolved = (site["localization_confidence"] >= localization_threshold
                            and site["position"] is not None and site["isoform"] is not None)
                result.append({**site, "donor_key": key, "resolution": "localized" if resolved else "unresolved"})
    return {"status": "exploratory", "source_sha256": cohort["source_sha256"],
            "processing_sha256": cohort["processing_sha256"], "cohort_sha256": digest(cohort),
            "localization_threshold": localization_threshold, "sites": result,
            "unmeasured_proteins": sorted(set(proteins)-{s["accession"] for s in result}),
            "interpretation": "Measured site abundance; no phosphorylation occupancy or kinase activity inference"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("profile", "neighbors", "compare", "sites"):
        p = sub.add_parser(name)
        p.add_argument("--cohort", required=True)
        if name != "sites":
            p.add_argument("--panel", required=True)
        if name in {"profile", "neighbors"}:
            p.add_argument("--encoder")
        if name == "neighbors":
            p.add_argument("--reference", required=True)
            p.add_argument("-k", type=int, default=5)
        if name == "compare":
            p.add_argument("--context-a", required=True)
            p.add_argument("--context-b", required=True)
        if name == "sites":
            p.add_argument("--proteins", required=True, nargs="+")
            p.add_argument("--localization-threshold", type=float, default=0.75)
    args = parser.parse_args(argv)
    cohort = load(args.cohort)
    encoder = ProteinEncoder.load(args.encoder) if getattr(args, "encoder", None) else None
    if args.command == "sites":
        result = sites(cohort, args.proteins, args.localization_threshold)
    else:
        panel = load(args.panel)
        if args.command == "compare":
            result = compare(cohort, args.context_a, args.context_b, panel)
        else:
            result = profile(cohort, panel, cohort["assay"], encoder)
            if args.command == "neighbors":
                result = neighbors(result, load(args.reference), args.k, panel=panel, encoder=encoder)
    print(json.dumps(result, allow_nan=False))


if __name__ == "__main__":
    main()
