# DNHacks · technical pitch

[Editable PowerPoint](output/DNHacks_2026_DN_Research.pptx) · [Delivery bundle](output/DNHacks_Presentation_Bundle.zip) · [PDF](output/DNHacks_2026_DN_Research.pdf) · [Speaker notes](speaker-notes.md) · [Contact sheet](output/contact-sheet.png)

**Ten slides, about 6 minutes 15 seconds.** The main deck contains the technical case, measured comparisons and the discovery demonstration structure. Every slide has a tentative script, detailed technical Notes, sources, rubric coverage and editing instructions. There is no separate technical-reference dependency.

| Slide | Argument and visual |
| --- | --- |
| 1 | Autonomous biological research; native editable architecture rendering replaces the cell cover. |
| 2 | Experimental urgency argument, with scoped AISI/Anthropic evidence and the requested NSCEB quote. |
| 3 | Ingestion and grounded graph → recursive sessions → acceptance; actual website captures. |
| 4 | Ground 3D inspection in recorded coordinate checks; actual inhibitor result and playable binder cinematic. |
| 5 | Masked reconstruction loss, justified analytical mean baseline, real training curve and recorded L40S fit. |
| 6 | Negative log-payoff loss, fresh-data betting, null assumptions, evidence trajectories and all predeclared representation comparators. |
| 7 | General research workflow, actual website capture as a placeholder, editable candidate counts and paper mockup fading on click. |
| 8 | Immediately following: frozen inputs, excluded paper, access audit and the teammate-run GPU task/timing slot. |
| 9 | First user, deployment integration, unit economics and adoption evidence to measure. |
| 10 | Three-year development thesis, including future trained allocation and concrete commercial/scientific milestones. |

## Play the video

The movie on **slide 4** is embedded H.264 and configured to start when the slide opens in **PowerPoint Slide Show mode**. The green **OPEN VIDEO** button opens `binder-reveal.mp4` beside the deck. Extract the entire delivery bundle first and keep the PPTX, PDF and MP4 together. The standalone MP4 is also available directly in Telegram.

A Telegram document preview or PDF displays a still frame. Native PowerPoint playback still needs rehearsal on the presentation machine; the XML and fallback packaging have been checked here. The 23.44-second clip is an authored website cinematic with illustrative geometry, not a model inference or scientific result. [Media provenance](assets/short/manifest.json).

Playback references: [Microsoft playback guidance](https://support.microsoft.com/en-us/powerpoint/play-a-video-automatically-in-a-slide-show) and [PresentationML video timing](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.presentation.video?view=openxml-3.0.1).

## Fill the teammate-run demonstration

The user confirms that the actual run records are on a teammate machine. The deck provides an inferred workflow and editable placeholders; missing local records do not prevent building the presentation.

- Slide 7: replace the sample website capture with the selected investigation. Fill proposed/passed/reviewed counts, the candidate's exact result and the later paper's title/date/DOI. The native white paper mockup has an 800ms on-click fade. Show the loop and survivors before the reveal.
- Slide 8: insert the real Library/source-reader capture, run/cutoff/input hashes and the recorded GPU task/device/time. Keep this slide directly after the paper reveal. Audit external retrieval and explain exactly what was excluded.
- The locally measured **3.41s L40S fit belongs to the expression encoder on slide 5**. It is not a discovery runtime or evidence that the teammate's recovery ran on a GPU. A frozen retrieval corpus cannot erase pretrained model knowledge; sealed post-cutoff data and equal-budget baselines are stronger subsequent tests.

## Defend the mathematics

Slide 5 shows recorded TRAIN masked reconstruction MSE and an **analytical training-mean reference**. Standardized nonconstant genes have TRAIN variance one, so predicting their TRAIN mean gives expected masked MSE approximately one. No empirical random-network run or epoch-level validation curve is implied. The masked loss forces prediction from other entries rather than copying a visible target. [Denoising rationale: Vincent et al., JMLR 2010](https://www.jmlr.org/papers/v11/vincent10a.html).

Slide 6 minimizes negative mean log-payoff on past pairs, then scores fresh pairs before reuse. Under the iid equal-distribution null, frozen preprocessing and predictable fitting, swap symmetry gives a conditionally fair factor and an anytime threshold of 20 at alpha .05. Constant critic `g=0` gives exactly `E=1`: an analytical no-information control. Arbitrary LLM confidence numbers have no such conditional-expectation guarantee. This construction follows [Pandeva et al., AISTATS 2024](https://proceedings.mlr.press/v238/pandeva24a.html); it is not a new theorem.

All predeclared RNA representation comparators remain visible: learned **3,652.81**, PCA **85.76**, and stronger IFIT3 **5,964.41**. These are evidence statistics, not accuracy or causal effects. PCA64 and learned128 are not dimension-matched. The separate synthetic null audit had **112/10,000 ever-crossings**, not zero. [Figure data and analytical-control definitions](assets/revision/plots/manifest.json).

The ordinary acceptance path validates reported fields; it does not independently recompute arbitrary output. Graph confidence counts source papers, not independent experiments. Real-trajectory branch-monitor training/calibration remains future work. The Notes retain these boundaries and additional protein/native-kernel details.

## Sources and manual editing

The urgency slide uses [AISI's scoped benchmark report](https://www.aisi.gov.uk/frontier-ai-trends-report), [Anthropic's adversarial evaluation](https://www.anthropic.com/research/next-generation-constitutional-classifiers), and [NSCEB's call for anticipatory preparedness](https://www.biotech.senate.gov/final-report/chapters/chapter-3/section-3/). Neither benchmark is evidence that a novice can build a biological weapon. No operational threat or jailbreak method is included.

Use **Change Picture** for captures/plots. Architecture, paper, metric fields and deployment diagrams are editable native shapes. Current Knowledge/Investigation images show actual React UI with labeled synthetic data; replace them with the final collection/run. [Capture provenance](assets/revision/manifest.json). The previous cell illustration and exact generation prompt remain as optional assets in that directory; they are absent from the current slides.

Save manual edits separately: rerunning the generator overwrites its outputs. Fonts are IBM Plex Sans/Mono; install them on the presentation machine because they are not embedded. The earlier 29-slide package is preserved at [PR90](https://github.com/richykim7/dnhacks/pull/90); the legacy reviewer PDF now aliases the same ten-page pitch. The old [layout kit](output/DNHacks_Layout_Kit.pptx) remains available.

## Rebuild

```sh
python3 presentation/build_pitch_figures.py
python3 presentation/build_deck.py
python3 presentation/render_deck.py
python3 presentation/package_deck.py
```

Uses existing python-pptx, Pillow, Matplotlib, LibreOffice and Poppler. Figures derive from committed aggregates; no model training, scientific experiment, app deployment or service restart is started. [Validation](validation.md).
