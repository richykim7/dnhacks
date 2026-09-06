# Tentative speaking script

Core slides 1–11: approximately five minutes, including a 55-second demo slot. Appendices 12–17 are for Q&A.

## 01 — Point compute at the next scientific discovery.

TENTATIVE SCRIPT · 25 seconds
A useful discovery can start with a connection between papers that nobody has tested together. DN Research is our working name for an engine that finds research directions, writes analyses against public data, and keeps the evidence inspectable. Our ambition is to turn more of the science we already have into experiments worth running.

EVIDENCE / STATUS
Working name; prototype. No confirmed new biological discovery or performance improvement is claimed.

BEFORE PRESENTING / NEXT EDIT
Replace DN Research after the team selects a product name. Open Category is proposed because the official event describes it as the DTX-sponsored home for cross-cutting technology; this is not a submitted category claim. Confirm the team's entered track. Keep the visual system. Core slides 1–11 target about five minutes, including the demo.

JUDGING CRITERIA
Problem & Real-World Impact; Novelty and Importance of AI

SOURCES
Repository: ARCHITECTURE.md at 1e83cfb158dd1c9d35894e05006bd9482a566233
Repository: frontend/DESIGN.md at 1e83cfb158dd1c9d35894e05006bd9482a566233

## 02 — Science is abundant. The next experiment is scarce.

TENTATIVE SCRIPT · 25 seconds
PubMed contains more than forty million citations and abstracts. Finding documents is only the beginning. A researcher still has to connect their claims, choose a tractable question, find the right data and check the result. We are building for that decision: what deserves the next unit of scientific effort?

EVIDENCE / STATUS
PubMed scale is an external fact. Workflow bottleneck is our product hypothesis, not a measured user-study finding.

BEFORE PRESENTING / NEXT EDIT
Recheck against the final demo build; preserve evidence labels.

JUDGING CRITERIA
Problem & Real-World Impact (25)

SOURCES
NIH / NLM · About PubMed: https://pubmed.ncbi.nlm.nih.gov/about/ (accessed 2026-09-06)

## 03 — Built around a scientist’s next decision.

TENTATIVE SCRIPT · 25 seconds
Our initial user is a computational biologist on a small oncology team. They need to decide where scarce experimental time should go. That drives the interface: a research tree for direction, source passages and code for scrutiny, and visible uncertainty. This is a working persona; interviews and usability measurements are still ahead.

EVIDENCE / STATUS
Persona is proposed, not based on completed interviews. UI design choices and accessibility features exist. Human approval controls are currently hidden in the frontend.

BEFORE PRESENTING / NEXT EDIT
Recheck against the final demo build; preserve evidence labels.

JUDGING CRITERIA
Understanding of the User (30); User Experience & Usability (40); Design Quality & Craft (30)

SOURCES
Repository: frontend/DESIGN.md at 1e83cfb158dd1c9d35894e05006bd9482a566233
Repository: docs/frontend.md at 1e83cfb158dd1c9d35894e05006bd9482a566233

## 04 — A research loop with evidence at every step.

TENTATIVE SCRIPT · 30 seconds
Here is the system. A knowledge graph connects scientific claims to their sources and context. The agent explores those relationships, writes and runs Python analyses, and submits the result. A deterministic screen can send it back to retry or reframe. A human decision, with a written note, is required before promotion into the accepted graph.

EVIDENCE / STATUS
Integrated architecture exists. The current screen validates reported statistics; it does not independently reproduce the analysis. Backend human-review API exists; frontend review controls are hidden.

BEFORE PRESENTING / NEXT EDIT
Recheck against the final demo build; preserve evidence labels.

JUDGING CRITERIA
Technical Execution (50); AI Technical Sophistication (50); Reliability, Evaluation & Trustworthiness (25)

SOURCES
Repository: ARCHITECTURE.md at 1e83cfb158dd1c9d35894e05006bd9482a566233
Repository: src/dnhacksbio/litmap/promote.py at 1e83cfb158dd1c9d35894e05006bd9482a566233
Repository: src/dnhacksbio/explorer/verifyqueue.py at 1e83cfb158dd1c9d35894e05006bd9482a566233

## 05 — The engineering is in how the loop behaves.

TENTATIVE SCRIPT · 30 seconds
AI is fundamental to interpreting papers, proposing connections and writing task-specific analyses. Our engineering makes that work inspectable: grounded claim identities, explicit actions, and durable branch control. Children report their findings; a parent chooses what continues. A restart preserves the decisions and artifacts. This is the behavior we can demonstrate and evaluate.

EVIDENCE / STATUS
Existing implementation: multi-pass extraction and identifier grounding, explicit actions, child reporting/parent decisions, immutable artifacts and ordered runtime events. Fork means split into research branches. Model roles: Opus reads papers, Sonnet checks direction and repairs extraction, MiniLM supports retrieval; no claim that this selection beats alternatives. No first-of-kind or measured superior allocation claim.

BEFORE PRESENTING / NEXT EDIT
Recheck against the final demo build; preserve evidence labels.

JUDGING CRITERIA
Novelty and Importance of AI (25); AI Technical Sophistication (50); Technical Execution (50)

SOURCES
Repository: src/dnhacksbio/litmap/extract.py at 1e83cfb158dd1c9d35894e05006bd9482a566233
Repository: src/dnhacksbio/litmap/grounding.py at 1e83cfb158dd1c9d35894e05006bd9482a566233
Repository: src/dnhacksbio/explorer/control.py at 1e83cfb158dd1c9d35894e05006bd9482a566233
Repository: src/dnhacksbio/explorer/runtime.py at 1e83cfb158dd1c9d35894e05006bd9482a566233
Repository: src/dnhacksbio/llm.py at 1e83cfb158dd1c9d35894e05006bd9482a566233

## 06 — One question. An inspectable trail.

TENTATIVE SCRIPT · 55 seconds
For the final demo, follow one pancreatic-cancer question through its source, hypothesis, code, result and feedback. We have a curated set of one hundred full-text papers with provenance. This current capture demonstrates the working interface using a synthetic test fixture; it is not a discovery result. Replace it with the recorded scientific investigation as soon as that run is ready.

EVIDENCE / STATUS
Screenshot: actual React app rendered by frontend/e2e tests with synthetic data, not a PDAC run. 100-paper corpus is real curation metadata; indexing does not imply completed claim extraction. Pancreatic cancer overall has 13.7% five-year relative survival in SEER 2016–2022; reserve that statistic for Q&A if useful and never imply prototype benefit.

BEFORE PRESENTING / NEXT EDIT
CRITICAL REPLACEMENT: choose a real run and record 45–60 seconds. Open exact source; select branch; show code and structured result; show rejection/candidate feedback. Do not promise visible human-review buttons. Keep local video or screenshots as fallback; never label a fixture as real.

JUDGING CRITERIA
Technical Execution (prototype works and polish); UX & Usability; Real-World Impact

SOURCES
Repository: demo/pdac/README.md at 1e83cfb158dd1c9d35894e05006bd9482a566233
Repository: frontend/e2e/workspace.spec.ts at 1e83cfb158dd1c9d35894e05006bd9482a566233
Repository: docs/frontend.md at 1e83cfb158dd1c9d35894e05006bd9482a566233
NCI SEER · Pancreatic Cancer Stat Facts: https://seer.cancer.gov/statfacts/html/pancreas.html (accessed 2026-09-06)

## 07 — A plausible result must survive scrutiny.

TENTATIVE SCRIPT · 25 seconds
Trust has three layers: what the source actually said, what the implemented numerical checks accept, and what a scientist concludes. The screen can reject a malformed result or one that contradicts its predicted direction. It still reads reported statistics. Independent reruns and confirmation remain necessary; a candidate is not a confirmed discovery.

EVIDENCE / STATUS
Ordinary falsifier checks fields, finite effect, n_units ≥ 8, p in (0,1], expected direction, p ≤ .05 and reported robust flag. This is not proof of independence, correct analysis or family-wide error control.

BEFORE PRESENTING / NEXT EDIT
Recheck against the final demo build; preserve evidence labels.

JUDGING CRITERIA
Reliability, Evaluation & Trustworthiness (25); Technical Execution (50)

SOURCES
Repository: src/dnhacksbio/falsifier.py at 1e83cfb158dd1c9d35894e05006bd9482a566233
Repository: src/dnhacksbio/methods.py at 1e83cfb158dd1c9d35894e05006bd9482a566233
Repository: src/dnhacksbio/litmap/promote.py at 1e83cfb158dd1c9d35894e05006bd9482a566233

## 08 — We test the trust layer, too.

TENTATIVE SCRIPT · 30 seconds
We also built a separate learned statistical diagnostic and evaluated its failure behavior. In ten thousand synthetic runs with no group difference, the learned-encoder version crossed its evidence threshold in one point one two percent of runs. Training data and scoring units are separated. This is a concrete component test, not end-to-end discovery accuracy or a deployed guarantee.

EVIDENCE / STATUS
Read directly from expanded-null.json: 112/10,000 ever crossings, Wilson 95% CI .93–1.35%; final rejections 20/10,000=.20%. Each repetition 96 independent synthetic pairs, 16 burn-in pairs; frozen synthetic encoder from separate 256-row training set. Ordinary fixed-horizon permutation rejects 513/10,000=5.13%; this is compatible with nominal 5%, not evidence it is unreliable. Invalid label-memorizing control rejects 10,000/10,000. All methods in appendix. Statistical diagnostic is separate from live falsifier.

BEFORE PRESENTING / NEXT EDIT
Keep synthetic, standalone and ever-crossing labels. Earlier paragraph in validation README says 10,000 runs not yet run; its later expanded section and JSON supersede that historical pilot statement. Do not imply broad 1.12% product false-positive rate.

JUDGING CRITERIA
AI Technical Sophistication (50); Reliability, Evaluation & Trustworthiness (25)

SOURCES
Repository: research/learned-evalue-validation/expanded-null.json at 1e83cfb158dd1c9d35894e05006bd9482a566233
Repository: research/learned-evalue-validation/README.md at 1e83cfb158dd1c9d35894e05006bd9482a566233
Repository: src/dnhacksbio/learned_evalue.py at 1e83cfb158dd1c9d35894e05006bd9482a566233

## 09 — Start with one team and one research decision.

TENTATIVE SCRIPT · 25 seconds
Our first commercial hypothesis is a private research workspace for an oncology team, with compute metered by use. The buyer is the research lead who owns prioritization. A pilot should answer three questions: can another analyst reproduce the output, does the scientist find it useful, and what does each reviewed candidate cost? We have not measured those outcomes yet.

EVIDENCE / STATUS
Proposed buyer and commercial model, no customer validation. Existing localhost research service is not production hardened. Cost formula and deployment blockers appear in appendix.

BEFORE PRESENTING / NEXT EDIT
Recheck against the final demo build; preserve evidence labels.

JUDGING CRITERIA
Feasibility & Deployment Potential (25); Understanding of the User (30)

SOURCES
Repository: docs/frontend.md at 1e83cfb158dd1c9d35894e05006bd9482a566233
Repository: docs/runtime.md at 1e83cfb158dd1c9d35894e05006bd9482a566233
Repository: plans/backlog.md at 1e83cfb158dd1c9d35894e05006bd9482a566233

## 10 — A focused prototype. A credible path forward.

TENTATIVE SCRIPT · 25 seconds
Today we have the inspectable research engine and separate statistical tooling. Next comes the evidence that matters: a real recorded pancreatic-cancer investigation, independent reruns and a matched-budget pilot. The plans extend into learned biological tests and three-dimensional experiment workbenches. We will add those capabilities against explicit validation milestones.

EVIDENCE / STATUS
Three learned tool plans are planning-only: protein/phosphosignaling, pharmacotype association and donor-level cellular ecosystems. Existing private expression/dependency/drug-response scoring is distinct from these future learned tools. New 3D plans cover inhibitor workbench, binder design, tumor-stroma and spindle simulation, with explicit reference/prediction/simulation/illustration provenance. They are not implemented tools or existing biological results. Real trajectory training and calibrated stopping are deferred.

BEFORE PRESENTING / NEXT EDIT
Recheck against the final demo build; preserve evidence labels.

JUDGING CRITERIA
Feasibility & Deployment Potential (25); Technical Execution (50)

SOURCES
Repository: plans/evalue-tool-council/README.md at 1e83cfb158dd1c9d35894e05006bd9482a566233
Repository: plans/evalue-tool-council/native-evidence-contract.md at 1e83cfb158dd1c9d35894e05006bd9482a566233
Repository: docs/branch-monitoring.md at 1e83cfb158dd1c9d35894e05006bd9482a566233
Repository: plans/3d-experiment-tools/README.md at 1e83cfb158dd1c9d35894e05006bd9482a566233

## 11 — More useful science from every dollar of compute.

TENTATIVE SCRIPT · 20 seconds
Scientific advantage depends on turning knowledge into evidence we can act on. We want to build infrastructure that helps American research teams do more useful science with their compute. Our next milestone is concrete: one independently reproduced, expert-reviewed candidate, with the full path from its source to the result.

EVIDENCE / STATUS
Ambition, not measured dollar efficiency. DTX vision emphasizes U.S. leadership across critical technologies including health. This is our audience-fit inference, not DTX endorsement.

BEFORE PRESENTING / NEXT EDIT
End the short pitch here and take questions. If a verified result lands, replace next milestone with that result and its precise scope. Add agreed team names/contact only after supplied.

JUDGING CRITERIA
Problem & Real-World Impact; Feasibility & Deployment Potential

SOURCES
DTX Ventures · Vision: https://www.dtxventures.com/vision (accessed 2026-09-06)
DNHacks · Official event and category descriptions: https://dnhacks.org/ (accessed 2026-09-06)

## 12 — Judging criterion map.

TENTATIVE SCRIPT · 20 seconds
The core story is deliberately weighted toward engineering, which accounts for half the main score and half the AI award. The supporting slides make the evidence, deployment assumptions and user decisions easy to inspect.

EVIDENCE / STATUS
All nine rubric items and weights match the user-provided rubric.

BEFORE PRESENTING / NEXT EDIT
Recheck against the final demo build; preserve evidence labels.

JUDGING CRITERIA
All criteria

SOURCES
DNHacks · Official event and category descriptions: https://dnhacks.org/ (accessed 2026-09-06)

## 13 — Current-state ledger.

TENTATIVE SCRIPT · 25 seconds
These status labels separate implementation from data preparation and scientific validation. A frozen corpus is useful infrastructure, but it does not exclude model memory or prove a blind discovery. A working statistical module also does not establish that the full research loop finds better hypotheses.

EVIDENCE / STATUS
Claim ledger reconciles current code with plans. Older forecasting materials and historical validation-pilot statements were not reused as current proof.

BEFORE PRESENTING / NEXT EDIT
Recheck against the final demo build; preserve evidence labels.

JUDGING CRITERIA
Technical Execution; Reliability & Trustworthiness

SOURCES
Repository: ARCHITECTURE.md at 1e83cfb158dd1c9d35894e05006bd9482a566233
Repository: demo/pdac/README.md at 1e83cfb158dd1c9d35894e05006bd9482a566233
Repository: research/learned-evalue-validation/README.md at 1e83cfb158dd1c9d35894e05006bd9482a566233

## 14 — Statistical evidence has a declared scope.

TENTATIVE SCRIPT · 35 seconds
The full comparison matters. A simpler single-feature method can outperform learned features on a particular task. Our real-data example uses a separate observational COVID expression cohort and the same thirty evaluation pairs for each method. It is a diagnostic engineering result, not cancer validation, causality or universal model superiority.

EVIDENCE / STATUS
Synthetic table read directly from expanded-null.json. Threshold 20; alpha .05. Permutation comparators have one fixed-horizon decision. Real final e-values: learned3652.81, PCA85.76, IFIT3 scalar5964.41, calibrated permutation99.00. 374 unique day-zero donors split 40/20/40; the same 30 selected evaluation pairs with 91 positive evaluation donors unused. Different representation widths; not an equal-width architecture ablation. Clinical labels not randomized. E-values must not be multiplied across dependent/reused data.

BEFORE PRESENTING / NEXT EDIT
Recheck against the final demo build; preserve evidence labels.

JUDGING CRITERIA
AI Technical Sophistication (50); Reliability, Evaluation & Trustworthiness (25)

SOURCES
Repository: research/learned-evalue-validation/expanded-null.json at 1e83cfb158dd1c9d35894e05006bd9482a566233
Repository: research/learned-evalue-validation/real-expression/README.md at 1e83cfb158dd1c9d35894e05006bd9482a566233

## 15 — Deployment and economics.

TENTATIVE SCRIPT · 30 seconds
We would start with a narrowly scoped research pilot. We need authenticated access, isolated execution and persistent workers that survive application deployment. The economics must include scientist review as well as model and compute spend. The intended first use is research prioritization; patient-facing decisions would require a separate validation and regulatory path.

EVIDENCE / STATUS
Research server is localhost-only in docs. Docker currently implemented; removal is a product decision but replacement environment/permissions unspecified. Security controls in this slide are requirements, not completed implementation or certification. No legal conclusion about device status.

BEFORE PRESENTING / NEXT EDIT
Recheck against the final demo build; preserve evidence labels.

JUDGING CRITERIA
Feasibility & Deployment Potential (25)

SOURCES
Repository: ARCHITECTURE.md at 1e83cfb158dd1c9d35894e05006bd9482a566233
Repository: docs/frontend.md at 1e83cfb158dd1c9d35894e05006bd9482a566233
Repository: docs/runtime.md at 1e83cfb158dd1c9d35894e05006bd9482a566233

## 16 — Originality and prior art.

TENTATIVE SCRIPT · 25 seconds
We should be compared with serious research agents, not a strawman chatbot. Co-scientist and Elicit already perform substantive research workflows. Our claim is the specific composition we built: grounded relationships, recursive executed investigations and an inspectable decision trail. We still need matched-budget comparisons to establish an advantage.

EVIDENCE / STATUS
Primary official descriptions reviewed. Do not claim first autonomous scientist, first multi-agent research system or unique experimental validation. Current Elicit research agent post is August 2026; DeepMind source May 2026.

BEFORE PRESENTING / NEXT EDIT
Recheck against the final demo build; preserve evidence labels.

JUDGING CRITERIA
Technical Execution (originality); Novelty and Importance of AI (25)

SOURCES
Google DeepMind · Co-scientist: https://deepmind.google/blog/co-scientist-a-multi-agent-ai-partner-to-accelerate-research/ (accessed 2026-09-06)
Elicit · Introducing Elicit Research Agent: https://elicit.com/blog/introducing-elicit-research-agent (accessed 2026-09-06)

## 17 — The next result should be hard to fool.

TENTATIVE SCRIPT · 25 seconds
The next evaluation should compare the research loop with a strong single agent and flat parallel research under the same total budget. Freeze tasks and starting evidence, account for failed branches, and have independent analysts rerun results. Measure expert usefulness and cost. Retrospective dates alone do not remove model-memory contamination.

EVIDENCE / STATUS
Evaluation proposal only; no new model runs or training authorized by creation of this deck. Predeclare dataset/task splits, evaluator rubric, budgets, stopping rules, output definitions and exclusions; report exact denominators and uncertainty when justified.

BEFORE PRESENTING / NEXT EDIT
Recheck against the final demo build; preserve evidence labels.

JUDGING CRITERIA
Reliability, Evaluation & Trustworthiness (25); Technical Execution (50); Feasibility (25)

SOURCES
Repository: plans/backlog.md at 1e83cfb158dd1c9d35894e05006bd9482a566233
Repository: plans/PLAN-demo-slides.md at 1e83cfb158dd1c9d35894e05006bd9482a566233
