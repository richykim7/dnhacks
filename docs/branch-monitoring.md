# Branch monitoring implementation

## Checkpoints and allocation

The first implemented stage is the research controller. Each `Explorer.run` completes at most one
bounded round, ending in an actual child-authored report or durable reporting failure. The CLI uses
`run_investigation` to apply explicit parent allocations. The report schema and validation live in
`explorer/control.py`. Reports reference existing work; the parent receives the supporting ordinary
research digest, not a private monitor value. Report references are assertions for inspection, not
independent verification of a finding.

New state is in `<trace_dir>/runtime/control.sqlite3`, beside the ordinary event journal. It contains
no private scores. Report version fixes each decision's identity. Continuing resets only the per-round
allowance. Forking atomically reserves all child slots and transfers the original worker to management.
A launch recorded as `launching` without a saved session stays blocked after restart: repeating a fork
could duplicate paid work. Existing children resume their stored transcript and control state.

The report-only SDK connection disables tools/MCP and caps output at 4096 tokens and 90 seconds per
attempt; two formatting repairs are allowed. An outage blocks immediately. `reporting_blocked` requires
explicit operator intervention; invoking normal run again does not silently restart it. A blocked parent
decision leaves `awaiting_parent` and can be retried by the controller. Failed/cancelled research remains
operational failure, distinct from a parent prune. The UI renders these actual lifecycle names.

Operational caps are not the fixed statistical success horizon. No trajectory model, calibrated
threshold or scientific-performance result is established by these controller tests. The remaining
private collection, comparison and operator-view work follows `plans/PLAN-branch-monitoring.md`.
