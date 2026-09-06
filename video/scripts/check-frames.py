"""Use the repository's shared browser queue for an isolated Remotion/Playwright check."""
import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from browser_tests import browser_slot, stop
with browser_slot():
    process = subprocess.Popen(['node', 'scripts/check-frames.mjs'], cwd=ROOT/'video', start_new_session=True)
    try:
        sys.exit(process.wait())
    finally:
        stop(process)
