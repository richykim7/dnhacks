# Illustrative cinematic demo

This is a curated visual story, not a simulated experiment result. It uses fixed local
illustrative geometry, no backend, network data, model calls, investigation mutation,
or invented scientific measurements. The normal research workspace is unchanged.

## Shared scene contract

Each scene default-exports a React component accepting
`{ time: number; reducedMotion?: boolean }`. `time` is external elapsed seconds in
`[0, 18]`. Each component owns its Canvas, fills its parent and contains no page controls.
All positions and camera motion derive from this time and fixed seeded local inputs;
no accumulated deltas or wall-clock randomness. Explicit reset may restart the sequence.
Reduced motion shows a stable composition; the shell labels it as a static view.

Sequence: 0–5 seconds establish with slow rotation; 5–11 approach/change;
11–15 interaction highlight; 15–18 hold. The shell owns play/pause/reset/scrub/fullscreen.

Visual palette: deep ink `#061019`, luminous cyan `#67e8f9` principal geometry,
restrained coral `#fb8c82` interacting geometry, soft white labels. Use subtle rim glow,
translucent layered surfaces and ample negative space. Avoid opaque HUD clutter,
excessive bloom and particles. Keep provenance explicitly illustrative in metadata.

Owners and import paths:

- s12: `frontend/src/demo/scenes/binder/BinderDemo.tsx`
- s14: `frontend/src/demo/scenes/tissue/TissueDemo.tsx`
- s15: `frontend/src/demo/scenes/spindle/SpindleDemo.tsx`
- s11: shell, controls, types, `frontend/src/main.tsx`, this document; excludes scene directories.

Scene owners include local reproduction instructions and an actually inspected
1920×1080 still, preferably a short video, inside their named directory. They may
include a standalone preview. Scenes are discovered at build time, so missing scenes
never produce broken imports or pretend to be available.

## Local preview

From an isolated checkout with frontend dependencies installed:

```sh
npm --prefix frontend run dev -- --port 5191 --strictPort
```

Open <http://127.0.0.1:5191/?demo=cinematic>. For a built preview, run
`npm --prefix frontend run build` followed by
`npm --prefix frontend run preview -- --port 5192 --strictPort` and open
<http://127.0.0.1:5192/?demo=cinematic>. No Python/backend process is needed.
Click a scene node to reveal it; use the transport controls to replay or inspect time.
The scene selector only enables components present in this checkout. No deployment
or running research service is involved.

## Shell validation and captures

The focused capture/interaction check uses the repository's queued, isolated browser
runner (its temporary backend is unused by the demo):

```sh
E2E_PYTHON=/path/to/prepared/.venv/bin/python npm --prefix frontend run e2e -- --config src/demo/capture.config.ts
```

It writes the map and available scene stills to `frontend/src/demo/captures/`, checks
node reveal, seeking, pause, reset, return focus, reduced-motion default, mobile overflow
and absence of API requests. Captures use Chromium SwiftShader; they are visual review
artifacts, not a claim about hardware frame rate. Use a local `npm ci` installation:
Vite can block font assets when node_modules is symlinked outside the checkout.

The inspected `captures/binder-node-reveal.webm` records a 1920×1080 node click and
the complete 18-second sequence. Reproduce only that recording with the capture
command above plus `--grep "record binder node reveal"`. The clip uses SwiftShader.

## Visual review

Reviewed the integrated binder, tissue and spindle 1080p stills for the shared ink,
cyan/coral palette, translucent geometry, uncluttered stage and readable transport.
The binder clip was inspected at approach, interaction and hold. Playback-rate checks
cover all three scenes; the recorded sequence reaches 18.0 seconds and stops.
The tissue owner's follow-up fixes the observed 390×844 framing and label collision;
its integrated mobile capture is in `scenes/tissue/assets/tissue-shell-mobile.png`.
No frame-rate benchmark or scientific output is implied.
