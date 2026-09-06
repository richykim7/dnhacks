# DNHacks 2026 presentation

The editable working deck is [DNHacks_2026_DN_Research.pptx](output/DNHacks_2026_DN_Research.pptx).
Use the [PDF](output/DNHacks_2026_DN_Research.pdf) to preview it and the
[contact sheet](output/contact-sheet.png) to see the visual system at a glance.
The [four-slide layout kit](output/DNHacks_Layout_Kit.pptx) provides reusable evidence, result,
demo and roadmap layouts. All text, diagrams and panels are editable PowerPoint objects;
the actual application screenshot is a raster image.

Every slide contains a tentative script in PowerPoint's **Notes** pane and Presenter View,
plus its evidence status, sources, editing instructions and judging criteria. The same material
is available in [speaker-notes.md](speaker-notes.md).

## Presenting and extending

- Slides **1–11** form a roughly five-minute core pitch (315 seconds of suggested timing, including
  a 55-second demo slot). Slides **12–17** answer judging and technical questions. Stop at slide 11
  or select slides 1–11 in PowerPoint's slide-show setup; appendices remain available for questions.
- For a three-minute route, use **1, 2, 4, 6, 7, 8, 11**, shorten the demo to 40 seconds and rehearse
  the transitions. Timing is a proposal; no official pitch-duration rule was supplied.
- **DN Research is a working name**, as stated by `frontend/DESIGN.md`. Rename consistently after
  the team decides. No team member names, customer logos, contact details or traction were invented.
- **Open Category is the proposed framing**, not a claim about the team's submitted track.
  The official event places DTX Ventures in Open and describes that category as a home for ambitious,
  cross-domain work. Its Health and Public Service description emphasizes government-facing service
  delivery. Confirm the entered track before presenting; oncology is the initial application either way.
- **Replace slide 6 before presenting a real discovery.** Its prominent label identifies a fresh
  capture of the actual interface using synthetic browser-test data. The real 100-paper corpus count
  is separate from that fixture. Use an actual run's source passage, question, code, structured result
  and feedback; preserve a local recording as fallback. Do not imply frontend review buttons exist.
- If a scientific result lands, insert a result slide after slide 6: question, independent units,
  method, predicted direction, measured effect/uncertainty, comparison and exact artifact. Update the
  claim ledger and close accordingly. A candidate screen pass is not independent reproduction.
- Duplicate slides in the layout kit or a matching core slide to add material. Keep one main argument
  per slide, update notes and sources, and preserve implemented/measured/planned/illustrative labels.

## Intention and visual system

Lead with **“Point compute at the next scientific discovery.”** The project is a research instrument
that helps a scientist select and inspect the next experiment. The narrative follows evidence →
hypothesis → executed analysis → feedback → scientist decision. It follows the non-biology-audience
brief in `plans/PLAN-demo-slides.md` and gives engineering and AI sophistication substantial core time.
Slide 12 explicitly maps every supplied criterion and point weight to supporting slides.

The style extends the existing product design: 16:9, mineral charcoal (`#17201F`), warm white
(`#F1EFE7`), muted green (`#A6C9B8`), amber uncertainty (`#DEB577`), IBM Plex Sans and IBM Plex Mono.
Most headlines are 36–46 pt; core body text is 19–25 pt. Small type is reserved for source/status
metadata and appendix detail. Pale evidence slides create pacing. The conceptual graph motif is
editable vector geometry and deliberately carries no biological or performance meaning.

Install the open-source [IBM Plex fonts](https://github.com/IBM/plex) on presentation machines for
matching line breaks. The fonts are **not embedded**. The PDF preserves the reviewed appearance.
PowerPoint can edit every text box and diagram, and the generator configures the theme fonts for new
objects. The separate layout kit is a set of editable slide examples, not custom Slide Master layouts.

## Evidence and research decisions

Source snapshot: `1e83cfb158dd1c9d35894e05006bd9482a566233`, 6 September 2026.
The checked-in deck is an evidence snapshot; the repository will continue evolving.

| Claim or decision | Source and scope |
| --- | --- |
| 40M+ biomedical citations and abstracts | [NIH/NLM About PubMed](https://pubmed.ncbi.nlm.nih.gov/about/), accessed 2026-09-06. Not full-text papers or our corpus size. |
| DTX audience fit | [DTX Vision](https://www.dtxventures.com/vision), accessed 2026-09-06. Its interest in U.S. critical-technology leadership motivates scientific-infrastructure framing; this is our inference, not endorsement. |
| Proposed Open Category | [Official DNHacks site](https://dnhacks.org/), accessed 2026-09-06. DTX presents Open; entered category still unconfirmed. User supplied the detailed scoring weights. |
| 100 curated full-text pancreatic-cancer papers | `demo/pdac/README.md`, `demo/pdac/papers.json`. Retrospective curation, 2007–2025; inclusion boundary 2026-01-25. Indexing does not establish completed claim extraction or a prospective discovery benchmark. |
| 1.12% synthetic false alarms | `research/learned-evalue-validation/expanded-null.json`: learned encoder, 112/10,000 **ever** crossings, Wilson 95% interval 0.93–1.35%. Final rejection rate is a different quantity: 20/10,000 = 0.20%. Separate diagnostic, not live discovery accuracy or an investigation-wide guarantee. |
| Learned real-expression diagnostic | `research/learned-evalue-validation/real-expression/README.md`: separate COVID observational cohort; 30 selected pairs, not clinical covariate matching. Show all principal comparators; the single-gene baseline has greater final evidence in the primary run. |
| Prior art | [DeepMind Co-scientist](https://deepmind.google/blog/co-scientist-a-multi-agent-ai-partner-to-accelerate-research/) and [Elicit Research Agent](https://elicit.com/blog/introducing-elicit-research-agent), accessed 2026-09-06. Both already do substantive research. No first-autonomous-scientist or superior-performance claim. |
| Oncology context reserved for Q&A | [NCI SEER](https://seer.cancer.gov/statfacts/html/pancreas.html), accessed 2026-09-06: 13.7% five-year relative survival, 2016–2022, pancreatic cancer overall. No PDAC-specific or prototype health-benefit inference. |
| Editable export choice | Reviewed [nexu-io/codex-slides](https://github.com/nexu-io/codex-slides); its current PPTX exports whole-slide images. Used the already-installed [python-pptx](https://python-pptx.readthedocs.io/) instead, because this deck must keep changing. No upstream template artwork copied. |

Important reconciliations: the old local forecasting judge brief describes a superseded product story
and is not evidence for this deck. The initial synthetic-validation README retains an earlier
“10,000 not yet run” paragraph; its later expanded evaluation section and machine-readable summary
record the completed 10,000-run audit used here. The architecture's “numbers are sound” shorthand
overstates what the ordinary falsifier independently establishes: it screens agent-reported fields
and flags. The deck says that explicitly. Human decisions are available in the backend while their
frontend controls are hidden. Docker execution still exists despite the plan to remove it. Learned
tool plans, statistical stopping and production hardening remain future work.

No source ingestion, research model calls, training, deployment, customer outreach or new scientific
evaluation were performed to make this presentation. The roadmap communicates intention only.

## Build and review

The presentation generator is self-contained and uses the existing Python package `python-pptx`.
It reads the checked-in diagnostic JSON for the synthetic null numbers and uses the screenshot in
`assets/workspace-fixture.png`. No change to the application dependencies is needed.

```sh
python3 presentation/build_deck.py
libreoffice -env:UserInstallation=file:///tmp/dnhacks-presentation-lo --headless \
  --convert-to pdf --outdir presentation/output \
  presentation/output/DNHacks_2026_DN_Research.pptx \
  presentation/output/DNHacks_Layout_Kit.pptx
```

The PPTX and PDF files are delivery artifacts. `speaker-notes.md` and `output/deck-manifest.json`
are regenerated by the script. Manual PowerPoint edits are not imported back into Python; save a
separate version if editing the deck directly. Re-render and inspect after substantial text changes.

Review includes LibreOffice rendering of all slides, visual inspection, PowerPoint package checks
and verification that all 21 delivered slides (17 deck + 4 kit) have notes. See
[validation.md](validation.md) for application gates and artifact checks.
