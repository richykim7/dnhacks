---
name: dependency-experiment
description: Submit an operator-registered Chronos dependency comparison and record its durable receipt.
---
# dependency-experiment

**One line:** Submit a registered deletion-versus-intact dependency comparison; receive only a receipt.
**Category:** functional-genomics
**Open-source:** Repository command; Python standard library client.
**Install:** Install this package in the experiment environment; the operator provisions the service.

Use only with an operator-provided protocol ID, family, hypothesis, cohort ID and manifest digest.
Do not invent registrations, infer deletion from generic LOF calls, upload confirmation outcomes,
or widen a rare-event cohort after inspecting results. Chronos knockout dependency is a different
intervention from drug inhibition; it does not establish pharmacological sensitivity or causality.

Save the operator-provided declarations in `dependency.json` using exactly this shape:

```json
{
  "spec": {
    "schema_version": 1,
    "method": "dependency-chronos-v1",
    "protocol_id": "operator-provided-protocol",
    "hypothesis": "Operator-provided frozen hypothesis",
    "family_id": "operator-provided-family"
  },
  "input": {
    "cohort_id": "operator-provided-cohort",
    "manifest_sha256": "operator-provided-64-character-sha256"
  }
}
```

Load this skill before `run_experiments`, declaring `method_id: "dependency-experiment"`.
Run the command using a stable investigation/branch-specific request ID:

```sh
python -m dnhacksbio.dependency_experiment --spec dependency.json --request-id investigation-branch-001
```

The command uses `DNHACKS_DEPENDENCY_ENDPOINT` (default localhost:8794).
Expected stdout: `{"receipt": "investigation-branch-001", "status": "accepted"}`.
Record the receipt and continue. Acceptance means durable submission, not a successful finding.
No `RESULT` is expected. Do not fabricate a result, submit this receipt to verification, read service
files, or replace a missing service with custom analysis. If acknowledgement is lost, retry unchanged
inputs with the same request ID. Renaming the request does not create a new experiment.
