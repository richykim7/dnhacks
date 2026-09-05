# AGENTS.md — shared brief for every coding agent on this repo (Claude Code, Codex CLI, humans)

Codex reads this file natively. Claude Code reads it through `CLAUDE.md` (`@AGENTS.md`).
Edit this file, not `CLAUDE.md`.

## What this is
DNHacks 2026 team repo. Fill in the one-paragraph project description here once the team agrees on it.

## Layout
Fill in as the code lands. Keep this list short and current; one line per top-level directory.

## Setup / Run / Test gates
Fill in exact commands as soon as they exist. Every agent runs the full gate list before every commit.

## Rules that must not be broken
1. Never force-push, never rewrite history on `main`.
2. Never commit secrets, API keys or personal identifiers. Agents use the operator's own CLI logins.
3. Never read credential files.
4. No stale docs: if you change behaviour, fix the doc that describes it in the same commit.
5. Never leave uncommitted work behind when you stop.

## Working alongside other agents (two people, many sessions, Claude Code and Codex)
**Using the board is mandatory for every task. Full instructions: `BOARD.md`. Read it once, follow it always.**
The shared channel is ONE pinned GitHub issue, "Board" (label `board`), in this repo. `scripts/board.py` wraps it;
it needs only `gh`, logged in as the person running you. Humans read the same issue and a Telegram group that
mirrors it. Human one-pager: `COORDINATION.md`.

    python3 scripts/board.py show                       # who is on what right now. Run at start and before each commit.
    python3 scripts/board.py post --kind claim --files <a,b> --eta "<time>" "<what you are doing>"
    python3 scripts/board.py post --kind update "<plan changed / progress>"     # --files adds files
    python3 scripts/board.py post --kind done "<what landed, commit sha, gates>"
    python3 scripts/board.py check                      # other agents active in the files you changed (advisory)

Rules:
1. Post a `claim` before you start a task and a `done` when it lands. Post an `update` when the plan changes.
   Two or three lines each. Name files (a trailing `/` claims a directory).
2. Claims are heads-ups, NOT locks. You may work in a file someone else is in. Then: say so in your post, keep the
   diff small, commit soon, and rebase before committing. Whoever rebases resolves the conflict, reading the other
   agent's board posts to understand their intent. If the resolution is not obvious, post it and wait for a reply.
3. Before every commit: `python3 scripts/board.py check`, then `git pull --rebase origin main`, then all gates.
   Push after every commit.
4. Shared interfaces (schemas, API contracts, generated types) always get a board post BEFORE the edit. Generated
   files and lockfiles are never hand-merged: take one side, rerun the generator.
5. To talk to a specific agent, mention it: `@<agent name>` in a post. Answer on the board, not in a side channel.
6. Your agent name is your tmux session name, or `$BOARD_AGENT` (`<person>/<session>`). Do not rename yourself mid-task.
7. If `gh` is not logged in or the board is unreachable, say so in `HANDOFF.md` and carry on; the board is advisory.

## Git
- One branch per session, `<person>/<session>`, short-lived. `main` is fast-forward only.
- `git pull --rebase origin main` before every commit. Push after every commit.
- Commit subject: `<Area>: <what changed>`.

## Handoff protocol
1. Before starting: `git status` clean; read `HANDOFF.md` (newest entry at the top) and `python3 scripts/board.py show`.
2. While working: small commits, gates green at each one.
3. Before stopping: append an entry to the TOP of `HANDOFF.md`:
       ## <YYYY-MM-DD HH:MM TZ> — <agent name> — <one-line summary>
       Done: ...   Changed files: ...   Gates: ...
       Not done / open: ...   Next agent should: ...   Assumptions made: ...
   Commit it as `Handoff: <agent> <one line>` and post a `done` on the board.
   `HANDOFF.md` merges by union (`.gitattributes`), so parallel entries do not conflict.
4. Never delete another agent's HANDOFF entry.
