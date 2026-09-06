# Native cortical motor fields

The adapter exports actual fixed anchor coordinates using `single:position` and
bound filament identity, abscissa and force using `single:link`. Positions use µm
and force vectors use pN. Unbound motors have null bound measurements. The native
reports, scientific chunks and immutable display bundle retain these values.
Captures must acknowledge the exact saved motor field, including comparisons.

The new export exposed a configuration defect: `placement=off` prevented requested
translations, leaving the previous cortical motors at the origin. The corrected
configuration uses `placement=anywhere` with explicit coordinates. Every anchor is
now compared with its prescribed ellipsoid position at every saved frame, with a
10⁻⁵ µm tolerance for native serialization. A native regression deliberately
corrupts an anchor to the origin and verifies rejection. Original archived runs
are preserved, but their cortical-localization comparisons are invalid.

A fresh linked engineering experiment used one seed, two initial centrosomes,
32 filaments per aster, 1 s duration and 0.1 s sampling. To exercise binding/export,
initial filament length was 4 µm, binding range 0.3 µm and binding rate 50/s;
these are explicit test assumptions, not biological estimates. The control has
no cortical motors. The intervention has 64 fixed anchors in a positive-x
crescent. Its bound counts across eleven saved frames were
0, 1, 2, 2, 1, 1, 1, 2, 3, 1, 3. Every native anchor passed the surface check.

The developer opened the actual [corrected comparison](spindle-review/motors.png):
the gold anchors form the requested crescent; both cell silhouettes and pole
identities remain visible. Counts are labelled per condition. The expandable
measurement table reports anchor position, bound filament and force vector.
[Exact protocol and capture provenance](spindle-motors.json) are retained.

This validates field placement/export and image provenance. It does not establish
biological motor effects, calibrated HSET dynamics or coupled-model convergence.

An additional runtime vision request for this corrected capture reached the
configured provider's session limit and produced no observation. The direct
developer pixel inspection above is separate. Runtime review failures now emit
an explicit failure receipt and cannot create a visual verdict. Earlier
image-bearing runtime reviews remain in the original scene workflow record.
