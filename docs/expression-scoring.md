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
acknowledgement should be retried with that ID. New IDs are distinct experiments, so clients must
not mint a fresh ID for a transport retry. Every accepted attempt remains in the private queue.

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
