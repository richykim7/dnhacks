# COORDINATION.md — how two people and many agents work on this repo at once

One page for humans. The agent-facing rules are in `AGENTS.md`, section
*Working alongside other agents*; both Claude Code and Codex read that file.

## The board

One pinned GitHub issue, **Board** (label `board`), is the shared channel.
Every agent, on either machine, posts there:

- when it starts a task: what, which files, rough time
- when the plan changes
- when it is done

Read it before starting and before every commit. The board plus git handles
routine communication, including small changes, reviews, blockers, and
unfinished work. Board posts do not require user confirmation.

Write `HANDOFF.md` only after substantial, long-running work and explicit
user confirmation that the task is done. Small tasks, including one-line
code changes, do not get handoffs. Agents should not ask for confirmation
just to write one. The entry format is in `AGENTS.md`.

```
python3 scripts/board.py show                 # who is on what, right now
python3 scripts/board.py show --all           # the log
python3 scripts/board.py post --kind claim --files src/x.ts --eta "40 min" "Adding the fan chart"
python3 scripts/board.py post --kind done "Fan chart in, gates green, commit abc123"
python3 scripts/board.py check                # anyone else in the files I changed?
```

Needs only the `gh` CLI, logged in as you, with write access to this repo.
Set `BOARD_AGENT=<yourname>/<session>` on a machine without tmux (inside
tmux the session name is used).

Humans can post too: comment on the issue in the GitHub app, or type in the
team Telegram group. Every board post is mirrored into that group, so both
of you watch it in the background. Mention an agent with `@<its name>` and
it gets a nudge when idle.

Only sessions post. Sub-agents a session spawns report to their parent, never
to the board, so ten helpers on one task are still one row here.

## Claims are heads-ups, not locks

Two agents may be in the same file. The rules are only:

1. Say so on the board first (`check` tells you who else is there).
2. Keep the change small and commit soon.
3. Sync with `origin/main` before every commit. Whoever integrates resolves conflicts, using
   the board to see what the other side meant.
4. If a conflict is not obvious, post it and let the other agent confirm
   before pushing.

## Git

- Before implementation, agents check the board's branch column and local worktrees. If another agent
  is active on the same branch, they create a unique task branch in a separate worktree from
  `origin/main`. They never switch another agent's shared checkout. If alone, they can reuse an
  appropriate task branch. Read-only work needs no new branch.
- Sync with `origin/main` before every commit; rebase unpublished commits or merge main into the task
  branch to preserve published history. Push after every commit.
- Agents create/update PRs and automatically merge completed work after validation; you do not need
  to approve each PR. Existing required checks/reviews still apply. Main history stays linear through
  rebase merging. No force pushes or rewriting main.
- Board `done` means implementation reached `main`; pushed branches and pending auto-merges get
  `update`. Read-only reviews can finish with `done` and no PR. Full integration rules: `AGENTS.md`, Git.
- Generated files and lockfiles are never hand-merged: take either side and
  rerun the generator.
- `HANDOFF.md` merges by union (`.gitattributes`), so two agents appending
  at the same time do not conflict.

## Ownership (advisory)

Each area has a default owner who is asked before a shared interface in it
changes. Fill in:

| Area | Owner |
|---|---|
| | |
| | |

## What each side runs

- Both: `gh` logged in; `scripts/board.py`.
- One machine only: `scripts/board_mirror.py --to <group chat id>` (board to
  Telegram and back, plus agent nudges). It relies on a local Telegram
  harness; nobody else needs it.
- Every other machine: `python3 scripts/board_nudge.py` in a spare tmux
  window (gh + tmux only). It turns `@name` mentions into a typed nudge in
  that agent's pane when the pane is idle. Without it, your agents only see
  mentions when they next read the board.
