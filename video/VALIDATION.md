# Latent Nature walkthrough validation — 2026-09-06

This revision replaces the first preview's recreated screens with current deployed
application captures. The earlier 138-second preview is superseded.

- Source UI: the deployed localhost:8765 app, checked against the repository's
  Latent Nature screenshots. Current logo, sidebar, library, native graph nodes,
  top-down search tree and researcher details are captured directly.
- Source media: 300 Playwright PNG captures at 1920×1000, plus the actual first
  page of the HA–CD44 article. Browser-local setup interception blocks all live
  API mutations. Actual existing graph/paper/history reads remain read-only.
- TypeScript: passes. Capture and check scripts pass syntax checks.
- Remotion Player: 56 sampled timestamps, no image-loading/page errors or caption
  overflow. Seven UI frames exactly match the original captured pixels, including
  the library, researcher workspaces and HA–CD44 review. Paper reveal pixels remain
  identical after seeking backwards.
- Manual review corrected a retained close-up camera after leaving researcher
  detail. The updated camera fits the actual visible node geometry as history
  advances, so the complete native tree expands within the viewport.
- Paper attribution: candidate 900004, branch
  pdac-frozen-investigation-03~1~1~1~1~1~1~1~1~1. The scenario's private_attribution
  identifies DOI 10.1186/s12964-026-02865-5. Publisher and PubMed metadata confirm
  publication on 7 April 2026.
- Exclusion check: exact DOI lookup returns zero papers in the seeded project's
  index; the DOI is absent from its frozen MANIFEST.json. Manifest SHA-256:
  ceb35417c56cb2b05dbbfc6ff8f942b55d621b04de4f72a4deaf9fee409c1699.
- The runtime calls this authored presentation history, not a measured holdout
  recovery. The ending preserves that provenance and does not imply a new run.

The target export is 5,100 frames, 170 seconds, 1920×1080, 30 fps, silent H.264.
Generated capture metadata, full-size review frames and media remain local under
video/public/capture and video/out. Export inspection is recorded with the final
media delivery. No scientific run, data mutation or deployment is performed.
