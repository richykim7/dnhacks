"""Direct host Python execution with captured output and owned-process cleanup.

The historical module name is retained for callers. No container runtime is used.
Execution runs as the app OS user; this module is not an OS security boundary.
"""
from __future__ import annotations

import ast
import codecs
import importlib.util
import json
import os
import selectors
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

_HERE = Path(__file__).resolve().parent
SANDBOX_LIB = _HERE / "sandbox_lib"
DATA_DIR = _HERE.parents[2] / "data"
_STREAM_CAP = 1_000_000


def ensure_environment():
    modules = ("numpy", "pandas", "scipy", "statsmodels", "sklearn", "pyarrow", "duckdb",
               "Bio", "gseapy", "pingouin", "matplotlib", "openpyxl", "GEOparse", "anndata", "h5py")
    missing = [name for name in modules if importlib.util.find_spec(name) is None]
    if missing:
        raise RuntimeError("Missing host experiment dependencies: " + ", ".join(missing)
                           + ". Run uv sync --extra experiments.")


def resolve_code_paths(code, paths):
    """Resolve documented legacy path literals, without creating host root aliases."""
    class Resolve(ast.NodeTransformer):
        def visit_Constant(self, node):
            if isinstance(node.value, str):
                for alias, target in paths.items():
                    if node.value == alias or node.value.startswith(alias + "/"):
                        return ast.copy_location(ast.Constant(str(target) + node.value[len(alias):]), node)
            return node
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code  # The child reports the original syntax failure through stderr.
    return ast.unparse(ast.fix_missing_locations(Resolve().visit(tree))) + "\n"


_HOST_BOOTSTRAP = """import ctypes, os, runpy, signal, sys
path, expected_parent = sys.argv[1], int(sys.argv[2])
if sys.platform.startswith('linux'):
    def parent_ended(signum, frame):
        os.killpg(os.getpgrp(), signal.SIGKILL)
    signal.signal(signal.SIGTERM, parent_ended)
    if ctypes.CDLL(None, use_errno=True).prctl(1, signal.SIGTERM, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), 'Cannot register parent-death cleanup')
    if os.getppid() != expected_parent:
        parent_ended(signal.SIGTERM, None)
sys.argv = [path]
runpy.run_path(path, run_name='__main__')
"""


def _stop_group(proc):
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


@dataclass
class RunResult:
    ok: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_s: float
    timed_out: bool
    artifacts: list[dict] = field(default_factory=list)


def stream_process(cmd, timeout, *, on_output=None, cancel=None, stop=None, cwd=None, env=None):
    """Drain both pipes incrementally with bounded retained tails and explicit offsets."""
    tails = {"stdout": "", "stderr": ""}
    offsets = {"stdout": 0, "stderr": 0}
    sent = {"stdout": 0, "stderr": 0}
    decoder = {s: codecs.getincrementaldecoder("utf-8")("replace") for s in tails}
    timed_out = False
    stopped = False
    start = time.monotonic()
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          stdin=subprocess.DEVNULL, start_new_session=True, cwd=cwd, env=env) as proc:
        try:
            with selectors.DefaultSelector() as selector:
                for name in tails:
                    selector.register(getattr(proc, name), selectors.EVENT_READ, name)
                while selector.get_map() or proc.poll() is None:
                    if not stopped and ((cancel and cancel.is_set()) or (timeout is not None and time.monotonic() - start > timeout)):
                        stopped = True
                        timed_out = not (cancel and cancel.is_set())
                        if stop:
                            stop()
                        _stop_group(proc)
                    for key, _ in selector.select(0.1):
                        raw = os.read(key.fileobj.fileno(), 4096)
                        name = key.data
                        chunk = decoder[name].decode(raw, final=not raw)
                        if not raw:
                            selector.unregister(key.fileobj)
                        tails[name] = (tails[name] + chunk)[-_STREAM_CAP:]
                        if on_output and raw and sent[name] < _STREAM_CAP:
                            on_output({"stream": name, "offset": offsets[name], "text": chunk})
                            sent[name] += len(raw)
                        offsets[name] += len(raw)
                _stop_group(proc)
                proc.wait()
        except BaseException:
            if stop:
                stop()
            _stop_group(proc)
            proc.wait()
            raise
    for name in tails:
        if offsets[name] > _STREAM_CAP:
            tails[name] = f"[Earlier output truncated; {offsets[name]} bytes produced]\n" + tails[name]
            if on_output:
                on_output({"stream": name, "offset": offsets[name], "truncated": True,
                           "text": "[Live output capped; final retained tail is in recorded output]"})
    return proc.returncode, tails["stdout"], tails["stderr"], timed_out


def run_code(code: str, *, timeout: int | None = None, cpus=4,
             network: str = "none", data_dir: Path | str | None = DATA_DIR,
             cache_dir: Path | str | None = None, job_base: str | None = None,
             scratch_dir: Path | str | None = None, progress=None, journal=None, cancel=None,
             scope: dict | None = None) -> RunResult:
    """Run Python directly in the active interpreter's environment.

    Network policy is supplied to the code as an instruction; host execution is not
    filesystem/network isolation. Only declared runtime variables are passed through.
    """
    if network not in {"none", "bridge", "allowed"}:
        raise ValueError("Unknown network policy")
    jobdir = Path(tempfile.mkdtemp(prefix="explorer-job-", dir=job_base)).resolve()
    try:
        output = jobdir / "output"; output.mkdir()
        cache = Path(cache_dir).resolve() if cache_dir else jobdir / "cache"
        scratch = Path(scratch_dir).resolve() if scratch_dir else jobdir / "scratch"
        cache.mkdir(parents=True, exist_ok=True); scratch.mkdir(parents=True, exist_ok=True)
        paths = {"/work": jobdir, "/cache": cache, "/scratch": scratch}
        if data_dir is not None:
            paths["/data"] = Path(data_dir).resolve()
        executed = resolve_code_paths(code, paths)
        script = jobdir / "code.py"; script.write_text(executed)
        env = {k: v for k, v in os.environ.items() if k in
               {"PATH", "LANG", "TZ", "SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"}
               or k.startswith("LC_")}
        threads = str(max(1, int(cpus)))
        env.update(PYTHONPATH=str(SANDBOX_LIB), PYTHONUNBUFFERED="1", PYTHONDONTWRITEBYTECODE="1",
                   MPLCONFIGDIR=str(jobdir / "matplotlib"), OMP_NUM_THREADS=threads,
                   OPENBLAS_NUM_THREADS=threads, MKL_NUM_THREADS=threads, NUMEXPR_NUM_THREADS=threads,
                   DN_ARTIFACT_DIR=str(output), DNHACKS_CACHE_DIR=str(cache), DNHACKS_SCRATCH_DIR=str(scratch),
                   DNHACKS_NETWORK_POLICY=network)
        if data_dir is not None:
            env["DNHACKS_DATA_DIR"] = str(paths["/data"])
        if scope is not None:
            env["DNHACKS_EXPERIMENT_SCOPE"] = json.dumps(scope)
        payload = {"status": "running", "execution_backend": "host", "interpreter": sys.executable,
                   "path_aliases": {k: str(v) for k, v in paths.items()}, "network_policy": network}
        if journal:
            payload["code"] = journal.blob(executed)
        if progress:
            progress("experiment.started", payload)
        t0 = time.monotonic()
        rc, out, err, timed_out = stream_process([sys.executable, "-u", "-c", _HOST_BOOTSTRAP, str(script), str(os.getpid())], timeout,
            cwd=jobdir, env=env, cancel=cancel,
            on_output=(lambda p: progress("experiment.output", p)) if progress else None)
        artifacts = []
        if journal:
            from .artifacts import collect
            artifacts = collect(output, journal)
        return RunResult(ok=(rc == 0 and not timed_out), exit_code=rc, stdout=out or "", stderr=err or "",
                         duration_s=round(time.monotonic() - t0, 2), timed_out=timed_out, artifacts=artifacts)
    finally:
        shutil.rmtree(jobdir, ignore_errors=True)


MAX_TREE_EXPERIMENTS = 6    # Queue host jobs; this does not end an investigation.


class SandboxPool:
    """One tree-wide allowance of concurrent host processes, shared by reference across every branch (the
    same shape as `ForkBudget` for branches). It is a queue, not a
    quota: every experiment still runs, fewer at once. A branch never holds a slot while awaiting
    something that needs one, so it cannot deadlock."""

    def __init__(self, total: int = MAX_TREE_EXPERIMENTS):
        self.total = max(1, int(total))
        self._sem = threading.BoundedSemaphore(self.total)

    @contextmanager
    def slot(self):
        self._sem.acquire()
        try:
            yield
        finally:
            self._sem.release()


def run_many(codes: list[str], *, max_parallel: int = 4, pool: "SandboxPool | None" = None,
             progress=None, experiment_scopes=None, **kw) -> list[RunResult]:
    """Run several experiments concurrently (the explorer's divergent fan-out). Order preserved.

    Blocking; call it off the event loop (`asyncio.to_thread`). `max_parallel` bounds this branch's
    fan-out; `pool`, when supplied, also bounds the whole fork tree."""
    from concurrent.futures import ThreadPoolExecutor
    if not codes:
        return []

    def one(item) -> RunResult:
        i, c = item
        args = dict(kw, progress=(lambda kind, payload: progress(i, kind, payload)) if progress else None)
        if experiment_scopes is not None:
            args["scope"] = experiment_scopes[i]
        if kw.get("cancel") and kw["cancel"].is_set():
            return RunResult(False, -9, "", "Cancelled before execution", 0, False)
        if pool is None:
            return run_code(c, **args)
        with pool.slot():
            if kw.get("cancel") and kw["cancel"].is_set():
                return RunResult(False, -9, "", "Cancelled before execution", 0, False)
            return run_code(c, **args)

    with ThreadPoolExecutor(max_workers=max(1, min(max_parallel, len(codes)))) as ex:
        return list(ex.map(one, enumerate(codes)))
