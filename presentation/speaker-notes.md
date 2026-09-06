# Tentative speaking script

Default judge pitch: slides 1, 2, 3, 4, 5, 6, 7, 8, 9, 14, 15, 16 (340 seconds). Slides 10–13 are hidden discovery storyboards; 17–29 are hidden Q&A. Every slide has editable PowerPoint Notes.

## 01 — Anticipate biology.

TENTATIVE SCRIPT · 25 seconds
Biology is an underappreciated source of future strategic power. Our thesis is that scientific lead time matters: understanding an emerging capability earlier gives scientists and institutions more time to prepare. DN Research is our working name for an engine that connects published evidence, proposes experiments and keeps the results inspectable.

EVIDENCE / STATUS
Strategic thesis and intended application. Current prototype is computational biological research; it does not demonstrate bioweapon prediction or operational threat prevention. Cover art is AI-generated conceptual imagery, not measured biology.

BEFORE PRESENTING / NEXT EDIT
Working name and entered category need final team confirmation. Use the Judge pitch custom show. This slide and the close are conceptual art; all scientific figures are sourced separately.

JUDGING CRITERIA
Problem & Real-World Impact (25); Feasibility & Deployment (25)

SOURCES
DTX Ventures · Vision: https://www.dtxventures.com/vision (accessed 2026-09-06)
NSCEB final report, April 2025, §3.3: https://www.biotech.senate.gov/final-report/chapters/chapter-3/section-3/ (accessed 2026-09-06)
Repository: ARCHITECTURE.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed
Repository: presentation/assets/v2/README.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed

## 02 — A warning about the way we innovate.

TENTATIVE SCRIPT · 20 seconds
The National Security Commission on Emerging Biotechnology put it directly: the United States tends to play catch-up after critical technologies have already become mainstream. That is a costly posture for biology. We need scientists and research systems that help us investigate what could become possible before it becomes obvious.

EVIDENCE / STATUS
Exact supplied quotation verified against the official NSCEB final report §1.3. The paragraph following the quote in this script is our strategic interpretation.

BEFORE PRESENTING / NEXT EDIT
Recheck against the final demo build; preserve evidence labels.

JUDGING CRITERIA
Problem & Real-World Impact (25)

SOURCES
NSCEB final report, April 2025, §1.3: https://www.biotech.senate.gov/final-report/chapters/chapter-1/section-3/ (accessed 2026-09-06)

## 03 — A biological lead can become a unilateral advantage.

TENTATIVE SCRIPT · 30 seconds
Biology can create asymmetric power: one actor may acquire a consequential capability before others understand it or can prepare. Waiting until a novel bioweapon or other biological risk is demonstrated leaves less time to respond. Reactive measures remain essential, but they are insufficient as our only posture. Our ambition is to reduce that window of unilateral advantage through earlier scientific investigation.

EVIDENCE / STATUS
Team thesis, informed by NSCEB strategic-surprise and foresight discussion. DARPA P3 describes the delay in developing countermeasures after threat identification. The graphic is conceptual; no lead-time savings or threat forecasting accuracy has been measured.

BEFORE PRESENTING / NEXT EDIT
Recheck against the final demo build; preserve evidence labels.

JUDGING CRITERIA
Problem & Real-World Impact (25); DTX audience relevance

SOURCES
NSCEB final report, April 2025, §3.3: https://www.biotech.senate.gov/final-report/chapters/chapter-3/section-3/ (accessed 2026-09-06)
DARPA · Pandemic Prevention Platform: https://www.darpa.mil/research/programs/pandemic-prevention-platform (accessed 2026-09-06)
DTX Ventures · Vision: https://www.dtxventures.com/vision (accessed 2026-09-06)

## 04 — Point compute at the questions that matter.

TENTATIVE SCRIPT · 25 seconds
There are useful connections waiting between existing findings. The hard part is deciding which connections deserve compute, what experiment can test them, and whether its output can be trusted. Our literature graph links claims from papers. Agents explore those links, run analyses with specialized tools and bring the evidence back for review. Pancreatic-cancer research is our initial proving ground.

EVIDENCE / STATUS
The graph motif is conceptual. The PDAC curation contains 100 papers; a curated corpus is not a completed extraction or discovery. An absent graph edge does not establish novelty.

BEFORE PRESENTING / NEXT EDIT
Recheck against the final demo build; preserve evidence labels.

JUDGING CRITERIA
Problem & Real-World Impact (25); Novelty and Importance of AI (25)

SOURCES
Repository: ARCHITECTURE.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed
Repository: demo/pdac/README.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed

## 05 — Make the next experiment a deliberate decision.

TENTATIVE SCRIPT · 25 seconds
Our initial user is a computational biologist with limited experimental capacity. They need direction and an audit trail. That is why the workspace exposes the research tree, the evidence behind a branch and the history of the investigation. This capture is the actual interface populated with browser-test data; the persona is a design hypothesis we still need to validate with users.

EVIDENCE / STATUS
Actual React UI; synthetic fixture. Keyboard focus, reduced motion and light/dark themes implemented. Human review is a backend capability; frontend approval controls remain hidden at the audited snapshot.

BEFORE PRESENTING / NEXT EDIT
Recheck against the final demo build; preserve evidence labels.

JUDGING CRITERIA
Understanding of the User (30); User Experience & Usability (40); Design Quality & Craft (30)

SOURCES
Repository: frontend/DESIGN.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed
Repository: docs/frontend.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed
Repository: presentation/assets/README.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed

## 06 — The graph directs exploration. Experiments constrain it.

TENTATIVE SCRIPT · 35 seconds
This is the full loop. Papers become source-linked claims. Research agents form questions and spawn alternative branches. They write analyses and call domain tools, then the system preserves outputs and screens reported results. A scientist can review the surviving evidence. The engineering goes beyond a chat interface: it includes recursive orchestration, budgets, durable execution, tool-specific data work and statistical components. Screen survival is not biological truth.

EVIDENCE / STATUS
Implemented architecture. Ordinary falsifier checks reported fields and flags; it does not independently rerun arbitrary code. Private evidence adapters and branch monitoring have different contracts and maturity. No qualifying end-to-end later-paper recovery is asserted.

BEFORE PRESENTING / NEXT EDIT
Recheck against the final demo build; preserve evidence labels.

JUDGING CRITERIA
Technical Execution (50); Novelty and Importance of AI (25); Technical Sophistication (50)

SOURCES
Repository: ARCHITECTURE.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed
Repository: docs/runtime.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed
Repository: docs/native-evidence.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed
Repository: docs/branch-monitoring.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed

## 07 — Inspect the image. Check the coordinates.

TENTATIVE SCRIPT · 35 seconds
Start with something tangible. This is our actual molecular workbench. The agent inspected a saved image, requested a cutaway to reduce occlusion, and identified a pair of atoms for a coordinate check. The measured distance was about 2.714 angstroms, a measure of proximity rather than a bonding or efficacy claim. A separate three-seed docking benchmark failed its recovery criterion. The image helps direct inspection; the numerical check constrains the interpretation.

EVIDENCE / STATUS
Actual surface-final.png capture from the scoped inhibitor workflow. The native PowerPoint crop focuses on the scene and omits surrounding controls; source image is unchanged. The recorded canonical O22 N2 / GLN670 OE1 distance is 2.7136221099760567 Å. Three-seed Vina 3VQU/O22 recovery: no pose met the frozen 2 Å RMSD criterion; best-any RMSD was about 2.675 Å. Distance and RMSD are different measurements. No affinity, hydrogen-bond assignment or therapeutic effect is claimed.

BEFORE PRESENTING / NEXT EDIT
Preserve the actual capture and separate the coordinate review from the benchmark. Full source receipts are in the inhibitor review. The binder visual loop and broader 3D tool status are in the appendix.

JUDGING CRITERIA
Technical Execution (50); Technical Sophistication (50); Design Quality & Craft (30)

SOURCES
Repository: docs/inhibitor-review/README.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed
Repository: docs/inhibitor-review/review.json at fee316580ba27951c2ad6fea4bdd4a6b335421ed
Repository: docs/inhibitor-review/benchmark.json at fee316580ba27951c2ad6fea4bdd4a6b335421ed

## 08 — Training is real. Advantage still has to be earned.

TENTATIVE SCRIPT · 35 seconds
We trained representations on real protein, drug-response and single-cell data with explicit splits and comparators. The important result is that the simplest method often won. PCA, a simple linear compression baseline, beat our protein denoiser. The expanded ecosystem study now has 72 donor records and real validation curves; exact PCA still leads external reconstruction. The drug-response model did not beat the mean baseline on the pancreatic subset. These findings tell us what to retain and what not to claim; the appendix contains the measured training histories and held-out comparisons.

EVIDENCE / STATUS
The protein study uses CPTAC data: 219 TRAIN cases, 110 LUAD validation cases and 105 PDAC development cases. The pharmacotype study contains 356 patient-origin groups, split 245 / 40 / 71. The expanded ecosystem study uses 45 training, 11 validation and 16 external donor records across five original studies. Its epithelial definition and cell-weighted metrics differ from the initial Peng/Lin pilot. These are exposed development or test characterizations, not clinical confirmation. No new training was performed for this deck.

BEFORE PRESENTING / NEXT EDIT
Recheck against the final demo build; preserve evidence labels.

JUDGING CRITERIA
Technical Execution (50); AI Technical Sophistication (50); Reliability, Evaluation & Trustworthiness (25)

SOURCES
Repository: docs/protein-training.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed
Repository: docs/pharmacotype-training.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed
Repository: docs/ecosystem-expansion.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed

## 09 — Evidence needs a budget for being wrong.

TENTATIVE SCRIPT · 30 seconds
Our internal e-value tools separate plausible output from statistical evidence. An e-value is an evidence score designed to stay small on average when the stated no-effect assumption is true. In one standalone synthetic audit, the learned method crossed its threshold at least once in 112 of 10,000 null runs—simulated data with no group difference—or 1.12 percent. That is not the false-positive rate of the whole product. The engineering also binds evidence to frozen inputs, prevents duplicate donor consumption within the shared private ledger and preserves replay. Low false-alarm rates alone do not establish useful power or biological validity.

EVIDENCE / STATUS
In expanded-null.json, the learned encoder crossed the threshold at least once in 112 runs. Only 20 runs, or 0.20%, were above the threshold at the end; this is a different metric. The synthetic encoder differs from the real-expression model. The native ledger requires an actual identity boundary: separate processes under the same Unix owner do not provide isolation. Current release gates for adequately powered real-data confirmation remain unmet.

BEFORE PRESENTING / NEXT EDIT
Recheck against the final demo build; preserve evidence labels.

JUDGING CRITERIA
Reliability, Evaluation & Trustworthiness (25); Technical Execution (50)

SOURCES
Repository: research/learned-evalue-validation/expanded-null.json at fee316580ba27951c2ad6fea4bdd4a6b335421ed
Repository: docs/native-evidence.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed

## 10 — Follow one question all the way to a reviewable result.

TENTATIVE SCRIPT · 45 seconds
[After verification] Here is the source claim. The agent identified this specific gap and chose this test because the available data could distinguish the alternatives. This is the code it ran, the result it produced and the check it had to survive. Finally, this is the scientist’s recorded decision. [Before verification] This is the evidence we require before presenting an end-to-end discovery claim.

EVIDENCE / STATUS
This is a prepared storyboard, not a measured investigation. It contains no invented candidate, result, scientist decision or hidden chain of thought. Use concise logged explanations and exact artifacts.

BEFORE PRESENTING / NEXT EDIT
Populate every slot from ONE run. Record its ID, source and date, data hash, code, output, falsifier feedback and human review. Keep failures visible. Enable the sequence only after an independent audit, and save a local recording.

JUDGING CRITERIA
Technical Execution (50); Reliability (25); UX (40)

SOURCES
Repository: plans/PLAN-demo-slides.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed

## 11 — First, show what survived.

TENTATIVE SCRIPT · 20 seconds
[After attaching the actual list] These are the candidates that survived the stated checks. Survival means a candidate merits review under that check’s contract; it does not establish truth or novelty. Let us focus on this one and what its result means. [Pause before advancing to the paper reveal.]

EVIDENCE / STATUS
There is no sourced survivor list yet. The three cards illustrate the layout only. Do not recite a candidate count or claim outcomes until the cards are replaced.

BEFORE PRESENTING / NEXT EDIT
Use the actual survivor count, rejected-branch denominator, named checks and exact run IDs. Select one candidate with a verified match to a later paper, and delete unused cards.

JUDGING CRITERIA
Technical Execution (50); Reliability (25)

SOURCES
Repository: plans/PLAN-demo-slides.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed

## 12 — Then reveal where the candidate leads.

TENTATIVE SCRIPT · 20 seconds
[After verification only] This candidate corresponds to the finding reported in this later paper. [Click; the paper fades in. Pause.] The compelling part is the route from the recorded evidence to that result. The next slide shows exactly what information the run could access, so you can judge what this recovery does—and does not—demonstrate.

EVIDENCE / STATUS
No paper has been selected, verified or presented as recovered. The paper group has a native 800 ms fade. PowerPoint playback is not available locally; the PDF shows the final state. This is not a novel-discovery claim.

BEFORE PRESENTING / NEXT EDIT
Insert the actual paper image while preserving the group entrance effect. Add accessible text, DOI, date and the rationale for the match. Keep the frozen-corpus slide IMMEDIATELY after the reveal. If no run qualifies, leave all four reveal slides hidden.

JUDGING CRITERIA
Technical Execution (50); Originality; Reliability (25)

SOURCES
Repository: plans/PLAN-demo-slides.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed
Repository: demo/pdac/README.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed

## 13 — What could the system actually know?

TENTATIVE SCRIPT · 25 seconds
The corpus was curated from 100 full-text papers published between 2007 and 2025, with an inclusive January 25, 2026 boundary. For this reveal, we must show the exact accessible manifest and demonstrate that the later paper was excluded from the run’s tools and data. Even then, pretrained model memory remains a limitation. Recovering a later published result from restricted evidence would be meaningful; it would not, by itself, prove an uncontaminated new discovery.

EVIDENCE / STATUS
The curation facts are committed. The actual run access boundary and the identity of the later paper remain unverified. The curation cutoff is not automatically a paper-publication-date cutoff for every task; check the manifest’s inclusive boundary.

BEFORE PRESENTING / NEXT EDIT
Keep this slide directly after the paper reveal. Add the actual run ID, frozen manifest hash, access logs, target paper hash and date, cutoff protocol, model version and memory control. Keep the uncertainty visible.

JUDGING CRITERIA
Reliability, Evaluation & Trustworthiness (25); Technical Execution (50)

SOURCES
Repository: demo/pdac/README.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed
Repository: demo/pdac/papers.json at fee316580ba27951c2ad6fea4bdd4a6b335421ed
Repository: plans/PLAN-demo-slides.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed

## 14 — Start with one research team. Earn the right to expand.

TENTATIVE SCRIPT · 30 seconds
The initial company opportunity is a research workflow people can evaluate in a small pilot. Start with one team, approved datasets and a bounded compute budget. Our pricing hypothesis is a workspace subscription plus metered compute, but willingness to pay is untested. The pilot has to measure whether researchers get useful, reproducible experiments and whether the total cost—including failed branches and review time—makes sense.

EVIDENCE / STATUS
This is a deployment and business proposal, not evidence of traction. Price the full investigation: LLM calls, GPU and CPU work, storage, egress and human review. Unit economics for a complete investigation have not been measured.

BEFORE PRESENTING / NEXT EDIT
Recheck against the final demo build; preserve evidence labels.

JUDGING CRITERIA
Feasibility & Deployment Potential (25)

SOURCES
Repository: docs/deployment.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed
Repository: docs/runtime.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed
Repository: plans/backlog.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed

## 15 — The next milestone is proof that survives outside the demo.

TENTATIVE SCRIPT · 25 seconds
There are three concrete deployment gates. First, independently reproduce a bounded investigation against strong alternatives. Second, harden a private pilot with real identity boundaries, restricted data access and execution, reliable logs and spend limits. Third, validate the workflow with researchers. Research use is the starting scope; clinical decisions or operational threat forecasting would need additional evidence, governance and regulatory review.

EVIDENCE / STATUS
These are proposed milestones. A separate process under the same Unix owner does not isolate private data. Data licenses, PHI and data agreements, SSO, tenancy, sandboxing and integration need review before broader deployment. No clinical regulatory clearance is implied.

BEFORE PRESENTING / NEXT EDIT
Recheck against the final demo build; preserve evidence labels.

JUDGING CRITERIA
Feasibility & Deployment Potential (25); Reliability (25); Understanding of User (30)

SOURCES
Repository: docs/deployment.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed
Repository: docs/native-evidence.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed
Repository: plans/backlog.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed

## 16 — Give scientists a head start.

TENTATIVE SCRIPT · 25 seconds
Biology will help shape industrial strength, health and security. We want scientists to have more lead time to understand what comes next. We have built the beginnings of an inspectable research engine and tested substantive parts of its toolkit. The next step is a bounded research partnership that can independently judge its usefulness. Our ambition is to reduce the window of unilateral biological advantage.

EVIDENCE / STATUS
This is a strategic ambition and a request for a pilot. It does not imply guaranteed prediction, deployment outcomes or an existing customer partnership. The closing art is conceptual. Alignment with DTX is our inference from its critical-technology thesis.

BEFORE PRESENTING / NEXT EDIT
Recheck against the final demo build; preserve evidence labels.

JUDGING CRITERIA
Problem & Real-World Impact (25); Feasibility (25)

SOURCES
DTX Ventures · Vision: https://www.dtxventures.com/vision (accessed 2026-09-06)
NSCEB final report, April 2025, §3.3: https://www.biotech.senate.gov/final-report/chapters/chapter-3/section-3/ (accessed 2026-09-06)
Repository: presentation/assets/v2/README.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed

## 17 — Every judging criterion has an evidence trail.

TENTATIVE SCRIPT · 25 seconds
The presentation gives the largest share of technical discussion to execution and AI sophistication, matching the fifty-point weights. We connect the problem to strategic lead time, show actual artifacts and negative results, and state deployment and user-validation gaps directly. The slide references here let us answer each rubric question with evidence instead of adjectives.

EVIDENCE / STATUS
The rubric was supplied by the user. The weights and slide references reflect that rubric. No scores have been self-awarded.

BEFORE PRESENTING / NEXT EDIT
Recheck against the final demo build; preserve evidence labels.

JUDGING CRITERIA
All supplied criteria

SOURCES
Repository: plans/PLAN-demo-slides.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed

## 18 — A useful view makes a hidden problem visible.

TENTATIVE SCRIPT · 25 seconds
A binder is a protein designed to attach to a target. This is a concrete design decision driven by the user’s task. A complete structure is good for orientation, but it can hide the interface. A contact-only cutaway and opposing view expose the region the scientist needs to inspect. The visual review caught a camera-preset bug that a screenshot test initially missed. Labels, reproducible camera state and coordinate checks make the image useful rather than decorative.

EVIDENCE / STATUS
The scene uses an illustrative 1CRN fixture. The recorded raycast captured 19 / 20 contact residues in the primary view, 18 / 20 in the reverse view and 20 / 20 across both views. These counts do not measure binding affinity. The UI inspection notes record actual iterations and fit at a 390 px mobile width.

BEFORE PRESENTING / NEXT EDIT
Recheck against the final demo build; preserve evidence labels.

JUDGING CRITERIA
Design Quality & Craft (30); UX (40); Understanding of User (30)

SOURCES
Repository: docs/binder-review/README.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed
Repository: docs/binder-review/scene-replay-interface-close.json at fee316580ba27951c2ad6fea4bdd4a6b335421ed

## 19 — What we trained—and what we did not.

TENTATIVE SCRIPT · 30 seconds
The trained components have different jobs. The expression model learns a representation, while the sequential bettor scores fresh paired observations. Protein, drug-response and ecosystem modules learn representations or prediction functions under their own split contracts. The branch monitor is different: it is intended to estimate a research branch’s future usefulness, but has not been fitted and calibrated on real trajectories. We do not count renderers or pretrained dependencies as models we trained.

EVIDENCE / STATUS
The following slides give each model’s data and splits. Training a model does not establish useful power or real biological confirmation. Biological evidence and branch-monitor statistics answer different questions and must remain distinct.

BEFORE PRESENTING / NEXT EDIT
Recheck against the final demo build; preserve evidence labels.

JUDGING CRITERIA
AI Technical Sophistication (50); Reliability (25)

SOURCES
Repository: research/learned-evalue-validation/real-expression/README.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed
Repository: docs/protein-training.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed
Repository: docs/pharmacotype-training.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed
Repository: docs/ecosystem-training.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed
Repository: docs/branch-monitoring.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed

## 20 — A measured training curve. A separate evidence trajectory.

TENTATIVE SCRIPT · 35 seconds
This expression diagnostic uses 374 day-zero donors: 149 for training, 74 for development and 151 for evaluation. We trained a masked autoencoder on genes selected from the training data for 100 epochs. The plotted loss is training loss; we did not retain a held-out loss at every epoch. The evidence plot measures something different: evidence from 30 selected evaluation pairs, of which 22 are scored after burn-in. The IFIT3 single-gene baseline finishes with more evidence than the learned representation.

EVIDENCE / STATUS
The source is TPM data from GSE212041. TRAIN contains 119 positive and 30 negative donors; DEV contains 59 positive and 15 negative donors; EVAL contains 121 positive and 30 negative donors. The 30 selected pairs are not clinical matches, and 91 positive evaluation donors are unused. The encoder is 19k → 512 → 128, fitted with Adam at .001 and seed 20260905. The bettor has 64 / 64 ReLU layers and maximizes log payoff using past data. It uses 4 pairs per batch, 2 burn-in batches, at most 100 epochs per update, patience 10, learning rate .0005 and weight decay .01. Final evidence is 3652.81 for the learned encoder, 85.76 for PCA and 5964.41 for IFIT3. This is not an independent estimate of clinical power.

BEFORE PRESENTING / NEXT EDIT
Recheck against the final demo build; preserve evidence labels.

JUDGING CRITERIA
AI Technical Sophistication (50); Reliability (25)

SOURCES
Repository: research/learned-evalue-validation/real-expression/README.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed
Repository: research/learned-evalue-validation/real-expression/training.json at fee316580ba27951c2ad6fea4bdd4a6b335421ed
Repository: research/learned-evalue-validation/real-expression/evaluation.json at fee316580ba27951c2ad6fea4bdd4a6b335421ed

## 21 — The protein baseline won the held-out reconstruction test.

TENTATIVE SCRIPT · 30 seconds
The protein model trains on 219 breast and colon tumors and is selected using 110 lung tumors. Values and missingness masks feed a denoiser with a 32-dimensional bottleneck. On frozen hidden entries, PCA’s mean squared error is 1.8243, compared with 2.1067 for the denoiser and 2.9318 for mean fill. The selected denoiser checkpoint is at the 50-epoch budget boundary, so we do not claim convergence. These results support retaining strong, simple comparators.

EVIDENCE / STATUS
The study selects 2,000 features using TRAIN coverage. Values and masks form 4000 inputs. Training uses AdamW at .001, batch size 32 and seed 0. The PDAC development set contains 105 cases, of which 104 are graded. Grade AUROC is .7816 for rank-PCA and .6262 for the denoiser; this is exposed development. Complete local artifacts for curated v2 are absent from this checkout; chart values come from committed documentation. Slide 28 presents the subsequent external benchmark with its own aggregate audit.

BEFORE PRESENTING / NEXT EDIT
Recheck against the final demo build; preserve evidence labels.

JUDGING CRITERIA
AI Technical Sophistication (50); Reliability (25)

SOURCES
Repository: docs/protein-training.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed
Repository: src/dnhacksbio/protein_encoder.py at fee316580ba27951c2ad6fea4bdd4a6b335421ed

## 22 — Two real datasets. Two limits on the claim.

TENTATIVE SCRIPT · 35 seconds
The PRISM task predicts adjusted log2 fold-change versus solvent control from molecular features, using 245 training, 40 validation and 71 test patient-origin groups. PCA is selected by mean validation error across three seeds; it does not beat the mean baseline in the pancreatic test subset. A separate 38-donor patient-derived organoid dataset measures aggregate response area. Its five-donor validation split favors the training mean over every learned method. This does not establish a successful predictor of full response curves or biological confirmation.

EVIDENCE / STATUS
PRISM covers 4 drugs at 8 doses and a 120 h exposure. Feature selection uses 1000 training genes. The compared representations are identity, PCA with 32 dimensions and one-layer tanh autoencoders with 15% masking, at most 150 epochs and patience 15. The ridge penalty is 10. A bounded bilinear critic uses an MSE objective on matched versus crossed views; molecular and response encoders train separately. The PDO split is 21 TRAIN / 5 VAL / 12 TEST. Its AUC target is one normalized area-under-response-curve value per drug, not a full dose-response curve. The CUDA fits were run, but epoch histories were not retained. Subsequent training-only RBF tuning achieved validation RMSE 0.1703 versus the mean baseline 0.1562; its improvement on an already exposed test set is not independent confirmation. Adaptive synthetic critic diagnostics show 35.52% power for the simple alternative and 0% for the nonlinear alternative. Release eligibility remains false.

BEFORE PRESENTING / NEXT EDIT
Recheck against the final demo build; preserve evidence labels.

JUDGING CRITERIA
AI Technical Sophistication (50); Reliability (25)

SOURCES
Repository: docs/pharmacotype-cuda-training.json at fee316580ba27951c2ad6fea4bdd4a6b335421ed
Repository: docs/pharmacotype-pdo-auc.json at fee316580ba27951c2ad6fea4bdd4a6b335421ed
Repository: docs/pharmacotype-training.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed
Repository: docs/pharmacotype-adaptive-validation.json at fee316580ba27951c2ad6fea4bdd4a6b335421ed
Repository: docs/pharmacotype-tuning.json at fee316580ba27951c2ad6fea4bdd4a6b335421ed

## 23 — Represent the cells. Keep the donor as the unit of evidence.

TENTATIVE SCRIPT · 35 seconds
Single-cell datasets contain many cells, but cells from one person are not independent donors. We trained separate representations for malignant-enriched and fibroblast compartments, using equal samples of 32 cells per eligible training donor. The count model uses a negative-binomial reconstruction objective. A separate set model tries to preserve donor summaries and stability across subsamples. Cell PCA wins the current reconstruction comparisons on the Peng holdout and Lin external development data. Missing compartments reduce the actual donor coverage.

EVIDENCE / STATUS
Peng donors T1–T16 form TRAIN; T17–T24 form DEV. Lin contributes 10 primary donors for external development. Actual training uses 512 malignant-enriched cells from 16 donors and 416 fibroblast cells from 13 donors. Peng has 8 eligible malignant-enriched and 5 eligible fibroblast held-out donors; Lin has 7 and 9 respectively. Both compartments are available in 5 Peng and 6 Lin donors. The negative-binomial model is 2000 → 32 tanh → 2001, trained for 20 CPU epochs with a library offset and learned dispersion. The set model is 32 → 8 tanh, followed by mean pooling and a 64-dimensional summary decoder. It trains for 20 epochs with Adam at .01, using reconstruction plus .1 times the stability loss. No held-out neural advantage or private biological confirmation was established.

BEFORE PRESENTING / NEXT EDIT
Recheck against the final demo build; preserve evidence labels.

JUDGING CRITERIA
AI Technical Sophistication (50); Reliability (25)

SOURCES
Repository: docs/ecosystem-training.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed
Repository: docs/ecosystem-training/metrics.json at fee316580ba27951c2ad6fea4bdd4a6b335421ed
Repository: docs/ecosystem-training/set-metrics.json at fee316580ba27951c2ad6fea4bdd4a6b335421ed

## 24 — Biological evidence and branch monitoring answer different questions.

TENTATIVE SCRIPT · 35 seconds
The internal evidence tools test specified measured relationships. The branch monitor asks a different question: whether continuing a research branch is likely to produce a qualifying result under a fixed policy and budget. Its design uses one logistic model per prefix and root-group-disjoint training, calibration and test splits. That implementation has not yet been trained or calibrated on real trajectories. We must not present its synthetic tests as a deployed statistical stopping guarantee.

EVIDENCE / STATUS
The proposed branch labeler uses an LLM assessor rubric after a legacy CANDIDATE result; its label is a proxy, not expert truth or independent reproduction. The monitor uses class-prior-corrected odds and history ratios, with weights for roots and episodes. At alpha .045 and delta .005, the first finite order-statistic threshold requires 116 independent successful calibration episodes; 115 are insufficient. Repeated checkpoints are not independent episodes. The operational limits of 3600 summed seconds and 288 actions are not a statistical deadline.

BEFORE PRESENTING / NEXT EDIT
Recheck against the final demo build; preserve evidence labels.

JUDGING CRITERIA
AI Technical Sophistication (50); Reliability (25)

SOURCES
Repository: docs/branch-monitoring.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed
Repository: docs/dependency-scoring.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed
Repository: docs/drug-response-scoring.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed
Repository: docs/expression-scoring.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed

## 25 — The differentiation has to be demonstrated.

TENTATIVE SCRIPT · 30 seconds
Existing research agents are substantive systems, so being an AI researcher is not enough of a differentiator. Our proposed wedge is executable, inspectable investigation with specialized tools and explicit evidence contracts. The right test is an equal-budget comparison against a strong single agent and flat parallel research. We should measure independently rerunnable useful work, not the number of generated hypotheses. A defensible product advantage remains to be earned.

EVIDENCE / STATUS
The primary prior-art pages were verified; no head-to-head comparison has been run. The project reuses open-source scientific tools and renderers. The novelty claim concerns engineering integration and the proposed workflow, not new foundational statistics or the first AI scientist.

BEFORE PRESENTING / NEXT EDIT
Recheck against the final demo build; preserve evidence labels.

JUDGING CRITERIA
Technical Execution originality (50); AI Novelty (25); Feasibility (25)

SOURCES
Elicit · Introducing Elicit Research Agent: https://elicit.com/blog/introducing-elicit-research-agent (accessed 2026-09-06)
Google DeepMind · Co-scientist: https://deepmind.google/blog/co-scientist-a-multi-agent-ai-partner-to-accelerate-research/ (accessed 2026-09-06)
Repository: plans/backlog.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed

## 26 — What a pilot must settle.

TENTATIVE SCRIPT · 30 seconds
For deployment, we need the total cost of a complete investigation, not just a cheap encoder fit. We need actual security boundaries, approved data access, restricted execution and an audit path that fits the customer’s workflow. Research use is the initial scope; privacy, licensing and any later clinical application require their own review. The current evidence supports a technically substantive prototype, while discovery recovery, customer value and production readiness still need proof.

EVIDENCE / STATUS
This evidence ledger describes the audited snapshot. Update it when newly merged work supplies source artifacts. Main-build tests check code behavior; they do not establish clinical or statistical validity. No TAM, customer logos, savings or regulatory clearance have been invented.

BEFORE PRESENTING / NEXT EDIT
Recheck against the final demo build; preserve evidence labels.

JUDGING CRITERIA
Feasibility & Deployment Potential (25); Reliability (25)

SOURCES
Repository: docs/deployment.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed
Repository: docs/native-evidence.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed
Repository: presentation/validation.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed

## 27 — Every 3D tool keeps its own evidence boundary.

TENTATIVE SCRIPT · 30 seconds
The binder workbench demonstrates a recorded visual loop, but its current showcased geometry is illustrative. Molecular tools now run scoped preparation and docking as well as image review and coordinate checks. Their three-seed recovery benchmark did not pass; no inhibition or efficacy is established. The spindle worker runs pinned native mechanics and exports real three-dimensional frames; biological calibration is still ahead. Tumor–stroma simulation and further image integrations are active work and should be upgraded in this deck only with their actual artifacts.

EVIDENCE / STATUS
Snapshot-specific status. Binder: no BindCraft inference demonstrated. Inhibitor: scoped docking and image-review workflow is merged; the frozen recovery result is negative. Spindle pilot uses stock aster_dynamic, shortened to 100 time steps, seed 41, 11 exported frames. Tissue development is separate from the measured statistical cellular-ecosystem module.

BEFORE PRESENTING / NEXT EDIT
When new work lands, replace this status with scoped run IDs, native receipts, actual images and numerical controls. Do not reuse an illustrative image as evidence of a measured biological result.

JUDGING CRITERIA
Technical Execution (50); AI Technical Sophistication (50); Design Quality (30)

SOURCES
Repository: docs/binder-review/README.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed
Repository: docs/inhibitor-workbench.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed
Repository: docs/spindle-build-pilot.json at fee316580ba27951c2ad6fea4bdd4a6b335421ed
Repository: plans/3d-experiment-tools/03-tumor-stroma.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed

## 28 — External data changed the conclusion.

TENTATIVE SCRIPT · 35 seconds
The larger Fudan benchmark includes 224 graded tumors. All five views were specified before scores were inspected. The primary rank-PCA model achieved an AUROC of 0.552, showing weak transfer. A prespecified secondary kernel achieved 0.694, but its source-fixed classification threshold gave only about 0.553 balanced accuracy. That is a follow-up ranking signal, not a validated grade classifier or independent sequential confirmation. The important result is that external data changed what we could responsibly claim.

EVIDENCE / STATUS
Source: protein-external-results.json. Primary rank-PCA AUROC 0.55249, 95% stratified bootstrap interval 0.47141–0.63377. Secondary RBF rank kernel 0.69376, interval 0.625–0.764; use the JSON for exact values. 224 graded tumors: 159 G3 and 65 G2, allowing 65 possible grade pairs. Reference-normalized CPTAC and label-free Fudan are different assays; cohort-wide processing prevents untouched-confirmation claims. PCA used 219 non-PDAC training cases; supervised balanced ridge heads used 104 CPTAC grades, penalty 1. RBF gamma was 1/feature-count. No external-label model tuning was performed.

BEFORE PRESENTING / NEXT EDIT
Keep all five prespecified views and sensitivity analyses available. Do not promote the secondary result to the primary result, select a threshold using external labels or describe this as a qualifying discovery-paper recovery.

JUDGING CRITERIA
Technical Execution (50); AI Technical Sophistication (50); Reliability (25)

SOURCES
Repository: docs/protein-external.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed
Repository: docs/protein-external-results.json at fee316580ba27951c2ad6fea4bdd4a6b335421ed
Repository: docs/protein-external-training.json at fee316580ba27951c2ad6fea4bdd4a6b335421ed
Repository: docs/protein-external-audit.json at fee316580ba27951c2ad6fea4bdd4a6b335421ed

## 29 — Real validation curves. PCA still leads externally.

TENTATIVE SCRIPT · 35 seconds
The expanded study now covers 72 donor records across five original studies: 45 for training, 11 for validation and 16 in external studies. These are the actual training and validation histories for the epithelial models, with all three seeds shown. The full record also contains fibroblast histories. Denoising training improves substantially, but exact PCA remains the stronger external reconstruction baseline. This is measured development work, not biological confirmation.

EVIDENCE / STATUS
Source fee3165: 338,900 prepared cells; a per-donor loading cap leaves 313,518. Separate epithelial/fibroblast denoising and negative-binomial encoders use 2,625 genes, width 256, latent size 64, 15% masking, up to 200 epochs and validation patience 35, seeds 2701–2703. The three-seed L40S run took 299 seconds with 10.8 GB peak allocation, excluding preceding pilot and later exact-PCA refresh. External MSE: exact PCA .28736/.23721, denoiser seed mean .29187/.24350, NB .36698/.29949 for epithelial/fibroblast. Epithelial denoising narrowly wins validation .20177 vs PCA .20197, so do not say PCA wins every validation comparison. Two NB fits select epoch 200; no blanket convergence claim. New epithelial definitions and cell-weighted metrics differ from the initial pilot. Seed variation is not donor uncertainty.

BEFORE PRESENTING / NEXT EDIT
Native PowerPoint crop shows the top two panels of the unchanged original figure. Complete four-panel PNG/PDF is docs/ecosystem-expansion/training-curves.*. Also review held-out-comparison.*, lineage-curves.* and association-controls.*. Lineage accuracy drops from 97.0% validation to 77.9% external Lin; donor-matching neural AUROC .647–.683 trails bilinear .692 on only 20 held-out donors.

JUDGING CRITERIA
AI Technical Sophistication (50); Reliability (25); Technical Execution (50)

SOURCES
Repository: docs/ecosystem-expansion.md at fee316580ba27951c2ad6fea4bdd4a6b335421ed
Repository: docs/ecosystem-expansion/metrics.json at fee316580ba27951c2ad6fea4bdd4a6b335421ed
Repository: docs/ecosystem-expansion/training-curves.pdf at fee316580ba27951c2ad6fea4bdd4a6b335421ed
