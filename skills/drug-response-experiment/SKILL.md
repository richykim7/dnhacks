---
name: drug-response-experiment
description: Submit an operator-registered biomarker versus drug-response AUC experiment and record its durable receipt. Does not perform exploratory drug analysis or synergy testing.
---
# drug-response-experiment

**One line:** Submit a frozen biomarker/drug-response experiment and record its receipt.
**Category:** pharmacogenomics
**Open-source:** Repository Python standard-library submission command.
**Install:** Install this repository; the operator provisions a private scoring service.

Use only an operator-provided registration JSON for a fixed biomarker, drug, exposure,
independent-donor cohort, assay strata and protocol. The command accepts no response measurements,
p/e values, executable paths, subtype cutoffs or analysis parameters.

Load this skill before `run_experiments`, with `method_id: "drug-response-experiment"`.
Run:

```sh
python -m dnhacksbio.drug_response_experiment \
  --spec registered-drug-experiment.json --request-id investigation-branch-drug-001
```

The operator sets `DNHACKS_DRUG_RESPONSE_ENDPOINT` (default localhost:8795).
Expected stdout: `{"receipt": "investigation-branch-drug-001", "status": "accepted"}`.
Record that receipt and continue. Acceptance means durable submission, not biological success.
No `RESULT` line is expected; do not submit a receipt as a verified finding or reconstruct statistics.
Retry a lost acknowledgement with the same ID and unchanged registration. Renaming the request
cannot create new evidence. Report an unavailable service; do not replace it with custom scoring.

The endpoint tests association, not treatment benefit, causality, mechanism or synergy.
Previously inspected donor measurements remain development data. Confidential confirmation requires
operator-owned data and filesystem permissions separate from the agent; do not inspect service files.
