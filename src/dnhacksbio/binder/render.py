"""Bounded local browser worker; navigates real runtime data without fabricated events."""
from __future__ import annotations

import base64
import json
import os
import signal
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from .geometry import canonical


def browser_renderer(base_url, investigation_id):
    parsed=urlsplit(base_url)
    if parsed.scheme not in {'http','https'} or parsed.hostname not in {'localhost','127.0.0.1','::1'} or parsed.username or parsed.password:
        raise ValueError('Capture requires a trusted local workspace server')
    script=Path(__file__).resolve().parents[3]/'frontend/scripts/capture-binder.mjs'
    def render(request):
        with tempfile.TemporaryDirectory(prefix='binder-capture-') as directory:
            source=Path(directory)/'request.json';destination=Path(directory)/'result.json'
            source.write_bytes(canonical({**request,'base_url':base_url,'investigation_id':investigation_id}))
            with (Path(directory)/'worker.log').open('wb') as log:
                process=subprocess.Popen(['node',str(script),str(source),str(destination)],stdout=log,stderr=log,start_new_session=True)
                try:
                    process.wait(timeout=request['render_seconds'])
                    if process.returncode:
                        from dnhacksbio.explorer.runtime import redact
                        with (Path(directory)/'worker.log').open('rb') as diagnostic:
                            diagnostic.seek(max(0,(Path(directory)/'worker.log').stat().st_size-3000))
                            detail=redact(diagnostic.read(3000).decode(errors='replace'))
                        raise ValueError('Browser capture failed: '+detail)
                    if not destination.exists() or destination.stat().st_size>12*1024*1024:
                        raise ValueError('Browser capture output missing or oversized')
                    result=json.loads(destination.read_text())
                    result['png']=base64.b64decode(result['png'],validate=True)
                    return result
                except subprocess.TimeoutExpired as exc:
                    raise ValueError('Browser capture exceeded render-time budget') from exc
                finally:
                    # Kill descendants even if the Node parent exited unsuccessfully.
                    try:os.killpg(process.pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                    process.wait()
    return render
