# Tissue runtime operations

The `tissue` action calls the same scoped service as `scripts/tissue_tool.py`. Require the complete
tissue-interface skill before dispatch. Never use tissue output as an audited statistical test.

Build the pinned source checkout with:

```
uv run python scripts/tissue_tool.py --build-source /path/to/PhysiCell --build-output /path/to/tissue-build
```

The checkout must be revision dbd3499250141b27600e91e501c54c46f68f2763 with unmodified engine source.
Set `TISSUE_ENGINE=/path/to/tissue-build/tissue` in the trusted runtime environment. The sibling
build.json pins the executable and compiler. `TISSUE_RENDER_URL` is a local serving origin (default
http://127.0.0.1:8765); serve the built frontend or the development app. Install Chromium via
`cd frontend && npx playwright install chromium`. No external renderer URL or caller-supplied executable
is accepted through the research action.

```
uv run python scripts/tissue_tool.py --journal /path/to/journal --project PROJECT --run RUN \
  --experiment EXPERIMENT --operation build_model --args '{"parameters":{"boundary":0.05}}'
```

Use the returned immutable model_id for simulate, returned job_id for job_status/cancel,
collected artifact_id for analyze/open_scene, recipe_sha256 for set_scene_view/capture_scene,
and capture_id for inspect_scene_capture/record_visual_review. All operations enforce the same
project/run/experiment ownership. History optionally takes an inclusive `through` event sequence.
Jobs retain logs/specification/status outside short tool observations and cap wall time, CPU,
memory and output files. Canceled partial conditions are not collected.
