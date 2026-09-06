# Learned biological tool council

Status: five independent proposal reviews and three separate planning-agent drafts completed; planning only. Requested 2026-09-06.
Baseline for this review: `6767be1`. No tool implementation, dataset acquisition, training or confirmation run is authorized by this planning task.

## Corrected objective

Propose reusable biological experiment tools useful in the pancreatic corpus and analogous to the existing learned expression evidence tool. The earlier dependency/drug/pathway plans selected conventional fixed-data tests followed by p-to-e calibration. Those implementations are not completion of this objective.

A candidate must specify meaningful biological operations, a reusable learned representation or payoff where justified, the data contract and independent units, and a native sequential evidence construction with an auditable score-before-train schedule. A neural model alone does not establish validity. A final scalar is still evidence for one declared null; an evidence trajectory cannot silently pool unrelated hypotheses, overlapping donors or repetitions of one dataset.

Five reviewers propose independently before seeing each other's recommendations. The parent then records convergence and assigns three separate agents to produce one implementation plan each. The available three worker slots require two review waves. Proposals are preserved under `reviews/`; the three final plans are linked below. None of these files is an autonomous implementation assignment.

## Corpus and existing architecture

The local `pdac-frozen` corpus card describes 100 full-text papers through 2026-01-25 on pancreatic cancer cell survival under abnormal division, nutrient use, redox/protein stress and tumor–stromal signaling. The actual manifest includes 34 division papers, 21 PDAC metabolism/context papers and 20 stress/functional-genomics papers, plus bridge/stromal categories. It includes some non-pancreatic mechanistic studies whose context must be checked.

The original `learned_evalue.py` implements a past-trained neural bettor scored on fresh units, with a frozen expression encoder, explicit sampling contract and a wealth path. Its documented real-expression example uses a COVID neutrophil cohort, not a pancreatic cohort. It is a standalone diagnostic; existing architecture intentionally keeps private evidence out of discovery feedback and ordinary falsifier/promotion decisions.

GPU availability was checked through the local handoff connector on 2026-09-06: an NVIDIA L40S reported 46,068 MiB total, 0 MiB used and 0% utilization at the check. This is an availability observation, not a reservation, runtime estimate or training result. Connection details remain local.

## Value of the three earlier integrations

Keep their reusable infrastructure: durable receipt submission, separate private scoring, immutable registered inputs/settings, provenance hashes, donor/alias checks, replay, retry deduplication and attempt audit. Existing learned expression compatibility was retained.

Integration update checked against main `bee2ade`: [the operator monitoring service](../../docs/branch-monitoring.md) now has an explicit `associate` command that imports a completed scoring receipt/canonical alias into an immutable private finding-review record. A human can record a written decision there. This is an additional concrete reuse path for the earlier adapters. Automatic receipt routing, discovery feedback and master-graph updates are still not wired; numerical evidence and branch-future-success statistics remain distinct.

Keep numerical operations where useful: dependency mean comparisons, observed drug-response AUC and rank association, paired expression preparation and optional differential-expression effects. These can become simple comparison baselines and data-preparation components.

Do not present them as three new learned tools: no new learned biological representation/payoff, native sequential evidence trajectory or trained PDAC model was delivered by those endpoints. No real confirmation cohort was bundled. Their private scalar results do not automatically drive exploration, branch monitoring or human promotion. Biological evidence and branch-future-success monitoring test different nulls; they need different contracts.

New plans must separately describe useful exploratory biological outputs from development/discovery data and operator-private confirmation evidence. They must not leak held-out evidence back to adaptively selecting agents merely to make the tool appear useful.

## Selection requirements

1. Concrete, repeated use on corpus questions, rather than one hard-coded gene pair.
2. A supported null and native evidence process, including how the conditional expectation bound survives training and preprocessing.
3. Public-source feasibility, with donors/models distinguished from nested measurements and missing confirmation data stated explicitly.
4. Measurable benefit over the existing learned-expression API and simpler baselines; added modality or hypothesis capability must be real.
5. Meaningful GPU training/evaluation when warranted, with CPU baselines and measured throughput before larger runs.
6. Architectural reuse, privacy and honest integration boundaries; no automatic verifier/promotion change.
7. Concrete validation and failure/stop criteria, including invalid controls and scarce-data failure.

## Independent convergence

All five reviews are complete. Initial rankings, before convergence:

| Reviewer | First | Second | Third |
| --- | --- | --- | --- |
| 1 | Pharmacotype association | Protein/PTM | Cellular ecosystems |
| 2 | Protein/PTM | Functional dependencies | Pharmacotype association |
| 3 | Functional dependencies | Protein/PTM | Pharmacotype association |
| 4 | Protein/PTM | Cellular ecosystems | Image phenotyping |
| 5 | Protein/PTM | Cellular ecosystems | Pharmacotype association |

For transparency, a simple 3/2/1 rank tally gives protein/PTM 13, pharmacotype 6, ecosystems 5, dependencies 5 and morphology 1. This is a summary of reviewer preferences, not an empirical performance score. Top-three inclusion counts are respectively 5, 4, 3, 2 and 1.

Selected for separate plans: **protein/phosphosignaling**, **learned pharmacotype association**, and **donor-level cellular ecosystems**. Protein/PTM has unanimous inclusion, a distinct measurement layer and the strongest located PDAC cohort inventories. Pharmacotype has four inclusions and a direct reusable nonlinear functional-response capability. Ecosystems wins the rank-point tie with dependency mapping because more reviewers selected it, it adds compartment/distribution information beyond bulk expression, and it directly addresses the corpus's stromal/metabolic questions. Its small independent-donor budgets remain a release gate, not a solved problem.

Dependency-program mapping remains a strong reserve, particularly for the corpus's division/functional focus. Eligible fresh PDAC models and shared Chronos fitting remain unresolved; it does not displace the selected modality diversity. Image phenotyping is exceptionally relevant to division biology, but reviewers found training resources rather than a verified PDAC confirmation set. Neither reserve is an implementation assignment.

The three planning agents must use the [shared native contract](native-evidence-contract.md), independently verify their selected data paths, and specify useful biological operations, training, evaluation, private sequential state and implementation milestones. The selection authorizes planning, not data acquisition or training. Parent source checks confirmed the Hwang publication/accessions and Korean proteomics availability statements; publication inventories remain distinct from audited usable donor counts.


## Three planning-agent deliverables

| Selected capability | Plan | First native evidence operation | Useful development outputs |
| --- | --- | --- | --- |
| Protein/phosphosignaling | [Protein plan](PLAN-protein-signaling.md) | Independent-group comparison of frozen measured protein representations; proposed open-metadata grade comparison is a feasibility/demo endpoint, not the only supported question | Protein/site profiles, coverage, module maps, similar tumors and exploratory comparisons |
| Learned pharmacotypes — **deprecated** | [Cancelled pharmacotype plan; historical reference only](PLAN-pharmacotype.md) | User cancelled on 2026-09-06; intended real-data e-value tool was not delivered | Inactive; do not resume without a new explicit user request |
| Cellular ecosystems | [Ecosystem plan](PLAN-cellular-ecosystems.md) | Independence of separately represented malignant/fibroblast state distributions across fresh donors | Compartment/state distributions, donor maps, exploratory coupling and actual-data spatial summaries |

Each plan was written by a separate planning agent after the five-review convergence. The parent reviewed the resulting interfaces, scope and data claims; a returning council reviewer audited mathematical/measurement risks. That audit found no kernel/schedule blocker and identified a confirmation-count disclosure ambiguity, which was corrected: public budgets are requirements, while realized confirmation counts and exclusions remain private. The protein plan independently verified that Fudan uses label-free quantification and has a much smaller described transcriptomic subset, motivating protein-only confirmation first. The drug plan identifies controlled-access molecular data as a real blocker. The ecosystem plan quantifies that its narrow untreated candidate population might offer at most nine two-donor blocks before exclusions. No plan claims that publication sample counts are ready-to-score independent donors.

Implementation is incremental: data/identity/assay audit, useful development operations and simple baselines, measured GPU representation training, shared native-process integration, then independently validated private confirmation. Release of a useful exploratory tool is distinct from release of a confirmatory experiment. Learned encoders must earn their cost through held-out utility/power comparisons; where simpler features win, report that outcome.

No new tool has been trained or implemented by this council. The three earlier fixed-data adapters remain available as preparation/infrastructure/baselines; these plans neither remove them nor claim their scalar outputs now drive the exploration loop.

Training coordination: the three plans share one L40S. CPU preparation/scoring may overlap within host limits; initial GPU pilots are serialized through one operator-managed queue/lease. Concurrent training is a later measured resource/throughput decision, not an assumption that each agent has a GPU. See the [shared scheduling rule](native-evidence-contract.md#coordination-on-the-shared-gpu).
