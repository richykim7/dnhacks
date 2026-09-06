"""Run browser tests with a per-user host queue and private servers/artifacts (POSIX)."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def browser_slot():
    # Shared by all worktrees; do not unlink a flock file while waiters may hold it.
    path = Path(f"/tmp/dnhacks-browser-{os.getuid()}.lock")
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("Waiting for another browser run on this host to finish...", flush=True)
            fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def stop(process):
    # Only our own process groups, including Chromium and Vite descendants.
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def wait_ready(process, path, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Server exited ({process.returncode}); inspect {path.parent} logs")
        if path.exists():
            return json.loads(path.read_text())["url"]
        time.sleep(0.1)
    raise RuntimeError(f"Server startup timed out; inspect {path.parent} logs")


def backend(ready):
    from http.server import ThreadingHTTPServer
    from dnhacksbio.webui.server import Handler

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    temporary = ready.with_suffix(".tmp")
    temporary.write_text(json.dumps({"url": f"http://127.0.0.1:{server.server_port}"}))
    temporary.replace(ready)
    server.serve_forever()


def run(args):
    frontend = ROOT / "frontend"
    python = os.environ.get("E2E_PYTHON", str(ROOT / ".venv/bin/python"))
    if not Path(python).is_file():
        raise RuntimeError("Run uv sync --extra dev first, or set E2E_PYTHON to a Python environment with the dev dependencies.")
    if not (frontend / "node_modules/@playwright/test/cli.js").is_file():
        raise RuntimeError("Run npm --prefix frontend ci first.")
    with browser_slot():
        results = frontend / "test-results"
        results.mkdir(exist_ok=True)
        run_dir = Path(tempfile.mkdtemp(prefix="run-", dir=results))
        print(f"Browser run: {run_dir}", flush=True)
        env = dict(os.environ)
        env.update(E2E_RUN_DIR=str(run_dir), PYTHONPATH=str(ROOT / "src"),
                   PYTHONUNBUFFERED="1", BINDER_REVIEW_DIR=str(run_dir / "binder-review"))
        # Test data must not inherit the hosted app's deployment lock.
        env.pop("DNHACKS_DEPLOY_LOCK", None)
        processes, logs = [], []

        def launch(command, cwd, log_name=None):
            log = None
            if log_name:
                log = (run_dir / log_name).open("w")
                logs.append(log)
            process = subprocess.Popen(command, cwd=cwd, env=env, start_new_session=True,
                                       stdout=log, stderr=subprocess.STDOUT if log else None)
            processes.append(process)
            return process

        try:
            with tempfile.TemporaryDirectory(prefix="dnhacks-browser-data-") as data:
                api = launch([python, str(Path(__file__).resolve()), "--backend", str(run_dir / "api.json")],
                             data, "api.log")
                env["API_PROXY_TARGET"] = wait_ready(api, run_dir / "api.json")
                vite = launch(["node", "scripts/e2e-server.mjs"], frontend, "vite.log")
                env["PLAYWRIGHT_BASE_URL"] = wait_ready(vite, run_dir / "vite.json")
                (run_dir / "run.json").write_text(json.dumps({
                    "checkout": str(ROOT), "api": env["API_PROXY_TARGET"],
                    "frontend": env["PLAYWRIGHT_BASE_URL"], "data": data,
                    "args": args,
                }, indent=2))
                test = launch(["node", "node_modules/@playwright/test/cli.js", "test", *args], frontend)
                try:
                    return test.wait()
                finally:
                    for process in reversed(processes):
                        stop(process)
                    processes.clear()
        finally:
            for process in reversed(processes):
                stop(process)
            for log in logs:
                log.close()


def main():
    def interrupted(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupted)
    try:
        if len(sys.argv) == 3 and sys.argv[1] == "--backend":
            backend(Path(sys.argv[2]))
            return 0
        return run(sys.argv[1:])
    except KeyboardInterrupt:
        return 130
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
