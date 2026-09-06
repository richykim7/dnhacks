# Development image inspection

All 21 listed captures were opened with the actual image-viewing tool. These are authored visual
fixtures, not native simulation results. The exact hashes are in captures.json.

- r1: Exterior/1600 and Exterior/1920 had an opaque-looking cyan domain box competing with the cells.
  Core and Comparison exposed states but smooth membranes resembled identical beads. Mobile clipped
  the close control; light mode had weak inspection-text contrast.
- r2: hidden field in Exterior, restrained volume opacity and procedural membrane normals improved
  focus. Mobile close control now fits and light text is legible. Core and Comparison revealed hollow
  clipped tumor membranes, requiring actual section caps.
- r3: section caps make the cut cells solid; comparison has readable common framing and distinct
  viable/dead states. The new focal-plane scale subsequently needed a height-based projection fix;
  these images therefore do not certify the final scale bar. Native-data and final integration
  captures remain required before accepting the complete instrument.

## Native data inspection and critique resolution

`native-r1-*` records the first actual native-data image pass. `native-final-*` records the
subsequent inspected revision: Exterior/Core/Comparison at1600×1000 and1920×1080, light mode,
390×844 reduced-motion mobile, and selected-cell Neighborhood. Every saved PNG was opened with
the image-viewing tool. The first three primary views also reached the actual vision model as
PNG bytes through the production HTTP renderer; their immutable receipts/observations are in
`native-final-receipts.json`. Three visual reviews completed after image-specific critique and
numerical cross-check. Biological verification remains false.

Concrete improvements: whole-volume count labels, explicit living-pearl/dead-violet legend,
fixed shared field range with midpoint ticks, source-voxel diagnostic and saturation count, and
diagnostic panels outside tissue geometry. Mobile places the field below the 3D scene. The scale
bar now uses the actual renderer height and camera projection. A subsequent Neighborhood camera
focus refinement is being checked separately; the pictured earlier Neighborhood view remains
a development capture, not the accepted focused view.

The final comparison visibly shows a localized pearl survivor cluster in the first condition
and violet dead cells in the suppressed condition. The two alanine fields differ only slightly;
that difference is not visually resolved, and the numerical inset says so through its values.
The inset samples the nearest recorded voxel center (10 µm for requested z0), labeled explicitly;
it does not invent a value at an unrecorded plane. The cutaway is a half-volume and can occlude
other cells; whole-volume counts must be audited numerically. The initial Exterior view deliberately
hides the field at t0 to establish geometry. These view limitations are not evidence of a biological
effect or a reason to remove a shared legend. Several model critiques misread colors or subtracted
the displayed concentrations incorrectly; the source arrays and actual pixels resolve those errors.

The native static rendering measurements record browser, software renderer, canvas dimensions,
draw calls, triangle counts and20 timed renders after three warmups. They are not sustained whole-
application frame rates. The10000-cell/128³ capacity case exceeded its90-second capture budget
in two initial attempts; no black frame or unavailable performance result was accepted. Capacity
optimization/measurement continues as a separate final milestone.
