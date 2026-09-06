"""Record an already running ingestion; see litmap.timeline for the reusable API."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from dnhacksbio.litmap.timeline import Observer, main  # noqa: E402,F401

if __name__ == "__main__":
    main()
