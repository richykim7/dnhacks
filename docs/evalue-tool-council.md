# Candidate computational-biology tools for background e-value scoring

Research review, 2026-09-05. No integrations below have been implemented or benchmarked here.
The later [PDAC reassessment](#pancreatic-cancer-reassessment) qualifies the original generic ranking.
The existing expression tool is a biological two-sample diagnostic. Genentech's E-valuator is a
separate agent-trajectory method; see [the source-paper clarification](learned-evalue-process.md#source-paper-identification).

## Review procedure and actual agreement

Three reviewer sessions received the same brief and repository, with separate conversation contexts.
Each ranked five tools before receiving any other reviewer's recommendations. A second round disclosed
the frozen lists and asked each reviewer to challenge the shared first choice. These are separate
reviews by the same agent system, not independent human experts or statistical evidence of validity.

| Candidate family | Reviewer A rank | Reviewer B rank | Reviewer C rank |
| --- | ---: | ---: | ---: |
| Pathway/TF activity with decoupler | 1 | 1 | 1 |
| PyDESeq2 gene-level differential expression | 3 | 3 | 2 |
| Selective dependency using DepMap/Chronos | 2 | 4 | 3 |
| Co-essentiality across cell lines | — | 2 (SKIT) | 5 (permutation-based) |
| Safe logrank survival testing | — | 5 | 4 |
| Donor-level cell composition with scCODA | 4 | — | — |
| Biomarker–drug-response dependence | 5 | — | — |

All three retained pathway activity as the first pilot after challenge, conditional on an explicit
independent evaluation design. They did not agree on the complete ranking, the exact first dataset,
or a common scoring construction for every candidate. Agreement is a prioritization signal, not a proof.

## Shortlist and contracts

The biology packages supply measurements or statistics. The proposed e-value adapters below are
additional work. SKIT and safe logrank already have native sequential constructions; that does not
mean their proposed biological deployment or our wrapper is already validated.

| Tool | Useful question and unit | Proposed evidence route | Main condition or risk |
| --- | --- | --- | --- |
| [decoupler with fixed PROGENy/CollecTRI signatures](https://decoupler.readthedocs.io/en/stable/) | Do two groups differ in a prespecified pathway/TF score? Independent donor/animal; aggregate cells within donor. | Freeze the network and per-sample scoring, then use bounded two-sample betting on fresh donor scores; alternatively one valid donor-level randomization p followed by fixed calibration. | Equal score distributions is the null. A pathway enrichment p over genes is not a donor-level treatment test. Inferred activity is not causal pathway activation. |
| [PyDESeq2](https://pydeseq2.readthedocs.io/en/stable/) | Does a prespecified gene respond to condition? Biological sample/donor, including donor × cell-type pseudobulk. | Calibrate a valid raw p-value; distinguish approximate NB/Wald model evidence from a justified treatment-randomization test using the DE statistic. | Requires raw counts, not TPM. A zero condition coefficient and exchangeability of treatment labels are different nulls. Label-dependent preprocessing must be rerun within permutations. |
| [Chronos/DepMap](https://link.springer.com/article/10.1186/s13059-021-02540-7) + restricted permutation | Does an A alteration associate with dependency on B? Unique biological cell line. | Freeze event, target, effect statistic and defensible exchangeability strata; compute a valid restricted-permutation p on held-out lines, then calibrate. | Observational mutation status is not randomized. Regression adjustment alone does not validate shuffling. Cell-line aliases, shared screen estimation, lineage and copy number need explicit treatment. Association does not establish synthetic lethality. |
| [Sequential Kernelized Independence Testing (SKIT)](https://proceedings.mlr.press/v202/podkopaev23a.html) on dependency profiles | Are two gene-dependency profiles independent across cell lines? Independently sampled line/cluster. | Established native independence-testing e-process; proposed application to frozen dependency measurements. | Marginal dependence can come from lineage or batch. Residualizing does not automatically create valid conditional-independence tests. Correlation percentile is not a null p-value. |
| [safestats::safeLogrankTest](https://search.r-project.org/CRAN/refmans/safestats/html/safeLogrankTest.html) | Do predefined groups differ in survival? Independent patient, with risk-set/event updates. | Established [safe logrank](https://proceedings.mlr.press/v146/grunwald21a.html), initially the exact implementation, wrapped from Python. | Needs appropriate censoring/risk-set assumptions and a new endpoint-bearing dataset. Cutpoint selection, repeated patients and informative censoring break naive interpretations. |

Composition analysis and biomarker–drug sensitivity are reasonable later candidates. For composition,
freeze a donor-level score and test it; a scCODA posterior inclusion probability is not a p-value or
e-value. For drug response, one response summary per independent line can enter an independence test;
doses, wells and repeated releases are not new independent observations. Their first-round support
was one reviewer each, so they should not be reported as unanimous choices.

## Proposed first pilot and disagreements preserved

Parent synthesis: start with one frozen pathway/TF score and a transparent donor-level test. This is
more interpretable than another unrestricted expression embedding and can reuse the receipt/worker
architecture. It needs a new scorer/input contract; the current service accepts TPM plus its frozen
encoder, so it cannot already accept arbitrary pathway scores or raw-count DE results.

The challenge round proposed three different first steps:

- **A: small known-positive engineering check.** NR3C1 activity for dexamethasone/control in
  [GSE52778](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE52778), selecting only the relevant
  conditions from four donor-derived airway cell lines. Under explicitly justified independent
  within-donor swap symmetry, enumerate 16 swaps. With the repo calibrator the greatest attainable
  e-value is 3. This cannot demonstrate crossing 20; it checks that the implementation respects the
  small biological sample size. The accession alone does not establish randomized assignment.
- **B: computational audit before a new cohort.** Use GSE212041 only as development data; fix unordered
  donor pairs and randomize fair orientations to audit a frozen PROGENy score's bettor. Then find a
  previously uninspected donor-replicated perturbation study with documented assignment. Independent
  arms fit the existing two-sample design; paired aliquots need a distinct paired construction.
- **C: explicitly specified future confirmation design.** Twelve independent donors with randomized
  matched treatment/control aliquots, an externally fixed IFN-response signature and a predeclared
  direction. Enumerate 4096 within-donor assignments under the sharp no-treatment-effect null.
  The maximum calibrated e-value is 63. This is a proposed design, not a dataset that the reviewer
  located or a measured result.

We should not silently call GSE212041 untouched confirmation for a newly selected pathway: it has
already been inspected and used for comparisons. Known-positive examples demonstrate engineering
behavior; a new biological claim needs an appropriate independent confirmation boundary.

For a first implementation, validate numerical invariants and exact small randomization cases;
then run null simulations, planted effects and donor-duplication/selection/refitting stress cases.
Freeze the method before a separate larger validation run. Report uncertainty, final evidence and
anytime crossings separately. Do not select the best pathway, seed, normalization or comparator after
seeing confirmation outcomes. No named new dataset or scientific family has been approved here.

## Common evidence rules

1. **Fix the null and unit before choosing the wrapper.** A mean effect, distribution difference,
   marginal independence, conditional association, survival hazard and agent-trajectory failure are
   different claims. Genes, cells, guides, wells and permutation draws generally are not independent
   biological replicates.
2. **Do not repair p-values by renaming them.** The existing repo uses `p_to_e(p) = p**(-0.5) - 1`
   for a valid superuniform p. Two reviewers initially proposed the different valid calibrator
   `1/(2*sqrt(p))`; neither should be chosen after results. [Calibration and merging theory](https://arxiv.org/abs/1912.06116)
   explains the general construction. With the repo formula and plus-one permutation p, B=999
   permits at most e≈30.62; e≥20 requires p≤1/441. The alternative formula permits only e≈15.81
   at B=999. These are algebraic limits, not measured power.
3. **A fixed-sample e-value is not automatically an e-process.** Re-running a test on the same data
   creates no fresh evidence. Products require independent or sequentially conditionally valid
   factors. Fixed weighted averages can combine valid e-values for the same null under dependence;
   different nulls need an explicit scientific interpretation and family procedure.
4. **Preserve blinding and provenance.** The agent runs the experiment command; the command emits a
   receipt and the runtime captures it. Worker-owned scores, failures and human reports stay out of
   discovery feedback. Record all attempts, frozen settings and data/selection provenance privately.
5. **Benchmark the promised claim.** Test null behavior under the stated design, relevant confounding
   failures, alternative sensitivity and repeatability. Simulations check implementation, not
   universal validity. Test autonomous scientific usefulness separately from arithmetic and transport.

Raw docking scores, AlphaFold confidence, LLM plausibility, pathway enrichment ranks and posterior
probabilities are not direct statistical e-values. BLAST's similarly named quantity has different
semantics. These can be exploratory features, but require a defensible null/calibration construction
before being used as evidence.

The council also flagged existing co-essentiality rank/enrichment language and unrestricted
observational permutations as potential sources of overclaiming. Those skills were not modified in
this research task; a future adapter must resolve the precise sampling/null contracts rather than
inherit an informal description as a guarantee.

## Pancreatic-cancer reassessment

The user clarified that candidates should suit pancreatic-cancer therapeutic discovery or relevant
basic science. Two original reviewers independently reassessed relevance without seeing one another's
new rankings. Both moved functional dependency ahead of pathway activity. They agreed on relevance
more strongly than ordering: A placed drug response second; B placed it fourth behind expression tools.
This supersedes pathway-first as a disease-specific priority, while preserving its lower integration
effort as a separate consideration. No tools or scientific workflows were changed.

| Candidate | PDAC assessment and example | Evidence contract to establish before integration |
| --- | --- | --- |
| DepMap/Chronos; treatment CRISPR screens with MAGeCK | Highest shared priority: target dependencies and modifiers of KRAS-inhibitor response. [PDAC resistance study](https://pmc.ncbi.nlm.nih.gov/articles/PMC10821578/) | Unique donor-derived model for cross-model generalization; biological screen replicate for within-model effects. Guides are nested observations. Baseline observational association, knockout effects and drug-by-knockout interactions require different nulls. |
| PharmacoGx; SynergyFinder | Raise measured drug-response analysis: organoid sensitivity and biomarker associations are directly useful. [PDAC organoid pharmacotyping](https://pubmed.ncbi.nlm.nih.gov/29853643/) | Start with a frozen per-model response summary and a justified association test. Dose points and wells are not independent models. A combination claim needs a prespecified additivity reference and uncertainty in single-agent response; Bliss/Loewe scores are not e-values. |
| decoupler and PyDESeq2 | Retain as core tools: resistance programs, classical/basal states and fibroblast responses. [IL1/JAK/STAT versus TGF-beta in PDAC fibroblasts](https://pubmed.ncbi.nlm.nih.gov/30366930/) | Fixed activity scores or raw-count gene analysis on independent donor/model units. Donor-by-cell-type pseudobulk avoids counting cells as donors. Paired perturbations need the appropriate paired design; mixture differences are not automatically regulatory changes. |
| Co-essentiality | Retain as supporting target/module discovery; treatment-anchored perturbation evidence is more direct for resistance questions. | Correlation can reflect lineage/batch. Freeze targets and distinguish marginal from conditional independence; verify model independence and shared preprocessing. |
| scCODA composition | Retain for immune/fibroblast abundance changes, generally as a supporting readout. | Donor-level replication and a clear compositional contrast; posterior inclusion probabilities do not become e-values by renaming. |
| Safe logrank | Still relevant for a defined outcome/response question, lower priority for mechanism discovery. | Independent endpoint-bearing patients, appropriate risk sets/censoring and fixed groups. Prognostic association alone does not identify a therapeutic vulnerability. |

Two useful omissions emerged. Both reviewers proposed [chromVAR](https://www.nature.com/articles/nmeth.4401)
for motif-associated accessibility and regulatory-state plasticity; [PDAC work](https://pmc.ncbi.nlm.nih.gov/articles/PMC9511995/)
provides a biological example. A also proposed [NicheNet](https://www.nature.com/articles/s41592-019-0667-5)
for tumor–stroma ligand hypotheses, motivated by the fibroblast study above. These remain discovery
readouts unless frozen motif/receiver-target scores are tested on appropriate independent units.
Motif accessibility does not prove TF binding, and inferred ligand activity does not prove communication.
Peak definitions, motif backgrounds and ligand/target choices must respect the confirmation boundary.

Published examples establish biological relevance, not availability of a suitable local validation
cohort. The original expression benchmark used neutrophil data, so its results do not establish PDAC
utility. Assessment priorities are dependency/resistance, measured drug response, and expression
mechanisms; data design and valid nulls decide which evidence adapter can actually be built first.
Trajectory monitoring is assessed separately in [the E-valuator/tree-search review](evaluator-tree-search-review.md).
