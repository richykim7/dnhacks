# Child checkpoints, parent-controlled forks and private trajectory monitoring

Consolidated planning document, 2026-09-06. Baseline: `3ed1107`.
Records the user's agreed design, including full-subtree outcomes and checkpoint visualization.
Implementation status: checkpoint reporting, explicit parent allocation, a private observation-only
monitor pipeline and separate authenticated operator console are implemented. User deferred actual
trajectory scoring/training until corpus ingestion. Controlled statistical deployment remains blocked
on representative rollouts, pilot-selected horizons, calibration and account separation. Shared runtime
action/time reservations and artifact-based private outcome labeling are implemented and fixture-tested.
Outcome adapters cover legacy submissions and runner-owned registered pathway, Chronos dependency
and biomarker/AUC receipts, including private review routing. Other receipt methods are not implicitly
supported. Real assessor/rollout validation remains required before statistical deployment.
See [implementation and limitations](../docs/branch-monitoring.md).
The paper analysis remains in [the research review](../docs/evaluator-tree-search-review.md).

## Intended behavior

Children do useful work in bounded rounds, report progress, and propose next work. Their parent
decides whether to continue, fork, finish or prune. An approved fork is executed by orchestration
code, rather than left as optional advice to the child. Private statistical monitoring may later
help decide when to stop a line. Its target is whether the subtree rooted at a child will produce a
qualifying new outcome within a fixed total budget, including work by descendants. It does not itself
assess whether a biological finding should be accepted.

**Reaching an action limit pauses progress and forces a report.** The agent must write that report
in a separate report-only turn. A runtime-generated summary is not a substitute. Budget exhaustion
alone is neither scientific failure nor permission to prune.

## Pre-change baseline and issues addressed

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

## Full-subtree outcomes and evaluation horizon

**Reporting cadence is not the success deadline.** The proposed 18-action round forces a report;
it does not require a scientific win. Evaluate complete continuations over multiple rounds and,
where authorized, generations. At the start of a monitored subtree episode, fix its objective,
initial evidence snapshot, terminal total budget and continuation/allocation policy. At every
checkpoint predict the same endpoint: will this subtree deliver a qualifying new outcome by that
endpoint? Remaining budget decreases; reports and forks do not refresh the deadline.

There is no justified numerical evaluation budget yet. In a development pilot, measure qualifying
outcomes versus cumulative compute and compare longer horizons to find delayed useful outcomes.
Choose a budget compatible with intended deployment, then freeze it before threshold calibration
and held-out testing. Count all descendant work, reporting and judge overhead; retain separate token,
tool-compute and time counters until the cost conversion is specified. Per-node action/depth caps
alone are not a subtree compute budget.

Collect the tree actually generated by the fixed policy, not every possible alternative fork.
Unrestricted branching can grow exponentially; a shared total budget bounds actual expenditure.
The new monitor stays observation-only while complete evaluation continuations are collected.
An ancestor alarm can be proposed at its checkpoints even if its eventual payoff comes from a
grandchild. That prediction target does not authorize unimplemented descendant cancellation.

The primary endpoint is **at least one relevant, nonduplicate new finding that passes the applicable
verification and the frozen evidence rubric**. A useful refutation can qualify; a nonsignificant
result alone does not establish a refutation. Any alternate milestone, such as resolving a necessary
data prerequisite, must be explicitly defined for that task before the run, rather than invented
after seeing the result. Preexisting findings in the initial snapshot do not count as new success.

| Outcome/event | Label or treatment |
| --- | --- |
| Qualifying finding from the child or its descendants | Success for the originating subtree episode. Preserve provenance of which work supplied it. |
| Complete permitted continuation without a qualifying outcome | Unsuccessful within that policy and budget; not proof the scientific idea is false. |
| Incomplete run, infrastructure failure, or premature cutoff outside the protocol | Unknown/censored; never automatically a negative training example. |
| Fork, checkpoint, submission, or parent survival decision | Action/allocation event, neither success nor failure by itself. |
| Pending evidence verification at endpoint | Await bounded adjudication of already-produced artifacts; do not mislabel queue delay as failure or add new research beyond the horizon. |

An evaluator may judge a complete natural finish under the frozen policy; a historical branch killed
by a selection rule has no observed full continuation. To estimate what further funding would have
achieved for that child, run an isolated evaluation continuation under the declared policy. Record
early termination and missing-label rates so operational exclusions cannot hide poor performance.

The rubric checks scientific relevance, method/evidence quality, information gained, and whether
concrete next steps are supported by the findings. Assess artifacts and provenance, not just the
child's narrative. The existing automated soundness gate alone does not establish relevance or
novelty. Require substantive evidence; a plausible future-work proposal is not sufficient.
No automatic points for forks, experiments, citations, submissions, verbosity or confidence. Check
duplicate evidence, unsupported claims and alternative explanations. Agents may know the scientific
criteria; private scores, confirmation evidence and assessment feedback remain withheld. A frozen
LLM final assessor is an initial proxy for rubric acceptance, not expert-certified scientific truth.

Intermediate rubric dimensions may help predict the final binary outcome; they are not a reward
sum and are not separate e-values to combine. Once a qualifying outcome is established, close this
episode's failure-monitoring target as successful. Further discovery requires a distinct objective,
budget and validated allocation policy; do not relabel success as failure or reset a stopped episode.
If confirmation is private, record target completion privately under the disclosure policy rather
than publishing the label to research agents.

## Private E-valuator integration

There are three separate responsibilities:

| Component | Question |
| --- | --- |
| Parent/judge | What next work is useful, and should it run sequentially or in parallel? |
| Trajectory monitor | Does the observed history justify stopping this child's subtree before its fixed success endpoint? |
| Biological evidence and human review | What does this experiment support, and should the finding be accepted? |

At checkpoints, a fixed verifier sees the objective, prefix-only actions/code/ordinary observations,
report, initial evidence snapshot, remaining budget, and known resource policy. Include only descendant
work already observable at that checkpoint under the declared policy. Hidden reasoning blocks are
not required. It returns a private progress score. The numerical wrapper consumes score history;
it is not another autonomous scientist.
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

Start with tens of representative completed subtree episodes to measure whether prefix scores predict
the defined endpoint; this pilot has no strong calibration claim. A leaf-only smoke test validates
plumbing, not the intended recursive pruning target. Fit, calibrate and test on separate investigations
with related tasks grouped together and mutable research memory isolated. Grouping prevents leakage
but does not make siblings independent or prove validity for adaptively selected descendants.
Use a fixed subtree sampling/continuation policy and validate any later policy change. The paper's
complete action-sequence experiments do not establish guarantees for this branching adaptation.
A corpus alone supplies neither trajectories nor outcome labels. Existing pruned logs lack
counterfactual outcomes; a reporting limit is not a negative label. A complete unsuccessful run to
the declared terminal horizon has the bounded outcome defined above.

One complete rollout supplies multiple prefix-score observations paired with its eventual label;
there is no need to restart from every checkpoint to obtain those observations. Keep one ordered
history per monitored subtree episode across continuations. Store root/episode/parent IDs, checkpoint
and prefix hash, budget/cost, policy/model/rubric versions, private verifier and monitor values, and
final label/provenance. Future evidence and final labels never enter historical verifier inputs.
An ancestor and descendant may share an outcome, but that creates correlated examples, not duplicate
independent successes. Report root, episode and checkpoint counts separately. Weight/sample histories
deliberately so long trees do not dominate simply by emitting more checkpoints.

For scale, the paper's alpha=.045/delta=.005 setting needs at least 116 independent successful
threshold-calibration trajectories just to permit a finite threshold. Fitting and final testing need
additional data; reaching that minimum does not establish power. Collecting LLM/tool rollouts can cost
much more than fitting the small model. Do not transplant a leaf threshold across all depths or claim
investigation-wide control from a marginal branch guarantee. The reference review gives further details.

## Human-facing monitor histories

Expose the following through an operator-authorized read path, separate from agent tools and recall:

- Investigation tree: latest monitor statistic, checkpoint count and operational status per child.
- Selected child: its episode history across checkpoints, with cumulative compute/checkpoint on the
  horizontal axis, monitor statistic on a log scale, and the calibrated stopping threshold. Mark
  reports, forks, continuations and stops. Monitor target completion is private review information.
- Selected finding: its experimental e-value and biological evidence in a separate panel.

These are different quantities: a larger trajectory statistic supports stopping an unsuccessful line;
an experiment e-value concerns its stated biological null. Label learned trajectory values as monitor
statistics, not probabilities or certified exact e-values. Mark uncalibrated/observation-only status;
show no active threshold where calibration is unavailable. No data means pending/unavailable, not zero.

Repeated checkpoints and children yield more readings and training rows, but changing the endpoint
alone does not create more observations. Some children still have a single dot. Display actual points
without smoothing or invented intermediate scores; do not add judge calls merely to decorate a chart.
If later monitoring continues at subtree events after a fork, specify and calibrate that observation
schedule first. Show lineage together without multiplying or splicing descendant statistics into one
cumulative e-value. Parent/descendant histories can overlap in evidence and are not independent.
Recorded checkpoint displays and a separate authenticated operator service are implemented; shared-console integration and additional post-fork observation schedules remain pending.

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

**Private scoring uses a separate outcome/review adapter.** The `private_experiment` runtime action
submits registered pathway, dependency and drug-response experiments with runner-owned request IDs.
`registered-receipts-v1` reconciles exact public request artifacts with operator queue aliases, frozen
settings and immutable completion snapshots. It automatically creates private review records after
method-specific validation. Standalone CLI stdout receipts remain unbound and cannot supply labels;
a receipt is not a valid RESULT. Scoring failures remain unavailable/censored, not negative findings.
Legacy TPM learned diagnostic outputs and other native methods require separate explicit contracts;
they are not promoted to confirmation by these adapters.

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
information can retain its existing path. A separate private review store and explicit disclosure export implement this separation. Registered receipt routing is implemented through outcome adjudication; discovery-snapshot refresh remains pending. Same-user filesystem access also needs an actual service/account boundary.

## Implementation stages and acceptance criteria

1. **Explicit rounds and reports:** change `Explorer.run`, dispatch, briefs and runtime lifecycle;
   implement tool-disabled mandatory reporting and durable pause/resume. Update UI semantics so
   checkpoint/awaiting-parent is not labeled completed or pruned.
2. **Parent allocation and enforced forks:** replace implicit promotion/continuation behavior with
   versioned parent decisions and idempotent execution. Preserve child context, provenance and resource
   accounting. Stop using experiment counts as the renewal criterion.
3. **Trace collection and monitoring comparison:** select the full-subtree horizon in a development
   pilot, freeze the rubric/policy, then add private prefix scores/outcomes and grouped
   train/calibration/test exports. Run observation-only evaluation before any monitored pruning.
4. **Private human review routing:** add operator-only evidence association and disclosure controls,
   with explicit per-method validity/family policy and human-facing checkpoint histories. Preserve
   ordinary legacy submissions; keep experimental evidence distinct from trajectory monitoring.
5. **Controlled deployment:** enable only validated branch populations/policies; compare equal total
   costs, counting reporting/judge overhead and evaluations that continue would-be-pruned children.

Acceptance checks must cover zero-action allowance entering reporting; malformed reports and model
failure staying paused; no research/tool/fork dispatch during reporting; early checkpoints and true
completion; restart at each state; duplicate approvals and concurrent budget reservations; mandatory
fork execution or explicit failure; no context/lineage loss; useful unfinished work getting a fair
continuation; and no hidden-score disclosure through errors, prompts, recall, receipts or human feedback.
Test submission before checkpoint and after earlier findings, preservation through pruning, queue drain
after worker termination, private-review provenance, and delayed disclosure without cross-run leakage.
Also test descendant success credit with provenance; no reward for forking/duplicate candidates;
fixed episode deadlines across checkpoints/forks; incomplete versus unsuccessful labels; pending
verification at the horizon; success closing its target; no future-evidence leakage into prefixes;
root-grouped exports; and truthful single-point/missing/uncalibrated displays with private access.

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
units, total subtree evaluation horizon and disclosure boundary. Suggested engineering defaults here
are 18 research actions per reporting round, warning with three remaining, and two report-repair
attempts. Tune from observed useful work and overhead;
these numbers do not imply statistical validity. Mandatory reporting, parent-authorized forks and
preservation of findings through pruning are the agreed behavioral requirements.
