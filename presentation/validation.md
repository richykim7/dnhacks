# Presentation revision review · 6 September 2026

Scientific source snapshot: `fee3165` (including inhibitor review, external protein/PDO results and expanded ecosystem training). The generator and manifests pin the full source commit. This task changes presentation and coordination infrastructure, not the research engine or its scientific results.

## Delivery review

- **29 editable slides**: 12-slide default pitch (340 scripted seconds), four hidden discovery storyboards and 13 hidden technical appendix slides. Three named custom shows support the normal pitch, shorter cut and conditional reveal route.
- **Four reusable layout slides**, also with notes. All **33 slides** reopen through `python-pptx`, pass ZIP integrity checks and include scripts or script prompts, status and editing instructions.
- Default judge PDF contains 12 pages. The reviewer PDF contains all 29 slides; its temporary export copy unhides slides and removes custom-show selection while leaving the delivered PPTX unchanged.
- LibreOffice rendered all 33 pages. Native PowerPoint text was compared with extracted PDF words: **no missing text tokens**. All text boxes remain within the slide canvas.
- Reviewed the full contact sheet and full-size cover, persona, scientific toolkit, reliability, deployment, training/transfer figures and closing slides. Fixed persona overlap, crowded roadmap copy, external-result footer overflow and closing contrast.
- The discovery-paper panel has a native 800 ms on-click fade, and the frozen-corpus slide is directly next. The sequence is explicitly unpopulated and hidden. Linux/LibreOffice rendering does not certify animation playback in native PowerPoint; the PDF shows the final state.
- Fourteen research figures are reproducible from committed measurements or explicit documented values. The [figure manifest](assets/v2/plots/manifest.json) records source hashes, plotted values, objectives, comparators and limits. No absent validation-loss histories were reconstructed.
- Conceptual cover/closing artwork has separate [provider provenance](assets/v2/provenance.json); it is not scientific evidence. Screenshots remain actual application captures with clear fixture/illustration/measured-workflow distinctions.

Rendering environment: system `python-pptx` 1.0.2, Pillow, Matplotlib, LibreOffice Impress 7.3.7 and Poppler. IBM Plex fonts are installed locally but are not embedded. Artwork, screenshots and figures are raster assets; presentation text, diagrams and panels are native editable objects. Standalone research-figure PDFs are also included.

[Artifact checks and SHA-256 hashes](output/artifact-checks.json) identify the delivery packages. The PDF is the reviewed appearance reference.

## Repository validation

Final Python validation used `592fb0a` plus this task’s changes. Frontend build, unit and full browser checks passed on `fee3165`; the subsequently merged isolation changes also passed a real empty-backend browser check. The scientific presentation remains pinned to the separately audited `fee3165` snapshot. Subsequent independent spindle/ecosystem work through `e871ed1` was incorporated without conflict; the changed coordination and cleanup callers were rechecked on that merge base.

| Gate | Result |
| --- | --- |
| Frontend production build | Passed; upstream 3Dmol `eval` and large-chunk warnings remain. |
| Frontend unit tests | 6 passed. |
| Tracked Python suite | 529 passed, 33 skipped; no failures (105 seconds). |
| Browser suite | 24 passed using the repository’s isolated browser runner; final empty-backend isolation case also passed. |
| Whitespace check | Passed. |

The isolated Python environment uses the declared development extra. Skips cover optional Torch/expression/spreadsheet/PDF adapters, Rscript/PharmacoGx, opt-in Docker and an unconfigured operator-pinned Cytosim build. No missing-vocabulary-data failure occurred; the wider ignored local vocabulary suite was not copied from another checkout.

Earlier integration checks passed 472 Python tests with 27 skips at `35b4103` and 490 with 29 skips at `af01505`. The final browser run used the repository runner, which owns isolated servers, data, ports and cleanup. An earlier run exposed a process-reaping race in the browser cleanup assertion. The correction now tolerates disappearance during reads and asynchronous exit while still failing if the owned child remains live after five seconds; the affected OS-level check passed 50 repetitions and the final full suite passed. No public preview or research app deployment was performed. The revised PowerPoint, 12-page pitch PDF and 29-page reviewer PDF were each delivered successfully through the existing Telegram transport.

Nudger regression and live-service evidence are documented in [the operating guide](../docs/board-nudger.md) and on the Board. The final nudger, shared-input and mirror regression selection passed all 63 cases. All real tmux fixtures use an owned private socket; Herdr routing verifies the existing pane and exact thread. Actual direct and managed-service probe arrivals were acknowledged by this active agent, distinct from transport receipts.

Local logs: `/tmp/dnhacks-presentation-v2-validation/`; service evidence: `/tmp/dnhacks-nudger-evidence/` and `~/.local/state/dnhacks-board/`.

## Remaining scientific additions

The project name and entered category remain team decisions. The full discovery reveal requires a verified run, candidate list, matching paper and exclusion/access audit. The frozen corpus alone cannot rule out pretrained model memory. Pilot cost, usefulness, user adoption, production hardening and clinical or operational deployment remain future evidence requirements; none was fabricated to complete the deck.
