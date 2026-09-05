# Independent adversarial review

The delegated reviewer had read-only access, did not write the solver or proof,
and independently implemented raw-mask oracles. Findings were returned to the
parent, who recorded this review. Review date: September 5, 2026. No novelty or
biological verification claim was accepted.

## Verdict and executed checks

The shared-core exact proof and fractional certificate survived review under
the stated deterministic, single-AND, nonnegative-reward assumptions. The two
seeded controls match all exact historical results, so the experiments do not
support superiority over the strongest applicable baselines.

- An independent reservation solver matched action enumeration on 960 random
  DAGs and 3,481 budgets (seed 751903, at most eight actions).
- Actual `model.py` matched an independently coded oracle on 900 DAGs and 10,800
  certificate checks (seed 195522). That oracle checked raw prerequisite and
  witness masks, avoiding the solver's `close`, `value`, and `requirements`.
- Cases included non-topological action labels, empty/duplicate witnesses,
  zero rewards, costs 1–5, zero budgets, interrupted optimization, and omitted,
  duplicated and invalid integer-mask advice. No feasibility, value, exactness,
  or bound defect was found.
- All 95 historical packet/budget cases matched action enumeration. The two
  seeded methods also matched all 93 positive optima.
- The shared-setup examples m=3,4,8 gave unseeded residual-greedy values 6,8,16
  and exact/seeded values 9,16,64.

These scratch audits are supplemental evidence. The checked-in executable audit
and 64 regression tests reproduce the relevant classes of checks; finite
enumeration is not the mathematical proof.

## Proof attacks and their resolution

| Attack / possible gap | Resolution |
|---|---|
| A reserved core mask may contain unavailable/unnecessary actions | Return only the union of selected full closures. Its cost is at most the reservation plus disjoint private costs, and it is closed. |
| Optimal solutions may contain uncompleted private work | Delete every action outside completed witness closures. Nonnegative completion reward does not fall; this union has an enumerated core mask. |
| Empty private sets can cause repeated 0-cost DP updates | Two separate DP layers count each reward once; empty/duplicate patterns were tested. |
| Anytime stopping might silently discard a better core mask | Every unresolved mask retains its fractional upper bound. Advice omissions are filled and duplicates removed. |
| Huge harmless budgets allocate huge arrays | Parent fixed `_profile` to cap B by total action cost; a budget 10^9 / one-action regression passes. |
| “Arbitrary advice” could mean arbitrary malformed objects | Scope is a finite sequence of integer masks, not unhashable arbitrary objects or an infinite generator. |
| Reported oracle counts did not count all actual score calls | Parent renamed the field to `candidate_evaluations`; per-policy candidates are not interchangeable black-box queries. |
| Hidden-box success incorrectly stands for paid revealed-child execution | Parent added a separate `revealing_action_oracle`, charging one for root revelation and one for child execution. Budget two returns 1/n; budget one returns zero. |
| Known outcomes quietly become uncertain experimental success | The report excludes uncertain success and unknown verifier outcomes from the exact theorem. |

The exact proof is a known SUKP specialization. The fractional relaxation is
standard. An approximation proof concern in the published Arulselvan paper
remains unresolved; it is described in the source audit. Its pseudocode was
checked, but our proof does not depend on its published approximation factor.

## Code and information audit

Scientific claims, evidence, contexts and citations (`litmap/graph.py`) differ
from the episodic log and agent fork lineage (`explorer/exploration.py`,
`lineage.py`). Shared stores/downloads/embeddings exist (`explorer.py:332–355`),
but an explicit action-prerequisite DAG and declared complementary rewards do
not. Those are research model changes, not already observed engine behavior.

The selector seam exists at `explorer.py:1040–1041`. Initial leaves all run
before selection (`1183–1190`); a selector replacement cannot be credited with
saving their initial acquisition cost. `_branch_digest` drops entry/evidence
identities, provenance, methods and most result fields, and truncates output
(`964–998`). It cannot establish complete reusable work or evidence coverage.

Source replacement regenerates evidence row IDs (`graph.py:121–147`), so reuse
across revisions requires source/content/version identity. Identical code on
two branch-specific datasets can produce opposite effects; globally caching by
code or claim title alone is incorrect.

Log/test reads exclude siblings (`lineage.py:74–91`, `explorer.py:402–408`), but
scratch directories are under the shared cache (`explorer.py:337`), and the
sandbox mounts that parent (`sandbox.py:70–77`). Scratch prevents collisions,
not filesystem access. Returning sibling-only findings through a global cache
changes the policy's information and invalidates a same-information comparison.

Default `/data` also exposes repository datasets. `freeze_year` filters selected
retrieval paths, while fetched titles and undated reads have differing behavior.
The engine as a whole is not a sealed historical-input sandbox. The prototype
instead accepts only the hash-pinned January 2018 file.

## Biological replay audit

Pinned SHA-256:
`8895ce10b7c119856c3cbd38d8cf08fb597dbd294b06e22eaf50c35ba0db05d3`.
The file has 2,372 rows and 1,293 numeric PMIDs. Independently counted: 392 PMIDs
support multiple evidence rows, 306 span variant IDs, and 142 span gene IDs.
The prototype's context definition gives 384 multi-context publications and 192
multisource contexts. Shared source acquisition is thus present structurally.

There is no evidence here of measured experimental complementarity or actual
reusable computational prerequisites. Distinct PMIDs can reuse an experiment.
At the initial review no live branch/experiment trajectories were found, only
CIViC snapshots and Dyport cached score tables. Parent follow-up after delivery
integration audited newly landed frozen graph-construction replays separately;
the report and `results/trace-audit.json` preserve that distinction.

The original potential mapping “any two PMIDs complete a context” would be an
OR-over-pairs objective and would invalidate the single-AND model. The implemented
mapping instead freezes one specified pair for every context. It retains all
eligible contexts, groups them lexicographically, and reads no later labels.
Costs are simulated unit source acquisitions. Pair choice, weights, and panel
sizes are declared simulation choices, not scientifically validated utilities.

Coverage facets include contexts outside the six completion rewards in each
packet. Its mean completion ratio 0.411111 measures an objective mismatch.
Residual witness greedy averages 0.969534; both seeded controls and exact attain
1.0. The strongest controls erase all measured gaps.

The full source graph's shared core is large; small packets deliberately reduce
it. Packet exactness does not establish scalable whole-corpus optimization.
Policies did not use future labels for objective design, selection, or tuning,
and no forecasting improvement is claimed.

## Remaining limits and recommendation

The solver constructs all 2^q profile bounds before its limited DP solves.
“Anytime” does not mean fast exponential-free preprocessing. General integer
budgets imply pseudopolynomial runtime; unit costs and the cap give the FPT
special case. No experimental-query savings theorem has been proved.

Retain delivery coverage for its declared objective. Use the exact solver for
small evidence-packet comparisons and certificates, and keep seeded methods in
every evaluation. The surviving contribution is a precise formulation, a
greedy failure boundary, and reproducible negative evidence against overclaiming
a new algorithm—not biological truth or forecasting lift.

Parent follow-up: oversized-budget, counter naming, and reveal/execute charging
corrections listed above are now implemented and covered by the checked-in
regression suite. The final report/figure received a second independent review
with no mathematical blocker. Parent corrected the cross-objective wording and
made plotted curves read actual result records rather than hardcoded formulas.
The independent reviewer did not make production edits.
