#!/usr/bin/env python3
"""board.py — the shared coordination board for every agent on this repo.

The board is ONE pinned GitHub issue (title "Board", label "board") in the
repo's origin. Each agent posts a short comment when it starts a task,
changes plan, or finishes. Claims are heads-ups, not locks: two agents may
work in the same file as long as both have said so and sync with main before
committing.

Only dependency: the `gh` CLI, logged in as the person running the agent.
Works from any machine; nothing here is specific to one box.

Usage (run from anywhere inside the repo):

  board.py init                          find or create + pin the Board issue
  board.py post  [--kind claim|update|done|note] [--files a,b] [--eta "40 min"] TEXT
  board.py show  [--all] [--limit N]     who is on what right now (latest per agent)
  board.py check [--files a,b]           other agents active in the files you touched
  board.py watch [--interval 30] [--once] [--cursor FILE]   stream new comments as JSONL
  board.py url                           print the issue URL

Agent name: --agent, else $BOARD_AGENT, else the tmux session name, else
"unnamed-agent" (set BOARD_AGENT on machines without tmux).

Each comment carries a hidden JSON header on its first line so `show`,
`check` and `watch` parse reliably:
  <!-- board {"v":1,"agent":..,"kind":..,"files":[..],"branch":..,"sha":..,"eta":..,"ts":..} -->
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

KINDS = ("claim", "update", "done", "note")
HEADER_RE = re.compile(r"^<!--\s*board\s+(\{.*?\})\s*-->", re.S)
TITLE = "Board"
LABEL = "board"


# ---------------------------------------------------------------- helpers

def sh(*cmd: str, check: bool = True, input: str | None = None) -> str:
    p = subprocess.run(cmd, text=True, capture_output=True, input=input)
    if check and p.returncode != 0:
        sys.stderr.write(p.stderr)
        raise SystemExit(f"command failed ({p.returncode}): {' '.join(cmd)}")
    return p.stdout


def repo_root() -> Path:
    return Path(sh("git", "rev-parse", "--show-toplevel").strip())


def owner_repo() -> str:
    url = sh("git", "remote", "get-url", "origin").strip()
    m = re.search(r"github\.com[:/]([^/]+)/([^/.]+)(?:\.git)?$", url)
    if not m:
        raise SystemExit(f"origin is not a GitHub remote: {url}")
    return f"{m.group(1)}/{m.group(2)}"


def git_branch_sha() -> tuple[str, str]:
    br = sh("git", "rev-parse", "--abbrev-ref", "HEAD", check=False).strip() or "?"
    sha = sh("git", "rev-parse", "--short", "HEAD", check=False).strip() or "?"
    return br, sha


def agent_name(explicit: str | None) -> str:
    if explicit:
        return explicit
    if os.environ.get("BOARD_AGENT"):
        return os.environ["BOARD_AGENT"]
    if os.environ.get("TMUX"):
        name = sh("tmux", "display-message", "-p", "#S", check=False).strip()
        if name:
            return name
    sys.stderr.write("board: no agent name; set BOARD_AGENT (using 'unnamed-agent')\n")
    return "unnamed-agent"


def cache_dir() -> Path:
    d = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "repo-board"
    d.mkdir(parents=True, exist_ok=True)
    return d


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def local_stamp(ts: dt.datetime) -> str:
    return ts.astimezone().strftime("%Y-%m-%d %H:%M %Z")


def parse_ts(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def gh_json(*args: str):
    out = sh("gh", *args)
    return json.loads(out) if out.strip() else None


# ---------------------------------------------------------------- issue

def find_issue(repo: str) -> int | None:
    cache = cache_dir() / f"issue-{repo.replace('/', '__')}"
    if cache.exists():
        try:
            return int(cache.read_text().strip())
        except ValueError:
            pass
    items = gh_json("issue", "list", "-R", repo, "--label", LABEL, "--state", "open",
                    "--json", "number,title", "--limit", "20") or []
    for it in items:
        if it["title"] == TITLE:
            cache.write_text(str(it["number"]))
            return int(it["number"])
    return None


def ensure_issue(repo: str) -> int:
    n = find_issue(repo)
    if n:
        return n
    sh("gh", "label", "create", LABEL, "-R", repo, "--color", "0E8A16", "--force",
       "--description", "Agent coordination board")
    body = (
        "Coordination board for every agent (Claude Code, Codex CLI, humans) working on this repo.\n\n"
        "Post with `python3 scripts/board.py post ...`; read with `python3 scripts/board.py show`.\n"
        "Claims are heads-ups, not locks. Rules: `AGENTS.md`, section *Working alongside other agents*.\n"
    )
    out = sh("gh", "issue", "create", "-R", repo, "--title", TITLE, "--label", LABEL, "--body", body)
    m = re.search(r"/issues/(\d+)", out)
    if not m:
        raise SystemExit(f"could not parse issue number from: {out}")
    n = int(m.group(1))
    sh("gh", "issue", "pin", str(n), "-R", repo, check=False)
    (cache_dir() / f"issue-{repo.replace('/', '__')}").write_text(str(n))
    return n


def issue_url(repo: str, n: int) -> str:
    return f"https://github.com/{repo}/issues/{n}"


# ---------------------------------------------------------------- comments

def fetch_comments(repo: str, n: int, since: str | None = None) -> list[dict]:
    out: list[dict] = []
    page = 1
    while True:
        q = f"per_page=100&page={page}" + (f"&since={since}" if since else "")
        batch = gh_json("api", f"repos/{repo}/issues/{n}/comments?{q}") or []
        out.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return out


def parse_comment(c: dict) -> dict | None:
    body = c.get("body") or ""
    m = HEADER_RE.match(body)
    if not m:
        # A hand-typed comment from a human on GitHub: keep it as a note.
        return {
            "id": c["id"], "agent": c.get("user", {}).get("login", "?") + " (github)",
            "kind": "note", "files": [], "branch": "", "sha": "", "eta": "",
            "ts": c["created_at"], "text": body.strip(), "url": c["html_url"],
        }
    try:
        h = json.loads(m.group(1))
    except json.JSONDecodeError:
        return None
    text = body[m.end():].strip()
    # drop the human header line and trailing meta lines we generated
    lines = [ln for ln in text.splitlines()
             if not (ln.startswith("**") and " · " in ln)
             and not ln.startswith(("files: ", "eta: ", "branch "))]
    h.update(id=c["id"], ts=c["created_at"], text="\n".join(lines).strip(), url=c["html_url"])
    h.setdefault("files", [])
    return h


def format_body(agent: str, kind: str, text: str, files: list[str], eta: str,
                branch: str, sha: str, ts: dt.datetime) -> str:
    header = {"v": 1, "agent": agent, "kind": kind, "files": files, "branch": branch,
              "sha": sha, "eta": eta, "ts": ts.isoformat().replace("+00:00", "Z")}
    lines = [f"<!-- board {json.dumps(header, separators=(',', ':'))} -->",
             f"**{agent}** · {kind.upper()} · {local_stamp(ts)}", text.strip()]
    if files:
        lines.append("files: " + ", ".join(files))
    meta = []
    if eta:
        meta.append(f"eta: {eta}")
    meta.append(f"branch {branch} @ {sha}")
    lines.append(" · ".join(meta))
    return "\n".join(lines) + "\n"


def active_state(parsed: list[dict]) -> dict[str, dict]:
    """Latest entry per agent, plus the set of files it is currently in.
    A `done` clears the files; `claim` replaces them; `update` adds to them."""
    state: dict[str, dict] = {}
    for p in sorted(parsed, key=lambda x: x["ts"]):
        a = p["agent"]
        s = state.setdefault(a, {"files": set(), "last": None})
        if p["kind"] == "claim":
            s["files"] = set(p["files"])
        elif p["kind"] == "update":
            s["files"] |= set(p["files"])
        elif p["kind"] == "done":
            s["files"] = set()
        s["last"] = p
    return state


def overlaps(path: str, claimed: set[str]) -> bool:
    for c in claimed:
        if c.endswith("/") and path.startswith(c):
            return True
        if c == path:
            return True
    return False


# ---------------------------------------------------------------- commands

def cmd_init(a):
    repo = owner_repo()
    n = ensure_issue(repo)
    print(issue_url(repo, n))


def cmd_url(a):
    repo = owner_repo()
    n = find_issue(repo) or ensure_issue(repo)
    print(issue_url(repo, n))


def cmd_post(a):
    repo = owner_repo()
    n = find_issue(repo) or ensure_issue(repo)
    text = " ".join(a.text).strip() or sys.stdin.read().strip()
    if not text:
        raise SystemExit("post: empty text")
    files = [f.strip() for f in (a.files or "").split(",") if f.strip()]
    br, sha = git_branch_sha()
    body = format_body(agent_name(a.agent), a.kind, text, files, a.eta or "", br, sha, now_utc())
    out = sh("gh", "issue", "comment", str(n), "-R", repo, "--body", body)
    print(out.strip() or "posted")


def cmd_show(a):
    repo = owner_repo()
    n = find_issue(repo) or ensure_issue(repo)
    parsed = [p for p in (parse_comment(c) for c in fetch_comments(repo, n)) if p]
    if a.all:
        for p in sorted(parsed, key=lambda x: x["ts"])[-a.limit:]:
            print(f"{local_stamp(parse_ts(p['ts']))}  {p['agent']:<18} {p['kind']:<6} "
                  f"{p['text'].splitlines()[0] if p['text'] else ''}"
                  + (f"  [{', '.join(p['files'])}]" if p['files'] else "")
                  + f"  (branch {p.get('branch') or '?'})")
        return
    state = active_state(parsed)
    if not state:
        print("board is empty")
        return
    rows = sorted(state.items(), key=lambda kv: kv[1]["last"]["ts"], reverse=True)
    print(f"{'agent':<18} {'kind':<6} {'when':<22} {'branch':<28} files / last message")
    for agent, s in rows:
        last = s["last"]
        first = last["text"].splitlines()[0] if last["text"] else ""
        files = ", ".join(sorted(s["files"])) if s["files"] else "-"
        branch = last.get("branch") or "?"
        print(f"{agent:<18} {last['kind']:<6} {local_stamp(parse_ts(last['ts'])):<22} {branch:<28} {files}")
        print(f"{'':<18} {'':<6} {'':<22} {'':<28} {first}")
    print(issue_url(repo, n))


def cmd_check(a):
    repo = owner_repo()
    n = find_issue(repo) or ensure_issue(repo)
    me = agent_name(a.agent)
    if a.files:
        files = [f.strip() for f in a.files.split(",") if f.strip()]
    else:
        root = repo_root()
        staged = sh("git", "diff", "--cached", "--name-only", check=False).split()
        unstaged = sh("git", "diff", "--name-only", check=False).split()
        files = sorted(set(staged) | set(unstaged))
        _ = root
    if not files:
        print("check: no changed files")
        return
    parsed = [p for p in (parse_comment(c) for c in fetch_comments(repo, n)) if p]
    state = active_state(parsed)
    hits = []
    for agent, s in state.items():
        if agent == me or not s["files"]:
            continue
        shared = [f for f in files if overlaps(f, s["files"])]
        if shared:
            hits.append((agent, shared, s["last"]))
    if not hits:
        print(f"check: nobody else is active in your {len(files)} changed file(s)")
        return
    print("check: heads-up, other agents are active in files you touched:")
    for agent, shared, last in hits:
        print(f"  {agent} ({local_stamp(parse_ts(last['ts']))}): {', '.join(shared)}")
        if last["text"]:
            print(f"    \"{last['text'].splitlines()[0]}\"")
    print("Not a block. Sync with main, keep the diff small, and post an update naming them.")


def cmd_watch(a):
    repo = owner_repo()
    n = find_issue(repo) or ensure_issue(repo)
    cursor = Path(a.cursor) if a.cursor else cache_dir() / f"cursor-{repo.replace('/', '__')}-{n}"
    seen_id = 0
    since = None
    if cursor.exists():
        try:
            st = json.loads(cursor.read_text())
            seen_id, since = st.get("id", 0), st.get("since")
        except json.JSONDecodeError:
            pass
    elif a.from_now:
        since = now_utc().isoformat().replace("+00:00", "Z")
    while True:
        try:
            comments = fetch_comments(repo, n, since)
        except SystemExit as e:
            sys.stderr.write(f"watch: fetch failed, retrying: {e}\n")
            comments = []
        for c in sorted(comments, key=lambda x: x["id"]):
            if c["id"] <= seen_id:
                continue
            p = parse_comment(c)
            if p:
                print(json.dumps(p), flush=True)
            seen_id = c["id"]
            since = c["created_at"]
            cursor.write_text(json.dumps({"id": seen_id, "since": since}))
        if a.once:
            return
        time.sleep(a.interval)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init").set_defaults(fn=cmd_init)
    sub.add_parser("url").set_defaults(fn=cmd_url)
    p = sub.add_parser("post")
    p.add_argument("--kind", choices=KINDS, default="update")
    p.add_argument("--files", help="comma-separated paths; a trailing / claims a directory")
    p.add_argument("--eta")
    p.add_argument("--agent")
    p.add_argument("text", nargs="*")
    p.set_defaults(fn=cmd_post)
    p = sub.add_parser("show")
    p.add_argument("--all", action="store_true", help="chronological log instead of per-agent state")
    p.add_argument("--limit", type=int, default=40)
    p.set_defaults(fn=cmd_show)
    p = sub.add_parser("check")
    p.add_argument("--files")
    p.add_argument("--agent")
    p.set_defaults(fn=cmd_check)
    p = sub.add_parser("watch")
    p.add_argument("--interval", type=int, default=30)
    p.add_argument("--once", action="store_true")
    p.add_argument("--from-now", action="store_true", help="on first run, skip history")
    p.add_argument("--cursor")
    p.set_defaults(fn=cmd_watch)
    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
