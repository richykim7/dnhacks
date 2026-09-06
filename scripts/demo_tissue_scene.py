#!/usr/bin/env python3
"""Exercise native jobs, collection, production scene capture and optional real image review."""

import argparse
import asyncio
import json
from pathlib import Path
import time
import os
import threading
from dnhacksbio.explorer.runtime import Journal
from dnhacksbio.tissue.schema import canonical
from dnhacksbio.tissue.tools import operate


async def run(args):
    args.output.mkdir(parents=True, exist_ok=True)
    from dnhacksbio.webui import data, projects, server

    data.PROCESSED = args.output / "data/processed"
    projects.PROJECTS = args.output / "data/projects"
    projects.CORPORA = args.output / "data/corpora"
    journal = Journal(data.PROCESSED)
    if not projects.exists("tissue-development"):
        projects.create(
            "Tissue development",
            description="Isolated conditional native model demonstration",
        )
    httpd = server.ThreadingHTTPServer(("127.0.0.1", args.port), server.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    os.environ["TISSUE_RENDER_URL"] = f"http://127.0.0.1:{args.port}"
    scope = dict(
        project_id="tissue-development",
        run_id="tissue-demonstration",
        experiment_id="alanine-exchange",
    )
    journal.register(
        scope["run_id"],
        "Conditional stromal alanine exchange",
        project=scope["project_id"],
    )
    if not journal.events(scope["run_id"]):
        journal.append(
            scope["run_id"],
            "native-demo",
            "attempt.started",
            {"branch_objective": "Inspect native alanine exchange"},
        )
        journal.append(
            scope["run_id"],
            "native-demo",
            "experiment.queued",
            {
                "title": "Native paired alanine exchange",
                "status": "running",
                "exploratory": True,
            },
            experiment_id=scope["experiment_id"],
        )

    async def tool(operation, **params):
        return await operate(journal, scope, operation, params)

    from validate_tissue import sources

    available = [
        e["payload"]["sha256"]
        for e in journal.events(scope["run_id"])
        if e["kind"] == "artifact"
        and e["payload"].get("kind") == "tissue_simulation"
        and e["payload"].get("status") == "available"
    ]
    if args.reuse and available:
        key = available[-1]
        job = {"job_id": "reused immutable artifact"}
    else:
        model = await tool(
            "build_model",
            parameters={"boundary": args.boundary},
            source_context=sources(args.corpus),
        )
        job = await tool("simulate", model_id=model["model_id"])
        start = time.monotonic()
        while True:
            state = await tool("job_status", job_id=job["job_id"])
            if state["status"] != "running":
                break
            if time.monotonic() - start > 600:
                raise TimeoutError("Native demonstration job timed out")
            await asyncio.sleep(0.5)
        if state["status"] != "completed":
            raise RuntimeError(state)
        key = state["artifacts"][0]
    journal.append(
        scope["run_id"],
        "native-demo",
        "experiment.finished",
        {"status": "completed", "exploratory": True},
        experiment_id=scope["experiment_id"],
    )
    scene = await tool("open_scene", artifact_id=key)
    from dnhacksbio.tissue.scenes import DEFAULT_VIEW

    scene = await tool(
        "set_scene_view",
        recipe_sha256=scene["recipe_sha256"],
        view=DEFAULT_VIEW,
        note="Review the exact exterior from the beginning",
    )
    results = []
    views = [
        ("Exterior", {}, [1600, 1000]),
        (
            "Core",
            {
                "preset": "Core",
                "section": 0,
                "opacity": 0.3,
                "frame": 4,
                "fieldMaximum": 0.1,
                "diagnosticSlice": True,
            },
            [1600, 1000],
        ),
        ("Comparison", {"comparison": True}, [1600, 1000]),
    ]
    if args.all_views:
        views.extend(
            [
                ("Presentation-Exterior", DEFAULT_VIEW, [1920, 1080]),
                (
                    "Presentation-Core",
                    {
                        "preset": "Core",
                        "section": 0,
                        "opacity": 0.3,
                        "frame": 4,
                        "fieldMaximum": 0.1,
                        "diagnosticSlice": True,
                    },
                    [1920, 1080],
                ),
                ("Presentation-Comparison", {"comparison": True}, [1920, 1080]),
                ("Light", {"theme": "light"}, [1600, 1000]),
                ("Mobile", {"theme": "dark", "comparison": False}, [390, 844]),
                (
                    "Neighborhood",
                    {"preset": "Neighborhood", "zoom": 1.6, "selection": 0},
                    [1600, 1000],
                ),
            ]
        )
    for name, view, viewport in views:
        if view:
            scene = await tool(
                "set_scene_view",
                recipe_sha256=scene["recipe_sha256"],
                view=view,
                note=f"Inspect {name.lower()} using exact native frame",
            )
        cap = await tool(
            "capture_scene", recipe_sha256=scene["recipe_sha256"], viewport=viewport
        )
        (args.output / f"{name}.png").write_bytes(
            journal.read_blob(cap["image_sha256"])
        )
        if args.vision and name in {"Exterior", "Core", "Comparison"}:
            observation = await tool(
                "inspect_scene_capture",
                capture_id=cap["capture_id"],
                question="Describe the visible tissue, nutrient field, numerical legends and occlusion. List concrete defects. Can any spatial effect be seen, and which biological claims cannot be inferred?",
            )
            cap["observation"] = observation
        results.append(cap)
        (args.output / "capture-receipts.json").write_bytes(canonical(results))
        print(
            json.dumps(
                {
                    "view": name,
                    "capture_id": cap["capture_id"],
                    "observation": cap.get("observation"),
                }
            ),
            flush=True,
        )
    print(
        json.dumps(
            {
                "scope": scope,
                "artifact_sha256": key,
                "journal": str(args.output),
                "job": job["job_id"],
            }
        )
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--corpus", type=Path, required=True)
    p.add_argument("--vision", action="store_true")
    p.add_argument("--port", type=int, default=8924)
    p.add_argument("--reuse", action="store_true")
    p.add_argument("--boundary", type=float, default=0.05)
    p.add_argument("--all-views", action="store_true")
    asyncio.run(run(p.parse_args()))


if __name__ == "__main__":
    main()
