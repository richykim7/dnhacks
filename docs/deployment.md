# Manual VM deployment

Cloudflare Tunnel forwards to the VM's localhost:8765 app. VS Code forwarding is
not involved. There is **no automatic deployment timer or merge trigger**.

When the user explicitly says "deploy latest main", use `scripts/deploy.py`.
Never substitute pulling into the running checkout, rebuilding its dependencies,
or restarting its service by hand. Never bypass a failed validation/activity check.

## First migration (not yet performed)

The existing app may still run from the shared coding checkout. The deployment
script deliberately refuses bootstrap if the target port is occupied. Coordinate
an idle maintenance window before stopping that old web server: no investigations,
corpus ingestion/builds, pending launch requests or direct CLI launches. Do not
stop scientific processes to make a deployment possible. Preserve the existing
data directory; do not copy a database while a writer is active.

Choose a persistent deployment home OUTSIDE the coding checkout and an existing
absolute research data directory. Record those nonsecret locations for future
operators. Do not store login emails, Cloudflare credentials or tokens in this file.
After the old service is safely stopped, run:

```sh
python3 scripts/deploy.py --home /absolute/deployment-home --data /absolute/research-data --bootstrap
```

Run on the actual VM, not a PID-isolated coding sandbox: the script requires
systemd as visible PID 1 so the process scan sees the host. Agents must use the
approved host execution mechanism, not weaken that check. The command requires
Linux, a working user systemd manager, Git authentication,
Python 3.12, uv, Node 22.12+, npm and installed Playwright browser dependencies.
Enable user lingering for reboot availability using the VM's normal administrator
procedure. Cloudflare's connector is separate and must not be restarted by this script.

## Subsequent deployments

```sh
python3 scripts/deploy.py --home /absolute/deployment-home --data /absolute/research-data
```

The command serializes deploys, refuses nonterminal/unreadable job records,
nonterminal or uncertain runtime journals (including paused investigations), and
known standalone explorer/ingestion processes, fetches main into a separate
repository and creates a commit-specific release with its own virtual environment.
It runs frozen dependency installation, frontend build/unit/browser tests and Python
tests against isolated test data. Missing datasets or failing tests block deployment;
there is no skip-validation flag. Existing candidate directories are retained for
audit and require inspection before a retry; there is no automatic deletion.

After validation, each release's `data` points at the same persistent research data.
The deployer obtains the exclusive research lease, checks activity again, atomically
switches `current`, and restarts only `dnhacks-web.service`. It verifies the exact
release SHA at `/api/deployment/health`; a failure restores and verifies the previous
release before allowing web mutations again. Source/dependency files of old releases
are retained. Rollback does NOT undo data changes; no schema migration is supported.
Changes requiring incompatible stored-data formats need a separately planned backup
and migration, not this command.

## Guard boundaries

All managed web POST requests acquire a shared lease. Launched jobs inherit their
own lease descriptor until their process exits, so the exclusive deployment lock
cannot overlap a launch or a running job. During the switch new POSTs receive 503;
GET health requests remain available. The generated web unit explicitly uses
`KillMode=process`: stopping/recovering the web process leaves detached research
children alone. This intentionally trades systemd group cleanup for the existing
job cancellation/PID tracking; do not change it to the default `control-group`.
Managed service restarts must still only use this command: surviving children must
not be run against an incompatible new backend or dependency environment.

Direct shell launches are **not interlocked** by the HTTP guard. A conservative
process scan detects known existing CLI jobs, but cannot prevent a new arbitrary
shell command from starting afterward. Operators/agents must keep standalone
research launchers quiet during the maintenance window. Do not claim the scan is
a machine-wide atomic guarantee. Unknown activity means defer deployment.

Tests cover overlapping leases, detached-child lease retention, uncertain job
records, standalone ingestion detection, HTTP 503 admission and rollback ordering.
An isolated real user-systemd drill verified that a detached dummy job survives
its parent service stopping with `KillMode=process` and continues blocking the
exclusive deployment lock. No scientific process was used in that drill. First
migration and authenticated production smoke checks remain pending.
