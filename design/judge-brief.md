# Judge brief: pitching the forecasting engine to DTX Ventures

Written 2026-09-05 from the state of `main` at `4d213d4` plus the computed runs in the
`forecast-runner` worktree (`demo/forecasting/runs/civic-2018-2022-*.json`, scored with
`dnhacksbio.forecasting.evaluation.compare_forecasts`). Every number below was recomputed for this
brief; anything not measured is labeled planned. Re-run the scorecard before the demo if the runs change.

## 0. What is true right now (the only numbers you may say aloud)

Cohort: CIViC clinical evidence frozen at 2018-01-01, outcomes read from the 2022-03-01 release.
Both files are hash-listed in the scenario manifest; scorers read `historical.json` only.

| Quantity | Value |
|---|---|
| Historical graph | 71 nodes, 131 claims, 216 evidence rows |
| Forecast universe | 683 candidate variant → therapy edges across 22 query variants |
| Confirmed by horizon | 24 of 683 (base rate 3.5%) |

Scorecard, structural path scorer, `llm_calls = 0`:

| Condition | AUROC | AP | P@5 | P@24 |
|---|---|---|---|---|
| Full historical graph (216 evidence rows) | 0.82 | 0.20 | 0.20 | 0.29 |
| Initial graph (54 seed rows) | 0.58 | 0.05 | 0.00 | 0.04 |
| Popularity (target degree) | 0.58 | 0.06 | 0.00 | 0.08 |
| Greedy coverage acquisition, 32 acquisitions | 0.60 | 0.05 | 0.00 | 0.04 |
| Uniform acquisition, 32 acquisitions | 0.67 | 0.08 | 0.20 | 0.04 |
| Top-singleton acquisition, 32 acquisitions | 0.63 | 0.06 | 0.00 | 0.04 |

Random expectation: AUROC 0.50, P@k 0.035.

Named results for the stage:

- Rank 1 of 683: PIK3CA mutation → cetuximab / panitumumab. Confirmed (CIViC evidence 6362).
- Rank 8: PTEN loss → pictilisib. Confirmed.
- 7 of the 24 confirmed edges sit in the top 24; 11 sit in the top 53.
- Worst miss: FLT3 ITD → ponatinib at rank 642. The 2018 graph had no path between them. This is the honest limit of structure-only scoring and the reason evidence ingestion is the lever.

Other established facts:

- Greedy coverage did not beat uniform acquisition at 32 acquisitions. Say this before a judge finds it.
- Evidence volume moved the score more than any policy did: 54 → 216 rows took AUROC from 0.58 to 0.82. Not a matched-budget ablation; a progress diagnostic.
- Coverage certificate: greedy ≥ 75% of the exact optimum at k = 2, checked on all 65,535 nonzero four-branch instances, worst case exactly 0.75 (Nemhauser–Wolsey–Fisher bound).
- Policy lab: 5,120 exhaustive reward/budget cases, 2,400 weighted-DAG certificates, 95 historical packet replays. Strong seeded baselines matched the exact optimum. No novel policy advantage. Documented as a negative result.
- External reference: Dyport 2016, 336,710 rows, 30,619 positives. Our recomputation of the authors' cached AGATHA-2015 scores: AUROC 0.735, AP 0.258. Not our model; a published bar to clear on identical rows.
- PubTator3 ingestion verified live (PMID 29355051, HTTP 200, three typed relations).

## 1. What DTX will score

Their public thesis: US dominance in AI, energy, defense, semiconductors, space, plus AGI, energy
independence, supply chains, and health. Binary framing: American leadership or Chinese/Russian
dominance. Founder criterion: "converting mission into market share."

So they will score four things, in this order: does this shift a strategic balance, is the claim
falsifiable, will it survive the next model release, and is there a buyer. The feedback you got last
time (not falsifiable, just a harness, competed away) maps onto items two through four. Item one is
where American-exceptionalism framing earns its keep, but only if the proof is real.

## 2. Talking points

### A. Biology is an underappreciated source of unilateral power

**The nuclear analogy is wrong in one specific way, and that way is the whole pitch.**
Nuclear power is bottlenecked on material. You can count centrifuges, sanction uranium, and inspect
reactors. Biological power is bottlenecked on the ordering of experiments: knowing which of the next
thousand experiments to run. That is an information problem, not a materials problem. Export controls
work on atoms and on chips. They do not work on the knowledge of which edge in the graph to test next.
Biology is therefore the domain where AI converts most directly into unilateral capability, and the
one domain in DTX's list where the United States cannot win by chokepoint. It can only win on lead time.

**Power is graph position, not stockpile.** Every confirmed association enables the next. A four-year
head start on the right edge is worth more than a warehouse. The metric of dominance is frontier-edge
lead time, and nobody currently measures it. We built the instrument that does.

**Proof points to cite (verify wording before saying them):**

- The National Security Commission on Emerging Biotechnology, April 2025: 49 recommendations, at least
  $15B over five years, and the finding that the US is "dangerously close to falling behind China."
  A congressionally chartered body already says the thesis. We say how to measure it.
- The COVID mRNA timeline: the sequence-to-candidate step took days; the evidence step took the better
  part of a year. Synthesis was never the bottleneck. Evidence ordering was. Our engine is an
  evidence-ordering engine.
- Our own backtest: with only structure from January 2018, the top-ranked candidate of 683 was
  confirmed by 2022. That is a measured four-year lead on one edge, and a miss rate we publish.

**Anticipation and attribution are the same instrument.** A graph that can say "this was knowable on
this date from this evidence" is a forecaster in one direction and an attribution tool in the other.
Sealed cutoffs are how you ask "could this actor have known this by then." One asset, two national
security customers. Say this once; it is the least obvious point in the deck.

### B. Reactive measures fail for novel bio; anticipation is possible

**Two clocks.** Reactive biodefense runs on the pathogen's clock, measured in days. Anticipation runs on
the literature's clock, measured in years. You cannot win on the short clock. Our backtest horizon is
four years. That is the clock we are on.

**Novelty breaks classifiers, not structure.** Detection is classification, and a new agent has no
training labels by definition. Our best-performing scorer uses no labels and no language model. It
scores an edge by its position in the evidence graph, so it applies to combinations nobody has seen,
by construction. That is the technical reason anticipation of new developments is possible at all,
and it is why the `llm_calls = 0` line matters strategically, not just as a purity claim.

**The lever is throughput, not IQ.** In our measurement, adding evidence rows moved AUROC from 0.58 to
0.82 while the choice of acquisition policy barely mattered. Anticipation is an ingestion problem. The
country that indexes its own science fastest sees the frontier first. Ingestion from PubTator3 is
verified. This is infrastructure, which is what DTX funds.

### C. This is not a harness

A harness has no ground truth. Everything below is a verifier that does not trust the model.

1. **Sealed-cutoff backtest.** Forecasts are written before the outcome file is opened. Hashes for both
   are in the manifest. The evaluator rejects any run with missing, extra, or duplicated candidates.
2. **Remove the LLM and it still works.** The 0.82 scorecard was produced with zero model calls. A
   harness with its model removed is nothing. Ours with the model removed is the best number in the deck.
3. **A certificate that ignores model confidence.** Branch selection carries an exact-oracle certificate
   at the current pool size and a 75% worst-case bound beyond it, checked exhaustively. No LLM score
   enters the guarantee.
4. **We falsified ourselves and shipped the negative result.** Greedy lost to uniform. The policy lab
   found no novel policy advantage after 5,120 exhaustive cases. A harness team has no policy lab.
5. **Executed, sandboxed experiments with a falsifier.** The explorer loop generates and runs code,
   and a separate falsifier checks primary null tests. Planned: anytime-valid e-values, so an agent that
   runs experiments sequentially cannot p-hack itself by stopping early. That is the difference between
   an autonomous scientist and a slot machine.

The product is the time-indexed provenance graph and the verifier stack. The model is a replaceable
proposer.

### D. Resilient to AI progress, and it gets better with it

**The contamination inversion.** Every "AI predicts science" demo gets less credible with each model
release, because a 2026 model that "predicts" 2022 biology may simply remember it. A sealed-cutoff,
structure-only scorecard is the only kind of evidence that survives that objection, and its value rises
as models get stronger. We sell the exam. Model progress increases demand for exams.

**Better model, same verifier.** A stronger proposer lowers our cost per candidate hypothesis and per
generated experiment. The scoreboard does not move unless the graph does. Nobody's model release
changes who owns the sealed cohorts.

**Better retrieval and tool use feed the binding lever directly.** Since throughput is the lever, every
advance in extraction quality goes straight into our score. We are downstream of the whole field.

**Domain agnostic by construction.** The scenario, forecast, outcome, and reveal records carry no
biology. Science4Cast (AI concepts) and mat2vec (materials) are the same shape. Semiconductors and
energy, both on DTX's list, are next cohorts, not rewrites.

**The real threat, stated honestly:** an end-to-end lab model that proposes and runs its own
experiments. Answer: a DoD or BARDA buyer still cannot trust it without a cutoff-sealed exam, and the
model cannot grade itself. That buyer needs us more, not less.

### E. Falsifiable benchmarks and kill criteria

Committed and measured:

- **B1, CIViC 2018 → 2022, structural scorer.** AUROC 0.82, AP 0.20 versus base rate 0.035 and
  popularity AUROC 0.58. 24 positives, so intervals are wide. Say "signal exists," not "solved."

Pre-registered, not yet met:

- **B2, matched-budget acquisition.** Beat uniform acquisition at 32 acquisitions on the frozen cohort.
  Current result: greedy 0.60 versus uniform 0.67. This is our own open failure and the next task.
- **B3, Dyport 2016 on identical rows.** Match or beat AGATHA-2015 (AUROC 0.735, AP 0.258) on the
  336,710-row table after reconstructing the historical input graph. 30,619 positives fixes the
  small-sample problem in B1.
- **B4, flat log versus static graph versus evolving graph** at equal tokens and retrieval budget.
  Answers "does the graph help" separately from "does more evidence help."
- **B5, contamination control. Measured 2026-09-06, and it failed in the informative direction.** With zero
  evidence, Claude Sonnet 5 scored AUROC 0.854 and AP 0.233 on all 683 candidates, above the structural
  scorer's 0.819 with the whole 2018 graph. The model already knows the answers on this packet. Consequence:
  no model-scored result on CIViC 2018→2022 may be presented as forecasting skill. The structural,
  zero-model number is the only clean one, and any model forecast claim moves to a cohort whose outcomes
  postdate the model's training data or to a prospective run. See `docs/forecasting-memory-control.md`.

Kill criteria, said out loud: if B3 cannot beat popularity on Dyport, structure is not worth building
on. If B4 shows the evolving graph never beats a flat log at equal budget, the graph is a visualization
and we say so.

### F. Why this deserves further development

- **Buyers who already have budget lines.** DTRA, BARDA, and IARPA horizon scanning; frontier-lab bio
  evaluation teams who need uncontaminated test beds; pharma portfolio triage, where "which of these
  683 edges gets confirmed" is literally the job. Allied governments are the NSCEB's sixth pillar.
- **Mission to market share, concretely.** Every database release ingested creates a new sealed cohort,
  which is a new benchmark, which is a new customer conversation. The asset compounds with calendar
  time, not with model size.
- **Sovereign scientific memory.** A time-indexed, provenance-complete graph of what American science
  knew, when, is infrastructure the way a fab is infrastructure. That is the sentence to leave with DTX.

## 3. How to present it (five minutes)

1. **0:00 The asymmetry.** One line: "In nuclear you control the material. In biology you can only
   control the lead time." Nothing else on the slide.
2. **0:30 The instrument.** Graph as of January 2018 on screen. The sealed outcome file's hash visible.
   Say: forecasts are written before this file is opened.
3. **1:00 The forecast.** Rank the 683 edges live or from the recorded run. Open rank 1: PIK3CA
   mutation → cetuximab / panitumumab. Show the three evidence paths and their evidence IDs. Let a judge
   click one.
4. **2:00 The reveal.** Open the outcome file. Rank 1 confirmed. Rank 8 confirmed. Seven of the top 24.
   Scorecard against random and popularity on one slide.
5. **3:00 The miss.** FLT3 ITD → ponatinib at 642. Show the empty neighborhood. Say why, and show the
   PubTator3 ingestion that fixes it. Misses inspectable is the credibility move.
6. **3:30 Not a harness.** Three bullets: zero model calls on that scorecard; the exhaustively checked
   certificate; greedy lost and we shipped it.
7. **4:00 Next benchmark, kill criteria, ask.** B2 and B3 with their thresholds. The ask is a Dyport-scale
   cohort and one wet-lab partner for prospective validation.

Visual rule: one graph, stable positions, the reveal changes edge status without rearranging the scene.
Provenance mode indicator always visible: computed, replayed, or illustrative.

## 4. Questions a good judge will ask

- **"This is 2015 link prediction."** Yes, the scorer is deliberately classic; it is the control.
  AGATHA scores 0.735 on Dyport and we will compare on identical rows. The novelty claim is the
  sealed-cutoff verifier stack and the evidence-acquisition loop that grows the graph, not the scorer.
- **"Why did greedy lose?"** Coverage certifies represented evidence, not forecast lift, and we wrote
  that before running it. Thirty-two acquisitions is small. The finding is that throughput is the
  lever, and B2 is pre-registered.
- **"Where is the LLM?"** It proposes hypotheses and writes experiments in the explorer loop, and it will
  revise the graph with citations. It is kept out of the scorecard until the contamination control passes.
- **"CIViC additions are curation lag, not discovery."** Correct. We say "later recorded," never "first
  discovered." Dyport uses MEDLINE dates and is the stronger claim.
- **"Twenty-four positives?"** Yes. Wide intervals. That is exactly why B3 exists.
- **"Are you building the thing you warn about?"** We rank published clinical associations from public,
  CC0 curated databases. No sequences, no pathogens, no wet lab. The defender needs to see the frontier
  before the adversary does, and this is the instrument for that.
- **"Why you?"** In sixteen hours the team produced a sealed cohort, an evaluator that rejects malformed
  runs, three policies, an exhaustively checked certificate, and two negative results about its own
  ideas. The instinct to falsify ourselves is the product.

## 5. Do not say

- "Predicts discoveries." Say "ranks later-confirmed associations from earlier evidence."
- Any percentage from earlier planning. The 96.08% figure was a toy world and is not this engine.
- "Novel algorithm." The policy lab established there is not one yet.
- "Greedy improves forecasting." It did not.
- "AI scientist." Say "evidence-ordering engine with a verifier stack."
- "First in the world." Database availability dates do not establish it.
