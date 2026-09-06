"""Bounded driver of the same production application used by the scientist."""

import base64
import json
import os
from pathlib import Path
import subprocess
import signal
import fcntl
from contextlib import contextmanager
import tempfile
from .schema import canonical, digest


@contextmanager
def browser_slot():
    fd = os.open(
        f"/tmp/dnhacks-browser-{os.getuid()}.lock",
        os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW,
        0o600,
    )
    with os.fdopen(fd, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def renderer(service, base_url=None):
    def render(recipe, viewport):
        service.artifact(recipe["artifact_sha256"])
        payload = dict(
            base_url=base_url
            or os.environ.get("TISSUE_RENDER_URL", "http://127.0.0.1:8765"),
            recipe=recipe,
            recipe_sha256=digest(recipe),
            viewport=list(viewport),
            investigation_id=service.manifest["investigation_id"],
        )
        script = (
            Path(__file__).resolve().parents[3] / "frontend/scripts/render-tissue.mjs"
        )
        with (
            browser_slot(),
            tempfile.TemporaryDirectory(prefix="tissue-render-") as folder,
        ):
            inp = Path(folder) / "input.json"
            out = Path(folder) / "output.json"
            inp.write_bytes(canonical(payload))
            process = subprocess.Popen(
                ["node", str(script), str(inp), str(out)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
            try:
                _, stderr = process.communicate(timeout=90)
                if process.returncode:
                    raise RuntimeError(
                        "Tissue browser capture failed: "
                        + stderr.decode(errors="replace")[-4000:]
                    )
                if not out.is_file() or out.stat().st_size > 32 * 1024 * 1024:
                    raise ValueError("Capture output missing or oversized")
            except subprocess.TimeoutExpired as exc:
                detail=(exc.stderr or b'').decode(errors='replace')[-1500:]
                raise TimeoutError('Tissue capture exceeded90s. '+detail) from exc
            finally:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
            result = json.loads(out.read_bytes())
        result["png"] = base64.b64decode(result["png"], validate=True)
        result["canvas_pngs"] = [
            base64.b64decode(p, validate=True) for p in result["canvas_pngs"]
        ]
        return result

    return render
