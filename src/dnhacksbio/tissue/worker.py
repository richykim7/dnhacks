"""One durable simulation worker, launched by the trusted runtime job controller."""

import json
from pathlib import Path
import resource
import sys
import time
from .engine import run_condition, bundle
from .jobs import atomic
from .schema import canonical


def main():
    directory = Path(sys.argv[1])
    spec = json.loads((directory / "spec.json").read_text())
    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
    resource.setrlimit(resource.RLIMIT_CPU, (300, 300))
    resource.setrlimit(resource.RLIMIT_FSIZE, (64 * 1024**2, 64 * 1024**2))
    # The parent records process identity before this worker updates progress.
    for _ in range(100):
        if (directory / "status.json").exists():
            break
        time.sleep(0.01)
    status = json.loads((directory / "status.json").read_text())
    try:
        artifacts = []
        for seed in spec["seeds"]:
            conditions = []
            for condition in spec["conditions"]:
                result = run_condition(
                    Path(spec["engine"]),
                    directory / f"{seed}-{condition}",
                    spec["model"],
                    condition=condition,
                    seed=seed,
                    duration=spec["duration"],
                    cancel=directory / "cancel",
                )
                if "frames" not in result:
                    status.update(status=result["completion_status"])
                    atomic(directory / "status.json", status)
                    return
                conditions.append(result)
                status["completed_conditions"] = (
                    status.get("completed_conditions", 0) + 1
                )
                atomic(directory / "status.json", status)
            data = bundle(spec["model"], conditions)
            data["simulation"]["build"] = spec["build"]
            path = f"seed-{seed}.json"
            (directory / path).write_bytes(canonical(data))
            artifacts.append(dict(kind="tissue_simulation", path=path))
        (directory / "manifest.json").write_bytes(
            canonical(dict(schema_version=1, artifacts=artifacts))
        )
        status.update(status="completed", finished_at=time.time())
        atomic(directory / "status.json", status)
    except Exception as exc:
        status.update(status="failed", reason=f"{type(exc).__name__}: {exc}")
        atomic(directory / "status.json", status)


if __name__ == "__main__":
    main()
