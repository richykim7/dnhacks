# Walkthrough validation — 2026-09-06

- TypeScript: `npm run check` passes.
- Playwright: `npm run check:frames` passes with 43 sampled timestamps,
  11 cursor-to-target hit checks, no page errors or important-text overflow,
  and byte-identical screenshots after backward seeking.
- Final investigation overview: all 43 authored research nodes fit within the
  graph viewport; pairwise rectangle checks find no overlapping node cards.
- Manual screenshot review corrected initial cursor offsets and overlapping
  research cards. Reviewed the updated early forms, graph and complete overview.
- Export: rendered all 4,140 frames at 1920×1080 / 30 fps / H.264, 138 seconds.
  The deliverable has no audio; the initial automatic silent AAC track was removed
  losslessly, and future renders use `--muted`.
- Export inspection: extracted 23 frames across the MP4, including setup,
  ingestion, both slow researcher inspections, expansion, review and ending.
- Package audit at validation: zero known vulnerabilities in the installed graph.
- No backend, scientific experiment, live data change or deployment was performed.

The output is a **preview**. The held-out paper/candidate/run/access-boundary
metadata has not been supplied. Its closing card says this explicitly; this
validation does not establish a scientific discovery or recovery.

Generated evidence stays local under `out/frame-check/`, `out/export-frames/`,
`out/export-contact-sheet.jpg` and `out/export-metadata.json`. Recreate the
browser evidence with the command above. The preview MP4 is
`out/product-walkthrough-preview.mp4`.
