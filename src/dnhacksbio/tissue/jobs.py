"""Durable bounded CPU jobs; process output is kept outside tool observations."""

import json
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4
from dnhacksbio.explorer.runtime import process_identity, safe_id
from .schema import canonical, digest


def atomic(path, value):
    temp = path.with_suffix(".tmp")
    temp.write_bytes(canonical(value))
    os.replace(temp, path)


def launch(service, model, conditions, seeds, duration=1440, engine=None):
    from .engine import build_model, ENGINE_REVISION

    expected = build_model(
        model["parameters"],
        source_context=model.get("source_context"),
        geometry=model.get("geometry"),
        question=model.get("question"),
    )
    if model != expected:
        raise ValueError("Model specification hash or assumptions changed")
    if (
        not isinstance(seeds, list)
        or not 1 <= len(seeds) <= 3
        or len(set(seeds)) != len(seeds)
        or any(type(s) is not int or not 0 <= s < 2**31 for s in seeds)
    ):
        raise ValueError("One to three unique computational seeds required")
    allowed = {
        "baseline",
        "secretion_off",
        "uptake_suppressed",
        "double_off",
        "alanine_rescue",
    }
    if (
        not isinstance(conditions, list)
        or not 1 <= len(conditions) <= 5
        or len(set(conditions)) != len(conditions)
        or set(conditions) - allowed
    ):
        raise ValueError("Invalid condition set")
    if type(duration) not in (int, float) or not 1 <= duration <= 2880:
        raise ValueError("Invalid duration")
    binary = Path(engine or os.environ.get("TISSUE_ENGINE", ""))
    if not binary.is_file():
        raise ValueError("Configure TISSUE_ENGINE to the pinned built CPU executable")
    build = json.loads((binary.parent / "build.json").read_text())
    if build.get("revision") != ENGINE_REVISION:
        raise ValueError("Unreviewed native engine revision")
    if digest(binary.read_bytes()) != build["executable_sha256"]:
        raise ValueError("Native engine build receipt mismatch")
    root = service.journal.directory / "tissue-jobs"
    root.mkdir(exist_ok=True)
    with service.lock():
        active = 0
        for old in root.glob("*/status.json"):
            record = json.loads(old.read_text())
            if record["status"] == "running" and process_identity(
                record.get("pid")
            ) == record.get("process_identity"):
                active += 1
        if active >= 2:
            raise ValueError("Two CPU jobs already active; retry after completion")
        jid = uuid4().hex
        directory = root / jid
        directory.mkdir()
        spec = dict(
            job_id=jid,
            scope=service.scope,
            model=model,
            conditions=conditions,
            seeds=seeds,
            duration=duration,
            engine=str(binary.resolve()),
            build=build,
        )
        atomic(directory / "spec.json", spec)
        with (directory / "worker.log").open("wb") as log:
            proc = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "dnhacksbio.tissue.worker",
                    str(directory.resolve()),
                ],
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                cwd=directory,
                env={
                    **os.environ,
                    "PYTHONPATH": str(Path(__file__).resolve().parents[2]),
                    "OMP_NUM_THREADS": "1",
                },
            )
        status = dict(
            job_id=jid,
            status="running",
            pid=proc.pid,
            process_identity=process_identity(proc.pid),
            started_at=time.time(),
        )
        atomic(directory / "status.json", status)
        service.append(
            "tissue.job",
            {
                "job_id": jid,
                "status": "running",
                "model_id": model["model_id"],
                "conditions": conditions,
                "seeds": seeds,
            },
        )
        return status


def job_status(service, jid, cancel=False):
    directory = service.journal.directory / "tissue-jobs" / safe_id(jid)
    spec = json.loads((directory / "spec.json").read_text())
    if spec["scope"] != service.scope:
        raise FileNotFoundError("Job outside experiment scope")
    if cancel:
        (directory / "cancel").touch()
    status = json.loads((directory / "status.json").read_text())
    if status["status"] == "running" and process_identity(
        status.get("pid")
    ) != status.get("process_identity"):
        status.update(status="failed", reason="Worker exited without completion")
        atomic(directory / "status.json", status)
    if status["status"] == "completed":
        from dnhacksbio.explorer.artifacts import collect

        with service.lock():
            prior = [
                e
                for e in service.history()
                if e["kind"] == "tissue.job"
                and e["payload"].get("job_id") == jid
                and e["payload"].get("status") == "collected"
            ]
            if not prior:
                artifacts = collect(directory, service.journal)
                if not artifacts or any(a["status"] != "available" for a in artifacts):
                    raise ValueError("Completed tissue output rejected by collector")
                for a in artifacts:
                    if not any(
                        e["kind"] == "artifact"
                        and e["payload"].get("tissue_job_id") == jid
                        and e["payload"].get("sha256") == a["sha256"]
                        for e in service.history()
                    ):
                        service.append("artifact", {**a, "tissue_job_id": jid})
                service.append(
                    "tissue.job",
                    {
                        "job_id": jid,
                        "status": "collected",
                        "artifacts": [a["sha256"] for a in artifacts],
                    },
                )
            status["artifacts"] = [
                e["payload"]["artifacts"]
                for e in service.history()
                if e["kind"] == "tissue.job"
                and e["payload"].get("job_id") == jid
                and e["payload"].get("status") == "collected"
            ][-1]
    return status
