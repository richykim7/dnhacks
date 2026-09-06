# Binder cinematic

Import the default export from `frontend/src/demo/scenes/binder/BinderDemo.tsx`.
The component takes `{ time: number; reducedMotion?: boolean }`, owns its Canvas,
and fills a parent with explicit width/height. Selection and playback belong to
the integrating shell. No shared types, entrypoints or production viewers changed.

The exported `binderDemoMetadata` declares **illustrative** provenance. Fixed seeds
1207/1211 generate a stylized helical fold and a lobed envelope locally. These are
not PDB coordinates, a docking calculation, an affinity estimate or an experiment.
No remote assets, fonts, APIs, models or runtime investigation state are used.

Timeline (seconds): 0–5 establishes the slowly rotating protein and separate binder;
5–11 smoothly approaches and seats the coral binder; 11–15 illuminates the contact
patch; 15–18 holds the final composition exactly. Every pose derives from the supplied
time; out-of-range values clamp, non-finite values use zero. Reduced motion shows
the static seated pose at 15 seconds. Reset by supplying zero. No internal clock,
randomness during rendering, orbit control or automatic looping.

## Local preview

With frontend dependencies installed, from the repository root:

```sh
npm --prefix frontend run dev -- --port 5199
```

Open `/src/demo/scenes/binder/preview.html` on that local server. The standalone
preview provides play/pause, reset and scrub controls outside the component.
`?time=15&capture=1` selects the hero still and hides controls;
`?time=0&capture=1` selects the opening; `?reducedMotion=1` freezes the final pose.
The preview heading and provenance footer are optional sibling presentation chrome,
not part of the embeddable scene. No backend is needed.

## Reproduce inspected artifacts

The capture script launches and closes its own Vite server and Chromium. It does
not reuse a development server or start a backend. Use the repository browser queue:

```sh
flock /tmp/dnhacks-browser-$(id -u).lock node frontend/src/demo/scenes/binder/capture.mjs
# Append --still-only to omit the short video.
```

`assets/binder-1920x1080.png` and `binder-establish-1920x1080.png` are actual inspected
1920×1080 screenshots at 15 and 0 seconds. `binder-preview.webm` records the sequence
at 1280×720, including brief startup/hold padding. `capture.json` records browser
errors and a byte-identical 15→0→15 screenshot replay check. Chromium SwiftShader
was used; the clip is a visual inspection artifact, not a GPU throughput benchmark.

Validation: project TypeScript check; actual opening/contact still inspection;
deterministic screenshot replay; short clip capture. No broad suites or backend tests.
