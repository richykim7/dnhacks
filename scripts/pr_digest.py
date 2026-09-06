#!/usr/bin/env python3
"""pr_digest.py — text a plain-prose summary of every merged PR by one author, based on the diff.

Runs on ONE machine (the one with the Telegram harness), in its own tmux session, e.g.

    tmux new-session -d -s dnhacks/pr-digest -c ~/projects/dnhacks 'python3 scripts/pr_digest.py --author iantinney'

fleet/bridge gives that tmux session a Telegram forum topic automatically, and the script sends there
(`tgx send --session <tmux session name>`). Every poll (default 60 s):

  1. `gh pr list --state merged --author AUTHOR` — anything merged since the last poll and not yet sent.
  2. For each: PR metadata + per-file stats + the diff (`gh pr diff`), reordered source-first with
     generated data and lockfiles last, capped per file and at --max-diff-chars overall.
  3. `claude -p` writes one short paragraph about what the CODE changed, with tools off, no project
     instructions loaded, and a system prompt that pins the format. The PR description is context only.
  4. `tgx send` to the topic. A PR is marked sent only after tgx succeeds; exit 2 (topic not bound yet,
     e.g. the bridge has not caught up with a fresh session) is retried on the next poll.

First run starts from now unless --backfill N asks for the last N merged PRs. --dry-run prints instead
of sending. State (sent PR numbers) lives in board.py's cache dir, never in the repo.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import board  # noqa: E402

HARNESS = Path(os.environ.get("HARNESS_ROOT", "/home/dev/projects/dashboard"))
TGX = HARNESS / "telegram" / "tgx"

SYSTEM_PROMPT = """You write short text messages to Rich, a team lead, about pull requests his teammate merged.
You are given the PR title, its description, per-file line counts, and the diff with source files first and
generated data last. Write ONE paragraph of 4 to 7 sentences, at most 900 characters: what changed and where
(name the main modules or components in words), what it does for the product or demo, and the one or two things
Rich should look at, such as changed interfaces or schemas, deleted or weakened tests, hard-coded values, TODOs,
or large generated files. Judge from the code, not from the description; if they disagree, say so in one clause.
Plain prose only: no markdown, no bullets, no headers, no code blocks, no preamble, no sign-off.
If part of the diff was cut, mention in a few words what you could not see. This is a phone text: be tight."""

# Diff ordering: source first, generated/data last, each file capped, so the budget is spent on code.
DATA_EXT = {".json", ".jsonl", ".csv", ".tsv", ".lock", ".svg", ".min.js", ".map", ".snap", ".ipynb", ".parquet", ".txt"}
LOCK_NAMES = {"uv.lock", "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "Cargo.lock"}


def _file_rank(path: str) -> int:
    name = path.rsplit("/", 1)[-1]
    if name in LOCK_NAMES:
        return 3
    low = name.lower()
    if any(low.endswith(e) for e in DATA_EXT):
        return 2
    if low.endswith(".md"):
        return 1
    return 0


def arrange_diff(diff: str, max_chars: int, per_file: int = 12000) -> tuple[str, list[str]]:
    """Reorder a unified diff so code files come first and data/lockfiles last; cap each file's hunk.
    Returns (text within max_chars, list of files that were cut or dropped)."""
    chunks = []
    for part in diff.split("\ndiff --git ")[0:]:
        if not part.strip():
            continue
        text = part if part.startswith("diff --git ") else "diff --git " + part
        first = text.splitlines()[0]
        path = first.split(" b/", 1)[1] if " b/" in first else first
        chunks.append((_file_rank(path), path, text))
    chunks.sort(key=lambda c: (c[0], c[1]))
    out, cut, used = [], [], 0
    for rank, path, text in chunks:
        cap = per_file * 3 if rank == 0 else per_file  # source gets three times the room of data files
        if len(text) > cap:
            text = text[:cap] + f"\n... [{path}: cut after {cap} of {len(text)} chars]\n"
            cut.append(path)
        if used + len(text) > max_chars:
            cut.append(path + " (dropped)")
            continue
        out.append(text)
        used += len(text)
    return "\n".join(out), cut


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def drain_stdin():
    # Telegram replies in the topic get typed into this pane by the inbox watcher; swallow them.
    try:
        for _ in sys.stdin:
            pass
    except Exception:
        pass


def gh(*args: str) -> str:
    p = subprocess.run(["gh", *args], text=True, capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args[:2])} failed: {p.stderr.strip()[:200]}")
    return p.stdout


def merged_prs(repo: str, author: str, limit: int) -> list[dict]:
    out = gh("pr", "list", "-R", repo, "--state", "merged", "--author", author, "--limit", str(limit),
             "--json", "number,title,mergedAt,url,author")
    rows = json.loads(out or "[]")
    return sorted(rows, key=lambda r: r["mergedAt"])


def pr_detail(repo: str, number: int) -> dict:
    out = gh("pr", "view", str(number), "-R", repo,
             "--json", "number,title,body,author,mergedAt,additions,deletions,changedFiles,files,url,mergeCommit")
    return json.loads(out)


def pr_diff(repo: str, number: int) -> str:
    return gh("pr", "diff", str(number), "-R", repo)


def build_prompt(d: dict, diff: str, max_chars: int) -> str:
    files = "\n".join(f"  {f['path']}  +{f['additions']} -{f['deletions']}" for f in d.get("files") or [])
    body = (d.get("body") or "").strip() or "(none)"
    text, cut = arrange_diff(diff, max_chars)
    note = (" (source files first; cut or dropped: " + ", ".join(cut) + ")") if cut else ""
    return (f"PR #{d['number']}: {d['title']}\n"
            f"Author: {d['author']['login']}   merged {d['mergedAt']}\n"
            f"Totals: +{d['additions']} -{d['deletions']} across {d['changedFiles']} files\n\n"
            f"PR description (context only, may be inaccurate):\n{body[:3000]}\n\n"
            f"Files:\n{files}\n\n"
            f"Diff{note}:\n{text}")


def summarize(prompt: str, model: str | None, timeout: int) -> str:
    # Tools off, no project/user settings, no session file: a pure one-shot read of the diff. cwd is a
    # temp dir so no CLAUDE.md / AGENTS.md from the repo leaks into the run.
    cmd = ["claude", "-p", "--output-format", "text", "--tools", "", "--setting-sources", "",
           "--no-session-persistence", "--system-prompt", SYSTEM_PROMPT]
    if model:
        cmd += ["--model", model]
    cmd.append("Summarize this merged pull request for Rich.")
    p = subprocess.run(cmd, input=prompt, text=True, capture_output=True, timeout=timeout,
                       cwd=board.cache_dir())
    if p.returncode != 0 or not p.stdout.strip():
        raise RuntimeError(f"claude -p failed rc={p.returncode}: {p.stderr.strip()[:300]}")
    return p.stdout.strip()


def format_message(d: dict, summary: str) -> str:
    who = d["author"]["login"]
    if len(summary) > 1500:  # the prompt asks for 900 chars; never let a runaway answer flood the phone
        summary = summary[:1500].rsplit(". ", 1)[0] + "."
    return (f"{who} merged PR #{d['number']}: {d['title']}\n\n{summary}\n\n"
            f"+{d['additions']} -{d['deletions']} across {d['changedFiles']} files\n{d['url']}")


def send(dest: str, text: str, dry: bool) -> int:
    if dry:
        print("----- DRY SEND ->", dest, "-----\n" + text + "\n-----", flush=True)
        return 0
    p = subprocess.run([str(TGX), "send", "--session", dest, "-"], input=text, text=True, capture_output=True)
    if p.returncode != 0:
        log("tgx failed", p.returncode, p.stderr.strip()[:200])
    return p.returncode


def tmux_session_name() -> str:
    if not os.environ.get("TMUX"):
        return ""
    p = subprocess.run(["tmux", "display-message", "-p", "#S"], text=True, capture_output=True)
    return p.stdout.strip() if p.returncode == 0 else ""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--author", required=True, help="GitHub login whose merged PRs to summarize")
    ap.add_argument("--repo", default=None, help="owner/repo (default: this checkout's origin)")
    ap.add_argument("--dest", default=None, help="tgx --session dest (default: this tmux session's name)")
    ap.add_argument("--interval", type=int, default=60)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="print messages instead of sending")
    ap.add_argument("--backfill", type=int, default=0, help="on first run, also do the last N merged PRs")
    ap.add_argument("--model", default=None, help="claude model id (default: the CLI's default)")
    ap.add_argument("--max-diff-chars", type=int, default=80000)
    ap.add_argument("--claude-timeout", type=int, default=300)
    ap.add_argument("--state", default=None, help="state file (default: board.py cache dir)")
    a = ap.parse_args(argv)

    repo = a.repo or board.owner_repo()
    dest = a.dest or tmux_session_name()
    if not dest and not a.dry_run:
        raise SystemExit("need --dest, or run inside the tmux session whose topic should receive the digest")
    state_path = Path(a.state) if a.state else board.cache_dir() / f"pr-digest-{repo.replace('/', '__')}-{a.author}.json"

    if state_path.exists():
        st = json.loads(state_path.read_text())
    else:
        # First run: everything already merged is old news, except an explicit backfill.
        prs = merged_prs(repo, a.author, 50)
        skip = prs[:-a.backfill] if a.backfill else prs
        st = {"sent": sorted(r["number"] for r in skip)}
        state_path.write_text(json.dumps(st))
    sent = set(st.get("sent", []))

    threading.Thread(target=drain_stdin, daemon=True).start()
    log(f"pr-digest up: {repo}, author {a.author}, -> {dest or '(dry)'}, every {a.interval}s, "
        f"{len(sent)} PRs already seen")

    while True:
        try:
            todo = [r for r in merged_prs(repo, a.author, 30) if r["number"] not in sent]
        except RuntimeError as e:
            log(e)
            todo = []
        for r in todo:
            n = r["number"]
            try:
                d = pr_detail(repo, n)
                diff = pr_diff(repo, n)
                log(f"PR #{n}: {len(diff)} diff chars, summarizing")
                summary = summarize(build_prompt(d, diff, a.max_diff_chars), a.model, a.claude_timeout)
            except (RuntimeError, subprocess.TimeoutExpired) as e:
                log(f"PR #{n} failed, will retry: {e}")
                continue
            rc = send(dest, format_message(d, summary), a.dry_run)
            if rc == 0:
                sent.add(n)
                state_path.write_text(json.dumps({"sent": sorted(sent)}))
                log(f"PR #{n} sent")
            else:
                log(f"PR #{n} not sent (tgx rc={rc}), will retry")
        if a.once:
            return 0
        time.sleep(a.interval)


if __name__ == "__main__":
    sys.exit(main())
