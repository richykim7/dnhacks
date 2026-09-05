# Closest-prior-art audit

Audited September 5, 2026 by a delegated literature reviewer, with an independent
theory reviewer checking the primary SUKP reduction. Sources are primary papers
or author implementations. “Published” below means attributed to that paper;
only results proved in [the report](report.md) are independently established here.
No result is classified as a surviving novelty claim.

## The closest result was missing from the starting menu

**Goldschmidt, Nehme, Yu (1994), _On the Set-Union Knapsack Problem_.** Its items
are sets of atomic elements, rewards add over items, and costs add once over
the selected union. This is exactly the deterministic prerequisite-closed
completion formulation. Sections 4–5 give a frontier DP and structural bounds.
Aggregating disjoint private portions and putting them before shared elements
makes the frontier at most the shared core. Our exact solver is consequently
a direct specialization, not a novel FPT theorem.
[Primary scan](https://iiif.library.cmu.edu/file/Cooper_box00024_fld00053_bdl0001_doc0001/Cooper_box00024_fld00053_bdl0001_doc0001.pdf)

**Arulselvan (2014), _A note on the set union knapsack problem_, Theorem 2.4.**
The published factor is `1−exp(−1/d)`, d≥2, where an element occurs in at most d
items. Compute `allocated_i=Σ_{a∈H_i}c(a)/frequency(a)`. Enumerate feasible seeds
of at most two items, scan remaining items in static decreasing reward/allocated
cost order, skip infeasible additions permanently, and return the best seed run.
Our `allocated_seed_greedy` follows the inspected Algorithms 1–2, then counts
incidentally completed items as an explicitly identified free enhancement.
[Paper](https://doi.org/10.1016/j.dam.2013.12.015)

An unresolved audit concern: the displayed approximation proof appears to omit
the seed from a budget-cover inequality. This may be an unstated residual-instance
convention. We found neither a counterexample nor an erratum. The implementation
matches the published pseudocode, but we do **not** independently certify that
approximation proof. The exact core theorem and experimental conclusions do not
depend on that published guarantee.
[Publisher Algorithm 1](https://ars.els-cdn.com/content/image/1-s2.0-S0166218X1300588X-fx1.jpg),
[Algorithm 2](https://ars.els-cdn.com/content/image/1-s2.0-S0166218X1300588X-fx2.jpg)

**_Coordinating Monetary Contributions in Participatory Budgeting_ (2025),
Appendix B, Theorem 16.** Laminar SUKP has an FPTAS via a reduction to knapsack
with chordal conflict graphs. Laminarity and a small shared core are different,
incomparable structural restrictions. A known approximation route already exists
if scientific patterns happen to be laminar.
[Primary paper](https://link.springer.com/article/10.1007/s10458-025-09715-7)

Pair witnesses contain Densest k-Subgraph; larger witnesses connect to Densest
k-Subhypergraph and Minimum p-Union. Small witness size is therefore not a
sufficient reason to expect a simple constant guarantee. NP-hardness of exact
optimization alone does not establish any particular approximation hardness.
[Primary DkSH/Minimum p-Union paper](https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.APPROX-RANDOM.2016.6)

## Required neighboring areas

| Area / source | What applies, and what prevents direct transfer |
|---|---|
| [Nemhauser–Wolsey–Fisher (1978)](https://thibaut.horel.org/submodularity/papers/nemhauser1978.pdf) | Known, normalized, monotone submodular coverage under cardinality gives the established greedy exponential bound. AND completion rewards violate submodularity. Fixed-batch optimality says nothing about unseen branches. |
| [Golovin–Krause, adaptive submodularity](https://arxiv.org/abs/1003.3967) | Adaptive greedy requires adaptive monotonicity and diminishing conditional expected marginals under the actual outcome law, with conditional-marginal access. An arbitrary LLM score is not that oracle. Learning another required success can increase a conjunction's marginal value. |
| [Feldman–Izsak (2014), Theorem 15](https://drops.dagstuhl.de/opus/volltexte/2014/4695/pdf/12.pdf) | Published cardinality factor `1−exp(−1/(d+1))` for bounded supermodular degree, with dependency access and polynomial dependence on n and 2^d. This is their dependency-aware algorithm, not arbitrary pair greedy. Prerequisite-closed sets are not automatically a matroid or an extendible system. |
| [Chen–Teng–Zhang (2019), supermodular width](https://www.microsoft.com/en-us/research/wp-content/uploads/2018/11/itcs19_complementarity.pdf) | A weaker complementarity parameter can be much smaller than degree, with corresponding batch-greedy guarantees and n^{O(width)} access complexity. “Small useful complementary batches” is already an investigated direction. |
| [Adaptive Seeding (2015)](https://arxiv.org/pdf/1507.02351) | Known bipartite topology, independent neighbor availability with known probabilities, two stages sharing a cardinality budget, and submodular reward support a locally adaptive factor approximately `(1−1/e)^2`. Arbitrarily discovered topology and AND rewards are outside those assumptions. |
| [Adaptive Sequence Submodularity (2019), Theorems 1–2](https://arxiv.org/pdf/1902.05981) | Published graph factor `γ/(2d_in+γ)` and rank-r hypergraph factor `γ/(r d_in+γ)` assume known topology, observable vertex states, edge-state semantics and weak adaptive submodularity. These reward edges encode order; they are not arbitrary prerequisites. |
| [Mitrovic et al., hypergraph sequence optimization (2018)](https://proceedings.mlr.press/v84/mitrovic18a.html) | An order-aware graph/hypergraph objective gives structure-specific greedy analysis. Known hyperedges and the stated submodular-on-edge reward are necessary; arbitrary jointly necessary experiments are not automatically covered. |
| [Bowers–Lindgren–Waggoner, Combinatorial Markov Search (2025), Corollary 5.1](https://arxiv.org/html/2502.08976v1) | Published `1/2−ε` online guarantee uses independent known finite Markov processes, paid exploration, and matroid-constrained claims. Reward minus exploration cost is the objective; the adaptive offline comparator also pays to discover outcomes. Shared observations/costs between processes break the separation. Calling that comparator cost-free clairvoyance would be inaccurate. |
| [Boodaghians et al., Pandora with order constraints](https://arxiv.org/pdf/2002.06968) | Tree constraints with independent known reward distributions admit generalized optimal thresholds. General DAG reachability has hardness even at depth two. A node may be opened after at least one predecessor in that model, unlike our all-prerequisites rule. Reward/cost approximation conventions must also be preserved. |
| [Berger et al., Pandora's Box with Combinatorial Cost (2023)](https://arxiv.org/abs/2303.01078) | Monotone submodular query-set costs and independent box rewards admit an optimal fixed order with adaptive stopping; general cost-oracle access has strong computational limits. Union costs can fit, while common observations that correlate hypotheses generally do not. |
| [Multi-Heuristic A*](https://ai.dmi.unibas.ch/research/reading_group/aine-et-al-rss2014.pdf) | A consistent anchor and inadmissible heuristics preserve completeness/bounded path cost (w1w2 under the stated assumptions). This is not a comparative experimental-query guarantee. Search states must retain every context feature affecting valid transitions. |
| [LazySP](https://cdn.aaai.org/ojs/13788/13788-40-17306-1-2-20201228.pdf) | Optimistic edge costs plus exact evaluation preserve path correctness. Arbitrary learned edge priorities do not inherit expected-query optimality. Scientific success must first be encoded as a verified path goal. |
| [The Provable Virtue of Laziness (2019)](https://www.ijcai.org/Proceedings/2019/0855.pdf), [learned lazy selectors](https://arxiv.org/abs/2110.04669) | Query-policy analysis has instances where the optimal expected-query strategy lies outside LazySP. Learned evaluation adds a training/outcome-distribution model; it does not repair unknown verification semantics. |
| [Arora–Dekel–Tewari (2012), Theorem 1](https://oferdekel.github.io/pdf/2012AroraDeTe.pdf) | Unrestricted adaptive adversaries can cause linear policy regret even against constant actions. Bounded-memory assumptions permit positive mini-batching results. Standard bandit regret cannot be cited for policies that change future graph/candidate trajectories without such a protocol. |

## Certificates and learned advice: additional close art

| Source | Relevant guarantee boundary |
|---|---|
| [Query Strategies for Priced Information (2002)](https://web.cs.ucla.edu/~sahai/work/web/2002%20Publications/J.CompSysSci2002.pdf) | Known Boolean functions, trusted costs and exact bit queries permit competitive comparisons with the cheapest realized certificate under specified function structure. Distribution-free evidence search is an established topic. |
| [Deshpande–Hellerstein–Kletenik, stochastic Boolean evaluation](https://arxiv.org/abs/1303.0726) | Independent bits with known probabilities/costs; objective is expected cost to determine a function. The logarithmic result uses a combined CNF/DNF representation, not arbitrary DNF alone. Budgeted total completion is a different objective. |
| [Allen et al., DNF evaluation](https://www.cs.cmu.edu/afs/cs/user/srallen/www/papers/dnfeval.pdf) | Even monotone DNF evaluation has significant hardness; short certificates may require much more work to discover. A short successful witness does not itself imply cheap acquisition. |
| [Erlebach et al., learning-augmented uncertainty-MST (2022)](https://drops.dagstuhl.de/storage/00lipics/lipics-vol244-esa2022/LIPIcs.ESA.2022.49/LIPIcs.ESA.2022.49.pdf) | Published γ-robust, `(1+1/γ)`-consistent query tradeoff for integer γ≥2 depends on trusted intervals, exact query answers, known graph, and MST witness structure. It is not a generic theorem for LLM-guided research. |

Our advice experiment only orders deterministic knapsack profiles with verified
fractional bounds. Its robust certificate is standard branch-and-bound. It does
not compete with these specialized query bounds, and performs no costly
experimental queries at planning time.

## Existing implementations inspected before building

| Implementation | Reuse decision |
|---|---|
| [SUKP I2PLS author page](https://leria-info.univ-angers.fr/~jinkao.hao/SUKP_I2PLS.html) | Code, 30 benchmark instances and solution certificates are supplied. Suitable large-instance empirical follow-up; too much machinery for a tiny transparent exact oracle. |
| [SUKP ANRMA (2026)](https://github.com/Zequn-Wei/SUKP), [author paper](https://leria-info.univ-angers.fr/~jinkao.hao/papers/WeietalSWEVO2026.pdf) | Live author repository contains algorithm, benchmarks and certificates. Stronger scalable empirical baseline for follow-up; no new approximation guarantee. Its related-work paraphrase drops a restriction on the 1994 DP, so theory here uses the original. |
| [Adaptive sequence author code](https://github.com/ehsankazemi/adaptiveSubseq) | Relevant if known-topology sequence semantics become the actual objective; currently a different model. |
| [LEMUR / LazySP](https://github.com/personalrobotics/lemur) | Existing generic search components; use if the product specifies path goals and expensive edge verification. |
| [SBPL MHA*](https://github.com/sbpl/sbpl/blob/master/src/planners/mhaplanner.cpp) | Existing robust heuristic search implementation; a new research-specific search engine is unnecessary for that guarantee. |

No external source code or dataset archives were copied into this prototype.
Links were inspected for available code/artifacts; redistribution licenses were
not comprehensively audited, so these are candidates for later reuse rather than
blanket licensing endorsements. The prototype implements mathematical recurrences
directly with Python's standard library and reuses the existing historical
snapshot and manifest.

## Novelty verdict

Established: coverage and the cited structural/search frameworks.
Derived here with complete proofs: shared-core specialization and rational
instance certificates. Constructed and proved here as explanatory boundaries:
the setup-greedy family and elementary revealed-action lower bound; neither is
claimed novel after this audit. Candidate new theorem: none surviving.

The open publication target is an explicitly modeled adaptive process with
shared observations, progressive candidate revelation, and restricted interfaces
or certificates. A positive result would need a sharper assumption/comparator
than “LLM proposes useful branches,” plus a reduction audit against the work
above. The current output provides a defensible baseline for that future effort.
