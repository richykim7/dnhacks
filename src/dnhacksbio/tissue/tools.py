"""The single tool contract for CLI and research runtime callers."""

import json
import asyncio
from .schema import canonical
from .scenes import SceneService


async def operate(journal, scope, operation, args):
    if not isinstance(args,dict):raise ValueError('Tissue operation arguments must be an object')
    service = SceneService(journal, scope)
    if not any(e["kind"] == "experiment.queued" for e in service.history()):
        raise FileNotFoundError("Create the owning exploratory experiment first")
    if operation == "build_model":
        from .engine import build_model

        model = build_model(
            args.get("parameters"),
            source_context=args.get("source_context"),
            geometry=args.get("geometry"),
            question=args.get("question"),
        )
        key = journal.store_bytes(canonical(model))
        service.append(
            "tissue.model", {"model_id": model["model_id"], "storage_key": key}
        )
        return model
    if operation == "simulate":
        from .jobs import launch

        event = next(
            (
                e
                for e in service.history()
                if e["kind"] == "tissue.model"
                and e["payload"]["model_id"] == args["model_id"]
            ),
            None,
        )
        if event is None:
            raise FileNotFoundError("Model not owned by this experiment")
        model = json.loads(journal.read_blob(event["payload"]["storage_key"]))
        return launch(
            service,
            model,
            args.get(
                "conditions",
                [
                    "baseline",
                    "uptake_suppressed",
                    "secretion_off",
                    "double_off",
                    "alanine_rescue",
                ],
            ),
            args.get("seeds", [0]),
            args.get("duration_minutes", 1440),
        )
    if operation in {"job_status", "cancel"}:
        from .jobs import job_status

        return job_status(service, args["job_id"], operation == "cancel")
    if operation == "cells":
        from .artifacts import frame_parts
        data=service.artifact(args['artifact_id']);ci=args.get('condition',0);fi=args.get('frame',0)
        offset=args.get('offset',0);limit=args.get('limit',50)
        if any(type(n) is not int or n<0 for n in [ci,fi,offset]) or type(limit) is not int or not 1<=limit<=100:raise ValueError('Invalid bounded cell page')
        frame=frame_parts(journal,args['artifact_id'],ci,fi)[0] if data.get('chunked') else data['conditions'][ci]['frames'][fi]
        state=args.get('state')
        if state not in {None,'alive','dead'}:raise ValueError('Unknown cell state')
        cells=[c for c in frame['cells'] if state is None or c['state']==state]
        return {'time_minutes':frame['time'],'condition':ci,'total':len(cells),'offset':offset,'cells':cells[offset:offset+limit]}
    if operation == "neighborhood":
        from .engine import neighborhood
        from .artifacts import read_frame

        data = service.artifact(args["artifact_id"])
        ci = args.get("condition", 0)
        fi = args.get("frame", 0)
        if type(ci) is not int or type(fi) is not int or ci < 0 or fi < 0:
            raise ValueError("Invalid exact frame index")
        frame = (
            read_frame(journal, args["artifact_id"], ci, fi)
            if data.get("chunked")
            else data["conditions"][ci]["frames"][fi]
        )
        return neighborhood(frame, args["cell_id"], args.get("radius_um", 35))
    if operation == "analyze":
        from .engine import analyze
        from .artifacts import read_frame

        data = service.artifact(args["artifact_id"])
        if data.get("chunked"):
            for ci, c in enumerate(data["conditions"]):
                c["frames"] = [
                    read_frame(journal, args["artifact_id"], ci, fi)
                    for fi in range(len(c["frames"]))
                ]
        result = analyze(data["conditions"])
        service.append(
            "tissue.analysis",
            {"artifact_sha256": args["artifact_id"], "analysis": result},
        )
        return result
    if operation == "open_scene":
        return service.open_scene(
            args["artifact_id"],
            args.get("preset", "Exterior"),
            args.get("note", "Inspect the tissue model"),
        )
    if operation == "set_scene_view":
        return service.set_scene_view(args["recipe_sha256"], args["view"], args["note"])
    if operation == "capture_scene":
        from .render import renderer

        return await asyncio.to_thread(
            service.capture_scene,
            args["recipe_sha256"],
            renderer(service),
            tuple(args.get("viewport", [1600, 1000])),
        )
    if operation == "inspect_scene_capture":
        return await service.inspect_scene_capture(args["capture_id"], args["question"])
    if operation == "record_visual_review":
        return service.record_visual_review(
            args["capture_id"], args.get("unresolved_defects", []), args["disposition"]
        )
    if operation == "history":
        return {"events": service.history(args.get("through"))}
    raise ValueError("Unknown tissue operation")
