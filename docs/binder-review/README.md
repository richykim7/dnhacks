# Interface Foundry visual review

Actual Chromium application captures were opened with the image-view tool, including full-page
composition and native stage crops. The synthetic test complex is two translated 1CRN copies,
with 654 atoms and 49 heavy-atom pairs below 2 Å. It is explicitly an illustration with clashes.
No binding success, biological target review or performance acceptance is implied.

Every image digest is recorded in `hashes.json`; camera and raycast visibility are in the saved
r04 scene records. Screenshots use deterministic cameras, no animation and local font assets.

| Revision | Viewed defect | Change and inspected outcome |
|---|---|---|
| r01 hero → r02 hero | Specimen crowds sequence rail; highlights look uniformly glossy | Reduced stage height, increased camera distance and roughness. r02 keeps the complete sequence rail visible with clearer space around the specimen. |
| r01 close → r02 close | Right and lower partner clipped substantially | Increased close-view distance. r02 restores most partner outline but solid views still occlude three of twenty contact residues. |
| r02 hero → r04 hero | Broad frontal lighting flattens depth | Shifted key light to the side, reduced ambient fill, raised cool rear light. r04 has stronger depth across the cyan partner and maintains the coral seam. |
| r02 close → r03 close | Only 17/20 contact residues visible over two solid opposing views | Added labeled contact-only cutaway with reduced sphere radii. r03 exposes 20/20 residues but leaves the seam too small. |
| r03 close → r04 close | Cutaway fitted against hidden full-complex bounds | Fit against contact geometry. r04 enlarges the seam without clipping, with 20/20 contact residues visible across the primary/opposing views. |
| r01 mobile → r04 mobile | Right silhouette clips outside scene | Iteratively fit projected bounds. r04 keeps both partners inside the 390px viewport; inspector remains reachable by vertical scrolling. |

Pearl/cyan versus bronze/violet were inspected as distinct lighting/material studies. Pearl/cyan
was selected for clearer chain/contact separation; the bronze study has darker crevices and more
competitive highlights. The bronze palette remains an explicit selectable study, with its matching
legend colors. No WebGPU comparison is claimed by this record.

A real image-bearing model call is recorded in `vision-probe.json`, including the exact supplied
r03 hero-stage PNG hash and measured token usage. The model identified the white, cyan and coral
regions and correctly described their spatial relation. This validates pixel transport, not a
scientific verdict or the later scene-tool/replay integration.

## Runtime scene integration review

The scoped scene service captured the real owning workbench from an isolated Journal containing
the explicitly illustrative translated-1CRN fixture. The exact PNG was opened at native resolution:
both chains and the coral seam fit; the front rim obscures part of the interface, so hero alone
cannot establish rear-face visibility. Image SHA-256: `bf2dd6396ab3c45bfb1ed9566a0f0744d6908ae47cc74604a5171699cbbbb23f`.
See [PNG](runtime-scene-hero.png), [capture state](runtime-scene-capture.json) and
[actual vision observation](runtime-scene-vision.json). The tools-disabled vision call received
those saved PNG bytes and requested the reverse contact-only view. Its wording about total rear
occlusion is qualitative, not a measured visibility fraction; use the captured raycast metadata and
opposing view. Coordinate diagnostics for this fixture remain 404 heavy-atom pairs ≤4.5 Å and 49
pairs below 2 Å, regardless of apparent image overlap. No affinity or design success is inferred.

An intermediate scene-replay change reset presets to hero when the action history was empty.
Opening the supposed close-up PNG exposed the error despite a passing screenshot test. The reset
now occurs only when history actually rewinds, and capture tests assert the requested preset.

After the reset fix, native close-up and mobile PNGs were opened and inspected. The close-up
shows the labeled contact-only cutaway, with no edge clipping; mobile keeps both chains inside
the stage and leaves the inspector reachable by vertical scrolling. Primary raycast visibility
is 19/20 contact residues, reverse 18/20, union 20/20.
- `scene-replay-interface-close-stage.png`: `41513157624988349f82cf51f26a386dbe6988691ddc54a9639092d4e4eab2cf`
- `scene-replay-mobile.png`: `f675d5dcf767a6538da7afc3be9f03733082de9d832112b8a0de041ffca69fe5`
- `scene-replay-interface-close.json`: `a0eaf3b90a652e590b7ff42e831d355d9c6002254e79ec4b651c151c531c5330`
- `scene-replay-reverse.json`: `86902dd5f1176198cf58e24475fa796a74572474e25a4d391b3cdc1aa03a3e1d`

The actual saved-camera pixel pick at (650,310) returned author chain A residue 39 with an empty
insertion code, using the original capture hash; see [pick receipt](runtime-scene-pick.json).
The default 30-second browser budget timed out under shared load; an explicit bounded 60-second
retry succeeded. No obsolete-camera pick was accepted.

The actual runtime loop then saved a reverse-view recipe in response to the image observation,
captured its owning workbench and opened the resulting PNG. The contact-only seam is visible
from the opposing side; its raycast reports 18 visible contact residues. Image hash: `ab36d79c7970c84d78d3b5f284bd1631665e917a48fd833e3d5840643cd0d236`.
See [reverse capture](runtime-scene-reverse.png) and [state](runtime-scene-reverse.json).
