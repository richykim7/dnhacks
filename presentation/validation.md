# Presentation review — 6 September 2026

Final source baseline: `1e83cfb158dd1c9d35894e05006bd9482a566233`.
Application source was not changed by this presentation task.

## Delivery checks

- Main PowerPoint: **17 slides**, including an **11-slide core** with 315 seconds of suggested timing.
- Layout kit: **4 distinct layouts** for evidence, comparison result, demo and roadmap.
- All **21 slides contain notes**, with scripts or script prompts, source/status context and editing guidance.
- Both PPTX ZIP packages pass integrity checks and reopen through `python-pptx`.
- LibreOffice Impress rendered both decks to PDF successfully. All 21 PDF pages were rasterized.
- Compared the words in native PowerPoint text against each rendered PDF page: **no missing tokens**.
- Reviewed the full-deck and layout-kit contact sheets, plus full-size demo, engineering and statistical
  evidence slides. Corrected the synthetic label, spacing, screenshot aspect ratio, inherited shadows,
  plain-language statistical label and template variety. No slide text extends outside the slide canvas.
- An independent code/evidence review corrected “matched evaluation pairs” to “selected evaluation pairs”
  and confirmed the synthetic metric, prior-art descriptions and falsifier limitations.
- [Artifact checks and SHA-256 hashes](output/artifact-checks.json) identify the reviewed delivery files.

Rendering environment: `python-pptx` 1.0.2, LibreOffice Impress 7.3.7, Poppler `pdftotext`/`pdftoppm`,
IBM Plex Sans and IBM Plex Mono installed locally. Fonts are not embedded in the PPTX files.
PowerPoint-native rendering was not available in this Linux environment; the PDF is the reviewed
visual reference. No animations or remote media are required for the delivered slides.

## Repository gates

| Gate on final source baseline | Result |
| --- | --- |
| `npm --prefix frontend run build` | Passed; documented upstream 3Dmol `eval` warning remains. |
| `npm --prefix frontend run test` | 6 passed. |
| `npm --prefix frontend run e2e -- --workers=1` | 19 passed; no final-run failure or retry. |
| `uv run pytest tests -ra` | 270 passed, 18 skipped; no failures. |
| `git diff --check` | Passed. |

The isolated tracked suite skips eight Torch/evalue tests, five PDF-dependency tests, two pydeseq2
tests, one decoupler test, one Rscript/PharmacoGx test and one opt-in real Docker smoke test. The wider
ignored/local vocabulary suite was not copied from another checkout; these counts describe the
tracked suite only. No missing-vocabulary-data failures occurred in this isolated suite.

An earlier check at `145566d` used the default two browser workers and hit one 30-second geometry
timeout. That test passed unchanged in an isolated retry; full serial suites passed both before and
after incorporating main's subsequent grounding fixes and 3D planning documents. No application code
was altered to hide the timeout. Browser server processes used isolated ports 8876 and 5276 and were
stopped after validation. Runtime terminal tests mock their subprocess calls; no shared tmux was touched.

Full local logs: `/tmp/dnhacks-presentation-validation/final-1e83cfb/`.

## Remaining presentation additions

The working name and proposed Open Category framing await team decisions. Slide 6 uses clearly labeled
synthetic interface data and must be replaced to demonstrate a real scientific run. No independent
biological confirmation, useful-discovery rate, cost savings, customer traction or production-security
certification was created or inferred. These are stated future milestones, not missing deck-generation work.
