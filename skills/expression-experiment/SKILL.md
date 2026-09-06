---
name: expression-experiment
description: Submit receipt-only TPM distribution or operator-registered paired pathway experiments without accessing private results.
---

# expression-experiment

**One line:** Submit an independent-donor TPM expression comparison with a durable experiment receipt.
**Category:** bulk-rna-seq
**Open-source:** Repository command; Python standard library client.
**Install:** Install this repository package in the experiment environment. The operator provisions the service.

## When to use

Use for comparing the overall expression distributions of two independent donor groups.
This does not establish a particular gene's effect direction, mechanism or causality.
For GEO loading and scale checks, use `geo_expression` first. GEO microarray values and
log-transformed expression are not TPM; do not pass them to this command.

## Steps

1. Declare the hypothesis, cohorts, independent donor unit, exclusions and sample budget before
   examining confirmation data. Keep confirmation donors separate from hypothesis selection and
   training. Donor identifiers alone do not establish independence; resolve aliases across cohorts.
2. Save one NPZ with exactly `Xa`, `Xb`, `genes`, `unit_a`, `unit_b`. Matrices contain finite,
   nonnegative TPM, rows are independent donors and columns match the unique gene names.
   Use string arrays for gene/donor IDs, never object arrays. Include at least 48 donors per group
   for the default service configuration. Donors must be unique within and across groups in a
   shared identifier namespace. Do not silently aggregate repeated samples or truncate inputs.
3. Save the JSON specification below, replacing every description with the actual design.
4. Run the command. Use a unique, stable request ID for this experiment, including the investigation
   and branch identity. If transport fails, retry the same ID and unchanged files. An acknowledged
   submission needs no retry; do not generate new IDs to repeat the same experiment.
5. Record the receipt in the experiment log and continue the planned investigation. Receipt
   acceptance means the inputs were durably submitted, not that any biological claim succeeded.
   This command returns no analysis statistics. Do not invent a `RESULT`, submit the receipt as a
   verified finding, or attempt to read service files. Follow the separate method guidance for
   exploratory analysis; keep its observations separate from this submission.

## Run

`experiment.npz` and `experiment.json` are input artifacts in the experiment's writable directory.
The command uses the operator-configured `DNHACKS_EXPRESSION_ENDPOINT` (default localhost:8793).
If the service is unavailable, report the setup problem; do not replace the command with custom analysis.

```json
{
  "hypothesis": "Declared comparison of population A and population B",
  "source": "Accession, release and cohort selection",
  "assumptions": "Independent donors; confirmation exclusions and sampling design",
  "unit_namespace": "Shared donor identifier system",
  "input_scale": "TPM"
}
```

```sh
python -m dnhacksbio.expression_experiment \
  --input experiment.npz --spec experiment.json \
  --request-id investigation-branch-experiment-001
```

Expected stdout: `{"receipt": "investigation-branch-experiment-001", "status": "accepted"}`.
When using `run_experiments`, first load this skill and declare
`method_id: "expression-experiment"`. A receipt without a `RESULT` line is expected.

## Registered fixed pathway endpoint

For an operator-frozen paired pathway protocol, use the registered cohort route instead of an
uploaded NPZ. The operator supplies the cohort ID, manifest hash, and exact public specification.
The service must be running `dnhacksbio.registered_expression_scoring`; the legacy encoder
service continues to support the `--input` route above. The two input flags are mutually exclusive.

```json
{
  "spec": {
    "schema_version": 2,
    "method": "paired-pathway-v1",
    "protocol_id": "operator-protocol-id",
    "hypothesis": "Exact operator-frozen hypothesis",
    "family_id": "operator-family-id"
  },
  "manifest_sha256": "operator-provided-64-character-sha256"
}
```

```sh
python -m dnhacksbio.expression_experiment --dataset-id operator-cohort-id \
  --spec experiment.json --request-id investigation-branch-experiment-002
```

This tests the declared fixed transcriptional score under the frozen design. It does not establish
pathway function, progression, or mechanism. Unsupported pairing, coverage, or assignment designs
produce no available private evidence. Registered public/development inputs do not become untouched
confirmation merely because they have a dataset ID. No eligible human PDAC CAF cohort is bundled.
The runtime captures the receipt; do not reconstruct statistics or query results. Renamed retries
remain aliases of one experiment, never additional evidence or fresh e-process increments.
