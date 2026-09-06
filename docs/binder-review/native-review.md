# Native binder action review

The native runtime action sequence opened the collected illustrative bundle, selected
`interface-close`, and captured the actual owning experiment through the local browser
on 2026-09-06. No API mocking was used for this probe. The saved PNG was opened with
the image-view tool at native resolution: coral target contacts and cyan binder atoms
are distinct, the specimen is not clipped, and the illustration/cutaway labels are readable.
This is the existing translated 1CRN software fixture, not a generated or validated binder.

[Capture](native-capture.png) and [camera/source snapshot](native-capture.json).
PNG SHA-256: `a140f154d4f9f78afe96da263cc36d747f7644055b1066308fe3afe8c34eb9b6`.
The requested browser viewport was 1600×1000 at DPR1; the PNG is the stage element crop.

The subsequent real native image-observation call reached the model provider but failed
with its session quota (reported reset 08:30 America/New_York). No model observation
was recorded and no new native vision success is claimed. The saved capture can be
reviewed later without recapturing. The earlier successful scene-service image transport
probe remains documented in the runtime scene review artifacts.

Provider failures now return a bounded, redacted error through native dispatch and the
CLI, preserve any usage already reported, and append no scene.review event. Regression
tests exercise a provider exception outside the RuntimeError hierarchy. This tests failure
handling and exact PNG transport; it does not substitute for the blocked live observation.
