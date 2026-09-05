# BOARD.md — the coordination board. Using it is mandatory.

You are one of several coding agents (Claude Code, Codex CLI) working on this repo at the same time,
on two different machines, for two people. The board is how everyone knows what everyone else is doing.
**Every agent uses it, every task, no exceptions.** An agent that edits code without posting on the board
is working blind and will collide with someone.

## What the board is

One pinned GitHub issue in this repo, titled **Board** (label `board`). Every agent posts short comments
there: what it is starting, what changed, what it finished. `scripts/board.py` does the posting and reading
for you. Humans read the same issue, and every post is mirrored into the team Telegram group, so both
people watch it live. Humans can reply there too, and their words come back onto the board.

## One-time setup (per machine)

1. `gh auth status` must show you logged in with write access to this repo. If not: `gh auth login`.
2. Pick your agent name: `<person>/<session>`, for example `alex/s1`, `alex/codex2`. Set it:
   `export BOARD_AGENT=alex/s1`. Inside tmux the tmux session name is used automatically if you skip this.
3. Test: `python3 scripts/board.py show`. You should see the current state, or "board is empty".

## The four commands

```
python3 scripts/board.py show                                   # who is on what, right now
python3 scripts/board.py post --kind claim --files <a,b> --eta "<time>" "<what you are doing>"
python3 scripts/board.py post --kind update [--files <c>] "<what changed>"
python3 scripts/board.py post --kind done "<what landed: commit sha, gates status>"
python3 scripts/board.py check                                  # who else is in the files you changed
```

`--files` takes comma-separated paths. A trailing `/` claims a whole directory (`src/api/`).
`show --all` prints the full log.

## When you MUST post

| Moment | Command | Example |
|---|---|---|
| Before you touch any file | `claim` | "Adding the fan chart to the tree view" `--files src/views/Tree.tsx --eta "40 min"` |
| Your plan or file set changes | `update` | "Also need to touch labels.ts for the legend" `--files src/labels.ts` |
| Something blocks you or you need another agent | `update` | "@alex/s1 the schema change broke the UI build, which way do you want it?" |
| Work lands (merged into main, gates green) | `done` | "Fan chart merged into main. Commit 3f2a1c9. lint/test/e2e green." |
| Before every commit | `check` | (prints who else is in your files; advisory) |
| Before you stop for any reason | `done` or `update` | "Stopping mid-task: fan chart renders; legend and tests remain in src/views/Tree.tsx." |

Two or three lines per post. Say what a stranger needs in order not to collide with you: files, intent, time.

## Same file, two agents: allowed, with rules

Claims are heads-ups, **not locks**. You may work in a file someone else is in. Then:

1. Say so in your post and name them: "Also in Tree.tsx alongside @alex/s1, only the legend block."
2. Keep the diff small and commit soon.
3. Sync with `origin/main` before every commit (see `AGENTS.md`, Git). Whoever integrates resolves conflicts, reading
   the other agent's posts to understand their intent.
4. If the resolution is not obvious, post it and wait for a reply before pushing.

Shared interfaces (schemas, API contracts, generated types) always get a post **before** the edit.
Generated files and lockfiles are never hand-merged: take one side, rerun the generator.

## Before every commit, in this order

```
python3 scripts/board.py show
python3 scripts/board.py check
git fetch origin
<rebase unpublished commits, or merge origin/main to preserve published history>
<run every test gate listed in AGENTS.md>
git commit
git push
<create/update PR; review diff; merge automatically after checks pass>
python3 scripts/board.py post --kind done "Merged into main: <sha>; gates: ..."
```

For an intermediate commit or pending auto-merge, post `update`. A pushed task branch is not yet landed.
Read-only tasks can post `done` when the review is finished, with no commit or PR.

## Talking to another agent

Mention it by name in a post: `@alex/s1`. Agent names are listed by `show`. Answer on the board, never in
a side channel, so everyone sees the exchange. Round trip is about a minute; do not wait on it for
things you can decide yourself. A mention becomes a typed nudge in the mentioned agent's tmux pane only
on a machine running `scripts/board_nudge.py` (or the mirror), and only for an agent whose tmux session
name is its board name; otherwise it lands on the agent's next `show`.

## Sub-agents never post

The board is for **sessions**, not for the helpers a session spawns. If you delegate work to sub-agents
(Claude Code `Agent`, Codex sub-agents, parallel workers of any kind), they report to you, their parent,
exactly as they already do. They do **not** run `board.py post`, and they do not get board names. You
fold what they found into your own posts: one `claim` when you start, `update` when the plan changes,
one `done` when it lands. Ten sub-agents on one task is still one agent on the board.

Why: every post is mirrored into the team Telegram group and nudges every mentioned session. On
2026-09-05 one person's sessions fanned out into a dozen posting sub-agents and put 34 messages into the
group in 12 minutes; nobody could follow it. Sub-agent chatter belongs in the parent's context, not
on the shared channel.

## Reading the board

Run `show` at the start of every task and before every commit. It prints one row per agent: what kind of
post they last made, when, their branch, which files they hold, and their last line. A `done` row means
they are out of those files. A `claim` or `update` starts/continues work; a later `note` does not release
it. Check earlier posts with `show --all` if the current row is ambiguous.

## Git rules that go with the board

- Before implementation, compare your branch with other active agents on the board and check local
  worktrees. If another agent is using it, create a unique task branch in a separate worktree from
  `origin/main`; do not switch their shared checkout. Post an update from the new worktree. If alone,
  reuse an appropriate task branch. Read-only tasks need no branch. Full rules: `AGENTS.md`, Git.
- Sync with `origin/main` before every commit without rewriting published commits; push after each.
- Agents automatically create/update and merge PRs into `main` after validation, without routine user
  approval. Use rebase merging for linear main history and respect required checks/reviews. Confirm
  the merge before `done`; pending auto-merge or blocked integration gets `update`.
- Never force-push. Never rewrite history. Never leave uncommitted work when you stop.
- The board is the main channel for routine progress, small changes, reviews, blockers, and unfinished
  work. Post `done` or `update` before stopping; board posts do not require user confirmation.
- Write `HANDOFF.md` only after substantial, long-running work and explicit user confirmation that the
  task is done (format in `AGENTS.md`). Small tasks do not get handoffs. Do not ask for confirmation just
  to write one. It merges by union, so two agents appending at once do not conflict.

## If the board is unreachable

`gh` not logged in, GitHub down: tell the user in the conversation, keep working, and post everything you
skipped as soon as it is back. An outage does not require a `HANDOFF.md` entry. The board is advisory,
but skipping it silently is not allowed.

## Putting this in your agent's instructions

Codex reads `AGENTS.md` in this repo. Claude Code reads `CLAUDE.md`, which imports `AGENTS.md`. Both
already point here. If you run an agent that reads neither, paste this into its system prompt:

> Before touching any file run `python3 scripts/board.py show`, then post a `claim` with `--files`.
> Post `update` when the plan changes and `done` when work lands in main. Sub-agents you spawn report to
> you and never post to the board. Before implementation, check
> active branches; use a separate branch and worktree if another agent is on yours. Run `show` and
> `check`, sync with origin/main, and validate before every commit. Push and automatically merge completed
> work after checks pass. Claims are heads-ups, not locks. Full rules: BOARD.md and AGENTS.md.
