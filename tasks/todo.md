# Research workspace review

## Review — DNHacks judge presentation

- Created [editable PowerPoint, PDF preview, speaker notes and reusable layout kit](../presentation/README.md)
  with an 11-slide core story and six Q&A slides. Every criterion and weight is mapped explicitly.
- Extended the existing IBM Plex, charcoal, warm-white and green design. Distinguished real corpus
  metadata and measured standalone statistics from synthetic interface data and future plans.
- Researched official DTX/event sources, PubMed, SEER and current research-agent prior art. Chose Open
  Category as a proposed framing and retained DN Research as a working name; neither is a team decision.
- Reconciled the old forecasting pitch and historical evaluation-pilot statements. The ordinary
  falsifier screens reported fields; no independent reproduction or new biological discovery is claimed.
- Source validation: build, six UI unit tests, 19 browser tests after an unchanged serial retry, and
  270 tracked Python tests passed with 18 optional-dependency/opt-in skips. The initial parallel browser
  run hit one 30-second geometry timeout. Wider ignored/local tests were not copied into this worktree.
- Reviewed rendered slides and notes; delivery checks and limitations are in
  [presentation/validation.md](../presentation/validation.md). Scientific demo, final team name and
  pilot measurements remain future additions. No scientific model runs, training or outreach performed.

## Review — policy lab proofs and experiments

- Delivered the [formal model and complete proofs](research/policy-lab/report.md), [primary-paper audit](research/policy-lab/literature.md), [independent adversarial review](research/policy-lab/adversarial-review.md), [executable prototype](../research_spikes/policy_lab/README.md), and [standalone demo/figure](research/policy-lab/demo.html).
- Closed deterministic witness completion is Set-Union Knapsack. The exact small-shared-core DP and fractional certificates survive review, but are derived from established 1994 work; no new theorem is claimed. Arbitrary learned advice may reorder planning work without corrupting the certificate.
- Proved an arbitrarily bad shared-setup family for correctly deduplicated witness greedy, pair-witness exact hardness, and a revealed-action lower bound versus clairvoyance with the same-information optimum stated separately. Both seeded controls solve the shared-setup family.
- Reproduced 5,120 exhaustive reward/budget cases and 2,400 weighted-DAG/advice certificates with no oracle mismatch or invalid bound. The checked-in research regression suite has 64 passing tests; independent reviewers ran additional raw-mask checks.
- All 95 January 2018 CIViC citation-packet/budget cases match action enumeration. On 93 positive cases, residual witness greedy averages 0.969534 of optimum; both seeded controls and exact reach 1.0 throughout. Citation pairs and unit acquisition costs are declared simulation choices, not biological verification. No later labels were read.
- Recommendation: retain delivery coverage greedy for its declared objective; use the existing exact specialization as a small-packet comparator/certificate. Proposed action/context/visibility/prerequisite/cost/verifier records were posted to the Board; production interfaces were not edited.
- Browser artifact checks passed: working theorem slider, no page errors, zero WCAG axe violations, and mobile layout without horizontal overflow. Final repository gate counts and integration commit are recorded on the Board; only tracked Python tests are present here, not the wider unversioned vocabulary suite. The clean dev-only environment initially lacked the already-declared optional LLM SDK; installed repository extras for full validation without changing dependency files.

## Review — existing research workspace and inspectable evidence

- Read the research launch, branching, experiment, submission, verification, graph and source-storage code alongside the actual frontend. The [code-grounded review](../docs/ux-code-review.md) ranks Findings, branch-to-scientific-result linkage, evidence inspection, navigation continuity and Library next actions.
- Implemented relationship selection and searchable browsing directly in the Knowledge screen, retaining its design tokens. Review controls are now hidden; backend review remains available. Directed graph layout, focused endpoints, source quotations, paper links, stored assertion certainty and biological context now form one interaction. Distinct measured properties remain visible and searchable.
- Added a read-only collection-scoped claim-detail API. Fixed an existing fallback snapshot collision between same-named databases with matching timestamps. Real-store regression tests cover identity isolation, forced lock fallback, missing metadata/evidence, invalid sources/claims and per-edge measured properties.
- Coordinated shared API changes before editing. The runtime owner is handling remembered investigation selection and exact experiment navigation. E-values, exploration policy, deferred evaluations and model calls remain outside this change.
- Validation: production build, 2 frontend unit tests, all 16 browser tests and 101 Python tests passed; one optional learned-evalue module skipped because Torch is absent. The wider unversioned local vocabulary tests were not copied into this isolated checkout. Dark/light and mobile screenshots of the actual React UI were inspected; clearly synthetic browser fixtures demonstrate interaction, not scientific results. Existing 3Dmol build warning remains. Diff whitespace check passed.
- Tested from isolated backend 8784 and Vite 5189. The shared public preview has no populated normal research collection; this change does not manufacture one. Final integration commit is recorded on the Board.

## Review — judge deck (presentation/pptx)

- Built a reproducible PowerPoint deck: `presentation/pptx/build_deck.py` writes `dnhacks-deck.pptx` (22 slides, 16:9) in the product's own visual system (IBM Plex, charcoal, sea-green / amber / rose semantics). Every slide carries a provenance tag (MEASURED / IMPLEMENTED / PLANNED / ILLUSTRATIVE) and a speaker script with timings and the source file for each number in its notes; unfilled items are marked `[TODO]` on the slide and in the notes. `README.md` there lists the five-minute cut and the pre-demo fill list.
- Framing follows `ARCHITECTURE.md` (discovery loop, falsifier with no answer key, human gate) and the non-bio-audience note in `plans/PLAN-demo-slides.md`. Judging criteria for all three prizes are mapped slide by slide in appendix A. The archived CIViC backtest from the removed forecasting module appears only as appendix C with its reconciliation caveats.
- Audience research: DTX Ventures presents the Open Category at DNHacks 2026 (Sept 5–6, Station DC); their public thesis line and the NSCEB "dangerously close to falling behind China" sentence were verified against primary pages and recorded in `dtx_context.json`. No public DTX pitch-deck guidance was found.
- Validation: deck built from a clean worktree at origin/main; rendered through LibreOffice to PDF/PNG and every slide inspected for overflow and overlap; `git diff --check` clean. No engine, frontend or test code changed.
