import copy
import json
from pathlib import Path
import pytest
from dnhacksbio.tissue.schema import validate, canonical, digest
from dnhacksbio.tissue.engine import build_model, run_condition
from dnhacksbio.tissue.artifacts import read_frame
from dnhacksbio.explorer.artifacts import collect
from dnhacksbio.explorer.runtime import Journal


@pytest.fixture
def tissue():
    return dict(
        kind="tissue_simulation",
        schema_version=1,
        category="illustration",
        name="Test tissue",
        domain=dict(bounds=[-10, -10, -10, 10, 10, 10], units="µm"),
        field_range=[0, 1],
        conditions=[
            dict(
                id="a",
                label="A",
                frames=[
                    dict(
                        time=0,
                        cells=[
                            dict(
                                id=4,
                                position=[1, 2, 3],
                                radius=2,
                                type="tumor",
                                state="alive",
                                parent_id=None,
                                alanine=0.2,
                            )
                        ],
                        field=dict(
                            dimensions=[2, 2, 2], values=[i / 10 for i in range(8)]
                        ),
                    )
                ],
            )
        ],
        provenance=dict(category="illustration"),
        analysis={},
    )


def test_roundtrip_chunks_and_hash_tamper(tmp_path, tissue):
    (tmp_path / "tissue.json").write_bytes(canonical(tissue))
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            dict(
                schema_version=1,
                artifacts=[
                    dict(
                        kind="tissue_simulation",
                        path="tissue.json",
                        sha256=digest(tissue),
                    )
                ],
            )
        )
    )
    j = Journal(tmp_path / "journal")
    a = collect(tmp_path, j)[0]
    assert a["status"] == "available"
    assert (
        read_frame(j, a["storage_key"], 0, 0)["cells"]
        == tissue["conditions"][0]["frames"][0]["cells"]
    )
    frame = read_frame(j, a["storage_key"], 0, 0)
    assert frame["field"]["values"] == pytest.approx([i / 10 for i in range(8)])
    manifest = json.loads(j.read_blob(a["storage_key"]))
    assert "cells" not in manifest["conditions"][0]["frames"][0]
    (tmp_path / "tissue.json").write_bytes(canonical({**tissue, "name": "tampered"}))
    assert collect(tmp_path, j)[0]["status"] == "rejected"
    with pytest.raises((ValueError, IndexError)):
        read_frame(j, a["storage_key"], -1, 0)
    chunk = j.directory / "blobs" / a["chunks"][1]["storage_key"]
    chunk.unlink()
    with pytest.raises(FileNotFoundError):
        read_frame(j, a["storage_key"], 0, 0)


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d["conditions"][0]["frames"][0]["cells"][0].update(
            position=[float("nan"), 0, 0]
        ),
        lambda d: d["conditions"][0]["frames"][0]["field"].update(
            dimensions=[100000, 2, 2]
        ),
        lambda d: d["conditions"][0]["frames"][0]["field"]["values"].append(1),
        lambda d: d["conditions"][0]["frames"][0]["cells"][0].update(radius=-1),
        lambda d: d.update(category="experimental_reference"),
        lambda d: d["domain"].update(units="mm"),
    ],
)
def test_invalid_arrays_fail_before_allocation(tissue, change):
    change(tissue)
    with pytest.raises(ValueError):
        validate(tissue)


def test_no_symlink_or_incomplete_collection(tmp_path, tissue):
    (tmp_path / "real.json").write_bytes(canonical(tissue))
    (tmp_path / "link.json").symlink_to(tmp_path / "real.json")
    (tmp_path / "manifest.json").write_bytes(
        canonical(
            dict(
                schema_version=1,
                artifacts=[dict(kind="tissue_simulation", path="link.json")],
            )
        )
    )
    assert collect(tmp_path, Journal(tmp_path / "j"))[0]["status"] == "rejected"
    tissue.update(
        category="simulation",
        model={},
        simulation={"completion_status": "canceled"},
        visual_schema={},
        analysis={"analysis_class": "simulation_sensitivity"},
    )
    with pytest.raises(ValueError, match="Incomplete"):
        validate(tissue)


def test_model_id_and_parameter_bounds():
    assert build_model()["model_id"] == build_model()["model_id"]
    assert build_model({"secretion": 0.2})["model_id"] != build_model()["model_id"]
    with pytest.raises(ValueError):
        build_model({"diffusion": float("nan")})
    with pytest.raises(ValueError):
        build_model({"survival": 1})


def test_canceled_engine_record(tmp_path):
    script = tmp_path / "slow"
    script.write_text("#!/bin/sh\nsleep 20\n")
    script.chmod(0o755)
    cancel = tmp_path / "cancel"
    cancel.touch()
    status = run_condition(
        script, tmp_path / "job", build_model(), duration=2, cancel=cancel
    )
    assert status["completion_status"] == "canceled"
    assert (
        json.loads((tmp_path / "job/status.json").read_text())["completion_status"]
        == "canceled"
    )


@pytest.fixture
def scene(tmp_path, tissue):
    from dnhacksbio.tissue.scenes import SceneService

    j = Journal(tmp_path / "journal")
    j.register("study", "Alanine exchange", project="p")
    j.append("study", "a", "attempt.started", {})
    j.append("study", "a", "experiment.queued", {"status": "queued"}, experiment_id="x")
    key = j.store_bytes(canonical(tissue))
    event = j.append(
        "study",
        "a",
        "artifact",
        {"kind": "tissue_simulation", "status": "available", "sha256": key},
        experiment_id="x",
        producer="collector",
    )
    return (
        SceneService(j, dict(project_id="p", run_id="study", experiment_id="x")),
        key,
        event["sequence"],
    )


def test_scene_ownership_cursor_stale_revision_and_picking(scene):
    from dnhacksbio.tissue.scenes import SceneService

    s, key, sequence = scene
    with pytest.raises(FileNotFoundError):
        s.artifact(key, sequence - 1)
    with pytest.raises(FileNotFoundError):
        SceneService(s.journal, {**s.scope, "project_id": "other"})
    with pytest.raises(FileNotFoundError):
        SceneService(s.journal, {**s.scope, "experiment_id": "other"}).artifact(key)
    first = s.open_scene(key)
    second = s.set_scene_view(
        first["recipe_sha256"],
        {"selection": 4, "section": 0},
        "Inspect exact source cell",
    )
    assert second["view"]["selection"] == 4
    with pytest.raises(ValueError, match="Stale"):
        s.set_scene_view(first["recipe_sha256"], {}, "Outdated")
    with pytest.raises(ValueError, match="not present"):
        s.set_scene_view(second["recipe_sha256"], {"selection": 999}, "Unknown ID")
    assert s.recipe(first["recipe_sha256"])["view"]["selection"] is None


def image_bytes(color="black", subject=False):
    import io
    from PIL import Image, ImageDraw

    im = Image.new("RGB", (320, 320), color)
    if subject:
        ImageDraw.Draw(im).ellipse((60, 60, 260, 260), fill="white")
    buffer = io.BytesIO()
    im.save(buffer, format="PNG")
    return buffer.getvalue()


def capture_renderer(recipe, viewport):
    png = image_bytes(subject=True)
    return dict(
        png=png,
        canvas_pngs=[png],
        recipe_sha256=digest(recipe),
        view=recipe["view"],
        renderer={"name": "test"},
    )


def test_black_canvas_cannot_receive_capture_or_review(scene):
    s, key, _ = scene
    recipe = s.open_scene(key)["recipe_sha256"]

    def black(r, viewport):
        return {**capture_renderer(r, viewport), "canvas_pngs": [image_bytes()]}

    with pytest.raises(ValueError, match="empty scene canvas"):
        s.capture_scene(recipe, black, (320, 320))
    assert not any(e["kind"] == "tissue.capture" for e in s.history())
    cap = s.capture_scene(recipe, capture_renderer, (320, 320))
    with pytest.raises(ValueError, match="actual pixel"):
        s.record_visual_review(cap["capture_id"], [], "complete")


def test_image_bytes_delivered_and_failed_vision_stays_incomplete(scene, monkeypatch):
    import asyncio
    import dnhacksbio.llm as llm

    s, key, _ = scene
    cap = s.capture_scene(
        s.open_scene(key)["recipe_sha256"], capture_renderer, (320, 320)
    )

    async def inspect(prompt, **kwargs):
        assert kwargs["images"] == [s.journal.read_blob(cap["image_sha256"])]
        return "A white round region is visible against the black background."

    monkeypatch.setattr(llm, "acomplete", inspect)
    assert (
        asyncio.run(
            s.inspect_scene_capture(cap["capture_id"], "Describe visible shapes")
        )["status"]
        == "observed"
    )
    with pytest.raises(ValueError):
        s.record_visual_review(cap["capture_id"], ["Legend missing"], "complete")
    assert (
        s.record_visual_review(cap["capture_id"], [], "complete")[
            "scientific_verification"
        ]
        is False
    )
    cap2 = s.capture_scene(
        s.set_scene_view(cap["recipe_sha256"], {"section": 1}, "Change section")[
            "recipe_sha256"
        ],
        capture_renderer,
        (320, 320),
    )

    async def unavailable(*args, **kwargs):
        raise TimeoutError("unavailable")

    monkeypatch.setattr(llm, "acomplete", unavailable)
    assert (
        asyncio.run(s.inspect_scene_capture(cap2["capture_id"], "Inspect"))["status"]
        == "unavailable"
    )
    with pytest.raises(ValueError):
        s.record_visual_review(cap2["capture_id"], [], "complete")


def test_simulation_cell_lifecycle_and_paired_time(tissue):
    first = tissue["conditions"][0]["frames"][0]
    second = copy.deepcopy(first)
    second["time"] = 1
    first["cells"][0]["state"] = "dead"
    tissue["conditions"][0]["frames"].append(second)
    with pytest.raises(ValueError, match="revive"):
        validate(tissue)
    second["cells"][0]["state"] = "dead"
    validate(tissue)
    extra = copy.deepcopy(tissue["conditions"][0])
    extra["id"] = "b"
    extra["frames"][1]["time"] = 2
    tissue["conditions"].append(extra)
    with pytest.raises(ValueError, match="identical exact"):
        validate(tissue)


def test_scoped_frame_http_denies_other_project_run_and_future(
    tmp_path, tissue, monkeypatch
):
    from types import SimpleNamespace
    from dnhacksbio.webui import runtime

    j = Journal(tmp_path / "journal")
    j.register("study", "Question", project="alpha")
    j.register("study~1", "Question", project="alpha")
    j.append("study", "a", "attempt.started", {})
    j.append("study", "a", "experiment.queued", {}, experiment_id="x")
    (tmp_path / "tissue.json").write_bytes(canonical(tissue))
    (tmp_path / "manifest.json").write_bytes(
        canonical(
            dict(
                schema_version=1,
                artifacts=[dict(kind="tissue_simulation", path="tissue.json")],
            )
        )
    )
    artifact = collect(tmp_path, j)[0]
    event = j.append(
        "study", "a", "artifact", artifact, experiment_id="x", producer="collector"
    )
    monkeypatch.setattr(runtime, "journal", lambda: j)
    handler = SimpleNamespace(
        _project_arg=lambda qs: qs.get("project", [None])[0],
        _send_json=lambda x: x,
        _send_bytes=lambda raw, _: raw,
    )
    path = f"study/tissue/{artifact['sha256']}"
    assert runtime.handle(handler, path, {"project": ["alpha"]})["cells"][0]["id"] == 4
    assert (
        len(runtime.handle(handler, path, {"project": ["alpha"], "part": ["field"]}))
        == 8 * 4
    )
    assert (
        "values"
        not in runtime.handle(
            handler, path, {"project": ["alpha"], "part": ["metadata"]}
        )["field"]
    )
    for route, query in [
        (path, {"project": ["beta"]}),
        (path, {"through": [str(event["sequence"] - 1)]}),
        (path.replace("study/", "study~1/"), {}),
    ]:
        with pytest.raises(FileNotFoundError):
            runtime.handle(handler, route, query)
    field = artifact["chunks"][1]["storage_key"]
    # A field digest on its own is not an API capability.
    with pytest.raises(FileNotFoundError):
        runtime.handle(handler, f"study/blob/{field}", {})


def test_model_geometry_is_immutable_and_bounded():
    model = build_model(geometry={"caf_shell_um": 140, "caf_offset_um": 0})
    assert model["model_id"] != build_model()["model_id"]
    with pytest.raises(ValueError):
        build_model(geometry={"caf_shell_um": 160})
    with pytest.raises(ValueError):
        build_model(geometry={"caf_count": 100000})


def test_neighborhood_uses_source_distance_not_display_shape(tissue):
    from dnhacksbio.tissue.engine import neighborhood

    frame = tissue["conditions"][0]["frames"][0]
    frame["cells"] += [
        dict(frame["cells"][0], id=5, position=[4, 6, 3], type="CAF"),
        dict(frame["cells"][0], id=6, position=[9, 9, 9]),
    ]
    result = neighborhood(frame, 4, 5)
    assert result["neighbor_ids"] == [5]
    assert result["caf_neighbors"] == 1


def test_cell_pages_expose_only_requested_source_ids(scene):
    import asyncio
    from dnhacksbio.tissue.tools import operate
    service,key,_=scene
    result=asyncio.run(operate(service.journal,service.scope,'cells',{'artifact_id':key,'state':'alive','limit':1}))
    assert result['total']==1 and result['cells'][0]['id']==4
    assert asyncio.run(operate(service.journal,service.scope,'cells',{'artifact_id':key,'offset':1}))['cells']==[]
    with pytest.raises(ValueError):asyncio.run(operate(service.journal,service.scope,'cells',{'artifact_id':key,'limit':10000}))
