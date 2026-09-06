# Source-derived surface review

The fixture is two translated copies of 1CRN, explicitly an illustration with 654 atoms,
404 heavy-atom pairs within 4.5 Å and 49 pairs below 2 Å. It is not a successful design.
All reviewed surfaces use the same source coordinates and mesh topology. Shading changes
never enter contact or buried-area calculations. Image hashes are in [surface-images.json](surface-images.json).

| Viewed image | Observation | Revision and outcome |
| --- | --- | --- |
| [r01](surface-r01-faceted.png) | Averaged triangle normals expose distracting faceting across large lobes. | Analytic source-sphere normals remove broad polygon facets. |
| [r02](surface-r02-creases.png) | The silhouette is clearer, but sharp witness changes produce jagged highlights at sphere intersections. | Spatially blended sphere normals (0.6 Å Gaussian width) soften those lighting seams without moving vertices. |
| [r05 pearl](surface-r05-pearl.png) | Target pearl and binder cyan remain distinct; the coral contact patch reads between them. Small shading seams remain near narrow intersections. | Selected baseline; analytical close/reverse views continue to expose source atoms rather than relying on this occluded hero surface. |
| [r05 copper](surface-r05-copper.png) | Bronze/violet is visibly different, but bright specular hotspots compete with the gold contact region. | Retained optional treatment; pearl/cyan remains the default for clearer contact inspection. |
| [r05 mobile](surface-r05-mobile.png) | Both structures fit at 390×844 with readable legend and controls; the inspector continues below the fold. | No horizontal overflow; reduced-motion capture preserves a static specimen. |

The [full page](surface-r05-page.png) retains a separate metric inspector and sequence rail.
The [Cα trace](surface-r05-trace.png) is an explicitly interpolated source backbone with omitted
sidechains, not a helix/sheet assignment. Source gaps and non-protein residues break its fragments.
The surface pick resolves the nearest vertex association of the intersected triangle to an exact
source atom/residue. Browser tests verify that switching representations preserves the 404-contact
assessment and missing affinity, and that close/reverse recipes resolve to the atomic cutaway.

[Surface analysis](surface-analysis.json) records 19,114 vertices and 38,221 triangles per role,
3.58 seconds for both meshes on this CPU process, and 123 MB process peak RSS including the
interpreter and libraries. Grid spacing is 0.8 Å; no decimation is performed. The recorded field
residual bound is not a Hausdorff or topology guarantee. These measurements do not establish
interactive frame time, GPU memory, or reference-hardware acceptance.
