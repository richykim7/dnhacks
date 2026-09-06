"""Pinned CPU engine build and bounded conditional runs."""

from __future__ import annotations
import csv
import json
import os
from pathlib import Path
import signal
import struct
import subprocess
import time
from .schema import canonical, digest, finite, validate

ENGINE_REVISION = "dbd3499250141b27600e91e501c54c46f68f2763"
ENGINE_VERSION = "PhysiCell 1.14.2 / bundled BioFVM"
DEFAULT_PARAMETERS = dict(
    diffusion=300.0,
    secretion=0.1,
    uptake=0.01,
    boundary=0.05,
    threshold=0.3,
    growth=0.0005,
)
DEFAULT_GEOMETRY = dict(
    tumor_radius_um=92.0, caf_shell_um=126.0, caf_count=95, caf_offset_um=15.0
)


def build_engine(source: Path, destination: Path):
    revision = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "HEAD"], text=True
    ).strip()
    if revision != ENGINE_REVISION:
        raise ValueError("Unreviewed PhysiCell revision")
    if subprocess.check_output(
        ["git", "-C", str(source), "diff", "HEAD", "--", "BioFVM", "core", "modules"]
    ):
        raise ValueError("Modified native engine source")
    destination.mkdir(parents=True, exist_ok=True)
    objects = []
    for folder in ["BioFVM", "core", "modules"]:
        for cpp in sorted((source / folder).glob("*.cpp")):
            if cpp.name in {"PhysiCell_digital_cell_line.cpp", "PhysiCell_POV.cpp"}:
                continue
            obj = destination / (cpp.stem + ".o")
            subprocess.run(
                [
                    "g++",
                    "-std=c++11",
                    "-O2",
                    "-fopenmp",
                    "-I",
                    str(source),
                    "-c",
                    str(cpp),
                    "-o",
                    str(obj),
                ],
                check=True,
                timeout=120,
                capture_output=True,
            )
            objects.append(str(obj))
    main = Path(__file__).resolve().parents[3] / "native/tissue/main.cpp"
    binary = destination / "tissue"
    subprocess.run(
        [
            "g++",
            "-std=c++11",
            "-O2",
            "-fopenmp",
            "-I",
            str(source),
            str(main),
            *objects,
            "-o",
            str(binary),
        ],
        check=True,
        timeout=120,
        capture_output=True,
    )
    diagnostics = main.with_name("diffusion.cpp")
    subprocess.run(
        [
            "g++",
            "-std=c++11",
            "-O2",
            "-fopenmp",
            "-I",
            str(source),
            str(diagnostics),
            *objects,
            "-o",
            str(destination / "diffusion"),
        ],
        check=True,
        timeout=120,
        capture_output=True,
    )
    receipt = dict(
        engine=ENGINE_VERSION,
        revision=revision,
        executable_sha256=digest(binary.read_bytes()),
        model_source_sha256=digest(main.read_bytes()),
        compiler=subprocess.check_output(["g++", "--version"], text=True).splitlines()[
            0
        ],
    )
    (destination / "build.json").write_bytes(canonical(receipt))
    return receipt


def build_model(parameters=None, *, source_context=None, geometry=None, question=None):
    params = DEFAULT_PARAMETERS | (parameters or {})
    if set(params) != set(DEFAULT_PARAMETERS):
        raise ValueError("Unknown parameter")
    for key, value in params.items():
        finite(value, 0, 1000 if key == "diffusion" else 1)
    if params["diffusion"] <= 0:
        raise ValueError("Positive diffusion required")
    geo = DEFAULT_GEOMETRY | (geometry or {})
    if set(geo) != set(DEFAULT_GEOMETRY):
        raise ValueError("Unknown geometry parameter")
    finite(geo["tumor_radius_um"], 30, 100)
    finite(geo["caf_shell_um"], geo["tumor_radius_um"] + 10, 140)
    finite(geo["caf_offset_um"], 0, 150 - geo["caf_shell_um"])
    if type(geo["caf_count"]) is not int or not 1 <= geo["caf_count"] <= 500:
        raise ValueError("CAF count outside bounds")
    if question is not None and (
        not isinstance(question, str) or not 1 <= len(question) <= 2000
    ):
        raise ValueError("Bounded model question required")
    if source_context is not None and (
        not isinstance(source_context, list) or len(canonical(source_context)) > 32768
    ):
        raise ValueError("Bounded source context required")
    model = dict(
        schema_version=1,
        question=question
        or "Under assumed spatial conditions, does stromal alanine support tumor volume and does uptake suppression abolish support?",
        parameters=params,
        parameter_provenance={
            k: dict(
                category="assumed",
                rationale="Conditional exploration; not fitted to biological measurements",
            )
            for k in params
        },
        geometry=geo,
        units=dict(
            time="min",
            length="µm",
            concentration="mM",
            diffusion="µm²/min",
            secretion="1/min",
            uptake="1/min",
            growth="1/min",
            threshold="dimensionless",
        ),
        boundary_conditions="constant extracellular alanine on outer voxel layer",
        source_context=source_context or [],
        analysis_class="simulation_sensitivity",
        endpoints=[
            "living tumor count",
            "living tumor volume",
            "radial survival",
            "field min/mean/max",
        ],
        assumptions=[
            "Alanine is the only modeled stromal support mechanism",
            "Uptake-scaled saturating support controls an assumed volume law and accumulated damage threshold",
            "Fixed cell centers; volume growth without cell division; no patient forecast",
        ],
    )
    return dict(model_id=digest(model), **model)


def run_condition(
    binary: Path,
    output: Path,
    model: dict,
    *,
    condition="baseline",
    seed=0,
    duration=1440.0,
    dt=0.5,
    spacing=20.0,
    timeout=120,
    cancel=None,
):
    if condition not in {
        "baseline",
        "secretion_off",
        "uptake_suppressed",
        "double_off",
        "alanine_rescue",
    }:
        raise ValueError("Unknown control")
    finite(duration, 1, 2880)
    finite(dt, 0.05, 5)
    finite(spacing, 10, 40)
    if (
        duration / dt > 60000
        or abs(duration / dt - round(duration / dt)) > 1e-8
        or abs(320 / spacing - round(320 / spacing)) > 1e-8
    ):
        raise ValueError("Invalid numerical grid")
    if type(seed) is not int or not 0 <= seed <= 2**31 - 1:
        raise ValueError("Invalid seed")
    finite(timeout, 1, 600)
    p = dict(model["parameters"])
    if condition in {"secretion_off", "double_off", "alanine_rescue"}:
        p["secretion"] = 0
    if condition in {"uptake_suppressed", "double_off"}:
        p["uptake"] *= 0.05
    if condition == "alanine_rescue":
        p["boundary"] = 1.0
    output.mkdir(parents=True, exist_ok=False)
    status = dict(
        condition=condition,
        seed=seed,
        completion_status="running",
        started_at=time.time(),
    )

    def record():
        (output / "status.json").write_bytes(canonical(status))

    record()
    cmd = [
        str(binary.resolve()),
        str(output.resolve()),
        str(seed),
        str(duration),
        str(dt),
        str(spacing),
        *[str(p[k]) for k in DEFAULT_PARAMETERS],
        *[str(model["geometry"][k]) for k in DEFAULT_GEOMETRY],
    ]
    with (output / "engine.log").open("wb") as log:
        process = subprocess.Popen(
            cmd,
            cwd=output,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env={**os.environ, "OMP_NUM_THREADS": "1"},
        )
        start = time.monotonic()
        while process.poll() is None:
            if (cancel and Path(cancel).exists()) or time.monotonic() - start > timeout:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                status["completion_status"] = (
                    "canceled" if cancel and Path(cancel).exists() else "timeout"
                )
                record()
                return status
            time.sleep(0.1)
    if process.returncode:
        status.update(completion_status="failed", returncode=process.returncode)
        record()
        return status
    n = round(320 / spacing)
    frames = []
    with (output / "frames.csv").open() as f:
        for row in csv.DictReader(f):
            idx = int(row["frame"])
            cells = []
            with (output / f"cells-{idx}.csv").open() as cfile:
                for c in csv.DictReader(cfile):
                    cells.append(
                        dict(
                            id=int(c["id"]),
                            position=[float(c[k]) for k in ["x", "y", "z"]],
                            radius=float(c["radius"]),
                            type="CAF" if int(c["type"]) else "tumor",
                            state="dead" if int(c["dead"]) else "alive",
                            parent_id=None,
                            alanine=float(c["alanine"]),
                            volume=float(c["volume"]),
                        )
                    )
            raw = (output / f"field-{idx}.f32").read_bytes()
            if len(raw) != n**3 * 4:
                raise ValueError("Engine field shape mismatch")
            frames.append(
                dict(
                    time=float(row["time"]),
                    cells=cells,
                    field=dict(
                        dimensions=[n, n, n],
                        values=list(struct.unpack("<" + "f" * n**3, raw)),
                    ),
                )
            )
    status.update(
        completion_status="completed",
        wall_seconds=time.monotonic() - start,
        dt=dt,
        spacing=spacing,
        executable_sha256=digest(binary.read_bytes()),
    )
    record()
    return dict(
        id=condition,
        label={
            "baseline": "CAF secretion · uptake intact",
            "secretion_off": "CAF secretion off",
            "uptake_suppressed": "Tumor uptake suppressed",
            "double_off": "Secretion and uptake suppressed",
            "alanine_rescue": "Extracellular alanine rescue",
        }[condition],
        frames=frames,
        simulation=status,
    )


def neighborhood(frame, cell_id, radius=35.0):
    finite(radius, 0.01, 1000)
    selected = next((c for c in frame["cells"] if c["id"] == cell_id), None)
    if selected is None:
        raise ValueError("Selected cell absent from exact frame")
    neighbors = [
        c
        for c in frame["cells"]
        if c["id"] != cell_id
        and sum((a - b) ** 2 for a, b in zip(c["position"], selected["position"]))
        <= radius**2
    ]
    return dict(
        cell_id=cell_id,
        radius_um=radius,
        neighbor_ids=[c["id"] for c in neighbors],
        neighbor_count=len(neighbors),
        living_neighbors=sum(c["state"] == "alive" for c in neighbors),
        caf_neighbors=sum(c["type"] == "CAF" for c in neighbors),
        mean_local_alanine_mM=(
            sum(c["alanine"] for c in neighbors) / len(neighbors) if neighbors else None
        ),
    )


def analyze(conditions):
    rows = []
    for c in conditions:
        f = c["frames"][-1]
        tumor = [x for x in f["cells"] if x["type"] == "tumor"]
        living = [x for x in tumor if x["state"] == "alive"]
        field = f["field"]["values"]
        rows.append(
            dict(
                condition=c["id"],
                seed=c.get("simulation", {}).get("seed"),
                living_tumor_count=len(living),
                living_tumor_volume_um3=sum(x["volume"] for x in living),
                field_mean_mM=sum(field) / len(field),
                field_min_mM=min(field),
                field_max_mM=max(field),
                radial_survival=[
                    dict(
                        inner_um=r,
                        outer_um=r + 25,
                        alive=sum(
                            x["state"] == "alive"
                            for x in tumor
                            if r <= sum(v * v for v in x["position"]) ** 0.5 < r + 25
                        ),
                        total=sum(
                            r <= sum(v * v for v in x["position"]) ** 0.5 < r + 25
                            for x in tumor
                        ),
                    )
                    for r in range(0, 100, 25)
                ],
            )
        )
    by_id = {c["id"]: c for c in conditions}
    contrasts = []
    for treated, control in [
        ("baseline", "secretion_off"),
        ("uptake_suppressed", "baseline"),
        ("alanine_rescue", "secretion_off"),
    ]:
        if treated not in by_id or control not in by_id:
            continue
        a = {
            c["id"]: c
            for c in by_id[treated]["frames"][-1]["cells"]
            if c["type"] == "tumor"
        }
        b = {
            c["id"]: c
            for c in by_id[control]["frames"][-1]["cells"]
            if c["type"] == "tumor"
        }
        if set(a) != set(b):
            raise ValueError("Paired contrast requires matching source cell IDs")
        rescued = [
            c
            for cid, c in a.items()
            if c["state"] == "alive" and b[cid]["state"] == "dead"
        ]
        caf = [c for c in by_id[treated]["frames"][0]["cells"] if c["type"] == "CAF"]
        distances = (
            [
                min(
                    sum((x - y) ** 2 for x, y in zip(c["position"], f["position"]))
                    ** 0.5
                    for f in caf
                )
                for c in rescued
            ]
            if caf
            else []
        )
        contrasts.append(
            dict(
                treated=treated,
                control=control,
                rescued_cells=len(rescued),
                maximum_rescue_distance_um=max(distances) if distances else None,
                distance_definition="source cell center to nearest initial CAF center; surviving treated and dead paired control",
                living_volume_difference_um3=sum(
                    c["volume"] for c in a.values() if c["state"] == "alive"
                )
                - sum(c["volume"] for c in b.values() if c["state"] == "alive"),
            )
        )
    return dict(
        analysis_class="simulation_sensitivity",
        grouping="paired condition within computational seed; cells nested within simulation",
        endpoints=rows,
        contrasts=contrasts,
        verification_eligible=False,
    )


def bundle(model, conditions):
    if any(
        not c.get("frames")
        or c.get("simulation", {}).get("completion_status") != "completed"
        for c in conditions
    ):
        raise ValueError("Incomplete conditions")
    data = dict(
        kind="tissue_simulation",
        schema_version=1,
        category="simulation",
        name="Conditional stromal alanine exchange",
        domain=dict(
            bounds=[-160, -160, -160, 160, 160, 160],
            units="µm",
            axis_order="xyz",
            handedness="right",
            field_layout="x-fastest",
        ),
        field_range=[0, 1.01],
        conditions=conditions,
        model=model,
        simulation=dict(
            completion_status="completed",
            engine=ENGINE_VERSION,
            engine_revision=ENGINE_REVISION,
        ),
        visual_schema=dict(
            adapter="tissue-v1",
            illustration_layers=["CAF elongation", "membrane lighting"],
            exact_frame=True,
        ),
        provenance=dict(
            paper_refs=model["source_context"],
            parameter_provenance=model["parameter_provenance"],
            assumptions=model["assumptions"],
        ),
        analysis=analyze(conditions),
    )
    return validate(data)
