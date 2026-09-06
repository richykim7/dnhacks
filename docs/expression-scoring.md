# Expression submission and private scoring

The discovery agent runs `python -m dnhacksbio.expression_experiment` with NPZ inputs, a JSON
specification and a stable request ID. It receives only `{"receipt": "...", "status": "accepted"}`.
Acceptance means a durable queue write, independent of whether numerical scoring later succeeds,
fails or lacks enough donors. The command does not print a RESULT or call the numerical module.
Agent instructions live entirely in `skills/expression-experiment/SKILL.md`.

## Operator setup

Install the package and numerical dependencies (`uv sync --extra evalue`) on the scoring host.
Use a frozen encoder NPZ trained on donors separate from confirmation. The existing training and
validation workflow remains in `scripts/evalue_real_data.py` and `research/learned-evalue-validation/`.
Artifacts and biological data are not bundled in Git.

```sh
python -m dnhacksbio.expression_scoring serve \
  --state /private/expression-service/investigation-001 \
  --encoder /private/models/expression-encoder.npz \
  --seed 0 --batch-pairs 8 --port 8793
```

The default listener is localhost. For a separate host, explicitly configure `--host` on a protected
network or behind an authenticated TLS reverse proxy. This service does not implement authentication;
do not expose it to a public network. Set `DNHACKS_EXPRESSION_ENDPOINT` in the experiment environment
to the reachable service URL. There is no Docker requirement.

Keep the service account, state directory and any confirmation data outside permissions available
to discovery code. Modes 0700/0600 protect against other OS users, not unrestricted code running as
the same user. Running both sides under one account is a development integration setup, not an
OS-enforced privacy boundary. Do not expose the operator export command, private DB or human reports
through agent tools, shared artifact mounts, corpus cards, recall or continuation feedback.

## Inputs and fixed protocol

NPZ keys: `Xa`, `Xb`, `genes`, `unit_a`, `unit_b`. Arrays use finite nonnegative TPM and string
identifiers (no pickle/object arrays). JSON fields are exactly `hypothesis`, `source`, `assumptions`,
`unit_namespace`, `input_scale` (the last must be `TPM`). The client does not select the encoder,
seed, architecture, batch size or stopping rule. Defaults require 48 independent donors per group.
The numerical implementation records truncation when groups have unequal sizes, validates known
training-donor overlap, and rejects repeated units. Namespaces and declarations do not prove
independence or prevent an upstream agent from inspecting uploaded data.

The diagnostic tests equality of expression distributions. It does not certify a directional gene
relationship or a causal mechanism. Predeclare independent confirmation data and the family of
attempts; blinding alone does not fix adaptive reuse of data. Existing verifier results and ordinary
exploratory statistics are unchanged and this service is not wired into family decisions.

## Durability, errors and replay

Requests commit to SQLite before HTTP 202. A retry with the same ID and identical payload returns
the same receipt regardless of worker state; changed inputs under that ID are rejected. A lost
acknowledgement should be retried with that ID. Renamed identical inputs are receipt aliases of one experiment; clients should still reuse
the original ID for transport retries. Every accepted attempt remains in the private queue.

One worker owns each queue via a process lock. Each job executes in a native child process with a
600-second timeout and one CPU thread. Numerical stdout/stderr are discarded; structured results
or failure categories are recorded only in the private DB. Failed jobs are not silently retried.
Restarting the service recovers interrupted running jobs with the same persisted inputs and settings.
An interrupted computation may therefore execute again, but it has only one durable receipt/result.

The encoder is copied into the private directory under its content hash; the worker verifies it.
Settings are frozen for that directory. Changing them requires a new queue and a predeclared new
protocol. Full NPZ inputs, declaration, input digest, configuration and numerical output are retained
for replay. The HTTP surface supports submission only: all GETs return 404, including result/status
paths. There are no callbacks into the agent journal or verification queue.

Operator-only export (write outside the discovery workspace, after the chosen disclosure boundary):

```sh
python -m dnhacksbio.expression_scoring export \
  --state /private/expression-service/investigation-001 \
  --output /private/reports/investigation-001.json
```

This exports every accepted attempt, including failures and unavailable diagnostics. Receipt IDs
join these records to experiment logs. Keep the database for complete input replay. Never feed
these exports back into an active discovery investigation.

The expression service now uses the shared `experiment_transport.py` queue and method validator
registry. Its CLI, HTTP envelope, encoder settings and private numerical routine remain compatible.
Renamed identical payloads share a canonical job; original receipt declarations are preserved in
private `aliases`. Old jobs are adopted on first submission without rescoring. Per-receipt child
locks prevent a surviving worker and a restarted service from concurrently scoring the same job.
The dependency adapter uses this transport with its own registered-cohort contract; it never treats
Chronos data as TPM. See [dependency scoring](dependency-scoring.md) for that operator setup.

## Registered paired pathway service

The second route preserves expression v1 and `learned_evalue.py`. Install `uv sync --extra dev
--extra expression` for pinned decoupler 2.2.0 / PyDESeq2 0.5.4 reference validation and optional
count effects. The pathway core uses double-precision fixed weighted sums; its reference fixture
checks `decoupler.mt.waggr(fun="wsum", times=0, empty=False)` directly. No gene-shuffle p-values
are used. Its only calibration is the existing `p_to_e` applied once to the paired assignment p.

Prepare a private NPZ with exactly `X, genes, sample_ids, unit_ids, pair_ids, condition, batch`.
`X` is samples × genes; identifiers are nonempty, trimmed Unicode arrays. Each pair contains exactly
one `control` and one `treatment` aliquot of the same donor, and each donor occurs in one pair only.
A pair must share a batch. Duplicate genes/sample IDs, nonfinite/negative values, object arrays,
forged NPY headers, oversized archives, and incomplete pairs are rejected. Counts must be integers.

For raw lanes or single cells, `expression_design.aggregate_counts` sums integer counts by donor
and condition; single-cell use also requires externally defined `cell_types` and a frozen
`selected_cell_type`. It rejects inconsistent pair/batch annotations. It does not infer cell types
or aggregate TPM. Preserve original-to-aggregate mappings in operator provenance. Missing genes
are excluded only according to the frozen coverage requirement; missing individual values fail.

Create an operator JSON registry with `schema_version: 1` and dictionaries `protocols`, `resources`,
`cohorts`, keyed by stable IDs. Unknown keys are rejected. Full required fields:

| Record | Fields |
|---|---|
| cohort | `path` (operator-local NPZ, relative to registry), `manifest` |
| manifest | `data_sha256`, `source`, `release`, `organism`, `input_scale`, `unit_namespace`, `aliases_resolved` (true), `discovery_units` (array), `confirmation` (boolean), `aggregation`, `mapping` |
| resource | `organism`, `source`, `release`, `mapping`, `weights` (canonical gene → finite weight) |
| protocol | `input_scale`, `assignment`, `assignment_justification`, `min_pairs`, `min_targets`, `direction`, `exact_limit`, `seed`, `organism`, `endpoint`, `dose`, `time`, `exclusions`, `aggregation`, `mapping`, `resource_id`, `cohort_id`, `hypothesis`, `family_id`, `count_effects` |

The operator freezes eligibility/exclusions during preparation, canonical gene mapping and donor
alias resolution, with source/release identifiers describing reproducible artifacts. The protocol
must agree with cohort/resource organism, mapping, scale and aggregation. Declared discovery donors
cannot occur in scoring input. Overlapping registered cohorts in the same donor namespace fail
unless the underlying data hash is identical; separate queues remain the operator's responsibility.
Declarations do not establish independence or protect outcomes already seen by discovery.

For the proposed TGFb pilot, freeze 100 canonical PROGENy targets and their resource release/weights,
`min_targets: 90`, `min_pairs: 12`, `direction: 1`, `exact_limit: 65536`, `seed: 0`. These are proposed
engineering settings, not a power justification. `assignment` must be `randomized-pairs` or
`swap-symmetry` with a specific justification; other designs receive private unavailable evidence.
Fair independent within-pair assignments are assumed. Matching alone is insufficient. Set
`count_effects: false` for TPM; only raw counts can enable approximate DE effects.

```sh
python -m dnhacksbio.registered_expression_scoring serve \
  --registry /private/expression/registry.json \
  --state /private/expression/queue-v1 --port 8793
```

This is an alternative service configuration on the same submission API, not an additional public
result API. The agent's `--dataset-id` specification file contains `{ "spec": {...},
"manifest_sha256": "..." }`; the public spec has exactly `schema_version: 2`,
`method: "paired-pathway-v1"`, `protocol_id`, `hypothesis`, `family_id`. The operator supplies these
values and the hash of canonical manifest JSON (sorted keys, compact separators, no NaN). The
client transmits `input: {cohort_id, manifest_sha256}`. It cannot select private paths or submit
p/e values, weights, plugins or conflicting hypotheses.

Data is copied under SHA256 into private storage; registry/settings, numerical package versions
and implementation hashes are frozen for that queue. Workers recheck hashes/versions. Private
results retain protocol, manifest, method/null/scale, coverage/exclusions, effect, p/e, assignment
settings, family, development/confirmation designation and replay hashes. Twelve complete pairs
have 4096 assignments and a maximum one-sided calibrated e-value of 63. Exact tests count ties;
larger orbits use 9999 seeded uniform assignments with the plus-one correction. The score null is
not the NB coefficient null, a mechanism, or tumor progression.

`count_effects: true` runs `~ donor + condition` PyDESeq2 privately and preserves unshrunk effects,
standard errors, Wald p and filtered BH outputs (missing values remain null). These are approximate
model-based outputs; they are never calibrated or substituted for pathway evidence. Unsupported DE
fits are reported privately alongside the separate pathway result.

Request retries and new request IDs for the same scientific protocol/data become receipt aliases
of one stored result, including after restart. Frozen protocol/cohort aliases do not add evidence.
There is no combination across adaptive pathways/families or across separate queues. Export all
accepted attempts and unique results only through the operator command:

```sh
python -m dnhacksbio.registered_expression_scoring export \
  --state /private/expression/queue-v1 --output /private/reports/pathway-v1.json
```

No eligible human paired PDAC CAF cohort is bundled or registered. GSE212041 remains development
neutrophil data; mouse PRJNA471312 is not the proposed human confirmation design. Cohort eligibility,
organism, documented randomization/symmetry, and prospective power must be audited before a locked
pilot. Synthetic fixtures validate implementation only. TF endpoints or gene-panel families require
separately frozen resources/protocols and must not replace an endpoint after inspecting its result.

### Synthetic operating-curve check

`python scripts/validate_expression_pathway.py --replicates 100` uses seed 20260906 and reports
all 18 settings with Wilson intervals and Monte Carlo standard errors. At the e ≥ 20 threshold,
4/8-donor designs cannot reject because of the attainable-evidence ceiling. With 12 donors,
rejection rates were 0%/1% for zero effect, 7%/9% for a 0.5-SD shift, and 53%/21% for a 1-SD shift
(homogeneous/heterogeneous Gaussian noise). Each rate uses only 100 synthetic replicates and is
uncertain. Sample mean e can exceed one by Monte Carlo variation; the exact small-orbit tests,
not these finite simulations, check the mean-e bound over the full null assignment distribution.
These curves do not justify a human cohort's sample size or establish power under other distributions.

Metadata-only candidate screen (2026-09-06; no expression outcomes downloaded):
[GSE123375](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE123375) describes pancreatic
disease-group microarrays, not randomized paired TGFb/vehicle TPM/count inputs.
[GSE122370](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE122370) describes skin CAF/matched
normal microarrays. The human pancreatic CAF sample
[GSM3133211](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSM3133211) describes immortalized
single CAF cells under varying PDAC:CAF co-culture ratios, not independent paired donor treatment.
None establishes the proposed eligible cohort. This limited screen is not evidence that no suitable
cohort exists; no candidate was registered or substituted into the locked design.
