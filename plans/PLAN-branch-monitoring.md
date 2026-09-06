# Child checkpoints, parent-controlled forks and private trajectory monitoring

Consolidated planning document, 2026-09-06. Baseline: `3ed1107`.
Records the user's agreed design and latest reporting correction. This task publishes the plan;
it does not implement runtime changes, collect trajectories or train a monitor.
The paper analysis remains in [the research review](../docs/evaluator-tree-search-review.md).

## Intended behavior

Children do useful work in bounded rounds, report progress, and propose next work. Their parent
decides whether to continue, fork, finish or prune. An approved fork is executed by orchestration
code, rather than left as optional advice to the child. Private statistical monitoring may later
help decide when to stop a line; it does not assess whether a biological finding should be accepted.

**Reaching an action limit pauses progress and forces a report.** The agent must write that report
in a separate report-only turn. A runtime-generated summary is not a substitute. Budget exhaustion
alone is neither scientific failure nor permission to prune.

## Current behavior and issues being addressed

`Explorer._act_fork` runs new leaves with forking disabled until they emit `done` or consume 18
actions. It waits for the sibling batch, invokes `_judge_promise`, retains up to two and enables
forking on survivors. The promise judge is already a separate LLM call owned by the parent code;
it returns relative ranks, not success probabilities. The parent conversation resumes only after
the awaited descendant work resolves.

Promoted children currently choose their own forks. `done` ends a round and can be followed by
resumption. Additional rounds depend on adding an experiment/submission, not a fresh promise
judgment. Limits are six continuation rounds, 96 cumulative actions per branch, depth six and 72
spawned child nodes per investigation. One action can be a graph lookup, up to eight experiments,
or an entire recursive fork; action count therefore does not measure compute cost well.

The change removes ambiguity between reporting and finishing, avoids treating activity counts as
scientific progress, and places approval of further work with the parent. Existing constants are
initial operational defaults to evaluate, not demonstrated optimal settings.

## Round allowance and mandatory reporting

1. Disclose the round allowance upfront. Start with 18 research actions and show remaining allowance
   in each turn. Allow an early checkpoint after a meaningful result, obstacle or proposed split.
2. With three research actions remaining, instruct the child to finish current work and prepare its
   report. It may explicitly report unfinished but promising work; do not demand a positive finding.
3. At exhaustion, stop dispatching research actions. A running action uses its ordinary completion,
   timeout or cancellation contract; reaching the step boundary is not permission to destroy its work.
4. Enter `reporting`: invoke the same child session with a report-only instruction and output schema.
   Disable research-tool dispatch and nested forks during this turn. Reserve a small, separately
   accounted token/time allowance for reporting outside the research-action allowance. Thus zero
   remaining research actions never prevents the required report.
5. Validate the actual agent report, persist it, then enter `awaiting_parent`. Parent continuation or
   expansion requires a valid report; exhaustion must not silently skip this phase.
6. If formatting fails, retry the report with the validation error and tools still disabled. Proposed
   default: two repair attempts, then durable `reporting_blocked` with explicit runtime diagnostics.
   Keep progress paused until reporting succeeds or an operator explicitly intervenes. Preserve the
   trace; do not fabricate a report, silently resume, label the science failed or let retries run forever.

Use the same validated report for voluntary checkpoints and completion requests. External cancellation
and genuine process failure remain distinct lifecycle events; the runtime cannot guarantee a model
response during an outage. Siblings may continue while one child's reporting is blocked, but its
unreported work is not eligible for automatic renewal or expansion.

Proposed report fields:

- Findings and supporting experiment/artifact/source references.
- Work completed since the previous checkpoint and unresolved questions.
- Blockers and what has been ruled out, including useful falsifications.
- Completion request, continuation proposal, or proposed fork subquestions.
- For each next step: expected information gained, feasibility, prerequisites and estimated cost.

The controller adds measured action/cost counters and immutable provenance; it does not trust the
agent's cost estimate as an accounting record. Reports contain no private biological scores,
confirmation-only data, monitor values, thresholds or alarm explanations.

## Clear lifecycle and parent decisions

| State/event | Meaning and allowed next step |
| --- | --- |
| `working` | Research actions permitted within the granted allowance. |
| `checkpoint` / allowance exhaustion | Research pauses; enter mandatory report production. |
| `reporting` | Only report generation/repair is permitted. |
| `awaiting_parent` | Valid report saved; research remains paused. |
| Parent `continue` | Resume this same child session with a concrete work objective and allowance. |
| Parent `fork` | Execute approved subquestions from this child's context, within reserved resource limits. |
| Parent `finish` | Accept task completion; no automatic continuation. |
| Parent `prune` | Stop allocating work to this line; retain all findings and pending review jobs. |
| `reporting_blocked` | Reporting failed operationally; preserve state for report retry/operator intervention. |

`done` becomes an explicit completion request with a valid final report, rather than the current
generic end-of-round signal. If the parent wants further work it must issue a new explicit continuation
decision. The runtime must not resume a supposedly finished branch merely because its experiment
count increased. Allowance exhaustion, scientific dead end, successful completion, explicit pruning,
and operational failure have distinct recorded reasons.

The parent uses the assigned objective, child's report and inspectable supporting work. It may approve
one bounded round for credible unresolved work rather than demand immediate success. Report timing
and parent decisions should be recorded individually, avoiding unnecessary waits for unrelated siblings;
comparative allocation can still use a consistent snapshot of available sibling reports.

## Parent-authorized forks

The child proposes directions because it has the detailed context. The parent can refine or add
subquestions after inspecting the evidence, and authorizes the concrete set. Require distinct questions,
expected information gain, feasible inputs/methods, and reasons to pursue them concurrently. Several
sequential tasks are not automatically several branches. Avoid duplicate siblings or forks that merely
evade a work allowance. Include adversarial testing when useful and consistent with the existing role.

After approval, code reserves the needed branch/resource slots and creates the approved descendants
from the child's saved session, with explicit objectives and allowances. The child does not get to
ignore the approved fork or substitute new subquestions. Repeated delivery of an approval must not
spawn duplicate descendants. Persist decision ID, report version, authorized children and execution state.
If limits or launch failures prevent execution, record a blocked/partial outcome and return it for a
revised allocation; never silently exceed caps or report an unexecuted fork as complete.

Use lineage IDs rooted at the child whose work is expanding, even though its parent authorized the
expansion. Retain that child's context and controller as the local manager of its descendants. Each
generation follows the same parent-approval rule. The root uses the equivalent investigation-level
controller for its initial fork. A split transfers work to descendants; it must not accidentally
double-fund an unrestricted original worker and its successors.

First implementation should gate leaf renewal and requested expansion before descendants launch.
Stopping an ancestor while descendants are active needs explicit ownership/cancellation semantics;
do not infer permission to cancel unrelated work or delete queued experiments. Keep this later case
disabled until tested. Evidence already produced survives pruning at every depth.

## Avoiding premature pruning and controlling cost

Give each new child a meaningful initial allowance. Frequent reporting is not frequent punishment:
missing a positive result, pending verification or a justified data-preparation step does not by itself
justify pruning. Judge informative failures and falsifications according to the assigned task.
Replace the experiment-count continuation rule with explicit next-work value/feasibility assessment.
Do not enforce a minimum survival fraction or automatically keep two weak branches; equally, do not
turn uncertainty into an automatic stop. Test continuation of useful slow-starting branches explicitly.

Retain action, depth and total-node caps as operational controls initially. Add accounting for tokens,
tool compute and elapsed time including descendant work; report time is counted separately but still
costs resources. Later budget tuning can use actual cost rather than equating a lookup with eight
experiments. A fork approval commits future resources; newly named descendants cannot reset the
investigation's allowance. Reserve/release grants transactionally under concurrent child decisions.

## Private E-valuator integration

There are three separate responsibilities:

| Component | Question |
| --- | --- |
| Parent/judge | What next work is useful, and should it run sequentially or in parallel? |
| Trajectory monitor | Does this child's progress history justify an early stop under its calibrated rule? |
| Biological evidence and human review | What does this experiment support, and should the finding be accepted? |

At checkpoints, a fixed verifier sees the objective, prefix-only actions/code/ordinary observations,
report, and known resource policy. Hidden reasoning blocks are not required. It returns a private
progress score. The numerical wrapper consumes score history; it is not another autonomous scientist.
The parent-owned controller enforces a resulting stop. Keep monitoring state across report/continuation
attempts; do not reset it for another chance. Parent research prompts do not receive numerical monitor
output, and a beam quota cannot revive a statistically stopped child.

Initial rollout is observation-only: record proposed child stops and continue evaluation copies to
their defined endpoint. Preserve useful branches while estimating false stops and potential savings.
Compare direct LLM pruning, PAC-calibrated raw scores and learned score-history models. If a child is
judged only once, sequential modeling has little extra opportunity; repeated meaningful checkpoints
provide the intended use case. Per-action judging is optional and must justify its cost.

[E-valuator v2](https://arxiv.org/html/2512.03109v2) uses existing verifiers and small classifiers,
with separate threshold calibration; learned ratios are not automatically exact e-processes. Known
benchmark answers supplied success labels in its experiments. Our final LLM assessor could label
completed branches, but the resulting guarantee would concern that assessor's acceptance, not scientific
truth. Freeze its rubric/model, withhold monitor output, and include useful refutations in its endpoint.

Start with tens of representative completed branches to measure whether prefix scores predict useful
outcomes; this pilot has no strong calibration claim. Fit, calibrate and test on separate investigations
with related tasks grouped together and mutable research memory isolated. Grouping prevents leakage
but does not make siblings independent or prove validity for adaptively selected descendants.
Use a fixed branch sampling/continuation policy for an initial leaf study and validate any later policy
change. A corpus alone supplies neither trajectories nor outcome labels. Existing pruned logs lack
counterfactual outcomes; pruning or exhaustion must not be labeled scientific failure by default.

For scale, the paper's alpha=.045/delta=.005 setting needs at least 116 independent successful
threshold-calibration trajectories just to permit a finite threshold. Fitting and final testing need
additional data; reaching that minimum does not establish power. Collecting LLM/tool rollouts can cost
much more than fitting the small model. Do not transplant a leaf threshold across all depths or claim
investigation-wide control from a marginal branch guarantee. The reference review gives further details.

## Candidate submission and human review

Current code permits any active node to submit its own completed, eligible experiment via `_act_submit`
without parent permission or waiting for a checkpoint. It requires a parsed RESULT and rejects the
unaudited `exploratory` method. `VerificationQueue.drain` performs automated checks, writes surviving
CANDIDATE records, and makes them eligible for the human promotion workflow. Human decisions require
a note. Review controls are currently hidden in the frontend; backend review/promotion paths exist.
Database availability can delay applying decisions. This is not immediate direct publication by a node.

Preserve submission during research. The branch monitor controls future spending, so pruning must not
remove an already submitted finding, cancel its review, or replace a human decision. A scientifically
useful completed result can coexist with little value in continuing its branch. Conversely, a surviving
branch has no automatic right to scientific acceptance.

**Private scoring requires an additional review adapter.** Today's expression command produces a receipt
and has no callback into verification/human review; a receipt is not a valid RESULT. Do not ask an agent
to read private evidence and manufacture that RESULT. Proposed operator-side routing joins a declared
finding/experiment ID, immutable receipt, scoring method/null, provenance and results into a private
human-review record. The receipt associates work; neither the agent nor the parent recreates it.
Scoring failures remain failures/unavailable, not positive or negative scientific findings.

Humans may inspect submitted work before branch completion. They should see method-specific evidence,
data limitations and whether confirmation is pending, valid or unavailable. Native e-values and
fixed-p calibrations need their stated nulls and selection/family rules; do not blindly replace the
legacy `p_null <= .05` gate with a universal e threshold. No automatic promotion based on either kind
of score. Human review cannot repair invalid sampling or repeated use of confirmation data.

**Review visibility and discovery feedback are different permissions.** Existing human decisions feed
back into exploration memory and runtime events. Reusing that path for private confirmation would leak
information even if the number itself were removed. During the frozen discovery/confirmation phase,
keep score-derived notes, acceptance/rejection, and resulting master-graph updates outside all relevant
agent views, recall and parent/judge context. Record review privately now; disclose or refresh the
discovery snapshot only at the predefined boundary. Ordinary feedback that uses no private confirmation
information can retain its existing path. This separation is future implementation work, not present
behavior. Same-user filesystem access also needs an actual service/account boundary.

## Implementation stages and acceptance criteria

1. **Explicit rounds and reports:** change `Explorer.run`, dispatch, briefs and runtime lifecycle;
   implement tool-disabled mandatory reporting and durable pause/resume. Update UI semantics so
   checkpoint/awaiting-parent is not labeled completed or pruned.
2. **Parent allocation and enforced forks:** replace implicit promotion/continuation behavior with
   versioned parent decisions and idempotent execution. Preserve child context, provenance and resource
   accounting. Stop using experiment counts as the renewal criterion.
3. **Trace collection and monitoring comparison:** add private prefix scores/outcomes and grouped
   train/calibration/test exports. Run observation-only evaluation before any monitored pruning.
4. **Private human review routing:** add operator-only evidence association and disclosure controls,
   with explicit per-method validity/family policy. Preserve ordinary legacy submissions.
5. **Controlled deployment:** enable only validated branch populations/policies; compare equal total
   costs, counting reporting/judge overhead and evaluations that continue would-be-pruned children.

Acceptance checks must cover zero-action allowance entering reporting; malformed reports and model
failure staying paused; no research/tool/fork dispatch during reporting; early checkpoints and true
completion; restart at each state; duplicate approvals and concurrent budget reservations; mandatory
fork execution or explicit failure; no context/lineage loss; useful unfinished work getting a fair
continuation; and no hidden-score disclosure through errors, prompts, recall, receipts or human feedback.
Test submission before checkpoint and after earlier findings, preservation through pruning, queue drain
after worker termination, private-review provenance, and delayed disclosure without cross-run leakage.

Report false stops on assessor-accepted branches, detection of unsuccessful branches, total cost,
task outcomes, and subgroup behavior for slow starts, data preparation and falsification. Plot monitor
paths and accepted outcomes versus total cost. Calibration alone does not ensure scientific utility.
Document all behavior changes and run repository gates in each implementation stage.

## Related tool plans and remaining choices

The parallel plans are complete and tracked: [dependency/CRISPR](evalue-dependency-integration.md),
[drug response/combinations](evalue-drug-response-integration.md), and
[pathway/TF/differential expression](evalue-expression-integration.md). They share private receipt
transport but use method-specific biological nulls; their evidence must not become trajectory feedback.

Before statistical deployment, fix the success rubric, calibration population/error target, resource
units and disclosure boundary. Suggested engineering defaults here are 18 research actions, warning
with three remaining, and two report-repair attempts. Tune from observed useful work and overhead;
these numbers do not imply statistical validity. Mandatory reporting, parent-authorized forks and
preservation of findings through pruning are the agreed behavioral requirements.
