"""Capture the actual deployed app while holding the shared browser slot."""
import os
import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from browser_tests import browser_slot, stop
with browser_slot():
    environment = dict(os.environ)
    environment.setdefault("CAPTURE_OUTPUT", str(ROOT / "video/public/capture"))
    script = "video/scripts/refine-graph.mjs" if environment.get("CAPTURE_FROM") == "graph" else "video/scripts/capture-app.mjs"
    process = subprocess.Popen(["node", script], cwd=ROOT, env=environment, start_new_session=True)
    try:
        result = process.wait()
        if result == 0:
            result = subprocess.run([sys.executable, "video/scripts/prepare-paper.py"], cwd=ROOT).returncode
        sys.exit(result)
    finally:
        stop(process)
