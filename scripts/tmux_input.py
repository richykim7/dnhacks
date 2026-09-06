"""Small, shared guards for automated tmux input. No model calls or screen logs."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import hashlib
import os
from pathlib import Path
import re
import subprocess
import time


@dataclass(frozen=True)
class Screen:
    pane: str
    pid: int
    cursor: bool
    in_mode: bool
    dead: bool
    x: int
    y: int
    width: int
    height: int
    text: str


class Tmux:
    def __init__(self, socket: str | None = None):
        self.base = ["tmux"] + (["-S", socket] if socket else [])
        self.socket = socket or self.run("display-message", "-p", "#{socket_path}").stdout.strip()

    def run(self, *args: str):
        return subprocess.run(self.base + list(args), text=True, capture_output=True,
                              timeout=5, check=True)

    def screen(self, target: str) -> Screen:
        fmt = "\t".join("#{" + f + "}" for f in (
            "pane_id", "pane_pid", "cursor_flag", "pane_in_mode", "pane_dead",
            "cursor_x", "cursor_y", "pane_width", "pane_height"))
        before = self.run("display-message", "-p", "-t", target, fmt).stdout.strip()
        pane, *fields = before.split("\t")
        # Current viewport only: never match a popup in historical scrollback.
        text = self.run("capture-pane", "-p", "-t", pane).stdout
        after = self.run("display-message", "-p", "-t", pane, fmt).stdout.strip()
        if before != after:
            raise ValueError("pane changed during capture")
        pid, cursor, mode, dead, x, y, width, height = map(int, fields)
        return Screen(pane, pid, bool(cursor), bool(mode), bool(dead), x, y,
                      width, height, text)

    def key(self, pane: str, key: str):
        self.run("send-keys", "-t", pane, key)


def state_dir() -> Path:
    base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    path = base / "dnhacks-tmux-input"
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


@contextmanager
def input_lock(socket: str, pane: str):
    """All cooperating board senders and the watcher use the same per-pane lock."""
    digest = hashlib.sha256(f"{socket}\0{pane}".encode()).hexdigest()
    with (state_dir() / (digest + ".lock")).open("a") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def codex_process(pid: int) -> bool:
    """Verify a native Codex descendant of this pane, without reading credentials."""
    pending, seen = [pid], set()
    while pending and len(seen) < 64:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        proc = Path("/proc") / str(current)
        try:
            exe = str((proc / "exe").readlink()).removesuffix(" (deleted)")
            if Path(exe).name == "codex":
                return True
            children = (proc / "task" / str(current) / "children").read_text()
            pending.extend(map(int, children.split()))
        except (OSError, ValueError):
            continue
    return False


@dataclass(frozen=True)
class Popup:
    selected: int
    waiting: int
    signature: tuple[str, ...]


def waiting_popup(screen: Screen) -> Popup | None:
    """Recognize only the known English Codex buffering menu, with hidden cursor."""
    if screen.cursor or screen.in_mode or screen.dead:
        return None
    lines = [line.strip() for line in screen.text.splitlines() if line.strip()]
    if not lines:
        return None
    row = re.compile(r"^(›|❯)?\s*(\d+)\.\s+(.+)$")
    starts = [i for i, line in enumerate(lines) if row.fullmatch(line)]
    if not starts:
        return None
    # The entire menu tail must have exactly the known rows and footer.
    start = starts[-1]
    while start > 0 and row.fullmatch(lines[start - 1]):
        start -= 1
    rows = []
    end = start
    while end < len(lines) and (match := row.fullmatch(lines[end])):
        rows.append(match.groups())
        end += 1
    labels = tuple(r[2] for r in rows)
    if labels not in (
        ("Retry with a faster model", "Dismiss and keep waiting", "Learn more"),
        ("Retry with a faster model", "Keep waiting", "Learn more"),
    ):
        return None
    if [r[1] for r in rows] != ["1", "2", "3"]:
        return None
    selected = [i for i, r in enumerate(rows) if r[0]]
    if len(selected) != 1:
        return None
    footer = " ".join(lines[end:])
    if footer not in (
        "No action is required. Codex will keep waiting, and this menu will close when the response is ready.",
        "Press enter to confirm or esc to go back",
    ):
        return None
    headers = (
        "Our systems are thinking a bit more about this request before responding. "
        "Hang tight or retry with a faster model for a quicker response, though it "
        "may be less capable of handling complex requests.",
        "Additional safety checks This request requires additional safety checks, "
        "which can take extra time. Hang tight or retry with a faster model for a "
        "quicker response, though it may be less capable of handling complex requests.",
        "Giving this request a little extra thought If you'd rather not wait, retry "
        "with a faster model. It may be less capable of handling complex requests.",
    )
    prefix = " ".join(lines[:start])
    header = next((h for h in headers if prefix.endswith(h)), None)
    if header is None:
        return None
    return Popup(selected[0], 1, (header, *labels, footer))


def menu_or_busy(screen: Screen) -> bool:
    if screen.dead or screen.in_mode or not screen.cursor:
        return True
    return bool(re.search(
        r"(?:^|\n)\s*[›❯]\s*\d+[.)]|esc to interrupt|ctrl\+c to interrupt|"
        r"press enter to confirm|enter to select|do you want to proceed|"
        r"retry with a faster model|dismiss and keep waiting", screen.text, re.I))


def dismiss_waiting(client: Tmux, pane: str, *, dry: bool = False) -> str:
    """Move by one arrow, recapture and verify, then accept only the waiting row."""
    with input_lock(client.socket, pane) as acquired:
        if not acquired:
            return "locked"
        a = client.screen(pane)
        popup = waiting_popup(a)
        if popup is None or not codex_process(a.pid):
            return "unrecognized"
        time.sleep(0.1)
        if client.screen(pane) != a:
            return "changed"
        if dry:
            return "would-dismiss"
        if popup.selected != popup.waiting:
            client.key(pane, "Down" if popup.selected < popup.waiting else "Up")
            time.sleep(0.1)
        b = client.screen(pane)
        after = waiting_popup(b)
        if (after is None or after.signature != popup.signature
                or after.selected != after.waiting
                or (a.pid, a.width, a.height) != (b.pid, b.width, b.height)):
            return "selection-not-verified"
        # Last possible check: never send a digit, Escape, or an unverified Enter.
        if client.screen(pane) != b:
            return "changed"
        client.key(pane, "Enter")
        time.sleep(0.1)
        return "dismissed" if waiting_popup(client.screen(pane)) is None else "still-open"


def send_board_message(session: str, text: str, *, socket: str | None = None) -> bool:
    """Defer on uncertain/menu states; keep the per-pane lock through submission."""
    # Control characters in a Board post must not become terminal input.
    text = " ".join(text.splitlines())
    if any(ord(c) < 32 or ord(c) == 127 for c in text):
        return False
    try:
        client = Tmux(socket) if socket is not None else Tmux()
        first = client.screen("=" + session + ":")
        with input_lock(client.socket, first.pane) as acquired:
            if not acquired:
                return False
            before = client.screen(first.pane)
            if before != first or menu_or_busy(before):
                return False
            lines = before.text.splitlines()
            if before.y >= len(lines):
                return False
            composer = lines[before.y].strip()
            # Positive empty-composer evidence; unknown layouts are deferred.
            if before.x != 2 or composer not in ("›", "❯", "› Ask Codex to do anything"):
                return False
            client.run("send-keys", "-t", before.pane, "-l", "--", text)
            time.sleep(0.15)
            after = client.screen(before.pane)
            if (menu_or_busy(after) or after.pid != before.pid
                    or "".join(text.split()) not in "".join(after.text.split())):
                return False
            if client.screen(before.pane) != after:
                return False
            client.key(before.pane, "Enter")
            return True
    except (OSError, ValueError, subprocess.SubprocessError):
        return False
