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
| Work lands (committed, gates green) | `done` | "Fan chart in. Commit 3f2a1c9. lint/test/e2e green." |
| Before every commit | `check` | (prints who else is in your files; advisory) |
| Before you stop for any reason | `done` or `update` | "Stopping mid-task, fan chart half done, see HANDOFF.md" |

Two or three lines per post. Say what a stranger needs in order not to collide with you: files, intent, time.

## Same file, two agents: allowed, with rules

Claims are heads-ups, **not locks**. You may work in a file someone else is in. Then:

1. Say so in your post and name them: "Also in Tree.tsx alongside @alex/s1, only the legend block."
2. Keep the diff small and commit soon.
3. `git pull --rebase origin main` before every commit. Whoever rebases resolves the conflict, reading
   the other agent's posts to understand their intent.
4. If the resolution is not obvious, post it and wait for a reply before pushing.

Shared interfaces (schemas, API contracts, generated types) always get a post **before** the edit.
Generated files and lockfiles are never hand-merged: take one side, rerun the generator.

## Before every commit, in this order

```
python3 scripts/board.py check
git pull --rebase origin main
<run every test gate listed in AGENTS.md>
git commit
git push
python3 scripts/board.py post --kind done "..."
```

## Talking to another agent

Mention it by name in a post: `@alex/s1`. Agent names are listed by `show`. Answer on the board, never in
a side channel, so everyone sees the exchange. Round trip is about a minute; do not wait on it for
things you can decide yourself.

## Reading the board

Run `show` at the start of every task and before every commit. It prints one row per agent: what kind of
post they last made, when, which files they hold, and their last line. A `done` row means they are out
of those files. A `claim` or `update` row means they are in them now.

## Git rules that go with the board

- One branch per session, `<person>/<session>`, short-lived. `main` is fast-forward only.
- Rebase before every commit. Push after every commit.
- Never force-push. Never rewrite history. Never leave uncommitted work when you stop.
- `HANDOFF.md`: append an entry at the top before you stop (format in `AGENTS.md`). It merges by union,
  so two agents appending at once do not conflict.

## If the board is unreachable

`gh` not logged in, GitHub down: say so in your `HANDOFF.md` entry, keep working, post everything you
skipped as soon as it is back. The board is advisory, but skipping it silently is not allowed.

## Putting this in your agent's instructions

Codex reads `AGENTS.md` in this repo. Claude Code reads `CLAUDE.md`, which imports `AGENTS.md`. Both
already point here. If you run an agent that reads neither, paste this into its system prompt:

> Before touching any file run `python3 scripts/board.py show`, then post a `claim` with `--files`.
> Post `update` when the plan changes and `done` when work lands. Run `check` and
> `git pull --rebase origin main` before every commit. Claims are heads-ups, not locks. Full rules: BOARD.md.
