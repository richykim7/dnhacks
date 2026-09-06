# Saved spindle movies and measured rendering

The runtime `export_scene_movie` action captures 2–120 increasing saved frame
indices with a fixed camera and encodes VP9/WebM. Comparison uses nearest saved
physical time and the same camera. The manifest records every frame's physical
and presentation time, poles, native motor fields, camera, image hash, browser,
served assets and encoder/script hashes. Geometry is not interpolated. Exports
are bounded to four movies per experiment, five minutes and an 8 MiB video.

Movies appear inline in their owning experiment, with explicit playback controls
and no autoplay. History hides them until their artifact event. The scoped blob
API serves video and its manifest only after that event; another run cannot read
them by guessing a digest. A numerical follow-up still creates a new experiment.

Operator setup requires `SPINDLE_FFMPEG_BIN` pointing to an absolute encoder path.
The pilot used imageio-ffmpeg 0.6.0's FFmpeg 7.0.2 static binary, with its exact
hash recorded. For example, an operator can obtain a local binary path with:

```sh
uv run --with imageio-ffmpeg==0.6.0 python -c \
  'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())'
```

Supply that path to the runtime environment, then use the registered `spindle`
action with `operation: export_scene_movie` and args such as
`{recipe_sha256, frames: [0,1,2], fps: 10, viewport: [1600,1000]}`.

## Actual native export

The [movie](spindle-review/movie.webm) shows the corrected cortical-motor
engineering experiment, not a browser fixture. It contains all eleven requested
samples from 0 through 1 s at 10 fps (1.1 s presentation duration, including the
last held sample). FFmpeg decoded all eleven frames successfully. Repeated
fixed-state exports produced identical video bytes. The developer inspected the
[decoded contact sheet](spindle-review/movie-contact.png): the comparison camera
and pole identities stay stable, with no visible abrupt camera jumps or strobing
across the saved samples. This is a short engineering clip, not biological proof.

## Performance scope

Measured on an AMD EPYC-Genoa Linux host using Chromium ANGLE SwiftShader software
at a 1600×1000 outer viewport. The scene contains two matched native conditions;
this is not a physical mobile-device benchmark or a maximum-density capacity test.
Three warmup updates precede measurement. The report includes host load and exact
browser, assets and encoder versions.

| Measurement | Recorded value |
|---|---:|
| Synchronous WebGL draw + finish p95 | 0.90 ms |
| Full saved-frame apply/readiness p95, including automation transport | 158.36 ms |
| Eleven-frame screenshot capture pipeline | 8.33 s |
| Video encoding | 1.90 s |

The fast draw measurement does **not** establish 60 fps interactive playback.
The full update path is slower, and the reference desktop/mobile performance
acceptance remains incomplete. Screenshot capture and encoding are offline costs,
separate from rendering. Exact samples and provenance are in
[the measured manifest](spindle-movie.json). No unavailable runtime vision review
was invented; this decoded-image inspection belongs to the developer review.
