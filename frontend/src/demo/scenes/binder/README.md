# Binder cinematic v2

Import the default export from `frontend/src/demo/scenes/binder/BinderDemo.tsx`.
It takes `{ time: number; reducedMotion?: boolean }`, owns its Canvas and fills a
parent with explicit width/height. Selection and playback belong to the shell.
The component fits a narrow left-side viewport; the standalone preview shows it
beside plain explanatory text. No shared types, entrypoints or production viewers change.

## Geometry and choreography

`binderDemoMetadata` declares **illustrative** provenance. Fixed local analytic
curves (seed 1207 for fold offsets) form nine helical ribbons, layered inner sheets,
and two contact lips around an open cleft. A smaller three-strand coral binder has
a distinct folded shape. Thick ribbons expose shaded front/side/back faces;
directional light, dark inner surfaces, occlusion and camera parallax establish depth.
There are no global translucent envelopes. These are not PDB coordinates, a docking
calculation, an affinity estimate or an experiment. No remote assets, APIs, models,
fonts or investigation state are used.

The deterministic timeline is:

- 0–5 seconds: clearly separated partners and slow target rotation.
- 5–11: the binder follows a cubic 3D curve, swings toward the viewer, rotates to
  align, and seats through the open mouth of the cleft. Camera framing closes in.
- 11–15: two restrained contact highlights appear **after** seating; the joined
  complex and camera gently orbit, retaining the binder's exact relative pose.
- 15–18: the final geometry and camera hold exactly.

All poses derive from supplied time; out-of-range values clamp and non-finite values
use zero. Reduced motion shows the static 15-second pose. Reset by supplying zero.
No internal animation clock, user orbit control, automatic looping or runtime randomness.

## Local preview

With frontend dependencies installed, from the repository root:

```sh
npm --prefix frontend run dev -- --port 5199
```

Open `/src/demo/scenes/binder/preview.html` on that server. Preview play/pause, reset
and scrub controls live outside the component. `?time=15&capture=1` selects the hero
still and hides controls; `?time=0&capture=1` selects the opening;
`?reducedMotion=1` freezes the final pose. No backend is needed.

## Reproduce inspected artifacts

The capture script starts and closes its own Vite server and Chromium. It does not
reuse a development server or start a backend. Use the repository browser queue:

```sh
flock /tmp/dnhacks-browser-$(id -u).lock node frontend/src/demo/scenes/binder/capture.mjs
# Append --still-only to omit the video.
```

Current inspected artifacts under `assets/`:

- `binder-v2.png`: 1920×1080 hero at 15 seconds.
- `binder-v2-opening.png`, `binder-v2-approach.png`, `binder-v2-seated.png`,
  `binder-v2-held.png`: inspected 0, 8, 11 and 18-second frames.
- `binder-v2.webm`: actual browser video at 1280×720, with startup/hold padding.
- `binder-v2-capture.json`: browser errors and a byte-identical replay check.

The superseded v1 captures were removed. Chromium SwiftShader was used; video frames
are visual review artifacts, not a hardware throughput benchmark. Validation includes
the project TypeScript check, inspected opening/approach/seated/held screenshots and
frames decoded from the actual video, plus deterministic screenshot replay. No broad
suites or backend tests.
