#!/usr/bin/env python3
"""Execute a scoped tissue tool call or build the pinned native adapter."""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from dnhacksbio.explorer.runtime import Journal
from dnhacksbio.tissue.tools import operate


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--journal")
    p.add_argument("--project")
    p.add_argument("--run")
    p.add_argument("--experiment")
    p.add_argument("--operation")
    p.add_argument("--args", default="{}")
    p.add_argument("--build-source")
    p.add_argument("--build-output")
    a = p.parse_args()
    if a.build_source:
        from dnhacksbio.tissue.engine import build_engine

        result = build_engine(Path(a.build_source), Path(a.build_output))
    else:
        if not all([a.journal, a.project, a.run, a.experiment, a.operation]):
            p.error("Full journal/project/run/experiment/operation scope required")
        result = asyncio.run(
            operate(
                Journal(a.journal, create=False),
                {
                    "project_id": a.project,
                    "run_id": a.run,
                    "experiment_id": a.experiment,
                },
                a.operation,
                json.loads(a.args),
            )
        )
    print(json.dumps(result, allow_nan=False))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, FileNotFoundError, KeyError, IndexError, RuntimeError, TimeoutError) as exc:
        print(json.dumps({'status':'failed','error':str(exc)[:2000]}))
        sys.exit(1)
