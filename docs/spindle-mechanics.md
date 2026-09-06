# Native spindle mechanics probes

The pinned 3D CPU solver was actually run at 0.002, 0.001 and 0.0005 s timesteps.
A motor attached to a fixed straight filament moved toward its minus end at the
configured unloaded speed of 1 µm/s. A separate athermal, unopposed classic
filament grew by 0.5 µm over one second with catastrophe and rescue disabled.
The preset tolerance was 10⁻⁵ µm against the analytic displacement at all eleven
saved times. Native trajectory serialization contributes finite precision.

| Probe | Timestep (s) | Maximum analytic error (µm) | Passed |
|---|---:|---:|---|
| motor | 0.002 | 1.91e-07 | True |
| motor | 0.001 | 3.81e-07 | True |
| motor | 0.0005 | 3.81e-07 | True |
| growth | 0.002 | 4.77e-08 | True |
| growth | 0.001 | 4.77e-08 | True |
| growth | 0.0005 | 4.77e-08 | True |

The runner verifies both executable hashes and the pinned source/build identity,
archives exact configurations, raw solver/report files and their hashes, and exits
nonzero on failed checks. Reproduce with an operator-pinned build:

```sh
uv run python scripts/validate_spindle_mechanics.py \
  --binary-dir /absolute/path/to/bin \
  --build-manifest /absolute/path/to/build.json \
  --output /new/validation-directory
```

These are engineering inputs based on upstream `cym/motor_race.cym` and
`cym/fiber_classic.cym`, not biological parameter estimates. The fixed motor-track
case deliberately disables the mechanics solve to isolate stepping semantics.
Passing these cases does not establish loaded force–velocity behavior, stochastic
binding rates, coupled-aster convergence, HSET specificity or PDAC calibration.
Those remain separate validation tasks. Exact results and provenance are in
[the measured receipt](spindle-mechanics.json).
