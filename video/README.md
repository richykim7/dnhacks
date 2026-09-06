# Latent Nature product walkthrough

The 170-second, 1080p/30 fps Remotion video uses **captures of the deployed frontend**.
There is no recreated application shell, library, graph or researcher card.
Playwright opens the actual app, types into its forms, opens papers, seeks its
history slider, opens researcher workspaces, and selects the HA–CD44 candidate.

Remotion adds a visible cursor, captions, short fades between captured growth
states, and the first-page paper reveal. Native graph topology, branding, sidebar,
library rows, candidate records and researcher detail come from the deployed UI.

## Capture, check and render

Use Node 22.12+ and Python 3 with PyMuPDF for the article page. From video/ run:

    npm ci
    npx playwright install chromium
    npm run capture
    npm run check
    npm run check:frames
    npm run render

The capture defaults to the deployed localhost app at port 8765. Override with
CAPTURE_BASE_URL. CAPTURE_OUTPUT sets an absolute capture folder; by default it
is video/public/capture. VIDEO_OUTPUT sets the final MP4 path; its default is
video/out/latent-nature-walkthrough.mp4. FRAME_CHECK_OUTPUT sets the screenshot
review folder. All generated media are local, ignored artifacts.

Both capture and frame checks hold the shared browser slot from
scripts/browser_tests.py and clean up only their own processes. The capture
visits the deployed website as explicitly requested; it never reuses a frontend
test server. Its browser-local route fulfills every non-GET API request, so form
submission cannot start research, ingestion, review decisions or any server writes.
First-open collection creation is staged in the browser. Subsequent source papers,
graph and investigation history are real existing application records.

Graph and paper arrival animation reveals existing rendered elements. Research
history is sought in an accelerating sequence; the camera is fitted to the actual
visible node geometry after each seek. Native styles and topology remain intact.

CAPTURE_FROM=tree resumes the capture from the investigation, preserving earlier
frames. Capture metadata includes clicked target bounds, exact screenshot times,
source URL, release-health response and history length. A failed capture writes
its checkpoint and fails; rendering refuses an incomplete capture.

## The HA–CD44 ending

The selected branch is
pdac-frozen-investigation-03~1~1~1~1~1~1~1~1~1, candidate 900004:

> HA–CD44 supports division tolerance in centrosome-amplified pancreatic cells.

The associated paper is Ozcan et al., “Stress adaptation pathways and HA–CD44
signaling maintain the survival of pancreatic cancer cells with centrosome
amplification,” Cell Communication and Signaling (7 April 2026),
https://doi.org/10.1186/s12964-026-02865-5.
The actual first PDF page appears with author/source/license credit, followed by
the evidence-boundary explanation.

The named target DOI is absent from the frozen manifest and the seeded project's
paper index. The local runtime explicitly identifies the investigation as an
authored presentation reconstruction. The video preserves that distinction and
does not call it an independently measured holdout recovery. This is an attribution
and presentation correction, not a new scientific run.

The article is © The Author(s) 2026, CC BY-NC-ND 4.0:
https://creativecommons.org/licenses/by-nc-nd/4.0/.
Its first page is reproduced unchanged; media and the full PDF remain untracked.

## Visual verification

The Playwright check seeks 62 times across all chapters, checks image loading and
caption overflow, saves screenshots, compares seven UI frames pixel-for-pixel
against their original browser captures, and checks that the paper reveal is
identical after seeking backwards. Inspect out/frame-check/index.html manually
as well: passing assertions alone does not establish visual fidelity.

Official Remotion skill used:
https://github.com/remotion-dev/skills/tree/main/skills/remotion-best-practices.
The locally installed skill was version 4.0.521. Local rendering is subject to
Remotion's license eligibility.
