"""Experiment-scoped immutable scene history and pixel-bearing visual review."""

from __future__ import annotations
import asyncio
import fcntl
import io
import json
from contextlib import contextmanager
from .schema import canonical, digest, finite

DEFAULT_VIEW = dict(
    theme="dark",
    preset="Exterior",
    frame=0,
    section=160,
    opacity=0,
    fieldMaximum=1.01,
    diagnosticSlice=False,
    comparison=False,
    condition=0,
    selection=None,
    azimuth=0.48,
    elevation=0.32,
    zoom=1,
)


def validate_view(view, artifact):
    if set(view) - set(DEFAULT_VIEW):
        raise ValueError("Unknown scene control")
    result = DEFAULT_VIEW | view
    if result["theme"] not in {"dark", "light"}:
        raise ValueError("Unsupported theme")
    if result["preset"] not in {"Exterior", "Core", "Neighborhood"}:
        raise ValueError("Unknown preset")
    for key, lo, hi in [
        ("section", -160, 160),
        ("opacity", 0, 1),
        ("azimuth", -100, 100),
        ("elevation", -1.1, 1.1),
        ("zoom", 0.6, 2.8),
    ]:
        finite(result[key], lo, hi)
    finite(result["fieldMaximum"], 0.001, 1000)
    if type(result["diagnosticSlice"]) is not bool:
        raise ValueError("Invalid diagnostic-slice option")
    ci = result["condition"]
    fi = result["frame"]
    if type(ci) is not int or not 0 <= ci < len(artifact["conditions"]):
        raise ValueError("Unknown condition")
    if type(fi) is not int or not 0 <= fi < len(artifact["conditions"][ci]["frames"]):
        raise ValueError("Unknown exact frame")
    if (
        type(result["comparison"]) is not bool
        or result["comparison"]
        and len(artifact["conditions"]) < 2
    ):
        raise ValueError("Unavailable comparison")
    if result["selection"] is not None and (
        type(result["selection"]) is not int or result["selection"] < 0
    ):
        raise ValueError("Invalid cell selection")
    return result


class SceneService:
    def __init__(self, journal, scope):
        if set(scope) != {"project_id", "run_id", "experiment_id"} or any(
            not isinstance(v, str) or not v for v in scope.values()
        ):
            raise ValueError("Full experiment scope required")
        self.journal = journal
        self.scope = scope
        self.manifest = journal.manifest(scope["run_id"], scope["project_id"])

    @contextmanager
    def lock(self):
        with (self.journal.directory / "tissue-scenes.lock").open("a") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            yield

    def history(self, through=None):
        run = self.journal.snapshot(self.manifest["investigation_id"], through)[
            "runs"
        ].get(self.scope["run_id"], {})
        return [
            e
            for e in run.get("history", [])
            if e.get("experiment_id") == self.scope["experiment_id"]
        ]

    def append(self, kind, payload):
        run = self.journal.snapshot(self.manifest["investigation_id"])["runs"][
            self.scope["run_id"]
        ]
        return self.journal.append(
            self.scope["run_id"],
            run["attempt_id"],
            kind,
            payload,
            experiment_id=self.scope["experiment_id"],
            producer="collector" if kind == "artifact" else "scene-service",
        )

    def artifact(self, key, through=None):
        if not any(
            e["kind"] == "artifact"
            and e["producer"] == "collector"
            and e["payload"].get("kind") == "tissue_simulation"
            and e["payload"].get("status") == "available"
            and e["payload"].get("sha256") == key
            for e in self.history(through)
        ):
            raise FileNotFoundError(
                "Tissue artifact not owned by this experiment at this cursor"
            )
        return json.loads(self.journal.read_blob(key))

    def recipe(self, key, through=None):
        if not any(
            e["kind"] == "tissue.scene" and e["payload"]["recipe_sha256"] == key
            for e in self.history(through)
        ):
            raise FileNotFoundError("Scene revision unavailable")
        recipe = json.loads(self.journal.read_blob(key))
        if recipe["scope"] != self.scope:
            raise ValueError("Scene scope mismatch")
        return recipe

    def latest(self, scene_id):
        return next(
            (
                e["payload"]["recipe_sha256"]
                for e in reversed(self.history())
                if e["kind"] == "tissue.scene" and e["payload"]["scene_id"] == scene_id
            ),
            None,
        )

    def save(self, recipe, note):
        if not isinstance(note, str) or not 1 <= len(note) <= 1000:
            raise ValueError("Bounded scene action note required")
        if sum(e["kind"] == "tissue.scene" for e in self.history()) >= 128:
            raise ValueError("Scene action budget exhausted")
        key = self.journal.store_bytes(canonical(recipe))
        payload = dict(
            scene_id=recipe["scene_id"],
            recipe_sha256=key,
            artifact_sha256=recipe["artifact_sha256"],
            view=recipe["view"],
            actor="agent",
            note=note,
        )
        event = self.append("tissue.scene", payload)
        return {**payload, "sequence": event["sequence"]}

    def open_scene(self, key, preset="Exterior", note="Inspect the tissue model"):
        data = self.artifact(key)
        view = validate_view({"preset": preset}, data)
        if preset != "Exterior":
            view.update(section=0, opacity=0.16)
        recipe = dict(
            schema_version=1,
            adapter="tissue@1",
            scope=self.scope,
            artifact_sha256=key,
            scene_id=digest(
                {"scope": self.scope, "artifact": key, "adapter": "tissue@1"}
            ),
            parent=None,
            view=view,
        )
        with self.lock():
            old = self.latest(recipe["scene_id"])
            if old:
                return {"recipe_sha256": old, **self.recipe(old)}
            return self.save(recipe, note)

    def set_scene_view(self, key, patch, note):
        with self.lock():
            old = self.recipe(key)
            if self.latest(old["scene_id"]) != key:
                raise ValueError("Stale scene revision")
            data = self.artifact(old["artifact_sha256"])
            view = validate_view(old["view"] | patch, data)
            if view["selection"] is not None:
                from .artifacts import read_frame

                frame = (
                    read_frame(
                        self.journal,
                        old["artifact_sha256"],
                        view["condition"],
                        view["frame"],
                    )
                    if data.get("chunked")
                    else data["conditions"][view["condition"]]["frames"][view["frame"]]
                )
                if view["selection"] not in {c["id"] for c in frame["cells"]}:
                    raise ValueError("Selected cell not present in exact frame")
                if patch.get("preset") == "Neighborhood" and "section" not in patch:
                    selected = next(
                        c for c in frame["cells"] if c["id"] == view["selection"]
                    )
                    view["section"] = max(
                        -160, min(160, selected["position"][2] + selected["radius"])
                    )
            return self.save({**old, "parent": key, "view": view}, note)

    def capture_scene(self, key, renderer, viewport=(1600, 1000)):
        if (
            len(viewport) != 2
            or any(type(x) is not int for x in viewport)
            or not 320 <= viewport[0] <= 1920
            or not 320 <= viewport[1] <= 1080
        ):
            raise ValueError("Capture viewport limit")
        recipe = self.recipe(key)
        self.artifact(recipe["artifact_sha256"])
        if viewport[0] <= 650 and recipe["view"]["comparison"]:
            raise ValueError(
                "Mobile capture requires one explicit condition; compare separate shared-scale frames"
            )
        if self.latest(recipe["scene_id"]) != key:
            raise ValueError("Stale capture revision")
        if sum(e["kind"] == "tissue.capture" for e in self.history()) >= 48:
            raise ValueError("Capture budget exhausted")
        result = renderer(recipe, viewport)
        png = result["png"]
        # Decode pixels, not only the PNG signature. Black/flat frames cannot become reviewed.
        from PIL import Image, ImageStat

        if not isinstance(png, bytes) or len(png) > 8 * 1024 * 1024:
            raise ValueError("PNG size limit")
        with Image.open(io.BytesIO(png)) as im:
            if im.format != "PNG" or im.size != tuple(viewport):
                raise ValueError("Capture dimensions mismatch")
            im.load()
            stat = ImageStat.Stat(im.convert("RGB"))
            if max(stat.stddev) < 3 or max(stat.mean) < 2:
                raise ValueError("Black or empty capture")
        canvases = result.get("canvas_pngs", [])
        if len(canvases) != (2 if recipe["view"]["comparison"] else 1):
            raise ValueError("Missing rendered scene pixels")
        for canvas in canvases:
            if not isinstance(canvas, bytes) or len(canvas) > 8 * 1024 * 1024:
                raise ValueError("Canvas size limit")
            with Image.open(io.BytesIO(canvas)) as im:
                if (
                    im.format != "PNG"
                    or not 1 <= im.width <= 3840
                    or not 1 <= im.height <= 2160
                ):
                    raise ValueError("Invalid canvas dimensions")
                im.load()
                stat = ImageStat.Stat(im.convert("RGB"))
                if max(stat.stddev) < 3 or max(stat.mean) < 2:
                    raise ValueError("Black or empty scene canvas")
        if result.get("recipe_sha256") != key or result.get("view") != recipe["view"]:
            raise ValueError("Rendered recipe mismatch")
        with self.lock():
            if self.latest(recipe["scene_id"]) != key:
                raise ValueError("Scene changed during capture")
            image_key = self.journal.store_bytes(png)
            receipt = dict(
                scope=self.scope,
                recipe_sha256=key,
                artifact_sha256=recipe["artifact_sha256"],
                image_sha256=image_key,
                viewport=list(viewport),
                renderer=result.get("renderer"),
                visual_review="pending",
            )
            capture = self.journal.store_bytes(canonical(receipt))
            self.append("tissue.capture", dict(capture_id=capture, **receipt))
            return dict(capture_id=capture, **receipt)

    def read_capture(self, key, through=None):
        if not any(
            e["kind"] == "tissue.capture" and e["payload"]["capture_id"] == key
            for e in self.history(through)
        ):
            raise FileNotFoundError("Capture not available in this experiment")
        return json.loads(self.journal.read_blob(key))

    async def inspect_scene_capture(self, key, question):
        from dnhacksbio.llm import acomplete

        capture = self.read_capture(key)
        png = self.journal.read_blob(capture["image_sha256"])
        if not isinstance(question, str) or not 1 <= len(question) <= 2000:
            raise ValueError("Bounded visual question required")
        try:
            observation = await asyncio.wait_for(
                acomplete(
                    "In at most 180 words, inspect these actual tissue image pixels. Describe visible cell states, field contrast, occlusion and whether scales exaggerate differences. Compare observations to visible labels rather than guessing unshown settings. This is a conditional simulation, not biological verification. "
                    + question,
                    images=[png],
                    tools_disabled=True,
                    max_turns=1,
                    max_attempts=1,
                    max_output_tokens=768,
                    effort="low",
                ),
                timeout=90,
            )
            if not isinstance(observation, str) or not observation.strip():
                raise ValueError("Empty vision observation")
            status = "observed"
        except Exception as exc:
            observation = f"Vision unavailable: {type(exc).__name__}"
            status = "unavailable"
        review = dict(
            capture_id=key,
            image_sha256=capture["image_sha256"],
            recipe_sha256=capture["recipe_sha256"],
            status=status,
            observation=observation,
        )
        review_key = self.journal.store_bytes(canonical(review))
        self.append("tissue.observation", {**review, "review_sha256": review_key})
        return review

    def record_visual_review(self, key, defects, disposition):
        capture = self.read_capture(key)
        if (
            disposition not in {"complete", "incomplete"}
            or not isinstance(defects, list)
            or len(defects) > 20
            or any(not isinstance(d, str) or len(d) > 1000 for d in defects)
        ):
            raise ValueError("Invalid visual critique")
        seen = any(
            e["kind"] == "tissue.observation"
            and e["payload"]["capture_id"] == key
            and e["payload"]["status"] == "observed"
            for e in self.history()
        )
        if disposition == "complete" and (not seen or defects):
            raise ValueError(
                "Complete review requires actual pixel observation and no unresolved defects"
            )
        review = dict(
            capture_id=key,
            recipe_sha256=capture["recipe_sha256"],
            disposition=disposition,
            unresolved_defects=defects,
            analysis_class="simulation_sensitivity",
            scientific_verification=False,
        )
        self.append("tissue.review", review)
        return review
