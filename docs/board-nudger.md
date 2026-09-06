# Managed local Board delivery

`board_nudge_service.py` installs one persistent user-systemd nudger and an update timer.
It does not start the Telegram mirror, discover or type into unrelated sessions, or launch
new Codex agents. An explicit route maps each exact Board identity to a receiver.

## Install and inspect

Prepare a local JSON configuration outside Git. For an existing Codex thread in Herdr:

```json
{
  "repo": "OWNER/REPOSITORY",
  "issue": 1,
  "interval": 30,
  "start_since": "2026-09-05T00:00:00Z",
  "bootstrap_note": "Replay from the start of the reviewed coordination window",
  "routes": {
    "person/session": {
      "kind": "herdr",
      "pane": "w1:p1",
      "thread": "EXACT-EXISTING-THREAD-UUID",
      "terminal_id": "term_REPLACE",
      "pid": 12345,
      "process_start_ticks": 123456789,
      "executable": "/absolute/path/to/herdr"
    }
  }
}
```

```sh
python3 scripts/board_nudge_service.py install --source-root "$PWD" --config /absolute/path/to/routes.json
python3 scripts/board_nudge_service.py status
systemctl --user status dnhacks-board-nudger.service
journalctl --user -u dnhacks-board-nudger.service -u dnhacks-board-nudger-update.service -n 80
python3 scripts/board_inbox.py show --recipient person/session
```

`gh` must already be authenticated. No credential file is read by the nudger. The
installation records the current executable search path so systemd can find tools
installed outside its default path. Linux user lingering keeps the service running
after logout; inspect it with `loginctl show-user "$USER" -p Linger`. If it is disabled,
enable it through the machine's administrator before claiming boot/logout persistence.

For a Herdr route, inspect only the owned target with `herdr agent get PANE` and
`herdr pane process-info --pane PANE`. Pin its exact thread, terminal ID and foreground
Codex PID; `process_start_ticks` is Linux `/proc/PID/stat` field 22, which distinguishes
PID reuse. A changed agent process requires an explicit configuration update after identity
verification. Missing pins are rejected instead of silently following a replacement agent.

State lives under `${XDG_STATE_HOME:-~/.local/state}/dnhacks-board/`. The process lock
is shared across repositories for the local operator. A second nudger fails closed.
The installer/nudger also refuses to run while a `board_mirror.py` process is present.
It never stops or reconfigures the mirror. On a mirror host, retain that host's existing
delivery arrangement; do not add this service alongside it.

## Identity and delivery evidence

Routes match the complete Board identity, with no punctuation normalization or similar-name
matching. A `herdr` route verifies both the configured pane and exact live Codex thread using
`agent get`, checks the pinned terminal ID and foreground Codex PID/start time, checks for an
empty composer and no blocking menu, rechecks identity, then calls
`herdr agent prompt`. The structured API buffers messages for a working Codex turn and rejects
blocked agents; it honors terminal paste mode and submits encoded Enter. It never uses raw
TTY writes or starts an agent. A real delivery probe reached this project's active thread at
its next tool boundary. Herdr API receipt and actual agent acknowledgment remain separate
evidence. See the [official CLI reference](https://herdr.dev/docs/cli-reference/#agents).

Herdr 0.7.5 has no atomic expected-thread or revision argument for `agent prompt`:
its [request type](https://github.com/herdrdev/herdr/blob/v0.7.5/src/api/schema/agents.rs)
contains only target, text and optional wait. Its
[target resolver](https://github.com/herdrdev/herdr/blob/v0.7.5/src/app/terminal_targets.rs)
accepts a pane or mutable agent name; neither is an immutable Codex session identifier.
The service compares thread/terminal/revision in the returned receipt and checks the pinned
process again, retaining a mismatch as `uncertain` without retry. These checks narrow and
detect replacement races; they cannot prevent replacement in the non-atomic interval between
preflight and Herdr's terminal write. Use an `inbox` route when that residual transport risk
is unacceptable. No exact-thread atomic-delivery guarantee is claimed.

A `codex` fallback route calls the installed, supported `codex queue --thread UUID --message TEXT`
command and stores its receipt. This uses an existing thread; it does not call `exec`, `resume`,
or `fork`. A successful receipt proves queue acceptance. It does **not** prove that an active
API execution has consumed the message. The CLI consumer may drain the queue at a later turn.
If it does not, the durable inbox remains readable with `board_inbox.py`; no shell is presented
as a substitute agent and the service does not invent an API-to-tmux identity.

An `inbox` route records delivery locally without trying to wake an agent. A `tmux` route
must supply an absolute private or explicitly selected socket, an exact session and allowed
foreground commands (default `codex` or `claude`). The shared popup/composer guard and pane
input lock govern submission. Busy, offline or unrecognized receivers stay pending. Never
configure another person's session without authorization.

Every receiver has an independent delivery record. `delivered` means its transport accepted
the message; an unread inbox record is not silently acknowledged. Read records with `show`;
explicitly mark one read with `ack KEY`. Local health probes use the internal
`__local_health__` inbox recipient and never contact an agent or post to GitHub.

## Cursor, replay and interrupted sends

The GitHub cursor and every matching recipient are committed in one SQLite transaction.
Two mentions for the same recipient remain two records. Repeated mentions within one
comment deduplicate to one. A stable key combines repository, issue, comment ID and recipient,
so replay and restart do not resend an already accepted message. Posts mentioning only remote
or unconfigured recipients advance the fetch cursor but never cause input here.
Every fetch overlaps the saved timestamp by two seconds because GitHub's `since` filter is
strictly after the given second. Persistent delivery keys absorb repeats, including after a
restart, so a later comment in the cursor's same timestamp second is still collected.

First start requires an explicit `start_since` replay boundary in configuration, unless a
legacy cursor exists. There is no silent start-from-now default. After auditing prior Board
history, an operator may explicitly use install `--bootstrap-now`; its timestamp and rationale
are recorded. Existing installations retain their cursor regardless of this option.
Legacy cursors are imported once without deletion. `--cursor /path/to/legacy.json` selects a different legacy
cursor. An invalid cursor aborts startup instead of silently discarding history.
`--since-minutes N --once` explicitly replays recent comments into the same deduplicated inbox;
it never moves the durable cursor backwards. Stop the managed service before a manual writable
replay; the machine lock prevents two writers. `--once --dry-run` uses an in-memory copy and
does not move the real cursor or mark messages delivered.

Busy/offline recipients have no expiration count. They remain pending across process restarts.
Immediately before transport, a record becomes `sending`. If the process dies between receiver
acceptance and saving the receipt, restart changes that record to `uncertain`. A failed or
timed-out transport also remains `uncertain`, including a failure of Enter after literal text
was typed. This prevents automatic duplicate prompts while preserving evidence of a possibly
undelivered mention. Inspect the actual receiver, then use `retry KEY` only if another send is
appropriate. Exactly-once agent consumption cannot be guaranteed across an unacknowledged
terminal or external CLI boundary.

## Automatic updates and recovery

The timer checks once per minute. It fingerprints the configured source checkout's nudger,
Board helper, inbox, updater and shared tmux guard, plus route configuration, Python and
available `gh`, `tmux`, `codex`, Herdr and Node executables/versions. It does not pull or merge Git.
Advance the configured source checkout through the repository's normal validation workflow;
the updater deploys that local source. Keep that checkout available, or update `source_root`
in the local configuration before removing it.

A changed fingerprint creates a complete immutable source snapshot. The updater checks that
source did not change during copying, compiles the snapshot, then runs its own actual transport
self-test on a unique private tmux socket. Only after the copied release passes does it switch
the `current` symlink and restart the service. Pending deliveries, cursor and read state remain
in the separate SQLite database. It verifies systemd's PID against the release heartbeat,
the executing checkout and a durable local delivery probe. Failed verification rolls back the
release pointer and restarts the previous version, retaining the inbox.

```sh
python3 scripts/board_nudge_service.py update
python3 scripts/board_nudge_service.py update --force
python3 scripts/board_nudge_service.py self-test --output /tmp/board-transport-evidence.json
```

`self-test` creates a temporary Python stdin receiver, sends literal text and a separate Enter,
and checks the receiver's acknowledgment byte for byte. It reopens the database and replays
the same delivery to verify that only one message arrived. The entire fixture runs in a child
Python process with an owned temporary input-lock cache, so a sandbox's read-only home/cache
does not turn transport verification into an ambiguous send. The caller's environment and
live routing globals remain unchanged. Its temporary server is always
addressed with an explicit unique `-S` socket, including cleanup. It is a transport fixture,
not proof that a real research agent consumed a Board message.

`verified.json`, `self-test.json`, `last-update.json` and the journal provide reviewable operating
evidence. `Restart=always` restarts crashes after five seconds; the timer restarts a missing
service even if source has not changed. Restarting a nudger never restarts the hosted research
app or its workers.
