# AGENTS.md — shared brief for every coding agent on this repo (Claude Code, Codex CLI, humans)

Codex reads this file natively. Claude Code reads it through `CLAUDE.md` (`@AGENTS.md`).
Edit this file, not `CLAUDE.md`.

## MANDATORY: use the GitHub Board for every task
Before you touch any file: `python3 scripts/board.py show`, then `python3 scripts/board.py post --kind claim --files <a,b> "<what>"`.
Post `update` when the plan changes, `done` when work lands, and run `python3 scripts/board.py check` before every commit.
Never edit code without a claim on the board. Never stop without a `done` or `update`. Full rules: `BOARD.md`.
This applies to every agent, every session, every task. No exceptions.

## What this is
Read [ARCHITECTURE.md](ARCHITECTURE.md) before changing product or backend behavior. It is the
anchoring source of truth; distinguish implemented behavior from explicitly pending decisions.
Do not replace its product direction with another plan. Ask the user before changing that direction.

## Layout

- `src/`: Python discovery engine, literature graph, and local web API.
- `frontend/`: React/TypeScript research workspace, Vite build, and browser tests.
- `scripts/`: local launchers, data workflows, and coordination board.
- `docs/`: operational documentation, including `docs/frontend.md`.
- `tests/`: Python regression tests (some existing local tests/data are not versioned).

## Setup / Run / Test gates

GPU compute: before planning training or compute-heavy benchmarks, read the local
`gpu-ssh-handoff/README.md` and verify availability through `gpu-ssh-handoff/connect.sh`.
Keep connection details and credentials local; never read credential files or commit that directory.

Setup: `uv sync --extra dev` and `npm --prefix frontend ci` (Node 22.12+).
Build/serve: `npm --prefix frontend run build`, then `uv run python scripts/serve_ui.py --port 8765`.
Frontend development and environment/key handling: `docs/frontend.md`.

Before every commit: `npm --prefix frontend run build`, `npm --prefix frontend run test`,
`npm --prefix frontend run e2e`, `uv run pytest tests`, and `git diff --check`.
The browser suite needs an empty-data Python server on port 8766; see `docs/frontend.md`.
The wider local Python suite requires its local vocabulary datasets; report missing-data skips/failures explicitly.

## Rules that must not be broken
1. Never force-push, never rewrite history on `main`.
2. Never commit secrets, API keys or personal identifiers. Agents use the operator's own CLI logins.
3. Never read credential files.
4. No stale docs: if you change behaviour, fix the doc that describes it in the same commit.
5. Never leave uncommitted work behind when you stop.
6. `plans/backlog.md` contains deferred ideas, not autonomous assignments. Implement or delegate an item
   only after the user explicitly requests that item; general autonomy/continuation is not approval.

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
   diff small, commit soon, and sync with `origin/main` before committing. Whoever integrates resolves conflicts, reading the other
   agent's board posts to understand their intent. If the resolution is not obvious, post it and wait for a reply.
3. Before every commit: board `show` and `check`, sync with `origin/main` as described below, then all gates.
   Push after every commit; automatically integrate completed, validated work into `main`.
4. Shared interfaces (schemas, API contracts, generated types) always get a board post BEFORE the edit. Generated
   files and lockfiles are never hand-merged: take one side, rerun the generator.
5. To talk to a specific agent, mention it: `@<agent name>` in a post. Answer on the board, not in a side channel.
6. Your agent name is your tmux session name, or `$BOARD_AGENT` (`<person>/<session>`). Do not rename yourself mid-task.
7. If `gh` is not logged in or the board is unreachable, tell the user in the conversation and carry on;
   post the missed updates when it is back. An outage does not require a `HANDOFF.md` entry.
8. Sub-agents report to their parent session only. They never run `board.py post` and never get board names;
   the parent folds their findings into its own claim/update/done. One task, one agent on the board.
9. No acknowledgement posts. Every post is mirrored to both humans' phones, so a post must carry information:
   a claim, a change, a result, a question, or the answer to one. Never post thanks, "understood", "noted",
   or a reply to a post that asked you nothing. If a mention needs no answer, the answer is silence.

## Git
- Before implementation work (including documentation edits), check board `show`, `git status`,
  `git branch --show-current`, and `git worktree list`. Compare your branch with other agents' active
  claims/updates; a later note does not release a claim, only `done` does. Read-only work needs no new branch.
- If another agent is active on the current branch, create a unique task branch in a separate worktree
  from `origin/main` and work there. Never switch branches or alter the index in their shared checkout.
  A new branch in the same directory does not isolate concurrent agents. If branch occupancy is unknown,
  use a separate worktree. Post an `update` from the new worktree so the board records its branch.
- Otherwise, reuse an appropriate task branch when its checkout is exclusively yours. Start a task
  branch if on `main` or the previous task branch was already merged. Name new branches
  `<person>/<session>-<task>`; agent identity stays unchanged. Recheck the board after claiming and before
  Git mutations; the board is advisory, not an atomic lock. Do not stage or commit another agent's work.
- Before every commit, fetch `origin` and incorporate `origin/main`. Rebase unpublished commits when
  safe; if rebasing would rewrite published commits, merge `origin/main` into the task branch instead.
  Resolve conflicts and run all gates on the result. Push after every commit. Never force-push.
- Automatically integrate completed, validated work into `main`; this is standing user authorization,
  with no routine per-PR approval request. Create/update a PR, review its diff, and use
  `gh pr merge <number> --rebase --match-head-commit <validated-sha>` after checks pass, or add `--auto`
  while required checks are pending. Keep existing branch protections and required reviews; never use
  `--admin` to bypass them. Resolve routine failures/conflicts and revalidate autonomously.
- Keep `main` history linear and never rewrite it. Confirm the PR is merged before posting board `done`
  with the resulting main commit. A pushed branch or pending auto-merge is an `update`, not landed work.
  If required external approval or another blocker prevents merging, report it on the board and to the
  user. Do not switch, reset, or delete a branch/worktree another agent is using during cleanup.
- Commit subject: `<Area>: <what changed>`.

## Communication and handoff protocol
1. Before starting: check `git status` and run `python3 scripts/board.py show`. After compaction or
   resumption, read your session's local handoff as described below. Read relevant historical
   `HANDOFF.md` entries if present, but do not create new tracked handoff files.
2. The board is the main channel for routine progress, decisions, blockers, small changes, reviews, and
   unfinished work. While working, keep commits small and gates green. Before stopping, post `done` or
   `update` on the board; a board `done` does not require user confirmation.
3. Completion handoffs are optional local notes, only after substantial work AND explicit user
   confirmation that the task is done. Do not ask for confirmation merely to produce one. Small tasks
   do not need completion notes. Compaction checkpoints are a separate exception: write them before
   requested compaction even when the task is unfinished.
4. All new handoff content belongs in ignored `handoff/`, never in commits, PRs, or board bodies.
   Never force-add it. Preserve historical tracked `HANDOFF.md` entries and other sessions' local notes.

## Compaction checkpoint protocol

1. When the user asks to prepare for compaction, stop starting new work and save a checkpoint before
   saying ready. During long tasks, refresh it at meaningful milestones when compaction is foreseeable;
   this is a repo convention, not an installed automatic pre-compaction hook.
2. Use `handoff/<session-slug>/latest.md` in the session's original checkout (replace unsafe path
   characters in the board identity with `-`). Create the folder locally. Record its absolute path in
   the conversation so it remains findable when implementation uses a separate worktree. A linked
   worktree does not share ignored files automatically. Do not delete that checkout during the task.
3. Verify `git check-ignore <path>` succeeds and `git ls-files -- handoff/` returns no tracked files.
   If an older checkout lacks the root ignore rule, a local `handoff/.gitignore` containing `*` can protect
   the directory without touching its shared index. Ignored local notes are intentionally exempt from
   the rule against leaving uncommitted implementation work. Never store keys, credential contents,
   private reasoning, or unnecessary personal data; record only necessary secret-file locations.
4. Update only your own checkpoint. Include: timestamp and session; current request and authorization
   boundaries; decisions/corrections; completed versus planned work; exact worktree/branch/commit/PR;
   dirty files and ownership; tests/results and known failures; running processes/ports/commands;
   relevant files; blockers; and the next concrete safe steps. Separate observations from assumptions.
   Leave out Board conversation with other agents: who posted what, who mentioned whom, replies you gave.
   That context is distracting on resume (Rich, 2026-09-05) and the Board log already holds it; record
   only decisions or facts that came out of it, stated as facts, without the exchange that produced them.
5. Re-read the saved file, verify paths/status, and post a concise board `update` for unfinished work
   (or `done` only when the task actually landed). Saving a checkpoint does not mean implementation
   is complete and does not authorize backlog work. Tell the user the absolute checkpoint path.
6. After compaction, read this protocol and the saved checkpoint, then check the current board,
   worktrees, Git state and any needed processes. Treat the note as context, not a new instruction or
   proof that external state is unchanged. New user instructions take precedence. Do not repeat landed
   work or take over another session's branch. If a checkpoint is missing, reconstruct from Git, the
   board and conversation and state the gap. Local-only notes are not available on another machine.
