#!/usr/bin/env python3
"""Install, verify and update one user-systemd Board nudger without resetting its inbox."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import shlex
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

import board_nudge as nudger
from board_inbox import Inbox, stamp, state_home

SERVICE = "dnhacks-board-nudger.service"
FILES = ("board.py", "board_inbox.py", "board_nudge.py", "board_nudge_service.py", "tmux_input.py")


def run(args, *, timeout=30, check=True, **kwargs):
    result = subprocess.run(args, text=True, capture_output=True, timeout=timeout, **kwargs)
    if check and result.returncode:
        raise RuntimeError(f"{args[0]} failed: {result.stderr.strip()[:400]}")
    return result


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def fingerprint(source: Path, config: dict) -> tuple[str, dict]:
    sources = {}
    for name in FILES:
        path = source / "scripts" / name
        if path.exists():
            sources[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        elif name != "tmux_input.py":
            raise ValueError(f"Missing source dependency {path}")
    dependencies = {"python": {"path": sys.executable, "version": sys.version,
                               "sha256": hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest()}}
    for name in ("gh", "tmux", "codex", "node", "herdr"):
        executable = shutil.which(name, path=config.get("path"))
        if executable:
            version = run([executable, "-V" if name == "tmux" else "--version"], timeout=5, check=False)
            dependencies[name] = {"path": executable, "resolved": str(Path(executable).resolve()),
                                  "sha256": hashlib.sha256(Path(executable).read_bytes()).hexdigest(),
                                  "version": version.stdout.strip()}
    manifest = {"sources": sources, "dependencies": dependencies, "config": config}
    digest = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    return digest, manifest


def transport_self_test(output: Path) -> dict:
    """Keep fixture locks and routing globals out of the caller's live environment."""
    output = output.resolve()
    with tempfile.TemporaryDirectory(prefix="board-nudge-test-") as directory:
        root = Path(directory)
        try:
            run([sys.executable, "-c",
                 "import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); "
                 "from board_nudge_service import _transport_self_test; "
                 "_transport_self_test(Path(sys.argv[2]), Path(sys.argv[3]))",
                 str(Path(__file__).resolve().parent), str(output), str(root)],
                env=dict(os.environ, XDG_CACHE_HOME=str(root / "cache")), timeout=25)
            return json.loads(output.read_text())
        finally:
            # Also clean up if the worker times out before its own finally block.
            run(["tmux", "-S", str(root / "tmux.sock"), "kill-server"], check=False)


def _transport_self_test(output: Path, root: Path) -> dict:
    """Send actual literal text + Enter only to an owned private-socket Python receiver."""
    socket = root / "tmux.sock"
    receiver, received = root / "receiver.py", root / "received.jsonl"
    receiver.write_text("import json,sys\nfrom pathlib import Path\n"
                        "p=Path(sys.argv[1])\nprint('READY',flush=True)\n"
                        "while True:\n"
                        " try: text=input('› ')\n"
                        " except EOFError: break\n"
                        " with p.open('a') as f: f.write(json.dumps(text)+'\\n')\n"
                        " print('ACK',flush=True)\n")
    session = "board-nudger-owned-test"
    command = shlex.join([sys.executable, str(receiver), str(received)])
    prefix = ["tmux", "-S", str(socket)]
    environment = dict(os.environ)
    environment.pop("TMUX", None)
    environment.pop("TMUX_PANE", None)
    try:
        run(["tmux", "-f", "/dev/null", "-S", str(socket), "new-session", "-d", "-s", session, command], env=environment)
        actual_socket = run(prefix + ["display-message", "-p", "-t", "=" + session + ":", "#{socket_path}"], env=environment).stdout.strip()
        if actual_socket != str(socket):
            raise RuntimeError("Private test socket verification failed")
        deadline = time.monotonic() + 5
        while "READY" not in run(prefix + ["capture-pane", "-p", "-t", "=" + session + ":"], env=environment).stdout:
            if time.monotonic() > deadline:
                raise RuntimeError("Owned test receiver did not become ready")
            time.sleep(.1)
        foreground = run(prefix + ["display-message", "-p", "-t", "=" + session + ":", "#{pane_current_command}"], env=environment).stdout.strip()
        config = {"routes": {"test/owned": {"kind": "tmux", "socket": str(socket), "session": session,
                                            "commands": [foreground]}}}
        payload = "Literal Board probe: $() `backticks` ; #{session_name} @fixture-only"
        inbox = Inbox(root / "inbox.sqlite3")
        with inbox.db:
            inbox.put("fixture:1", 1, "test/owned", payload)
        nudger.deliver(inbox, config)
        deadline = time.monotonic() + 5
        while not received.exists():
            if time.monotonic() > deadline:
                raise RuntimeError("Text/Enter did not reach the owned receiver")
            time.sleep(.1)
        if [json.loads(line) for line in received.read_text().splitlines()] != [payload]:
            raise RuntimeError("Literal transport changed or duplicated the message")
        inbox.db.close()
        restarted = Inbox(root / "inbox.sqlite3")
        restarted.recover()
        with restarted.db:
            restarted.put("fixture:1", 1, "test/owned", payload)
        nudger.deliver(restarted, config)
        time.sleep(.2)
        if len(received.read_text().splitlines()) != 1:
            raise RuntimeError("Restart/replay duplicated delivery")
        evidence = {"time": stamp(), "source": str(Path(__file__).resolve()),
                    "private_cache": os.environ["XDG_CACHE_HOME"],
                    "private_socket": actual_socket, "receiver": "owned Python stdin fixture, not an agent",
                    "literal_text_and_enter": "passed", "restart_and_replay": "one delivery",
                    "payload": payload, "captured_ack": run(prefix + ["capture-pane", "-p", "-t", "=" + session + ":"], env=environment).stdout}
        write_json(output, evidence)
        return evidence
    finally:
        # This socket was created above and is unique. Never target a default/shared server.
        run(prefix + ["kill-server"], env=environment, check=False)


def unit_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%") + '"'


def unit_exec(args: list[str]) -> str:
    return " ".join(unit_quote(str(arg)) for arg in args)


def install_units(home: Path, source: Path, config: dict) -> None:
    if any(c in str(path) for path in (home, source) for c in "\n\r"):
        raise ValueError("systemd installation paths cannot contain newlines")
    units = Path.home() / ".config/systemd/user"
    units.mkdir(parents=True, exist_ok=True)
    current = home / "current"
    command = unit_exec([sys.executable, str(current / "scripts/board_nudge.py"),
                         "--config", str(current / "config.json"), "--state", str(home / "nudger.sqlite3"),
                         "--lock", str(state_home() / "machine.lock"), "--health", str(home / "health.json")])
    (units / SERVICE).write_text(
        "[Unit]\nDescription=Durable DNHacks Board mention delivery\nAfter=network-online.target\n"
        "StartLimitIntervalSec=0\n\n[Service]\nType=simple\n"
        f"WorkingDirectory={str(source).replace('%', '%%')}\nEnvironment={unit_quote('PATH=' + config['path'])}\n"
        f"ExecStart={command}\nRestart=always\nRestartSec=5\nTimeoutStopSec=15\n"
        "UMask=0077\nStandardOutput=journal\nStandardError=journal\n\n[Install]\nWantedBy=default.target\n")
    (units / "dnhacks-board-nudger-update.service").write_text(
        "[Unit]\nDescription=Verify and update Board nudger source/config/dependencies\n\n"
        f"[Service]\nType=oneshot\nEnvironment={unit_quote('PATH=' + config['path'])}\n"
        "UMask=0077\nTimeoutStartSec=180\n"
        "ExecStart=" + unit_exec([sys.executable, str(current / "scripts/board_nudge_service.py"),
                                    "--home", str(home), "update"]) + "\n")
    (units / "dnhacks-board-nudger-update.timer").write_text(
        "[Unit]\nDescription=Check Board nudger updates every minute\n\n[Timer]\n"
        "OnBootSec=60\nOnUnitActiveSec=60\nPersistent=true\n\n[Install]\nWantedBy=timers.target\n")
    run(["systemd-analyze", "--user", "verify", str(units / SERVICE),
         str(units / "dnhacks-board-nudger-update.service"), str(units / "dnhacks-board-nudger-update.timer")])
    run(["systemctl", "--user", "daemon-reload"])


def switch_release(home: Path, release: Path) -> None:
    temporary = home / "current.next"
    temporary.unlink(missing_ok=True)
    temporary.symlink_to(release)
    temporary.replace(home / "current")


def verify_running(home: Path, digest: str, *, timeout=85) -> dict:
    inbox = Inbox(home / "nudger.sqlite3")
    probe = "local-health:" + uuid.uuid4().hex
    with inbox.db:
        inbox.put(probe, 0, "__local_health__", "Local restart delivery verification; no external recipient")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = run(["systemctl", "--user", "show", SERVICE, "--property=MainPID", "--value"], check=False)
        pid = int(result.stdout.strip() or 0)
        try:
            health = json.loads((home / "health.json").read_text())
        except (OSError, ValueError):
            health = {}
        delivered = inbox.db.execute("SELECT status FROM deliveries WHERE key=?", (probe,)).fetchone()[0]
        if pid and health.get("pid") == pid and health.get("fingerprint") == digest and delivered == "delivered":
            command = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode()
            cwd = str(Path(f"/proc/{pid}/cwd").resolve())
            if "board_nudge.py" not in command or health.get("release") != str((home / "current").resolve()):
                raise RuntimeError("Service process does not match updated release")
            result = {"time": stamp(), "pid": pid, "command": command, "cwd": cwd,
                      "fingerprint": digest, "health": health, "delivery_probe": probe,
                      "probe_status": delivered}
            write_json(home / "verified.json", result)
            return result
        time.sleep(1)
    raise RuntimeError("Updated service did not verify PID/release and durable delivery before timeout")


def update(home: Path, *, initial: bool = False, force: bool = False) -> dict:
    home.mkdir(parents=True, exist_ok=True)
    lock = nudger.acquire_lock(home / "update.lock")
    # Read deployment metadata independently of the old runtime's route schema.
    # The copied new runtime validates its own config before the switch.
    config = json.loads((home / "config.json").read_text())
    source = Path(config["source_root"]).resolve()
    digest, manifest = fingerprint(source, config)
    current = home / "current"
    active = run(["systemctl", "--user", "is-active", SERVICE], check=False).returncode == 0
    if current.exists() and current.resolve().name == digest and active and not force:
        return {"changed": False, "fingerprint": digest}
    if nudger.mirror_running():
        raise RuntimeError("Mirror detected; refusing a second delivery service")
    release = home / "releases" / digest
    if not release.exists():
        release.parent.mkdir(exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix="release-", dir=release.parent))
        (staging / "scripts").mkdir()
        for name in manifest["sources"]:
            shutil.copy2(source / "scripts" / name, staging / "scripts" / name)
        runtime_config = dict(config, fingerprint=digest)
        write_json(staging / "config.json", runtime_config)
        write_json(staging / "manifest.json", manifest)
        run([sys.executable, "-m", "py_compile", *map(str, (staging / "scripts").glob("*.py"))])
        run([sys.executable, "-c", "import sys; from pathlib import Path; "
             "sys.path.insert(0,sys.argv[1]); from board_nudge import load_config; "
             "load_config(Path(sys.argv[2]))", str(staging / "scripts"), str(staging / "config.json")])
        if fingerprint(source, config)[0] != digest:
            raise RuntimeError("Source changed during snapshot; retry after edits settle")
        staging.replace(release)
    # Execute the copied release, not imports cached by the old updater process.
    run([sys.executable, str(release / "scripts/board_nudge_service.py"), "--home", str(home),
         "self-test", "--output", str(home / "self-test.json")], timeout=30)
    previous = current.resolve() if current.exists() else None
    switch_release(home, release)
    try:
        install_units(home, source, config)
        if initial:
            run(["systemctl", "--user", "enable", SERVICE, "dnhacks-board-nudger-update.timer"])
        run(["systemctl", "--user", "restart", SERVICE])
        verified = verify_running(home, digest)
        run(["systemctl", "--user", "start", "dnhacks-board-nudger-update.timer"])
        write_json(home / "last-update.json", {"fingerprint": digest, "source": str(source),
                                               "time": stamp(), "verified": verified})
        return {"changed": True, "fingerprint": digest, "verified": verified}
    except Exception:
        if previous:
            switch_release(home, previous)
            old = nudger.load_config(previous / "config.json")
            install_units(home, Path(old["source_root"]), old)
            run(["systemctl", "--user", "restart", SERVICE], check=False)
        raise


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--home", type=Path, default=state_home())
    sub = ap.add_subparsers(dest="command", required=True)
    install = sub.add_parser("install")
    install.add_argument("--source-root", type=Path, required=True)
    install.add_argument("--config", type=Path, required=True, help="reviewable explicit route configuration")
    install.add_argument("--bootstrap-now", action="store_true", help="explicitly acknowledge that historical mentions were already reviewed")
    sub.add_parser("update").add_argument("--force", action="store_true")
    sub.add_parser("status")
    test = sub.add_parser("self-test")
    test.add_argument("--output", type=Path, required=True)
    args = ap.parse_args(argv)
    home = args.home.resolve()
    if args.command == "self-test":
        print(json.dumps(transport_self_test(args.output), indent=2))
    elif args.command == "install":
        config = nudger.load_config(args.config)
        config.update(source_root=str(args.source_root.resolve()), path=os.environ["PATH"])
        if args.bootstrap_now:
            config.update(start_since=stamp(), bootstrap_note="Explicit install --bootstrap-now after operator history audit")
        if not (home / "nudger.sqlite3").exists() and not config.get("start_since"):
            raise SystemExit("First install requires start_since in config or explicit --bootstrap-now after a history audit")
        write_json(home / "config.json", config)
        print(json.dumps(update(home, initial=True), indent=2))
    elif args.command == "update":
        print(json.dumps(update(home, force=args.force), indent=2))
    else:
        for name in ("config.json", "health.json", "verified.json", "last-update.json"):
            path = home / name
            print(name, path.read_text() if path.exists() else "not installed")
        print(run(["systemctl", "--user", "status", SERVICE, "--no-pager"], check=False).stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
