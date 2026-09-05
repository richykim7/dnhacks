# COORDINATION.md — how two people and many agents work on this repo at once

One page for humans. The agent-facing rules are in `AGENTS.md`, section
*Working alongside other agents*; both Claude Code and Codex read that file.

## The board

One pinned GitHub issue, **Board** (label `board`), is the shared channel.
Every agent, on either machine, posts there:

- when it starts a task: what, which files, rough time
- when the plan changes
- when it is done

Read it before starting and before every commit. Nothing else needs to be
shared: the board plus git is the whole handoff.

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

## Claims are heads-ups, not locks

Two agents may be in the same file. The rules are only:

1. Say so on the board first (`check` tells you who else is there).
2. Keep the change small and commit soon.
3. Rebase before every commit. Whoever rebases resolves the conflict, using
   the board to see what the other side meant.
4. If a conflict is not obvious, post it and let the other agent confirm
   before pushing.

## Git

- One branch per session: `<person>/<session>`. Short-lived.
- `git pull --rebase origin main` before every commit. Push after every commit.
- `main` is fast-forward only. No force pushes, no history rewriting.
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
