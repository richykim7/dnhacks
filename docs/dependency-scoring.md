# Private dependency scoring

The first adapter accepts a frozen operator registration for a one-sided Chronos dependency
comparison. It returns a durable receipt to discovery code and stores evidence privately.
No biological confirmation pilot or actual PDAC cohort is bundled. MTAP deletion / PRMT5 in PDAC
is a candidate endpoint, not an established association, drug-response result or causal claim.
MAGeCK count ingestion and replicated interaction calibration remain a subsequent extension;
this adapter rejects guide counts and agent-supplied statistics or executable paths.

## Deployment and commands

Install this repository under a service identity that discovery code cannot impersonate. Keep
registration files, state, source data and exports outside discovery-readable mounts, artifact
roots and terminal capture. Same-user processes and mode 0700 alone do not protect against
unrestricted same-user discovery code. The HTTP listener provides submissions only; provision
network access to the operator-configured listener (default localhost:8794) as appropriate.
Do not expose this unauthenticated submission listener to an untrusted network.

```sh
python -m dnhacksbio.dependency_scoring serve \
  --state /private/dependency-queue --registration /private/registration.json
python -m dnhacksbio.dependency_scoring export \
  --state /private/dependency-queue --output /private/new-results.json
```

Export is offline/operator-only, creates a new mode-0600 file, and includes one result per
canonical job plus receipt aliases with their original declarations. No results, completion
status, counts, scoring errors or callbacks are exposed over HTTP. GET always returns 404;
POST `/experiments` returns only receipt/accepted or a generic submission error. Registration
mismatches are accepted durably and reported as unavailable privately, preventing a registration
existence/hash-validation oracle. This does not claim timing-side-channel resistance.

The queue freezes the complete registration in SQLite before accepting work. Changing settings
requires a new state directory. A worker-owner lock and per-receipt child locks serialize recovery;
interrupted jobs are requeued on service startup. Child stdout/stderr are discarded. A killed child
may be recomputed with the same frozen seed, but only one durable result row exists. Keep the queue
for retries: deleting it loses deduplication. Separate queues do not supply a global multiple-testing
ledger and must not be counted as independent evidence for the same models.

`experiment_transport.py` is shared with the unchanged expression client/service API. Adapters
register method-specific validators and subprocess modules. Request-ID conflicts are rejected,
identical retries return the same acknowledgement, and renamed duplicates share one canonical job.
Every accepted receipt ID preserves its original payload in `aliases`; repeated identical transport
retries are idempotent for scoring. Private `submissions` records every structurally valid attempt,
including retries and conflicting declarations, with timestamp and outcome; export includes this audit. A migration adopts existing expression jobs without rescoring them. Historical
duplicates already present in an old queue are preserved; migration does not validate their combination.

## Frozen registration

`registration.json` contains exactly `protocol`, `manifest`, and `rows`. Unknown fields fail closed.
JSON hashes use UTF-8, sorted keys, separators `(',', ':')`, and no NaN; use
`dependency_scoring.digest(value)` offline. Settings include full replay inputs, not external
mutable paths. Source-file hashes must be verified against the release files by the operator before
registration; the service verifies the table/manifest declarations, not a remote download.

The protocol has exactly these fields:

| Field | Required value/meaning |
| --- | --- |
| `schema_version`, `method` | `1`, `dependency-chronos-v1` |
| `protocol_id`, `hypothesis`, `family_id` | Frozen IDs and exact hypothesis copied into the submission |
| `target`, `event_gene`, `event`, `disease` | Target and deletion-gene symbols, `curated_deletion`, exact eligible disease label |
| `direction` | `stronger_in_deleted` |
| `statistic` | `block_size_weighted_mean_difference` |
| `min_group` | Integer at least 8, after exclusions and uninformative-block removal |
| `uninformative_blocks` | `exclude` |
| `permutations` | `9999` |
| `exact_limit` | Integer 1–100000, maximum enumerated orbit |
| `seed` | Integer 0–4294967295, frozen before confirmation |
| `exchangeability_justification` | Why labels are uniformly exchangeable within blocks conditional on frozen scores, eligibility and counts |
| `chronos_invariance_audit` | Implications of shared Chronos fitting/copy-number correction for that invariance |
| `block_justification`, `eligibility`, `power_assessment` | Prespecified screen/library blocks, cohort selection and sample-size justification |
| `exchangeability_supported` | Boolean; false yields unavailable evidence |

The manifest has exactly these fields:

| Field | Required value/meaning |
| --- | --- |
| `schema_version`, `cohort_id` | `1`, stable registered cohort identifier |
| `sources` | Nonempty list of `{url, release, sha256, scale}`; HTTPS source/release URLs and actual raw-file hashes/scales |
| `annotation_scale` | `curated_deleted_intact_unknown` |
| `annotation_definition` | Release-specific curated deletion definition and provenance; verify CN scale before any upstream threshold |
| `target` | Must match protocol target |
| `biological_unit_mapping` | Model/alias ID → canonical donor unit; resolve shared donors and repeated screens before registration |
| `discovery_units` | Canonical units previously used for hypothesis selection, including overlapping releases |
| `exposure` | `operator-held-confirmation` or `development`; development is privately unavailable |
| `release_overlap_audit` | How repeated releases/screens and discovery/confirmation overlap were resolved |
| `table_sha256` | Canonical hash of `rows` |

Each row contains exactly `unit_id, model_id, disease, event_status, block_id, target_effect`.
IDs are nonempty strings. Disease must match eligibility; event is `deleted`, `intact`, or `unknown`.
Effect is a finite Chronos number or null. Missing calls remain unknown; missing effects are excluded.
Duplicate models or canonical donor units and inconsistent alias mappings are rejected. Eligibility
and alias resolution must be fixed before looking at confirmation effects. The operator may reuse
`depmap_harmonize.DepMap.chronos`/`.model` readers to prepare the table; do not use its generic
mutation/CN/expression OR `lof_call` as a deletion annotation. No model is picked automatically from
repeated screens and no pan-cancer fallback is performed.

The service verifies declarations, not their scientific truth: descriptive audits require operator
review. Declaration of operator-held exposure cannot undo prior outcome access. Unknown biological
aliases cannot be discovered from opaque strings alone.

## Statistic and interpretation

Drop blocks lacking both groups. With n_s the informative block size and N their total, freeze
`T = sum_s (n_s/N) * (mean_intact_s - mean_deleted_s)`. Positive T means stronger dependency
in deleted models. Permutations preserve each block's group counts. Small orbits are enumerated;
larger orbits use 9,999 uniform draws with replacement and the frozen seed. Ties (including a
conservative floating tolerance) count as exceedances. Exact p is the full-orbit tail fraction;
Monte Carlo p is `(1+b)/(B+1)`. Apply `p_to_e(p)` once. Evidence is fixed-data, not an e-process.
There is no automatic e-BH, multiplication of overlapping tests, verifier submission or promotion.

Private results retain the canonical experiment key, protocol/manifest/table and implementation
hashes, replay protocol/manifest, Python version, null, exclusions, group/block counts, effect,
permutation configuration/attainable resolution, p and E. Missing design support, discovery overlap,
development data or insufficient support yields unavailable evidence, never a zero measurement.
Malformed registrations fail before serving; unexpected scoring failures remain private queue errors.

A request must match the entire frozen public spec and manifest digest. Changing hypothesis,
family, target, blocks or cohort cannot obtain a second valid result by renaming a receipt.
The accepted mismatched attempt is preserved with its own private unavailable record.

Validity relies on the [permutation invariance assumption](https://arxiv.org/abs/1411.7565) and
[valid-input calibration](https://arxiv.org/abs/1912.06116). The
[Chronos model](https://link.springer.com/article/10.1186/s13059-021-02540-7) does not by itself establish
exchangeability of observational deletion labels. OLS adjustment does not validate global shuffling.

## Validation and pilot boundary

Run `pytest tests/test_dependency_evalue.py tests/test_dependency_scoring.py tests/test_expression_scoring.py`.
Synthetic tests enumerate heterogeneous/unequal/tied null orbits, check mean E and rejection bounds,
show invalid global-shuffle confounding, exercise attainable resolution and a paired selective-effect
power curve, and test hashes, aliases, missing calls, retries, private failures and transport leakage.
These are software evaluations, not PDAC evidence or a biological power study.

Before an operator-run locked pilot: establish the real cohort/release and untouched donor set,
review curated deletion calls and shared-fitting invariance, justify blocks and power, freeze the
registration, and verify the service/storage identity boundary. If support is insufficient, retain
unavailable evidence. Do not expand eligibility by inspecting confirmation outcomes.
