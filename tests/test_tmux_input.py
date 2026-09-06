"""Adversarial screen fixtures: automated Enter must never accept another menu."""
from dataclasses import replace
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import tmux_input as ui
REAL_CODEX_PROCESS = ui.codex_process


MENU = """Our systems are thinking a bit more about this request before responding.
Hang tight or retry with a faster model for a quicker response, though it
may be less capable of handling complex requests.

› 1. Retry with a faster model
  2. Dismiss and keep waiting
  3. Learn more

No action is required. Codex will keep waiting, and this menu will close when
the response is ready.
"""


TWO_MENU = """Our systems are thinking a bit more about this request before responding.

› 1. Dismiss and keep waiting
  2. Learn more

No action is required. Codex will keep waiting, and this menu will close when
the response is ready.
"""


def screen(text=MENU, **kwargs):
    return replace(ui.Screen("%1", 123, False, False, False, 0, 0, 100, 30, text), **kwargs)


def selected_waiting(s):
    return replace(s, text=s.text.replace("› 1.", "  1.").replace("  2.", "› 2."))


class Client:
    socket = "fixture"

    def __init__(self, screens):
        self.screens = iter(screens)
        self.keys = []
        self.writes = []

    def screen(self, pane):
        return next(self.screens)

    def key(self, pane, key):
        self.keys.append(key)

    def run(self, *args):
        self.writes.append(args)


@pytest.fixture(autouse=True)
def isolate(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    monkeypatch.setattr(ui.time, "sleep", lambda _: None)
    monkeypatch.setattr(ui, "codex_process", lambda _: True)


def test_arrow_then_verified_waiting_enter():
    a = screen()
    b = selected_waiting(a)
    c = Client([a, a, b, b, screen("›", cursor=True)])
    assert ui.dismiss_waiting(c, "%1") == "dismissed"
    assert c.keys == ["Down", "Enter"]


def test_waiting_already_selected_sends_only_enter():
    a = selected_waiting(screen())
    c = Client([a, a, a, a, screen("›", cursor=True)])
    assert ui.dismiss_waiting(c, "%1") == "dismissed"
    assert c.keys == ["Enter"]


@pytest.mark.parametrize("bad", [
    screen(cursor=True), screen(in_mode=True), screen(dead=True),
    screen(MENU.replace("Dismiss and keep waiting", "Switch to Luna")),
    screen(MENU.replace("› 1.", "  1.")),
    screen(MENU.replace("  3.", "› 3.")),
    screen(MENU + "› Ask Codex to do anything\n"),
    screen("\n".join("> " + line for line in MENU.splitlines())),
    screen(MENU.replace("No action is required.", "Truncated footer")),
    screen(MENU.replace("Our systems are thinking a bit more about this request before responding.", "Some other popup")),
    screen("Select Model and Effort\n› 1. Luna\n2. Astra\nPress enter to confirm or esc to go back"),
])
def test_unknown_or_inactive_layout_never_sends_input(bad):
    c = Client([bad])
    assert ui.dismiss_waiting(c, "%1") == "unrecognized"
    assert not c.keys


def test_non_codex_process_never_receives_input(monkeypatch):
    monkeypatch.setattr(ui, "codex_process", lambda _: False)
    c = Client([screen()])
    assert ui.dismiss_waiting(c, "%1") == "unrecognized"
    assert not c.keys


@pytest.mark.parametrize("replacement", [screen("›", cursor=True), screen(),
    selected_waiting(screen(pid=999)), selected_waiting(screen(width=60)),
    screen("Do you want to proceed?\n› 1. Yes\n2. No")])
def test_replaced_menu_or_unmoved_selection_never_gets_enter(replacement):
    a = screen()
    c = Client([a, a, replacement])
    assert ui.dismiss_waiting(c, "%1") == "selection-not-verified"
    assert c.keys == ["Down"]


def test_last_capture_change_prevents_enter():
    a, b = screen(), selected_waiting(screen())
    c = Client([a, a, b, screen("›", cursor=True)])
    assert ui.dismiss_waiting(c, "%1") == "changed"
    assert c.keys == ["Down"]


def test_dry_run_sends_nothing():
    a = screen()
    c = Client([a, a])
    assert ui.dismiss_waiting(c, "%1", dry=True) == "would-dismiss"
    assert not c.keys


def test_input_lock_prevents_other_sender():
    with ui.input_lock("fixture", "%1") as acquired:
        assert acquired
        c = Client([])
        assert ui.dismiss_waiting(c, "%1") == "locked"
        assert not c.keys


def test_board_defers_on_the_reproduced_popup(monkeypatch):
    a = screen()
    c = Client([a, a])
    monkeypatch.setattr(ui, "Tmux", lambda: c)
    assert not ui.send_board_message("test", "Board notice")
    assert not c.keys and not c.writes


def test_board_aborts_enter_if_menu_opens_after_typing(monkeypatch):
    a = screen("› Ask Codex to do anything", cursor=True, x=2)
    c = Client([a, a, screen()])
    monkeypatch.setattr(ui, "Tmux", lambda: c)
    assert not ui.send_board_message("test", "Board notice")
    assert len(c.writes) == 1
    assert not c.keys


def test_board_delivers_only_after_verified_text(monkeypatch):
    a = screen("› Ask Codex to do anything", cursor=True, x=2)
    b = screen("› Board notice", cursor=True, x=14)
    c = Client([a, a, b, b])
    monkeypatch.setattr(ui, "Tmux", lambda: c)
    assert ui.send_board_message("test", "Board notice")
    assert c.keys == ["Enter"]


def test_board_preserves_user_draft(monkeypatch):
    a = screen("› My unfinished draft", cursor=True, x=2)
    c = Client([a, a])
    monkeypatch.setattr(ui, "Tmux", lambda: c)
    assert not ui.send_board_message("test", "Board notice")
    assert not c.keys and not c.writes


def test_old_and_new_headers_and_wrapping():
    old = MENU.replace(
        "Our systems are thinking a bit more about this request before responding.",
        "Additional safety checks\nThis request requires additional safety checks, which can take extra time.")
    old = old.replace("Dismiss and keep waiting", "Keep waiting")
    assert ui.waiting_popup(screen(old)) is not None
    latest = MENU.replace(
        "Our systems are thinking a bit more about this request before responding.\n"
        "Hang tight or retry with a faster model for a quicker response, though it\n"
        "may be less capable of handling complex requests.",
        "Giving this request a little extra thought\nIf you'd rather not wait, retry with a faster model. "
        "It may be less capable of handling complex requests.")
    assert ui.waiting_popup(screen(latest)) is not None


@pytest.mark.parametrize("count,initial", [(3, 0), (3, 1), (3, 2), (2, 0), (2, 1)])
def test_real_tmux_selects_only_waiting(tmp_path, monkeypatch, count, initial):
    """A native fake-Codex menu on a separate socket records the actual chosen row."""
    import shutil
    import subprocess
    import time
    if not shutil.which("cc") or not shutil.which("tmux"):
        pytest.skip("native tmux fixture needs cc and tmux")
    # The fixture is native so tmux's real cursor visibility and arrow handling
    # are tested, without launching a model or touching an existing server.
    source = tmp_path / "fixture.c"
    source.write_text(r'''
#include <stdio.h>
#include <stdlib.h>
#include <termios.h>
#include <unistd.h>
int main(int argc, char **argv) {
  struct termios original, raw;
  tcgetattr(0, &original); raw=original; cfmakeraw(&raw);
  raw.c_oflag |= OPOST | ONLCR; tcsetattr(0, TCSANOW, &raw);
  setbuf(stdout, NULL); int selected=atoi(argv[2]); int count=atoi(argv[3]);
  const char *labels[]={"Retry with a faster model", "Dismiss and keep waiting", "Learn more"};
  for (;;) {
    printf("\033[?25l\033[2J\033[HOur systems are thinking a bit more about this request before responding.\n");
    if(count==3) printf("Hang tight or retry with a faster model for a quicker response, though it\nmay be less capable of handling complex requests.\n\n");
    for(int i=0;i<count;i++) printf("%s %d. %s\n", i==selected?"›":" ",i+1,labels[i+(count==2)]);
    printf("\nNo action is required. Codex will keep waiting, and this menu will close when\nthe response is ready.\n");
    int ch=getchar(); if(ch==EOF) break;
    if(ch==27 && getchar()=='[') { int arrow=getchar(); if(arrow=='B' && selected<count-1) selected++; if(arrow=='A' && selected>0) selected--; }
    if(ch=='\r' || ch=='\n') {
      FILE *f=fopen(argv[1],"w"); fprintf(f,"%d",selected); fclose(f);
      printf("\033[?25h\033[2J\033[HDISMISSED\n");
      sleep(20); break;
    }
  }
  tcsetattr(0,TCSANOW,&original); return 0;
}
''')
    binary, result = tmp_path / "codex", tmp_path / "chosen"
    subprocess.run(["cc", str(source), "-o", str(binary)], check=True, capture_output=True)
    socket = str(tmp_path / "tmux.sock")
    base = ["tmux", "-S", socket]
    subprocess.run(base + ["-f", "/dev/null", "new-session", "-d", "-s", "fixture",
                          "-x", "120", "-y", "30", str(binary), str(result), str(initial), str(count)],
                   check=True, capture_output=True)
    try:
        client = ui.Tmux(socket)
        monkeypatch.setattr(ui, "codex_process", REAL_CODEX_PROCESS)
        # Restore real sleep; this fixture needs actual render scheduling.
        import select
        monkeypatch.setattr(ui.time, "sleep", lambda seconds: select.select([], [], [], seconds))
        deadline = time.monotonic() + 5
        while ui.waiting_popup(client.screen("fixture:0.0")) is None:
            assert time.monotonic() < deadline, "fixture menu did not render"
            ui.time.sleep(0.05)
        assert ui.dismiss_waiting(client, "%0") == "dismissed"
        assert result.read_text() == ("0" if count == 2 else "1")
    finally:
        subprocess.run(base + ["kill-server"], check=False, capture_output=True)


@pytest.mark.parametrize("initial", [0, 1])
def test_two_option_selects_waiting_by_label(initial):
    waiting = screen(TWO_MENU)
    a = waiting if initial == 0 else selected_waiting(waiting)
    assert ui.waiting_popup(a).waiting == 0
    c = Client([a, a, waiting, waiting, screen("›", cursor=True)])
    assert ui.dismiss_waiting(c, "%1") == "dismissed"
    assert c.keys == (["Up", "Enter"] if initial else ["Enter"])


@pytest.mark.parametrize("bad", [
    TWO_MENU.replace("  2. Learn more", "  3. Learn more"),
    TWO_MENU.replace("Dismiss and keep waiting", "Dismiss and continue"),
    TWO_MENU.replace("Dismiss and keep waiting", "Yes, approve"),
    TWO_MENU.replace("› 1.", "  1."),
    TWO_MENU.replace("  2.", "› 2."),
    TWO_MENU.replace("1. Dismiss and keep waiting", "1. Learn more")
            .replace("2. Learn more", "2. Dismiss and keep waiting"),
    TWO_MENU.replace("  2. Learn more", "  2. Learn more\n  3. Retry with a faster model"),
    TWO_MENU.replace("Our systems are thinking a bit more about this request before responding.",
                     MENU.split("\n\n")[0]),
    MENU.replace(MENU.split("\n\n")[0], TWO_MENU.split("\n\n")[0]),
    TWO_MENU.replace("No action is required. Codex will keep waiting, and this menu will close when\nthe response is ready.",
                     "Press enter to confirm or esc to go back"),
    TWO_MENU + "› Ask Codex to do anything\n",
    "\n".join("> " + line for line in TWO_MENU.splitlines()),
])
def test_two_option_unknown_or_mixed_layout_sends_nothing(bad):
    c = Client([screen(bad)])
    assert ui.dismiss_waiting(c, "%1") == "unrecognized"
    assert c.keys == []


@pytest.mark.parametrize("before,after", [
    (screen(), screen(TWO_MENU)),
    (selected_waiting(screen(TWO_MENU)), selected_waiting(screen())),
])
@pytest.mark.parametrize("phase", ["stability", "selection", "final"])
def test_layout_switch_never_gets_enter(before, after, phase):
    target = selected_waiting(screen()) if before.text == MENU else screen(TWO_MENU)
    captures = {
        "stability": [before, after],
        "selection": [before, before, after],
        "final": [before, before, target, after],
    }
    c = Client(captures[phase])
    assert ui.dismiss_waiting(c, "%1") == (
        "selection-not-verified" if phase == "selection" else "changed")
    assert "Enter" not in c.keys


def test_two_option_unmoved_learn_more_never_gets_enter():
    a = selected_waiting(screen(TWO_MENU))
    c = Client([a, a, a])
    assert ui.dismiss_waiting(c, "%1") == "selection-not-verified"
    assert c.keys == ["Up"]


def test_board_defers_on_two_option_popup(monkeypatch):
    a = screen(TWO_MENU)
    c = Client([a, a])
    monkeypatch.setattr(ui, "Tmux", lambda: c)
    assert not ui.send_board_message("test", "Board notice")
    assert not c.keys and not c.writes


@pytest.mark.parametrize('partial', [False, True])
def test_before_send_callback_runs_only_at_transport_boundary(monkeypatch, partial):
    a = screen('› Ask Codex to do anything', cursor=True, x=2) if partial else screen()
    c = Client([a, a, screen()] if partial else [a, a])
    monkeypatch.setattr(ui, 'Tmux', lambda: c)
    evidence = []
    def before_send():
        assert not c.writes
        evidence.append('started')
    assert not ui.send_board_message('test', 'Board notice', before_send=before_send)
    assert evidence == (['started'] if partial else [])
    assert len(c.writes) == int(partial)


def test_before_send_persistence_failure_prevents_terminal_write(monkeypatch):
    a = screen('› Ask Codex to do anything', cursor=True, x=2)
    c = Client([a, a])
    monkeypatch.setattr(ui, 'Tmux', lambda: c)
    def fail():
        raise OSError('state unavailable')
    assert not ui.send_board_message('test', 'Board notice', before_send=fail)
    assert not c.writes and not c.keys
