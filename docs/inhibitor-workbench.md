# Inhibitor workbench

Open Investigations, select a researcher, open its Experiments tab, and choose
**Open inhibitor workbench** on a collected PDB/mmCIF artifact. No structure
artifact means no workbench button. This does not add a top-level route or
populate an investigation with demo data.

The first implementation normalizes deposited coordinates through Gemmi and
provides residue selection, canonical distances, proximity contacts, matte and
luminous displays, clipping, and PNG/JSON export. The original artifact remains
immutable; the existing run/project and playback-cursor checks guard geometry
requests. Exported JSON is a local report, not a registered evidence artifact.

Preparation reports a blocker rather than modifying chemistry. Docking, candidate
comparison, molecular dynamics, scientific solvent surfaces, and runtime-agent
image delivery are not implemented. Display bonds and CA traces are illustrative.
Proximity is not an assigned hydrogen bond; affinity and inhibition are unmeasured.
This is a partial implementation of the inhibitor plan, not completion of all
its visual, scientific, performance, and agent-vision milestones.

For local viewing, build with `npm --prefix frontend run build`, then run
`uv run python scripts/serve_ui.py --port 8765` from the checkout containing the
desired investigation data. Open http://127.0.0.1:8765. Deployment of a running
shared instance is separate from merging source code.

The development-only `?sceneReview=1` controller permits deterministic camera,
style and selection review and rejects stale capture revisions. It is excluded
from production builds.

Integration review opened actual 1600×1000 and 390×844 browser captures. The
first pair exposed a blank scene: OrbitControls initialized after camera setup
and reset its target. Initializing the controls before positioning the camera
restored the molecule in both viewports. A second review found atom geometry
behind the lower caption and top metadata; opaque label backgrounds improve
legibility. This limited integration review does not certify all of the plan's
visual-selection or performance milestones.
