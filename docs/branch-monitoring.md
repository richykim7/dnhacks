# Branch monitoring implementation

## Checkpoints and allocation

The first implemented stage is the research controller. Each `Explorer.run` completes at most one
bounded round, ending in an actual child-authored report or durable reporting failure. The CLI uses
`run_investigation` to apply explicit parent allocations. The report schema and validation live in
`explorer/control.py`. Reports reference existing work; the parent receives bounded ordinary research records (including code/results, with coverage declared), not a private monitor value. Report references are assertions for inspection, not
independent verification of a finding.

New state is in `<trace_dir>/runtime/control.sqlite3`, beside the ordinary event journal. It contains
no private scores. Report version fixes each decision's identity. Continuing resets only the per-round
allowance. Forking atomically reserves all child slots and transfers the original worker to management.
A launch recorded as `launching` without a saved session stays blocked after restart: repeating a fork
could duplicate paid work. Existing children resume their stored transcript and control state.

New ordinary investigations are unbudgeted by default: no app model/report/experiment deadlines,
lifetime action/round/depth/tree caps, or custom output-token ceiling. Checkpoints still request parent
allocation (18 actions initially by default), and cancellation remains available. Explicit bounded
monitoring runs retain their frozen contracts and report repair policy. An outage can still block
work. `reporting_blocked` requires explicit recovery; normal restart does not erase a recorded failure.

Operational caps are not the fixed statistical success horizon. No trajectory model, calibrated
threshold or scientific-performance result is established by these controller tests. The private collection/comparison and separate operator service are described below.

## Private monitoring pipeline (inactive until a corpus is ready)

The private package is `dnhacksbio.branch_monitoring`. Nothing in `Explorer`, the ordinary research
API or the UI starts its worker. Corpus ingestion and actual trajectory collection/scoring/training
are explicitly deferred by the user. All current monitor tests use deterministic synthetic fixtures.

The operator enrolls episodes before their first observed action. An episode fixes its objective,
starting evidence IDs, group/root IDs, terminal budget, allocation and sampling policies, corpus hash,
verifier model/prompt, rubric and disclosure boundary. Re-enrollment cannot refresh those values.
A preselected calibration unit is unique within a related investigation group. Select that unit
before knowing its outcome; filtering for the most successful child would invalidate calibration.

A minimal enrollment file has this shape (values shown are examples, not a validated PDAC policy):

```json
{
  "episode_id": "study-episode", "run_id": "study", "root_id": "study", "group_id": "related-task-1",
  "objective": "Resolve the declared research question", "initial_evidence": [], "start_sequence": 0,
  "calibration_unit": true, "subgroup": "data-preparation",
  "protocol": {
    "policy_id": "parent-allocation-v1", "rubric": "A new, relevant, verified, nonduplicate finding supported by artifacts; useful refutation counts",
    "verifier_model": "<pinned model>", "verifier_prompt_version": "subtree-prefix-v1",
    "corpus_hash": "<frozen snapshot hash>", "budget_unit": "research_actions", "terminal_budget": 288,
    "disclosure_boundary": "after-frozen-study", "sampling_policy": "preselected-root-v1"
  },
  "outcome_policy": {
    "assessor_model": "<pinned final assessor>", "prompt_version": "subtree-outcome-v1",
    "verification_policy": "legacy-submission-v1", "adjudication_seconds": 600,
    "assessment_timeout": 90, "max_candidates": 100, "initial_snapshot": []
  }
}
```

The example's 288-action horizon is not a recommended success deadline. The runtime now enforces
prospective subtree contracts in `explorer/budget.py`, in the same SQLite transactions as parent grants.
Pass `--budget-spec contract.json` to the explorer CLI; Python callers use `subtree_budget`.
An explicit empty budget spec selects 43200 summed operation seconds and 2880 research actions, with
600-second research operations, 600-second report/judge calls and 10-second fork launches. These are
bounded-mode defaults, not empirically selected scientific horizons. Unbudgeted runs cannot supply a
finite monitor horizon. Restart loads the original contract;
a changed contract or retrospective enrollment is rejected. Nested explicit budgets charge every ancestor.

Before research, the controller reserves up to three mandatory report attempts. A fork reserves each
child's action and report grants atomically, with a share of remaining research time. Unused grants return
at a valid checkpoint or a failed launch. Research, report, judge and launch operations reserve time
before dispatch, then settle measured duration. New research must fit its full operation ceiling;
small residual grants force reporting rather than launching an underfunded action. Concurrent descendants cannot overdraw the shared ledger;
new IDs and continuations do not reset it. A spent research allowance forces a real report before ending
allocation. Report/parent failures remain operational states, not negative scientific labels.

Seconds are summed operation wall time, including waiting inside an operation, not GPU/CPU-seconds or
money. Async deadlines request cancellation; a backend that overruns or cannot confirm cancellation is
recorded as a budget violation, charged conservatively and blocked from further dispatch. Unsettled
operations survive a crash without an automatic refund or retry. This is not process isolation or a
hard operating-system compute quota. Session connection setup is inside the corresponding funded research/report call. Session teardown
and runner bookkeeping are not model/tool compute. External legacy verification is not timed by this
ledger; the private assessor has its own frozen adjudication allowance and measured cost record.

The collector supports `research_actions` and `accounted_seconds`. Bound episodes read authoritative budget snapshots saved with each checkpoint. Legacy checkpoint
counters remain available for old records. Outcome collection must bind the runtime contract before
research; legacy runs that already spent work cannot be enrolled retrospectively. Pilot horizon selection, real rollouts and calibration remain deferred.

Run these commands only under the operator account after corpus readiness and frozen enrollment:

```sh
python scripts/run_explorer.py --run-id study --trace-dir /research-traces --prepare-only
python -m dnhacksbio.branch_monitoring prepare --state /operator/monitor --trace-dir /research-traces --spec enrollment.json
# Start the same run with the same goal/database/card/trace arguments when the corpus is ready.
python scripts/run_explorer.py --run-id study --trace-dir /research-traces
python -m dnhacksbio.branch_monitoring score --state /operator/monitor --trace-dir /research-traces --watch
python -m dnhacksbio.branch_monitoring label --state /operator/monitor --trace-dir /research-traces --episode-id study-episode --watch
python -m dnhacksbio.branch_monitoring export --state /operator/monitor --output /operator/episodes.json
python -m dnhacksbio.branch_monitoring fit --data /operator/episodes.json --output /operator/model.json
python -m dnhacksbio.branch_monitoring calibrate --data /operator/episodes.json --model /operator/model.json --output /operator/calibration.json
python -m dnhacksbio.branch_monitoring evaluate --data /operator/episodes.json --model /operator/model.json --calibration /operator/calibration.json --output /operator/evaluation.json
```

The worker reads the journal through each checkpoint's fixed cursor and resolves only ordinary research
inputs/observations and reports. It never reads raw reasoning transcripts, current KG state, final labels,
private experimental results, or private human feedback. Prior score predictions and outcomes never
enter verifier inputs. Oversized inputs and verifier failures are unavailable observations, not zero.
Each checkpoint stores a prefix hash, private score/statistic, budget, frozen scoring identity and
verifier time/token overhead. Repeated worker polling cannot rescore a saved checkpoint or mix model
versions in one episode. The worker writes only its separate private SQLite store. A bound, closed episode may still replay
historical checkpoints through its frozen terminal cursor, so final-label timing cannot erase training
histories. This never authorizes post-endpoint observations or places labels in verifier prompts.
Exported cost summaries include later prefix-replay overhead without rewriting the immutable label.

`outcomes.py` binds an executable final-assessment workflow before any admitted operation. `prepare`
checks the exact subtree's controller contract, current cursor and initial evidence artifacts. It freezes
assessor model, prompt/collector/verification versions, rubric, initial snapshot and adjudication limits.
Nonempty initial snapshots contain `{finding_id, claim, artifact_refs}` with verified content-addressed
blob references; their IDs must match `initial_evidence`. The runtime contract and outcome policy are
part of the fitting/calibration protocol identity, without unique run timestamps leaking into that hash.
Use an explicit contract for a sampled child before its work; root enrollment does not automatically
enroll every future descendant as an independent calibration unit.

The `label` worker reads the controller and journal without writing either. It waits for a durable subtree
endpoint and reconciles cost/action totals against admitted operations. It freezes only experiments
completed and submitted before that endpoint, gathering their actual code, stdout, parsed results and
source-event references. Exact baseline replays, repeated submissions and duplicate artifact bundles
cannot earn another finding. `legacy-submission-v1` requires the matching legacy `CANDIDATE` soundness
event from the verifier producer. `registered-receipts-v1` additionally supports the registered private
methods below. A receipt or large e-value is never treated as a legacy RESULT or universal success gate.

The frozen assessor sees these artifacts, the initial snapshot, objective and rubric. It receives no
trajectory values, parent survival decisions, raw reasoning, human review notes or future research.
It checks relevance, nonduplication and substantive support, including useful falsification. This is an
LLM rubric proxy after the existing automated soundness gate, not expert scientific certification or an
independent rerun of the experiment. No human experts are required to exercise this initial workflow.

Verification may finish after research ends, within a deadline fixed at endpoint time. Polling never
extends it or funds new research. Assessor calls have fixed input/output/time caps and one durable claim
per artifact, preventing duplicate calls across workers/restarts. Failures stay unavailable; at expiry,
missing verification/artifacts/assessments are censored, never negative examples. A qualifying descendant
finding closes the private target successfully. A completed continuation with no qualifying finding is
unsuccessful under the frozen policy; cancellation, pruning without an evaluation continuation, or
infrastructure/budget violations are censored. More discovery requires a new declared episode.

Assessment records include endpoint, artifact/audit hashes, verification provenance, measured runtime
cost, assessor cost and prefix-verifier overhead. Labels never update research memory or human-review
status. The low-level legacy manual-record API remains available for old fixtures, but cannot close a
bound episode. The fitting/calibration/evaluation CLI accepts only workflow-qualified labels; manual
assertions and censored/incomplete outcomes are excluded. Real assessor selection, rollout collection
and empirical validation still await corpus readiness.

Training uses one logistic classifier per prefix length and the paper's class-prior-corrected odds ratio.
Related roots stay in one deterministic group partition. Training weights roots equally and episodes
within roots equally, avoiding dominance by large trees. Unsupported lengths and missing-prefix scores
remain unavailable. Calibration uses one preselected episode per independent root/group and the maximum
statistic over each complete successful history. Fitting, calibration and test overlap is rejected,
including related groups. Protocol and fitted-model hashes must match. Incomplete successful calibration
histories are rejected. These checks prevent obvious leakage; they do not establish independence or
transport validity for adaptive branching by themselves.

Algorithm 1's binomial-tail order statistic and strict `statistic > threshold` comparison are implemented.
At alpha=.045/delta=.005, 115 independent successful calibration episodes yield no threshold; at 116,
the threshold is their largest path maximum. Multiple checkpoints are not independent successes.
The comparison exports direct raw-verifier thresholding, PAC-calibrated raw scores and history ratios,
with false stops, unsuccessful detection, Wilson intervals, subgroup counts and potential saved costs
when endpoint costs were supplied. Replayed savings are not realized outcome improvements. Learned
ratios are labeled monitor statistics; no exact e-process or investigation-wide guarantee is claimed.

## Protected human view and experimental review

A separate HTTP service serves the operator console. It is intentionally absent from the ordinary
research API. Start it under an account that can read private monitor/scoring stores but is inaccessible
to research processes. Set `DNHACKS_MONITOR_OPERATOR_TOKEN` to a distinct operator-only secret of at least
32 characters, then run:

```sh
python -m dnhacksbio.branch_monitoring serve --state /operator/monitor --port 8804
```

Open that service's root page and enter the operator token. The page shell contains no private data;
every record read and review write requires authorization. No CORS access is granted. The browser keeps
the token in memory only. Keep the service local or behind an authenticated HTTPS operator gateway;
never inherit its secret into research processes. The console is a separate operator page, not an added
panel in the shared research console. Same-user unrestricted code can bypass filesystem confidentiality;
file modes and a second process alone do not solve that. Actual separate account/filesystem/network
permissions must be provisioned before private deployment. No such deployment was performed here.

The console lists enrolled children by lineage with latest statistic, count and status. Selecting a child
shows recorded points on a logarithmic statistic axis, a calibrated threshold only when available, and
checkpoint/cost rows. One reading is one dot. Missing data is unavailable, never a fabricated zero or
smoothed path. Experimental evidence is a separate panel, with method, stated null, validity policy and
provenance. There is no multiplication or splicing of sibling trajectories.

The `associate` command reads an already completed private scoring queue receipt (including canonical
aliases), joins an operator-declared run/experiment/finding and method/null/family policy, and stores an
immutable private review record. It never reruns scoring or asks the agent to fabricate `RESULT`.
Incomplete scoring remains unavailable. A human decision requires a written note; an e-value alone
never automatically promotes a finding. Existing legacy `submit` and verification paths are unchanged.

```sh
python -m dnhacksbio.branch_monitoring associate --state /operator/monitor --spec association.json
python -m dnhacksbio.branch_monitoring review --state /operator/monitor --spec review.json
python -m dnhacksbio.branch_monitoring disclose --state /operator/monitor --boundary after-frozen-study --authorize-boundary --output /operator/disclosure.json
```

Disclosure produces only an explicitly authorized boundary-specific export. Neither a private decision
nor its note updates ordinary recall, feedback or the master graph automatically. A future discovery
snapshot refresh must consume this export under the declared boundary; the shared discovery graph is
not silently changed. Registered receipt discovery and routing run automatically inside private outcome
adjudication and the standalone operator `route` worker. Human review decisions remain separate from the frozen automated outcome label.


## Registered private receipt outcomes

Use the runner action `private_experiment` with `method_id`, the operator-provided public `spec`, and
`input: {cohort_id, manifest_sha256}`. Load the corresponding experiment skill first. The runner selects
the endpoint from its operator environment and creates the request/experiment ID itself. It records
exact request bytes before dispatch; only the accepted receipt enters research observations. The
operation uses the existing action/time ledger and paused-state guard. A transport interruption is
reconciled privately against durable acceptance, without an automatic new research request.

| Outcome method | Required skill | Runner endpoint environment | Evidence contract |
| --- | --- | --- | --- |
| `paired-pathway-v1` | `expression-experiment` | `DNHACKS_EXPRESSION_ENDPOINT` | Fixed registered pathway/TF score, paired assignment or justified swap symmetry; count effects remain descriptive auxiliary evidence. |
| `dependency-chronos-v1` | `dependency-experiment` | `DNHACKS_DEPENDENCY_ENDPOINT` | Frozen Chronos table and within-block event-label exchangeability, independent confirmation units. |
| `biomarker_auc.v1` | `drug-response-experiment` | `DNHACKS_DRUG_RESPONSE_ENDPOINT` | Frozen observed-dose response and stratified biomarker association; no causal/synergy conclusion. |

For `prepare`, replace the example's `verification_policy` with `registered-receipts-v1` and add
`receipt_sources` to `outcome_policy`. Each supported method must have its own source entry:

```json
{
  "dependency-chronos-v1": {
    "directory": "/operator/dependency-queue",
    "validity_review": {
      "review_id": "study-design-v1",
      "method_id": "dependency-chronos-v1",
      "assumptions": "Document the actual independence and exchangeability review here",
      "family_policy": "Document the prospective family and selection policy here",
      "disclosure_boundary": "after-frozen-study",
      "confirmation_units_disjoint": true,
      "design_supported": true,
      "selection_frozen": true
    }
  }
}
```

This is the `receipt_sources` value, not a complete episode spec. The declarations must describe a
real operator-reviewed design; copying `true` does not establish validity. The adapter rejects missing
reviews and freezes their exact contents, queue settings, implementation hashes and preexisting
scientific identities before research. Queue paths and review record IDs are episode provenance and
are excluded from the shared fitting protocol hash; method and substantive review policy remain in it.
The actual assessment endpoint, model/rubric and all accounting rules above still apply.

At the endpoint the collector freezes eligible runner requests, including descendants. It checks exact
payload hashes, method and manifest/protocol/artifact provenance, accepted timestamps and canonical
scientific identity. Renamed aliases cannot earn another finding or claim another run's work. Existing
queue identities are excluded even if they finish later. Printed stdout receipts cannot authenticate
ownership: they cause censoring, as do registered requests used with the legacy-only label policy.
Mismatches, unavailable designs, failed jobs and unresolved acknowledgements do not become negatives.

`QueueStore` provides an opt-in completion contract enabled by these three registered stores. It records
terminal status, result, frozen settings and completion time in one SQLite transaction. Their terminal
rows/snapshots are immutable; other stores retain their existing native replay contracts. Completion after the research endpoint is allowed
only within the frozen adjudication deadline; polling never changes that deadline. A completed result
without a completion snapshot is unavailable, not retrospectively timestamped. New queues initialize
this schema normally. Upgrade existing queues only in an explicitly authorized service maintenance
window; no service was upgraded or restarted by this implementation. Frozen-software queues can require
new registrations after a code upgrade. Never rewrite their previous scientific results to make them fit.

The operator can route completed evidence while research is still running:

```sh
python -m dnhacksbio.branch_monitoring route --state /operator/monitor --trace-dir /research-traces --episode-id study-episode --watch
```

This uses the same frozen ownership/method checks and creates only private review records. It neither
calls a model nor closes an outcome, and repeated routing is idempotent. After the endpoint it retains
the same production cutoff and adjudication deadline. `label` also routes evidence automatically, so
running this extra worker is optional unless early human inspection is wanted. Human decisions and
notes never enter the final assessor or prefix verifier, and do not modify research state.

The adapter validates method provenance and fixed-p calibration arithmetic without rerunning any
permutation or model. Valid evidence, its stated null, and the frozen validity/family review enter the
private final assessor. It checks relevance, substantive support and novelty. There is no universal
p/e threshold; nonsignificance alone cannot qualify as falsification. The exact private evidence also
routes to an immutable human review record, with no automatic decision, promotion or research feedback.
Concurrent/restarted label workers retain the existing one-attempt assessment claim and private export.

**Coverage boundary:** the old uploaded-TPM learned two-sample output is explicitly diagnostic-only;
this change does not make it confirmatory. Protein, ecosystem, other native methods and standalone
stdout-only submissions are not automatically covered by these three registered contracts. Use an
explicit additional adapter before collecting training episodes that depend on those receipt methods.

## Readiness after this engineering milestone

Fixture-tested engineering covers controller budgets, lineage, prospective enrollment, receipt/artifact
collection, method verification, private assessment/review, deadline/censoring rules, historical-prefix
replay and training-eligible export. No real assessor or trajectory model was invoked for this work.

Still required before a real training study: confirm corpus readiness and freeze its snapshot; choose
and validate the actual assessor/rubric; run authorized development continuations to choose the total
horizon; freeze the sampling/allocation/family/disclosure policies and supported method population;
then collect representative completed episodes with independent fit/calibration/test groups. A separate
operator account/filesystem/network boundary is required for private deployment. Existing synthetic
tests do not establish predictive benefit or scientific acceptance. At the paper's example error targets,
116 independent successful calibration units are needed merely to permit a finite threshold, in addition
to fitting and held-out evaluation units. Statistical stopping remains disabled.
