#!/usr/bin/env python3
"""Measure the production renderer on a declared synthetic capacity fixture."""

import argparse
import json
from pathlib import Path
import threading
from dnhacksbio.explorer.runtime import Journal
from dnhacksbio.explorer.artifacts import collect
from dnhacksbio.tissue.schema import canonical
from dnhacksbio.tissue.scenes import SceneService
from dnhacksbio.tissue.render import renderer


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--port", type=int, default=8925)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    from dnhacksbio.webui import data, projects, server

    data.PROCESSED = a.output / "data/processed"
    projects.PROJECTS = a.output / "data/projects"
    projects.CORPORA = a.output / "data/corpora"
    if not projects.exists("tissue-capacity"):
        projects.create(
            "Tissue capacity",
            description="Synthetic rendering performance fixture, not a scientific result",
        )
    journal = Journal(data.PROCESSED)
    scope = dict(
        project_id="tissue-capacity", run_id="tissue-capacity", experiment_id="capacity"
    )
    journal.register(
        scope["run_id"], "Renderer capacity measurement", project=scope["project_id"]
    )
    journal.append(
        scope["run_id"],
        "a",
        "attempt.started",
        {"branch_objective": "Inspect rendering capacity fixture"},
    )
    journal.append(
        scope["run_id"],
        "a",
        "experiment.queued",
        {"status": "completed", "title": "Synthetic rendering capacity"},
        experiment_id=scope["experiment_id"],
    )
    cells = [
        dict(
            id=i,
            position=[
                -142.5 + (i % 20) * 15,
                -142.5 + ((i // 20) % 20) * 15,
                -144 + (i // 400) * 12,
            ],
            radius=4.0,
            type="CAF" if i % 7 == 0 else "tumor",
            state="dead" if i % 5 == 0 else "alive",
            parent_id=None,
            alanine=0.3,
        )
        for i in range(10000)
    ]
    field = dict(
        dimensions=[128, 128, 128],
        values=[0.1 + 0.4 * ((i % 128) + 0.5) / 128 for i in range(128**3)],
    )
    artifact = dict(
        kind="tissue_simulation",
        schema_version=1,
        category="illustration",
        name="Synthetic renderer capacity fixture",
        domain=dict(bounds=[-160, -160, -160, 160, 160, 160], units="µm"),
        field_range=[0, 1.01],
        conditions=[
            dict(
                id="capacity",
                label="10000 source cells · 128³ field",
                frames=[dict(time=0, cells=cells, field=field)],
            )
        ],
        provenance=dict(
            category="illustration",
            purpose="Rendering capacity only; no scientific outcomes",
        ),
        analysis=dict(analysis_class="illustration"),
    )
    (a.output / "tissue.json").write_bytes(canonical(artifact))
    (a.output / "manifest.json").write_bytes(
        canonical(
            dict(
                schema_version=1,
                artifacts=[dict(kind="tissue_simulation", path="tissue.json")],
            )
        )
    )
    result = collect(a.output, journal)[0]
    if result["status"] != "available":
        raise RuntimeError(result)
    journal.append(
        scope["run_id"],
        "a",
        "artifact",
        result,
        experiment_id=scope["experiment_id"],
        producer="collector",
    )
    service = SceneService(journal, scope)
    scene = service.open_scene(result["sha256"])
    scene = service.set_scene_view(
        scene["recipe_sha256"],
        {"opacity": 0.2},
        "Measure fixed native-grid rendering capacity",
    )
    httpd = server.ThreadingHTTPServer(("127.0.0.1", a.port), server.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    reports = []
    try:
        for name, viewport in [("desktop", (1600, 1000)), ("mobile", (390, 844))]:
            capture = service.capture_scene(
                scene["recipe_sha256"],
                renderer(service, f"http://127.0.0.1:{a.port}"),
                viewport,
            )
            (a.output / f"{name}.png").write_bytes(
                journal.read_blob(capture["image_sha256"])
            )
            reports.append(
                dict(
                    profile=name,
                    source_cells=10000,
                    source_field=[128, 128, 128],
                    frame_payload_bytes=sum(c["byte_length"] for c in result["chunks"]),
                    capture=capture,
                )
            )
            print(json.dumps(reports[-1]), flush=True)
        (a.output / "performance.json").write_bytes(canonical(reports))
    finally:
        httpd.shutdown()
        httpd.server_close()


if __name__ == "__main__":
    main()
