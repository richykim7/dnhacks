# HANDOFF.md — newest entry at the top

Every agent (Claude Code or Codex CLI) appends an entry here before it stops.
Format in `AGENTS.md`, section "Handoff protocol".

## 2026-09-05 10:35 EDT — Claude Code — coordination board set up
Done: `scripts/board.py`, `scripts/board_mirror.py`, `AGENTS.md`, `CLAUDE.md`, `COORDINATION.md`,
`.gitattributes`, this file. Pinned "Board" issue created.
Changed files: all of the above (first commit).
Gates: none exist yet.
Not done / open: project description, layout, setup and gate commands in `AGENTS.md`; ownership table in
`COORDINATION.md`; Telegram group mirror starts once the group exists.
Next agent should: read `AGENTS.md`, run `python3 scripts/board.py show`, post a claim before starting.
Assumptions made: claims advisory, not locks; agent name = tmux session name or `$BOARD_AGENT`.
