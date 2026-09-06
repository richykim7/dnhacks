# SPINDLE cinematic

Default import: `frontend/src/demo/scenes/spindle/SpindleDemo.tsx`.
Pass `{ time: number, reducedMotion?: boolean }`; seconds are clamped to 0–18.
The component owns its Canvas, fills a sized parent, and includes no controls or
page labels. `spindleMetadata` explicitly marks the scene as curated illustration.
All paths are fixed local analytic geometry with seed offset 1511. No requests,
scientific trajectory, measured outputs, or backend integration are involved.

0–5s establishes the cell with a slow turn; 5–11s organizes the spindle and coral
chromosomes; 11–15s reveals attachment highlights; 15–18s holds. Camera and every
animated transform derive solely from the supplied time. Backward seeking resets
exactly. Reduced motion holds the 15-second composition at every input time.
Geometry is cached; rendering is demand-driven with DPR capped at 1.5.

## Local preview

From the repository root (existing frontend dependencies required):

```sh
npm --prefix frontend run dev -- --port 5195
```

Open `http://127.0.0.1:5195/src/demo/scenes/spindle/preview.html?time=14`.
Use `?play` for one 18-second sequence, `?time=0` for the opening, or
`?reducedMotion` for the static composition. Reload explicitly restarts playback.
Preview typography and provenance labels belong to this standalone page only.
The scene itself is ready for the shared demo shell without these labels.

## Capture reproduction

Use the repository's isolated, queued runner; no development server is reused:

```sh
npm --prefix frontend run e2e -- --config src/demo/scenes/spindle/capture.config.ts
```

For a worktree without its own Python environment, prefix the command with
`E2E_PYTHON=/absolute/path/to/existing/.venv/bin/python`.
This creates the checked-in 1920×1080 `still-{0,8,14,18}.png` captures and
`spindle.webm` preview recording. The capture configuration explicitly uses
Chromium SwiftShader; recording cadence is therefore not hardware performance
validation. PNGs show exact external timestamps; the video is real browser
playback. No model-generated imagery or numerical simulation is used.

Validation: focused scene/preview TypeScript checking and the queued browser
capture cases, with actual rendered still inspection. Broad suites are omitted.
