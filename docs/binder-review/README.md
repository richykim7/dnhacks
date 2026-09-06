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
