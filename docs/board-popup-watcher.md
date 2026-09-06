# Codex keep-waiting watcher

`scripts/codex_popup_watch.py` polls current tmux viewports every two seconds. It
only handles the known English Codex buffering popup, selecting **Dismiss and keep
waiting** (or the older **Keep waiting** label). It keeps the current model and
request running. It does not handle approvals, trust prompts, model pickers,
errors, or usage-limit dialogs, and does not disable server-side checks.

It recognizes both the three-option menu (retry, wait, learn more) and the
observed two-option menu (dismiss and keep waiting, learn more). The two-option
variant requires its exact shorter thinking header and no-action-required footer.
The waiting target comes from the recognized label: option 1 in the two-option
menu, option 2 in the three-option menu. Headers and rows from different variants
are not interchangeable. A change of variant during selection aborts before
Enter; unrecognized wording such as “Dismiss and continue” is left alone.

Run one watcher for the local tmux server:

```sh
python3 scripts/codex_popup_watch.py --session-prefix dnhacks/ --once --dry-run
python3 scripts/codex_popup_watch.py --session-prefix dnhacks/
```

Use `--socket /path/to/tmux/socket` for another tmux server. A per-server lock
prevents duplicate watchers. Stop with Ctrl-C or SIGTERM; no Codex session needs
restarting. The watcher needs Linux `/proc` access to verify a native Codex process
under each pane, and normal access to tmux and its own cache directory.

Before acting it requires a live pane outside copy mode, a hidden cursor, the
complete recognized menu ending at the bottom of the visible content, and two
identical captures. It moves the highlight with an arrow, rereads the screen, and
checks that the selected label is the waiting option before Enter. It never types
a menu number or uses Escape. Unknown wording/layouts are left alone. Logs record
pane IDs and outcomes only, without transcripts. No model calls are used.
An unsuccessful selection is latched until that menu disappears. Successful
dismissals have a 30-second per-pane cooldown to bound repeated interactions.

The board mirror and standalone nudger share a per-pane input lock with the
watcher. They defer on menus, hidden cursors, unknown composers, or changing
screens. After typing a board message, they check again before Enter. If that
check fails, text may remain in the composer for manual inspection; they do not
clear potentially user-owned text. Existing mirror/nudger processes must reload
the updated scripts to use these guards. Fleet's other senders do not acquire
this repository's lock.

Screen inspection and key injection cannot be atomic with Codex's own rendering
or human input. These checks reduce accidental selection; they cannot eliminate
every timing race. Structured `codex queue` delivery remains the planned fix for
board notifications. The watcher is an interim convenience, not a guarantee that
uncoordinated terminal writers are safe.

Validation includes unknown/quoted/truncated menus, selected-row verification,
copy mode and visible cursors, disappearing/replaced menus, and board delivery
interlocks. An isolated real tmux fixture tests the actual arrow/Enter sequence.
