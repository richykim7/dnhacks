# Tissue cinematic

Integration: default import `frontend/src/demo/scenes/tissue/TissueDemo.tsx`.
Render `<TissueDemo time={seconds} reducedMotion={false} />` in a sized parent.
The component owns its Canvas and fills the parent; it has no controls, requests,
production tissue imports, model calls, or runtime dependencies. The named
`tissueDemoMetadata` export records illustrative provenance and seed 1409.

This is a curated illustration, **not a simulated experiment result**. The 67
rounded tumor cells, 10 elongated stromal cells, fibers and population lens are
synthetic design geometry. No field, measurement, effect or efficacy is implied.

Time is clamped to 0–18 seconds. 0–5 establishes a slow orbit; 5–11 approaches the
local neighborhood; 8–13 reveals the selected population; 11–15 gently shifts
surrounding stroma beside it; 15–18 holds. Every pose derives directly from the
provided time, including backward seeks. Reduced motion fixes the composed
15-second pose. The shell owns playback/reset. Rendering is on demand, with DPR
capped at 1.5; no postprocessing or external fonts/textures are used.

## Preview and capture

From the repository root, with frontend dependencies installed:

```sh
npm --prefix frontend run dev -- --port 5194
# Open http://127.0.0.1:5194/src/demo/scenes/tissue/preview.html?play
# Static pose: ?time=13 ; reduced motion: ?reducedMotion
```

The standalone preview provides `window.setTissueTime(seconds)` for local capture.
Its animation driver supplies elapsed time to the component. It is not imported
by the application shell.

Capture with an owned ephemeral Vite server and the shared browser queue (no
backend starts, and no existing server is reused):

```sh
python3 - <<'PY'
import sys, subprocess
sys.path.insert(0, 'scripts')
from browser_tests import browser_slot
with browser_slot():
    subprocess.run(['node', 'frontend/src/demo/scenes/tissue/capture.mjs', '--clip'], check=True)
PY
# Encode optional exact-time frames with an installed ffmpeg:
ffmpeg -y -framerate 12 -i frontend/src/demo/scenes/tissue/assets/frames/%04d.png \
  -c:v libvpx -b:v 2200k -pix_fmt yuv420p frontend/src/demo/scenes/tissue/assets/tissue.webm
```

`--clip` renders 217 exact-time frames from 0 through 18 seconds at 12 fps;
rendering speed does not change the animation. Omit it for four stills only.
Chromium and its SwiftShader software renderer must be available through the
existing Playwright installation. Captures are visual evidence, not a hardware
performance benchmark.

## Visual review

Inspected the actual 1920×1080 opening and focus captures; then eased the camera
approach to preserve margins and corrected membrane color conversion for clearer
cyan rims. Final opening, focus and hold captures retain translucent layers,
coral stroma and two small labels. Artifacts are under `assets/`.
TypeScript checking passed; browser capture reported no page errors. A backward
seek capture is compared with the first 13-second capture to check deterministic
reproduction. No broad suites or scientific validation were run.
