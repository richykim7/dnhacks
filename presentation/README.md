# DNHacks 2026 · DN Research

The current editable deck is [DNHacks_2026_DN_Research.pptx](output/DNHacks_2026_DN_Research.pptx).
The [judge-pitch PDF](output/DNHacks_2026_DN_Research.pdf) shows the default presentation.
The [reviewer PDF](output/DNHacks_2026_Reviewer_Copy.pdf) includes the optional discovery sequence and technical appendix.
Every slide has a tentative script, evidence status, sources and editing instructions in PowerPoint **Notes**;
[speaker-notes.md](speaker-notes.md) provides the same text. Use the [contact sheet](output/contact-sheet.png) for an overview.

This revision consolidates the earlier decks in `presentation/output/` and `presentation/pptx/`.
The latter is retained as an archived draft; use this deck for subsequent work.

## Presentation route

- **Judge pitch:** slides **1–9, 14–16**, 5 minutes 40 seconds as scripted. Technical evidence receives substantial time, reflecting the 50-point execution and AI-sophistication weights.
- **Three-minute cut:** slides **1, 2, 4, 6, 7, 9, 16**. Shorten the spoken transitions and rehearse.
- **Optional discovery sequence:** slides **10–13**, hidden by default. Full investigation → surviving candidates → paper fade-in → frozen corpus on the **immediately following slide**. These are explicitly unpopulated storyboards. No qualifying run or matching excluded paper was verified at the source snapshot.
- **Technical Q&A:** slides **17–29**, hidden by default. Includes the complete rubric map, model/data/objective/split details, real training and evaluation figures, design evidence and deployment questions.

PowerPoint **Slide Show → Custom Slide Show** contains the judge pitch, three-minute cut and a discovery-reveal route.
Do not activate the discovery route until its four slides are populated and audited. The PPTX hides storyboards and appendices from the default show; the reviewer PDF displays them with their status labels.
No official pitch duration was supplied. DN Research remains a working name; Open Category remains proposed rather than a claim about the submitted track.

## Intention

**Anticipate biology. Before it changes the balance of power.**

The strategic thesis is that biology is an underappreciated future source of unilateral advantage, and that scientific lead time can support earlier defensive preparation. The opening uses the exact NSCEB 2025 report §1.3 quotation requested by the team. The product is an inspectable research engine; it does not demonstrate bioweapon prediction, operational threat prevention or clinical benefit. Reactive measures remain necessary; anticipation is the additional posture we aim to enable.

For DTX Ventures, the connection is scientific infrastructure and critical-technology leadership, inferred from its public thesis. The pitch then grounds that ambition in an initial computational-biologist persona, working engineering, real artifacts, measured negative results and a small private-pilot business hypothesis. It claims no customers, pricing validation, revenue or superior discovery rate.

The visual system combines mineral charcoal, warm ivory, muted mint and amber with IBM Plex Sans/Mono, large editable headlines and generous space. Two matching conceptual editorial backgrounds were generated through the existing LaoZhang adapter. They are decorative, never scientific evidence. Actual application captures retain their illustration/fixture labels. Research figures are generated from committed measurements with Matplotlib; no scientific images or loss histories were invented.

## Finish the discovery sequence

1. Select one real run with source claim, concise logged decision, code, data identity, raw result, checks and a recorded human decision.
2. Populate the actual survivor list, including the relevant denominator and the checks each candidate passed. A survivor is not automatically a true or novel finding.
3. Verify the matching later paper, its exact claim, publication date and exclusion from every accessible run input. Replace the paper group on slide 12 while retaining its native 800 ms on-click fade.
4. Keep slide 13 immediately next. Attach the frozen manifest/hash, tool-access boundary, cutoff and model-memory limitations. A curated corpus is not itself proof of a run's access boundary.
5. Independently audit the claim, then unhide all four slides. Keep a local recording and final-state PDF fallback. Linux rendering cannot certify native PowerPoint animation playback.

## What the technical figures establish

| Component | Measured material | Boundary |
| --- | --- | --- |
| Expression | 100 training-loss epochs; measured sequential evidence trajectories | No epoch-level validation-loss history retained. Separate observational COVID diagnostic, not PDAC. Single-gene comparator wins final evidence in the primary run. |
| Protein | Held-out hidden-entry error comparisons from committed training report | PCA beats denoiser. The subsequent Fudan cross-assay benchmark shows weak primary-model transfer and a secondary ranking signal requiring further evaluation. No invented convergence curve. |
| Drug response | Real CUDA validation comparisons and pancreatic-subset baseline; separate real PDO AUC validation | No pancreatic utility or full-curve PDO success established. Mean predictor wins PDO validation. |
| Cellular ecosystems | Initial count/set-model histories and final errors; expanded 72-donor GPU train/validation histories | Cells are nested within donors. Exact PCA leads external reconstruction in the expanded study. Initial pilot and new cell-weighted metrics are not directly comparable. |
| E-value diagnostics | Synthetic-null crossings, explicit denominators and confidence intervals | Not a product false-positive rate, biological power guarantee or investigation-wide certificate. |
| Branch monitor | Implemented model/calibration contracts and readiness explanation | No real-trajectory fitting or calibration yet; no fabricated plot or live calibrated-pruning claim. |

[Plot manifest](assets/v2/plots/manifest.json) stores source hashes and exact plotted data. [Editorial provenance](assets/v2/provenance.json) records prompts and the adapter's estimated $0.18 generation cost; account balance/final billing could not be read using the inference key. No new scientific training or experiments were run for this presentation.

## Rebuild and extend

```sh
python3 presentation/build_figures.py
python3 presentation/build_deck.py
python3 presentation/render_deck.py
```

The scripts use existing `python-pptx`, Matplotlib, Pillow, LibreOffice Impress and Poppler. No application dependency was added for slide authoring. The evidence snapshot is pinned in `deck_style.py` and written into the [deck manifest](output/deck-manifest.json); re-audit new findings before changing it.

Text, diagrams and paper-reveal panels are native editable PowerPoint objects. Artwork, charts and screenshots are raster assets; standalone chart PDFs are also provided. The [four-slide layout kit](output/DNHacks_Layout_Kit.pptx) provides reusable evidence, result, demo and roadmap examples. It is not a set of custom Slide Master layouts.

Install [IBM Plex](https://github.com/IBM/plex) on the presentation machine; fonts are not embedded. The PDF preserves the reviewed appearance. Manual PowerPoint edits do not round-trip to Python, so save them as a separate version or update the generator. The reviewed [codex-slides project](https://github.com/nexu-io/codex-slides) uses image-native slides; this deck retains editable text and diagrams because the project is still evolving.

Sources: [NSCEB §1.3](https://www.biotech.senate.gov/final-report/chapters/chapter-1/section-3/), [NSCEB §3.3](https://www.biotech.senate.gov/final-report/chapters/chapter-3/section-3/), [DARPA P3](https://www.darpa.mil/research/programs/pandemic-prevention-platform), [DTX Vision](https://www.dtxventures.com/vision), [DNHacks](https://dnhacks.org/). Full source/status details appear in each slide's notes. See [validation.md](validation.md) for rendering and repository checks.
