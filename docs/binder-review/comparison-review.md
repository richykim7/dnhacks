# Paired binder review — 2026-09-06

The comparison uses two illustrative 654-atom complexes. These are translated copies of
1CRN for renderer/contract validation, not generated binders or demonstrated binding.
The second fixture was rebuilt and validated through `make_bundle` and `validate_bundle`
after translating the original binder chain by (3, 0.7, −0.5) Å. Target coordinates remain
identical. Its collected SHA256 is
`93e871354af07ca53c86d6cd60637aeec65e5e3330fb2396a328f5ab8a161540`.
The original has 404 heavy-atom pairs ≤4.5 Å and49 pairs <2 Å; the shifted fixture has171
and12 respectively. Both are nondominated on the displayed contact-maximization and
clash-minimization axes; that limited geometric trade-off is not a binding-quality rank.

## Inspected revisions

All PNGs below were opened with the image-view tool, including the native capture at its
saved resolution. Browser screenshots are actual rendered workbench images.

| Image | SHA256 | Observations and revision |
| --- | --- | --- |
| [r01 desktop](comparison-r01-desktop.png) | `579734d7d059461722ab5f5c012f871e7096fe3848f36edf963e85fcff107fee` | Shared-camera composition is readable, but the two identities appear together in one caption. This first baseline uses identical geometry with a changed candidate label. Add a label over each lane and validate a genuinely changed illustrative pose. |
| [r02 desktop](comparison-r02-desktop.png) | `9847c31768b90f78364897b05d5d5f053f9ac89be97a2f4bde74e02de1a30562` | Each source has its own label; targets share orientation and scale. Cyan partners remain distinct from pearl targets and coral contacts. Neither specimen is clipped. |
| [r02 resized](comparison-r02-resized.png) | `32114e9eba7c4f165b585bfe56c04cf235e20d73aa5e3ad3840e416af9f77110` | At1000×800 the right selection is gold and the inspector shows its171 contacts/12 clashes, rather than the primary candidate's404/49. No label collision. |
| [r02 mobile](comparison-r02-mobile.png) | `ccf7fbc994b2e6a696a40ecb1c03230e824d9c2ad259c404f89cc0d562525ba0` | At390×844 both silhouettes and source labels remain visible without horizontal page scrolling. The contact inspector is below the sequence rail and requires vertical scrolling. The smaller pair is appropriate for comparison overview; individual inspection can return to a single specimen. |
| [native capture](comparison-native.png) | `fa549114ef6da1e932c8cc3a22d81fa4323a1a73dcffc2624938ec2d5c58b7df` | Actual runtime PNG preserves both lane identities, one legend, aligned targets and readable contact regions. No biological success is implied by the composition. |

## Contract evidence

[Native capture metadata](comparison-native-capture.json) records both source hashes,
equal CSS viewports, one actual camera and the physical transform. Its PNG is1275×670,
cropped from the requested1600×1000 workbench viewport. The saved-pixel native pick at
(921.373,296.273) returns the second source hash and its exact residue identity
`["A",35,"","",null]`; see [pick result](comparison-native-pick.json).
The driver scales PNG pixel coordinates to the actual CSS box before raycasting.

The targeted browser check verifies one canvas, shared camera during rotation, equal viewport
size after resizing, candidate-specific picks/metrics, mobile overflow and source removal on
historical rewind. The initial check exposed readiness resolving against the old single-view
controller while comparison loaded. Readiness now waits for the exact requested controller.
Python adversarial checks reject mismatched source/camera/scale/viewport metadata, unavailable
sources and a pick that claims the opposite lane's candidate. Collected byte hashes are preserved
even when a bundle is formatted differently from canonical JSON.

These are correctness and visual checks. Demand-render frame intervals include idle time and
do not establish the planned interactive performance budget. WebGPU comparison, orthographic
projection and an eligible live design pilot remain separate acceptance work. No new model
observation was requested for this comparison capture.
