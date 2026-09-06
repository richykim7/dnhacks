#!/usr/bin/env python3
"""Reproducible CPU demonstration, analytical diagnostics and declared sensitivity scenarios."""

from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
from dnhacksbio.tissue.engine import (
    build_model,
    run_condition,
    bundle,
    analyze,
    ENGINE_REVISION,
)
from dnhacksbio.tissue.schema import canonical, digest

SOURCE_NOTES = {
    9: "Human PSC-conditioned media and PDAC culture/tracing; 1 mM alanine supplementation. Growth support depends on nutrient limitation. Orthotopic/co-injection studies motivate the exchange mechanism, not a 3D diffusion rate or spatial reconstruction.",
    18: "Murine KP pancreatic/lung tumor interstitial fluid measured by isotope dilution and external calibration. Bulk TIF differs from plasma and varies by site/diet; concentrations cannot identify consumption or release rates. No measured cellular spatial alanine map.",
    21: "PDAC SLC38A2 loss reverses alanine flux and changes other amino acid/redox pathways. 1 mM extracellular alanine and approximately 200–400 µM plasma contextualize nutrient scenarios. No significant cleaved-caspase increase in the reported initiation tumors; the model damage/death rule is not calibrated to this study.",
}


def sources(corpus):
    manifest = json.loads((corpus / "MANIFEST.json").read_text())
    if manifest["last_publication_date"] != "2026-01-25":
        raise ValueError("Wrong scientific cutoff")
    result = []
    for paper in manifest["papers"]:
        if paper["ref"] not in SOURCE_NOTES:
            continue
        raw = (corpus / paper["raw_file"]).read_bytes()
        if digest(raw) != paper["raw_sha256"]:
            raise ValueError("Frozen source changed")
        result.append(
            dict(
                ref=paper["ref"],
                doi=paper["doi"],
                title=paper["title"],
                year=paper["year"],
                raw_sha256=digest(raw),
                context=SOURCE_NOTES[paper["ref"]],
            )
        )
    if len(result) != 3:
        raise ValueError("Required frozen sources missing")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    build = json.loads((args.engine.parent / "build.json").read_text())
    if build["revision"] != ENGINE_REVISION or build["executable_sha256"] != digest(
        args.engine.read_bytes()
    ):
        raise ValueError("Unverified native engine")
    context = sources(args.corpus)
    # Frozen before execution: these are assumed scenarios, not estimated confidence intervals.
    scenarios = [
        ("reference", {}, {}),
        ("secretion-low", {"secretion": 0.05}, {}),
        ("secretion-high", {"secretion": 0.2}, {}),
        ("uptake-low", {"uptake": 0.005}, {}),
        ("uptake-high", {"uptake": 0.02}, {}),
        ("boundary-low", {"boundary": 0.01}, {}),
        ("boundary-plasma-context", {"boundary": 0.3}, {}),
        ("boundary-alanine-supplement", {"boundary": 1.0}, {}),
        ("CAF-near", {}, {"caf_shell_um": 110.0, "caf_offset_um": 0.0}),
        ("CAF-far", {}, {"caf_shell_um": 140.0, "caf_offset_um": 0.0}),
        ("CAF-sparse", {}, {"caf_count": 48}),
    ]
    controls = [
        "baseline",
        "uptake_suppressed",
        "secretion_off",
        "double_off",
        "alanine_rescue",
    ]
    protocol = dict(
        scenarios=scenarios,
        seeds=[0, 1, 2],
        conditions=controls,
        duration_minutes=1440,
        endpoints=[
            "living_tumor_count",
            "living_tumor_volume_um3",
            "radial_survival",
            "field_mean_mM",
        ],
        grouping="simulation seed; cells nested within simulation",
        analysis_class="simulation_sensitivity",
        provenance="All kinetic/geometry and damage parameters assumed; 1 mM rescue transferred from in-vitro supplement context; no fitted parameters",
    )
    protocol_path = args.output / "protocol.json"
    if protocol_path.exists() and protocol_path.read_bytes() != canonical(protocol):
        raise ValueError("Protocol differs from existing execution")
    protocol_path.write_bytes(canonical(protocol))
    diagnostics = []
    for spacing, dt in [(40, 1), (20, 0.5), (10, 0.25)]:
        raw = subprocess.check_output(
            [str(args.engine.parent / "diffusion"), str(spacing), str(dt), "10"],
            text=True,
        )
        diagnostics.append(json.loads(raw.strip().splitlines()[-1]))
    rows = []
    contrasts = []
    reference = None
    for name, parameters, geometry in scenarios:
        model = build_model(parameters, source_context=context, geometry=geometry)
        for seed in protocol["seeds"]:
            conditions = []
            for condition in controls:
                folder = args.output / f"{name}-{seed}-{condition}"
                cached = folder / "validated-condition.json"
                if cached.exists():
                    result = json.loads(cached.read_text())
                    if (
                        result["simulation"]["executable_sha256"]
                        != build["executable_sha256"]
                    ):
                        raise ValueError(
                            "Cached run used a different executable; use a fresh output directory"
                        )
                else:
                    result = run_condition(
                        args.engine, folder, model, condition=condition, seed=seed
                    )
                    if not result.get("frames"):
                        raise RuntimeError(f"Incomplete {folder}: {result}")
                    cached.write_bytes(canonical(result))
                conditions.append(result)
            artifact = bundle(model, conditions)
            rows.extend(
                dict(scenario=name, **row) for row in artifact["analysis"]["endpoints"]
            )
            contrasts.extend(
                dict(scenario=name, seed=seed, **row)
                for row in artifact["analysis"]["contrasts"]
            )
            if name == "reference" and seed == 0:
                reference = conditions
                artifact["simulation"]["build"] = build
                (args.output / "tissue.json").write_bytes(canonical(artifact))
            print(
                json.dumps(dict(scenario=name, seed=seed, status="completed")),
                flush=True,
            )
    convergence = []
    for spacing, dt in [(20, 0.25), (10, 0.5), (10, 0.25)]:
        model = build_model(source_context=context)
        result = run_condition(
            args.engine,
            args.output / f"convergence-{spacing}-{dt}",
            model,
            spacing=spacing,
            dt=dt,
        )
        endpoint = analyze([result])["endpoints"][0]
        convergence.append(dict(spacing_um=spacing, dt_minutes=dt, endpoint=endpoint))
    replay = run_condition(
        args.engine,
        args.output / "deterministic-replay",
        build_model(source_context=context),
    )
    deterministic = digest(replay["frames"]) == digest(reference[0]["frames"])
    report = dict(
        protocol_sha256=digest(protocol),
        build=build,
        sources=context,
        protocol=protocol,
        analytical_diffusion=diagnostics,
        deterministic_replay_exact_float32=deterministic,
        convergence=convergence,
        endpoints=rows,
        contrasts=contrasts,
        biological_validation=False,
    )
    (args.output / "report.json").write_bytes(canonical(report))
    (args.output / "manifest.json").write_bytes(
        canonical(
            dict(
                schema_version=1,
                artifacts=[dict(kind="tissue_simulation", path="tissue.json")],
            )
        )
    )
    if (
        not deterministic
        or diagnostics[-1]["max_absolute_error_mM"] > 0.001
        or any(d["relative_mass_error"] > 1e-10 for d in diagnostics)
    ):
        raise RuntimeError("Numerical acceptance failed; inspect report")
    print(json.dumps(dict(status="completed", report=str(args.output / "report.json"))))


if __name__ == "__main__":
    main()
