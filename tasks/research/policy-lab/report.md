# Policy lab: what shared scientific evidence lets us guarantee

Research date: September 5, 2026. Initial source audit: `4d213d4`.
Scope: isolated prototypes, with no production controller or interface edits.

## Decision

**Retain delivery coverage greedy for its declared coverage objective.** Adopt the
existing Set-Union Knapsack formulation and a small-shared-core exact solver as
an isolated completion comparator and certificate. A complete proof survives
independent review, but its closest 1994 predecessor subsumes it. No publication
novelty or forecasting improvement is established.

The useful finding is a boundary: shared evidence can make acquisition cheaper,
yet correct deduplication alone does not make greedy allocation reliable. A
single expensive reusable prerequisite gives an arbitrarily bad family for
residual-cost greedy. Strong seeded methods fix that family and match exact
optimization on every historical packet we tested. That last comparison is a
reason to avoid claiming that a new controller is needed.

The primary proof target is deterministic completion of explicit evidence
requirements with a small shared-action core. The fallback is an information
lower bound for actions revealed during exploration. Both targets were resolved
within the requested first gate; the same package supplies final experiments,
review, recommendations, and a demo artifact.

Read the [primary-paper audit](literature.md), [independent review](adversarial-review.md),
[executable model](../../../research_spikes/policy_lab/model.py), and
[reproduction instructions](../../../research_spikes/policy_lab/README.md).

## 1. What the repository actually supports

The scientific claim graph and exploration tree encode different relations.
`litmap/graph.py` stores canonical claims, source evidence, context slots, and
citations. `explorer/exploration.py` stores episodic entries, while
`explorer/lineage.py` defines the fork lineage and permitted memory reads.

| Starting observation | Verified meaning and limit |
|---|---|
| Branches share evidence/work | They share stores, downloaded resources and claim embeddings (`explorer.py:332–355`). There is no explicit reusable-action prerequisite DAG. |
| Exploration reveals candidates | Initial leaves cannot fork; selected survivors regain that ability (`1183–1217`). A complete candidate catalog or distribution of future branches is absent. |
| Experiments can complement each other | Scientifically plausible and expressible in a prototype. Current logs/synthesis do not enforce an AND-pattern objective or demonstrate measured complementarity. |
| Selection is injectable | `_judge_promise`, `1040–1041`, accepts `judge_fn(digests,k)`. All initial leaves run before this seam, so its immediate allocation decision concerns continuation. |
| Evidence identity/provenance exists | Claim/source/context/citation records exist. `_branch_digest`, `964–998`, omits identities, provenance and most result fields, keeps six results, and truncates explanation to 800 characters. |
| Reuse depends on visibility/context | Lineage-filtered log/test reads exclude concurrent siblings. Branch-specific scratch prevents filename collisions; it does not enforce filesystem isolation because the shared cache parent is mounted. |

Evidence row IDs are allocated again when a source is replaced. A reusable
artifact therefore needs source/content/version identity, not just a transient
database evidence number. Identical code or hypothesis labels also do not imply
identical inputs, allowed observations, or results.

The production graph's source-count confidence formula is not a calibrated
probability of truth. None of the results below uses it. We read the learned
e-value plan: its statistical null/selection/dependence obligations are separate
from completing a declared evidence packet. A valid statistical measurement is
not automatically a verifier of every biological interpretation attached to it.

## 2. Formulation map

These are distinct optimization problems, with distinct comparators. No single
guarantee is transferred between them.

| Formulation | Information, actions and success | Comparator and assumptions | Complexity / disposition |
|---|---|---|---|
| Fixed weighted coverage | Known offered branches and facet incidence; choose ≤k branches; reward union of nonnegative weighted facets. No hidden structure within a batch. | Best offered k-subset, same snapshot. Deterministic coverage; fixed incidence/weights; equal branch charges. | Established greedy bound `1−(1−1/k)^k`, O(kN) marginal evaluations. Retain delivery baseline. |
| **Closed witness completion** | Known action DAG, costs, AND patterns and deterministic completion outcomes; acquire prerequisite-closed action unions, paying each reusable action once. | Best same-information feasible set, budget B. Full formalization below. | Exactly SUKP; NP-hard generally. Small-core DP is primary surviving result. |
| Stochastic evidence acquisition | State includes observed action outcomes and unresolved requirements; successful completion depends on paid pass/fail observations. | Optimal adaptive policy under a specified prior, or fixed policy if explicitly chosen. Joint outcome law and observation model must be supplied. | Adaptive submodularity need not hold. Boolean-function evaluation is close for “find one completed witness.” No new theorem established here. |
| Revealed-action search | Known initial roots; observed root result exposes an otherwise unavailable child; separate reveal and execution costs. | Same-information Bayesian policy versus a separately labeled clairvoyant upper bound. | Exact tiny Bellman oracle and 1/n clairvoyant lower bound below; unlimited computation does not remove missing information. |
| Learned advice with certificates | Same deterministic instance as primary model; advice orders core-profile computation; verified fractional bounds control stopping. | Exact deterministic optimum. Advice is any finite sequence of integer masks, including omissions/duplicates. | Standard branch-and-bound certificate; fewer planning DP solves can occur. No experimental-query saving theorem. |

Adaptive seeding, adaptive sequence/hypergraph methods, Markov Search, Pandora,
A*, LazySP, and policy-regret comparisons are audited in the companion source
map. Their stochastic, independence, objective, or graph-oracle assumptions are
not silently imposed on the current engine.

## 3. Primary model and assumptions

Let A be n atomic reusable actions, with positive integer costs c(a). The known
prerequisite graph is acyclic. `cl(X)` adds all transitive prerequisites of X.
There are m declared reward items; item i has one required action set W_i and
nonnegative integer reward w_i. Put

`H_i = cl(W_i)` and `F(S) = Σ_i w_i · 1[H_i ⊆ S]`.

Choose `S = cl(S)` with `c(S) = Σ_{a∈S} c(a) ≤ B`, maximizing F(S). Success
means completing these declared evidence requirements, or attaining a separately
declared completion threshold. It does not mean that a hypothesis is true.

The controller's state is the acquired action/artifact set, remaining budget,
and fixed instance records. The entire DAG, witnesses, costs, and completion
outcomes are known at the decision snapshot. Previously acquired closed set S0
can be removed from each H_i and from the remaining action costs; already
completed patterns become empty patterns with constant reward. The code solves
the resulting residual instance from the empty set.

Actions may reveal payloads that have not been read, but the declared completion
predicate/outcome must be known, deterministic, and correctly recorded. A
retrieval task whose objective is acquiring specified documents fits this model.
An experiment with an unknown probability of yielding useful support does not.
Scoring planned requirements is another possible use, but then the guarantee is
about planned completion, not realized evidence.

Execution follows any topological order of the selected actions and stops when
the plan is complete, within B total work. B is total unique charged work, not
parallel makespan, peak memory, or wall-clock deadline. Abundant compute can
evaluate independent profiles in parallel but does not alter this comparator.

The comparator is the best feasible acquisition set with exactly the same
complete information. Determinism and known outcomes make adaptive observation
policies no stronger than this set optimizer. The model assumes neither LLM
calibration nor stochastic independence because no stochastic outcomes enter
its objective. It **does** assume correct candidate records and verification.
Wrong or incomplete records yield, at best, an optimum for those records.

An action can be paid once across patterns only if its artifacts are reusable:
immutable input hashes, code/tool/environment version, relevant graph/context,
randomness or stored result, and allowed visibility must agree. Two citations of
the same experiment are not two independent measurements. Reuse and statistical
independence are different relations.

Each reward has a single conjunction. “Any of several alternative experimental
paths establishes the same hypothesis” is an OR-over-AND objective, and counting
its alternative witnesses additively overcounts that hypothesis. The prototype
does not implement that extension.

## 4. Complete proof: exact optimization with a small shared core

**Classification: derived specialization of Goldschmidt–Nehme–Yu (1994), not a
candidate new theorem.** The deterministic model is Set-Union Knapsack: patterns
are profitable items and their actions are weighted elements paid by union.
The original paper's frontier DP already subsumes the restriction below after
private actions are aggregated. [Original paper, sections 4–5](https://iiif.library.cmu.edu/file/Cooper_box00024_fld00053_bdl0001_doc0001/Cooper_box00024_fld00053_bdl0001_doc0001.pdf)

Define `K = {a : a occurs in at least two H_i}`, `q = |K|`,
`K_i = H_i ∩ K`, `P_i = H_i \ K`, and `d_i = c(P_i)`. Private sets P_i are
pairwise disjoint. For every T⊆K with c(T)≤B, define the ordinary knapsack profile

`D(T) = max Σ_{i∈I} w_i`, subject to `K_i⊆T` for every chosen item and
`Σ_{i∈I} d_i ≤ B−c(T)`.

**Theorem 1.** Under the assumptions in section 3,
`OPT = max_{T⊆K, c(T)≤B} D(T)`. The union of full H_i for a maximizing profile's
selected items realizes a global optimum.

**Proof.** Fix a profile T and any feasible item selection I. Its realized set
`S_I = ⋃_{i∈I} H_i` is closed because every H_i is closed. Disjoint private sets
and core eligibility give

`c(S_I) = c(S_I∩K) + Σ_{i∈I}d_i ≤ c(T)+Σ_{i∈I}d_i ≤ B`.

It completes all selected items, so nonnegative weights give
`F(S_I) ≥ Σ_{i∈I}w_i`. Hence D(T)≤OPT for every T.

Conversely take an optimal closed set S*. Let I* be all items it completes and
`U* = ⋃_{i∈I*} H_i`. U* is closed, is contained in S*, and completes exactly the
same patterns: each originally completed pattern is in the union, and containment
prevents a newly completed pattern. Thus `F(U*)=OPT` and `c(U*)≤B`.
Choose `T* = U*∩K`. Every i∈I* is eligible and disjoint private sets give

`c(T*)+Σ_{i∈I*}d_i = c(U*)≤B`.

I* is a feasible selection in D(T*) with value OPT. Therefore D(T*)≥OPT,
proving equality. The union realizing a maximizing profile is feasible and
has value at least OPT, so it realizes OPT. ∎

T is a **reservation**, not an acquisition. The returned plan omits unused
reserved actions and is the union of selected full closures. Arbitrary masks
cannot cause an invalid acquisition. In fact K itself is prerequisite-closed:
every prerequisite of an action in two H_i occurs in those same two H_i.

```text
close all witnesses; count action incidence; find K
best ← empty acquisition set
for every T ⊆ K with cost(T) ≤ B:
    eligible ← {(d_i, w_i, H_i) : H_i ∩ K ⊆ T}
    I ← ordinary 0–1 knapsack(eligible, B − cost(T))
    S ← union of full H_i for i in I
    best ← whichever of best and S has greater realized F
return best
```

Two DP layers correctly handle zero-private-cost items, duplicate closures,
and empty patterns without repeatedly counting an item. Closure construction
uses graph traversal and bitset unions; a simple bound is O(n(n+e)+mn) elementary
incidence work for n actions and e prerequisite edges. After preprocessing,
the core algorithm takes O(2^q m(B'+1)) knapsack transitions, where
`B'=min(B,Σ_a c(a))`. With unit costs B'≤n, this is fixed-parameter tractable in q.
For binary-encoded arbitrary costs it is **pseudopolynomial**, not FPT in q alone:
q=0 already includes ordinary knapsack.

Each arithmetic comparison and action-union mask has its ordinary bit cost;
the transition count is not a bit-complexity claim. Streaming profiles needs
O(B') DP entries, each storing value and an n-bit realizing mask. The prototype
stores all profiles for certificates, adding O(2^q m) item records. Planning
uses **zero experimental queries**. Executing a chosen plan takes |S| paid
actions, with total unique cost≤B.

Why the 1994 theorem subsumes this result: replace every nonempty private set P_i
by one element of cost d_i. Different such elements never share a witness.
Order them before the core elements; the interaction frontier in the original
recurrence is contained in K. Core enumeration is a transparent special case,
not a new parameterized algorithm.

## 5. Complete proof: bounds survive misleading advice

Let U_T be the fractional relaxation of D(T), allowing each item fraction in
[0,1]. Include eligible zero-cost items, sort others by w_i/d_i, and fill the
capacity fractionally. The implementation uses exact rational arithmetic.

**Theorem 2.** A feasible incumbent L and all profile relaxations give
`L≤OPT≤max_T U_T`. If some profiles are solved or safely pruned, replace their
bounds by L; every unresolved profile must retain its valid bound. Therefore

`L≤OPT≤U = max(L, max_unresolved U_T)`.

For U>0, `L/OPT ≥ L/U` whenever OPT>0. If U=0, the optimum is zero. An exact
certificate is obtained when U=L.

**Proof.** Fractional feasibility relaxes integer feasibility, so D(T)≤U_T.
Theorem 1 gives OPT=max_T D(T). Every processed profile was realized and compared
with the incumbent; its exact value is at most L. A profile pruned when its
bound is at most the incumbent also remains bounded by the later, nondecreasing
L. Taking the maximum over all profiles proves the bound. Feasibility proves
the lower inequality. Division proves the stated fraction. ∎

```text
compute a valid fractional U_T for EVERY feasible core profile
order profiles using advice; append omitted profiles, discard duplicates
for profiles in that order:
    if U_T ≤ incumbent: prune
    else if planning limit permits: solve D(T), consider its realized union
    else: retain U_T as unresolved
return realized plan and [incumbent, max(incumbent, unresolved bounds)]
```

Advice may be a completely misleading finite integer-mask sequence. It affects
order, never feasibility, rewards, bounds, or completeness. The guarantee assumes
no confidence calibration. Default ordering uses the verified upper bound; it
already supplies the helpful order in our demonstration, so the experiment
does not establish an advantage from LLM advice.

This is standard fractional relaxation and branch-and-bound reasoning. Computing
all profile bounds costs O(2^q m log(m+1)) arithmetic operations before the first
limited DP solve. If r profiles are solved, add O(rm(B'+1)) transitions. The
`max_profiles` control does not eliminate exponential preprocessing. Any savings
concern optimizer computation; expensive experimental-query cost remains zero.

The usual submodular residual-singleton certificate is invalid for conjunctions:
one two-action pattern has zero singleton gains at the empty set but positive
optimum at budget two.

## 6. Complete counterexamples and information limits

### Shared investment defeats correctly deduplicated greedy

For integer m≥3, take setup s of cost m, m leaves l_i of cost one requiring s,
and target patterns `{s,l_i}` of weight m. Add 2m independent singleton distractors
of cost and reward one. Budget B=2m. There is only one shared action, pattern
size is at most two, and prerequisite depth is one.

**Proposition 3.** Greedy selecting the affordable witness with largest actual
additional completion reward per newly acquired unique cost obtains 2m; OPT=m².
Its ratio 2/m tends to zero.

**Proof.** Until setup is acquired, every target has density m/(m+1)<1, while
each unused distractor has density one. Distractors change neither target cost
nor target value. Greedy buys all 2m distractors and exhausts the budget.
Without setup any solution has value≤2m. With setup, at most m unit actions
remain affordable. With k leaves and j distractors, k+j≤m and
`mk+j≤mk+(m−k)=m+(m−1)k≤m²`. Setup plus all m leaves attains m². ∎

The best single witness is worth m, so choosing the better of that and greedy
does not repair the failure. This example charges every shared action once;
its gap is not caused by duplicate computation. **Both seeded controls solve
the family optimally**, so it does not demonstrate a gap against them. For
residual-density seeding, the enumerated seed containing one target purchases
setup; each remaining leaf then has marginal density m>1 and all leaves fit.
For allocated-density ordering, each target's allocated cost is `m/m+1=2`,
so its density m/2>1 outranks every distractor; even the empty seed buys all
targets within 2m. Thus these control results hold throughout the slider family.

### Coverage can be correct for the wrong objective

Four actions cost one; budget two. Two distractors cover three disjoint facets
each and earn completion reward one each. Actions a,b cover one facet each and
jointly earn completion reward 100. Coverage greedy chooses distractors,
correctly attaining optimal coverage six, but earns completion reward two.
The completion optimum earns 100. This proves no cross-objective guarantee;
it does not refute the standard coverage theorem. The executable artifact
records the exact coverage masks as well as all completion values.

### Pair requirements alone are not an easy structural restriction

**Proposition 4.** Exact completion optimization is NP-hard even with no
prerequisites, unit action costs, unit rewards, and pairs only.

**Proof.** Given a graph G and integer k, make its vertices actions and each edge
a pair witness. Set budget k. F(S) is the number of edges induced by S. It
attains `k(k−1)/2` exactly when G contains a k-clique. This polynomial reduction
from CLIQUE proves the claim. ∎

This is the known Densest-k-Subgraph special case, not a new hardness theorem.
High sharing is the obstacle even when witness rank is only two. Small q and
bounded frequency/laminar structure are different restrictions.

### Revealed actions make clairvoyance too strong

Initially there are n≥2 indistinguishable roots, each costing one. A hidden
instance index J determines the unique root that reveals a previously
unavailable child. Executing that child costs one and earns verified reward one.
Other roots reveal nothing. Budget two; all instances supply identical advice.

**Proposition 5.** For every randomized controller there is an instance where
its expected reward is at most 1/n, while a clairvoyant controller earns one.
A deterministic controller has an instance with reward zero.

**Proof.** Let p_j be the probability the first action is root j. Success in
instance J requires this first root to be J: finding it on the second action
leaves no budget to execute the child. Thus expected reward≤p_J. Since
Σ_j p_j≤1, some p_J≤1/n. A clairvoyant controller chooses J then its child. For
a deterministic controller, choose a different J than its first root. ∎

This holds with unlimited compute, shallow reveal structure, no sharing, perfect
verification, and unit costs. It is **not** an impossibility against the same-
information optimum. With a known uniform prior on J, that optimum also equals
1/n. The executable Bellman recurrence pays both reveal and child execution;
for general integer budget b it returns `min(n,max(0,b−1))/n`. A separate
hidden-box oracle pays once and rewards on opening, returning min(b,n)/n.

The recurrence uses state (unopened count, whether the child is available,
remaining budget). If a child is available and budget remains, execute it. Else
probe a root, transitioning to child-available with probability 1/unopened and
to another failure with the complementary probability. Stop at zero budget.
There are O(nb) possible cached states, O(1) symmetric-action transitions per
state, and at most b actual paid actions. The uniform outcome model is an
explicit assumption; it is not inferred from LLM confidence.

## 7. Matched-cost experiments

All policy runs share the same action identities, available records, completion
evaluation objective, and budget. Coverage optimizes its separate facet objective.
Costs are charged on the union of actions, including prerequisite
closure. There are no model calls or live experiments. `experimental_queries=0`
means the planning runs acquire no hidden measurements; `unique_cost` is the
simulated cost of executing their selected plans. A smaller selected cost is
reported rather than silently padding the plan with useless work.

Controls are deduplicated facet coverage, singleton completion, residual-union
witness density, uniform random acquisition over 32 fixed seeds, two-witness-
seeded residual density, and Arulselvan's allocated-density two-seed method.
The last follows the published pseudocode and counts all incidentally completed
patterns after each seed run as an explicit free enhancement. Its approximation
proof is not reproved here; a reviewer flags an unresolved presentation issue
in that published proof in the literature audit. Our exact results do not rely
on it.

Exact action enumeration supplies an independent tiny comparator. The additional
unit tests use raw witness/prerequisite masks, avoiding the solver's closure and
value helpers. `candidate_evaluations` records each policy's own candidate
evaluations, not comparable black-box oracle calls. Wall times are single local
runs and are diagnostic; they are not controlled performance benchmarks.

**Synthetic shared-setup results:**

| m | Budget | Deduplicated witness greedy | Both seeded methods | Core exact |
|---:|---:|---:|---:|---:|
| 3 | 6 | 6 | 9 | 9 |
| 4 | 8 | 8 | 16 | 16 |
| 6 | 12 | 12 | 36 | 36 |
| 8 | 16 | 16 | 64 | 64 |

The action oracle enumerates all subsets for m=3,4. Larger rows are checked
against the proved m² optimum. A separate caching-only control compares the
same m completed targets: duplicated cost m(m+1), union cost 2m. That arithmetic
improvement is explicitly a caching effect, unlike Proposition 3.

With m=32, one helpful profile solve reaches `[1024,1024]`; one misleading solve
returns `[64,1024]`; finishing the second solve returns `[1024,1024]`. Default
upper-bound ordering is already helpful. This demonstrates honest certificates
under bad advice, not learned-query superiority.

**Finite audits:** 5,120 exhaustive four-action singleton/pair reward-family and
budget combinations; 2,400 weighted-DAG/advice certificates over 600 random
instances. Zero exact-oracle mismatches or invalid bounds. An independent
reviewer additionally checked 960 DAGs/3,481 budgets and 900 DAGs/10,800 actual
solver certificates. The checked-in regression suite has 64 tests. These counts
check implementations; the proofs above establish the general statements.

### Frozen biological mechanism audit

Only the hash-pinned January 2018 CIViC release is accepted by the script. It
contains 2,372 rows and 1,293 numeric PMIDs. Group context is the exact tuple
`(gene_id,variant_id,disease,drugs,evidence_type,evidence_direction,clinical_significance)`.
There are 384 publications appearing in multiple such contexts and 192 contexts
with at least two publications. Thus reusable source acquisition is present.

We freeze one specific pair—the two smallest numeric PMIDs—for every eligible
context, with weight one. This defines a **two-citation audit packet**, not an
independent-evidence or biological-truth verifier. All 192 contexts are retained
in lexicographic groups of six. Each packet has at most 12 source actions,
unit simulated costs, and budgets at one-third, one-half, and two-thirds of its
source count (rounded down, at least one; duplicate budgets removed).
This produces 32 packets and 95 budgeted instances; 93 have positive optimum.
The packet construction is fixed before policy execution and uses no future
labels. Core sizes happen to be 0–4 within these deliberately small packets.

| Policy | Mean completed-packet reward / optimum | Worst ratio |
|---|---:|---:|
| Deduplicated coverage | 0.411111 | 0 |
| Singleton completion | 0.919355 | 0.25 |
| Deduplicated witness | 0.969534 | 0.5 |
| Two-seed witness | 1 | 1 |
| Allocated two-seed | 1 | 1 |
| Shared-core exact | 1 | 1 |

All 95 exact results match action enumeration. Means exclude only zero-optimum
cases. Coverage facets include all historical contexts attached to packet sources,
including contexts outside the six rewarded patterns: its lower completion
score is an objective mismatch, not evidence that it optimizes coverage badly.
Both seeded methods erase every measured completion gap.

These citation-packet comparisons are structural simulations, not live branch or
experiment trajectories. Paper costs and packet rewards are declared
simulation choices. Distinct PMIDs can share experiments. Lexicographic small
packets deliberately localize sharing and may cut cross-packet reuse; they do
not validate global tractability. The full context graph has a large shared core
(384 sources; 68 among multisource contexts before fixing pairs).

No later labels are loaded or purchased in these deterministic experiments. The separate
revealing-action simulation deliberately charges observations. The packet prototype accepts
only the pinned old file.

## 8. Failed approaches and remaining research boundary

- A new “shared evidence knapsack” theorem was ruled out by SUKP and the original
  frontier DP. The exact core theorem is useful but not novel.
- Pair lookahead is not a novel approximation argument. The pair-only model
  contains Densest-k-Subgraph; stronger restrictions must do the work.
- Deduplicating greedy fixes repeated charges, but not setup investment.
- The tested strongest seeded methods match exact. There is no measured
  completion advantage over them on these historical packets.
- Adaptive-submodular guarantees do not follow from graph evolution or AND
  patterns. Conditional marginal value can increase after another success.
- Arbitrary LLM heuristics cannot justify clairvoyant comparisons when useful
  actions are hidden. A prior, reveal model, or weaker comparator is necessary.
- Advice-controlled exact search supplies a certificate; calling fewer DP solves
  “fewer experiments” would be incorrect. All bounds still require exponential
  core preprocessing in this implementation.
- An initial larger synthetic sweep spent excessive time in repeated seeded
  greedy computation. The final full-baseline sweep uses m≤8, and the larger
  advice-only examples are separately labeled. No timed-out result is reported
  as a completed benchmark.

A credible publication attempt must extend beyond these known results. The
specific open question is a resource-bounded, same-information adaptive guarantee
when a small evolving interface carries shared observations between otherwise
private search processes. It needs a precise joint outcome/revelation model,
valid context-dependent reuse, and a bound that differs from existing SUKP,
Boolean-evaluation, and Markov-search results. We have no proof or established
conjecture for that extension. Starting a publication claim now would be premature.

## 9. Concrete architecture recommendation and demo artifact

Keep the scientific claim graph, agent lineage, and reusable-action DAG as
different relations. A small research-only action manifest is enough; do not
replace the graph database. Read full canonical evidence records instead of
display digests when forming coverage or completion patterns.

| Required record / change | Purpose | Estimated implementation effort |
|---|---|---|
| Immutable action key: inputs, code/tool version, relevant context, randomness/result version, visibility | Establish when paying once is valid; make incompatible contexts separate actions | 2–4 hours for a replay-only adapter, longer for live tools |
| Prerequisite IDs and unique cost by action; incurred/planned cost distinction | Charge shared work consistently; distinguish initial leaf costs from continuation | 2–3 hours once a replay action catalog exists |
| Frozen pattern ID, one required-action set, weight, verifier definition/version | Make the completion objective checkable and prevent alternative-path double counting | 1–2 hours for explicit fixtures plus scientist review |
| Candidate/snapshot hash, selected IDs, realized union, lower/upper bound, timing | Reproduce a selection certificate and expose unresolved optimization | 1–2 hours to connect this stdlib prototype |

These are estimates and proposed interfaces, posted to the Board before any
shared edit. This research does not implement them in production. Domain-specific
rules belong in the pattern/verifier adapter; the optimization remains domain
agnostic. A scientist should choose meaningful patterns before algorithm tuning.

The [standalone demo artifact](demo.html) shows the costly shared prerequisite,
the exact and greedy values, the strong seeded control, and the historical
completion comparison. Its labels state the deterministic objective and its
limits. A judge can see both the attractive mechanism and why the evidence does
not support a novelty or forecasting claim.

Final recommendation: **retain greedy for the hackathon delivery; adopt this
existing exact specialization as the policy lab's small-instance certificate.**
The research contribution delivered here is a rigorous formulation, a meaningful
greedy limitation, a comparator boundary, and reproducible negative evidence
against overstating a new method.
