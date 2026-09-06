# Persistent node scene review

The selected collected structure now stays on the left while the owning researcher's activity and
findings remain on the right. The source selector mounts one viewer and removes later sources when
history is rewound. Fixtures below are translated 1CRN illustrations, not designed binders.

| Viewed image | Observation | Revision |
| --- | --- | --- |
| [Initial desktop](node-r01-desktop.png) | Large repeated headings push the lower molecule off the first screen. | Compact the workbench heading and timeline; fit stage height to the node container. |
| [Initial mobile](node-r01-mobile.png) | The first screen contains controls but no visible specimen. | Reduce mobile chrome and keep a bounded stage above the coordinate inspector. |
| [Revised desktop](node-r02-desktop.png) | Complete pearl/cyan surface silhouette, coral contact patch and legend fit beside the activity feed. | Retain the compact layout. |
| [Revised mobile](node-r02-mobile.png) | Specimen is visible without horizontal scrolling, but the surface description overlaps its upper edge. | Put provenance and candidate name in one compact row; place the description directly below it. |

The [final mobile capture](node-r03-mobile.png) was opened at native resolution: provenance and
candidate name share a row, the description clears the silhouette, both bodies and the legend are
visible on the first screen. The [final desktop capture](node-r03-desktop.png) also includes actual
recorded action notes and string observations in the adjacent feed.

Desktop revision uses the existing source-derived surface fixture; the initial layout probe used
its atomic representation. This comparison evaluates composition, not a change to scientific
coordinates or evidence. Surface limitations and the earlier material comparison remain in
[surface review](surface-review.md). Detailed inspectors remain available by scrolling.

The real native runtime also selected the non-default surface bundle in the owning experiment and
captured it through the production driver. The [PNG](node-native-capture.png) was opened with the
image-view tool: two distinct pearl/cyan bodies, coral interface, readable provenance/units and no
clipped silhouette. [Exact source/camera snapshot](node-native-capture.json).
PNG SHA-256: `18a1ba89c2305526be889ef79939a06a249312ba4b54e6bea2ff7d50008c3164`.
This capture used a real local journal/API/browser, not mocked endpoints. No new model observation
was requested while the provider quota was unavailable.

Browser checks verify the same canvas survives activity-tab changes, only one selected source is
mounted, later sources disappear on rewind, camera positions change at intermediate instants,
manual takeover cancels the remaining transition, and reduced motion remains fixed. Transition
motion is presentation only; source coordinates and measurements are unchanged. The demand-render
frame intervals are not a performance benchmark or a claim of meeting the plan's p95 target.

The corrected motion check samples three distinct rendered camera positions rather than assuming
a frame occurs within70ms. It then starts a fresh transition, verifies motion is active, and confirms
pointer-down cancels it. [First intermediate frame](node-camera-motion-0.png),
[last sampled frame](node-camera-motion-2.png), and [camera positions](node-camera-motion.json).
The first and last saved images were opened: the contact-only cutaway rotates continuously around
its target without a coordinate change. Canvas-only motion probes intentionally omit DOM legends;
they are not substituted for the labeled capture artifact. The earlier wall-clock sample failure
was a test scheduling assumption, not a successful performance measurement.
