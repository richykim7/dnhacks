"""Add a terminal presentation bundle to an existing app data root without replacing state.

The default is a read-only validation. Apply copies a private project and referenced
immutable blobs, then inserts the investigation in one journal transaction. A receipt
allows a retry after an interrupted registration; existing records are never replaced.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sqlite3
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from dnhacksbio.explorer import lineage
from dnhacksbio.explorer.runtime import Journal, TERMINAL, safe_id
from dnhacksbio.webui.deployment import lease
from dnhacksbio.webui.projects import ID_RE

RECEIPT = ".presentation-import.json"
HASH = re.compile(r"^[a-f0-9]{64}$")


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest_file(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def regular(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
        raise ValueError(f"Expected a private regular file: {path.name}")


def readonly(path):
    return sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=20)


def references(value):
    """Find runtime blob references, including references inside JSON output blobs."""
    if isinstance(value, dict):
        if "storage_key" in value:
            key = value["storage_key"]
            if not isinstance(key, str) or not HASH.fullmatch(key):
                raise ValueError("Invalid immutable blob key")
            if value.get("sha256", key) != key:
                raise ValueError("Blob digest metadata disagrees with its key")
            yield key, value.get("byte_length")
        for child in value.values():
            yield from references(child)
    elif isinstance(value, list):
        for child in value:
            yield from references(child)


def load_bundle(source, destination, project, root):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError("Source and destination must be separate data roots")
    if not ID_RE.fullmatch(project):
        raise ValueError("Invalid project identifier")
    if lineage.root(safe_id(root)) != root:
        raise ValueError("Expected an investigation root identifier")
    project_path = source / "projects" / project
    if project_path.resolve() != project_path:
        raise ValueError("Source project must be a private directory")
    regular(project_path / "project.json")
    regular(project_path / "kg.duckdb")
    if (project_path / "kg.duckdb.wal").exists():
        raise ValueError("Source graph has a pending WAL; close its writer before export")
    record = json.loads((project_path / "project.json").read_text())
    if record.get("id") != project or record.get("presentation_only") is not True:
        raise ValueError("Project must explicitly be presentation_only and match its ID")
    if record.get("adopted"):
        raise ValueError("Presentation project must own its graph")
    if record.get("kg_db") and Path(record["kg_db"]).resolve() != project_path / "kg.duckdb":
        raise ValueError("Project graph points outside its private directory")
    if record.get("runs") != [root]:
        raise ValueError("Project must contain exactly the requested investigation")
    files, links = {}, {}
    for path in sorted(project_path.rglob("*")):
        relative = str(path.relative_to(project_path))
        if path.is_symlink():
            if relative != "papers" or not path.resolve().is_dir():
                raise ValueError("Only a read-only papers directory link is permitted")
            links[relative] = str(path.resolve())
        elif path.is_file():
            regular(path)
            if relative == RECEIPT:
                raise ValueError("Source must be a staged bundle, not an imported project")
            files[relative] = digest_file(path)
        elif not path.is_dir():
            raise ValueError("Unsupported project filesystem entry")
    journal = source / "processed/runtime/journal.sqlite3"
    regular(journal)
    with readonly(journal) as con:
        con.execute("BEGIN")
        manifests = [tuple(r) for r in con.execute("SELECT run_id,investigation_id,project_id,body FROM manifests ORDER BY run_id")]
        events = [tuple(r) for r in con.execute("SELECT investigation_id,sequence,event_id,body FROM events ORDER BY investigation_id,sequence")]
    if not manifests or not events:
        raise ValueError("Presentation journal is empty")
    run_ids, decoded = set(), []
    for run_id, investigation_id, project_id, body in manifests:
        m = json.loads(body)
        if (investigation_id != root or project_id != project or lineage.root(safe_id(run_id)) != root
                or m.get("run_id") != run_id or m.get("investigation_id") != root or m.get("project_id") != project
                or m.get("parent_run_id") != lineage.parent(run_id)):
            raise ValueError("Manifest is outside the requested project or lineage")
        run_ids.add(run_id)
        decoded.append(m)
    if root not in run_ids or any(lineage.parent(r) not in run_ids for r in run_ids if r != root):
        raise ValueError("Incomplete investigation lineage")
    lifecycles, event_ids, previous_time = {}, set(), -math.inf
    for expected_sequence, (investigation_id, sequence, event_id, body) in enumerate(events, 1):
        e = json.loads(body)
        if (investigation_id != root or sequence != expected_sequence or e.get("sequence") != sequence
                or e.get("investigation_id") != root or e.get("event_id") != event_id
                or e.get("run_id") not in run_ids or e.get("parent_run_id") != lineage.parent(e["run_id"])
                or event_id in event_ids):
            raise ValueError("Event identifiers, sequence or lineage are inconsistent")
        when = e.get("occurred_at")
        if not isinstance(when, (int, float)) or not math.isfinite(when) or when < previous_time:
            raise ValueError("Event timestamps must be finite and monotonic")
        previous_time = when
        event_ids.add(event_id)
        if e.get("kind") == "attempt.started":
            lifecycles[e["run_id"]] = "running"
        elif e.get("kind") == "lifecycle":
            lifecycles[e["run_id"]] = e["payload"].get("lifecycle")
        decoded.append(e)
    if any(lifecycles.get(r) not in TERMINAL for r in run_ids):
        raise ValueError("Every imported run must have a terminal final lifecycle")
    blobs, pending = {}, list(references(decoded))
    while pending:
        key, size = pending.pop()
        path = source / "processed/runtime/blobs" / key
        regular(path)
        if size is not None and path.stat().st_size != size:
            raise ValueError("Blob byte length mismatch")
        if key in blobs:
            continue
        if digest_file(path) != key:
            raise ValueError("Immutable blob content does not match its hash")
        blobs[key] = path
        try:
            child = json.loads(path.read_bytes())
        except (UnicodeDecodeError, ValueError):
            continue
        pending.extend(references(child))
    identity = dict(version=1, project_id=project, root_id=root, files=files, links=links,
                    manifests=manifests, events=events, blobs=sorted(blobs))
    fingerprint = hashlib.sha256(encoded(identity).encode()).hexdigest()
    return dict(source=source, destination=destination, project_path=project_path, project=project,
                root=root, record=record, files=files, links=links, manifests=manifests,
                events=events, blobs=blobs, fingerprint=fingerprint)


def inspect_destination(bundle, con=None):
    """Return new, recover, or noop; extra scoped review events are preserved."""
    target = bundle["destination"] / "projects" / bundle["project"]
    existing_project = target.exists() or target.is_symlink()
    if existing_project:
        if target.is_symlink() or not (target / RECEIPT).is_file():
            raise ValueError("Destination project exists without this import receipt")
        regular(target / RECEIPT)
        receipt = json.loads((target / RECEIPT).read_text())
        if receipt.get("fingerprint") != bundle["fingerprint"]:
            raise ValueError("Destination project conflicts with the staged bundle")
        current = json.loads((target / "project.json").read_text())
        if current.get("presentation_only") is not True or current.get("id") != bundle["project"]:
            raise ValueError("Destination presentation ownership changed")
        regular(target / "kg.duckdb")
        if Path(current.get("kg_db", "")).resolve() != target / "kg.duckdb":
            raise ValueError("Destination graph is no longer private")
    journal = bundle["destination"] / "processed/runtime/journal.sqlite3"
    if con is None and journal.exists():
        with readonly(journal) as reader:
            reader.execute("BEGIN")
            return inspect_destination(bundle, reader)
    if con is None:
        return "recover" if existing_project else "new"
    if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='manifests'").fetchone():
        raise ValueError("Destination journal has no recognized schema")
    expected_manifests = {r[0]: r for r in bundle["manifests"]}
    actual_manifests = {r[0]: tuple(r) for r in con.execute(
        "SELECT run_id,investigation_id,project_id,body FROM manifests WHERE investigation_id=? OR project_id=?",
        (bundle["root"], bundle["project"]))}
    # Also detect a run ID already owned by another investigation.
    for run_id in expected_manifests:
        row = con.execute("SELECT run_id,investigation_id,project_id,body FROM manifests WHERE run_id=?", (run_id,)).fetchone()
        if row and tuple(row) != expected_manifests[run_id]:
            raise ValueError("Run identifier collision")
    rows = [tuple(r) for r in con.execute("SELECT investigation_id,sequence,event_id,body FROM events WHERE investigation_id=? ORDER BY sequence", (bundle["root"],))]
    for event in bundle["events"]:
        row = con.execute("SELECT investigation_id,sequence,event_id,body FROM events WHERE event_id=?", (event[2],)).fetchone()
        if row and tuple(row) != event:
            raise ValueError("Event identifier collision")
    if actual_manifests or rows:
        if not existing_project or actual_manifests != expected_manifests or rows[:len(bundle["events"])] != bundle["events"]:
            raise ValueError("Existing investigation conflicts with this import")
        for investigation_id, sequence, event_id, body in rows[len(bundle["events"]):]:
            event = json.loads(body)
            if (event.get("run_id") not in expected_manifests or event.get("investigation_id") != bundle["root"]
                    or event.get("sequence") != sequence or event.get("event_id") != event_id
                    or event.get("kind") != "experiment.human_reviewed" or event.get("producer") != "human-review"):
                raise ValueError("Only scoped human review events may follow imported history")
        return "noop"
    return "recover" if existing_project else "new"


def durable_json(path, value):
    fd, name = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(encoded(value) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        sync_directory(path.parent)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def copy_blob(source, target, digest):
    if target.exists() or target.is_symlink():
        regular(target)
        if digest_file(target) != digest:
            raise ValueError("Destination immutable blob conflicts with its hash")
        return
    fd, name = tempfile.mkstemp(dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as out, source.open("rb") as inp:
            shutil.copyfileobj(inp, out)
            out.flush()
            os.fsync(out.fileno())
        if digest_file(Path(name)) != digest:
            raise ValueError("Source blob changed during import")
        # An atomic no-replace publication preserves a concurrent writer's blob.
        try:
            os.link(name, target)
        except FileExistsError:
            regular(target)
            if digest_file(target) != digest:
                raise ValueError("Concurrent blob conflicts with immutable digest")
        os.unlink(name)
        sync_directory(target.parent)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def insert_records(con, bundle):
    con.executemany("INSERT INTO manifests VALUES (?,?,?,?)", bundle["manifests"])
    con.executemany("INSERT INTO events VALUES (?,?,?,?)", bundle["events"])


def import_bundle(source, destination, project, root, *, apply=False, deployment_home=None):
    bundle = load_bundle(source, destination, project, root)
    action = inspect_destination(bundle)
    result = dict(action=action, applied=False, project_id=project, root_id=root,
                  manifests=len(bundle["manifests"]), events=len(bundle["events"]),
                  blobs=len(bundle["blobs"]), fingerprint=bundle["fingerprint"])
    # Validate existing immutable destinations even on a no-op or dry run.
    for digest in bundle["blobs"]:
        target = bundle["destination"] / "processed/runtime/blobs" / digest
        if target.exists() or target.is_symlink():
            regular(target)
            if digest_file(target) != digest:
                raise ValueError("Destination immutable blob conflicts with its hash")
        elif action == "noop":
            raise ValueError("Imported history is missing a referenced immutable blob")
    if not apply:
        return result
    deployment_lock = Path(deployment_home) / "research.lock" if deployment_home else None
    # A shared lease coexists with research, but excludes a deployment transition.
    with lease(path=deployment_lock):
        runtime = bundle["destination"] / "processed/runtime"
        runtime.mkdir(parents=True, exist_ok=True)
        with lease(exclusive=True, path=runtime / "presentation-import.lock"):
            action = inspect_destination(bundle)
            if action == "noop":
                return dict(result, action="noop", applied=True)
            blobs = runtime / "blobs"
            blobs.mkdir(exist_ok=True)
            for digest, path in bundle["blobs"].items():
                copy_blob(path, blobs / digest, digest)
            target = bundle["destination"] / "projects" / project
            receipt = dict(version=1, fingerprint=bundle["fingerprint"], project_id=project,
                           root_id=root, imported_events=len(bundle["events"]), state="prepared")
            staging = None
            try:
                if action == "new":
                    area = bundle["destination"] / "projects/.presentation-imports"
                    area.mkdir(parents=True, exist_ok=True)
                    staging = Path(tempfile.mkdtemp(dir=area))
                    for relative, digest in bundle["files"].items():
                        output = staging / relative
                        output.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(bundle["project_path"] / relative, output)
                        if digest_file(output) != digest:
                            raise ValueError("Source project changed during import")
                        with output.open("rb") as stream:
                            os.fsync(stream.fileno())
                    if (bundle["project_path"] / "kg.duckdb.wal").exists():
                        raise ValueError("Source graph became active during import")
                    for relative, linked_path in bundle["links"].items():
                        (staging / relative).symlink_to(linked_path, target_is_directory=True)
                    record = dict(bundle["record"], kg_db=str(target / "kg.duckdb"))
                    durable_json(staging / "project.json", record)
                    durable_json(staging / RECEIPT, receipt)
                # Journal initializes only an absent database; existing schemas are untouched.
                journal = Journal(bundle["destination"] / "processed", create=not (runtime / "journal.sqlite3").exists())
                with journal.connect() as con:
                    con.execute("BEGIN IMMEDIATE")
                    current = inspect_destination(bundle, con)
                    if current == "noop":
                        return dict(result, action="noop", applied=True)
                    if staging is not None:
                        if target.exists() or target.is_symlink():
                            raise ValueError("Destination project appeared during import")
                        os.rename(staging, target)
                        staging = None
                        sync_directory(target.parent)
                    insert_records(con, bundle)
                durable_json(target / RECEIPT, dict(receipt, state="imported"))
                return dict(result, action=action, applied=True)
            finally:
                if staging is not None:
                    shutil.rmtree(staging)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="Staged data root")
    parser.add_argument("--destination", type=Path, required=True, help="Actual app data root")
    parser.add_argument("--project", required=True)
    parser.add_argument("--root", required=True)
    parser.add_argument("--apply", action="store_true", help="Register after validation; default only reports")
    parser.add_argument("--deployment-home", type=Path, help="Installation home containing research.lock")
    args = parser.parse_args()
    try:
        print(json.dumps(import_bundle(args.source, args.destination, args.project, args.root,
                                      apply=args.apply, deployment_home=args.deployment_home), indent=2))
    except (ValueError, OSError, sqlite3.Error, RuntimeError) as exc:
        parser.exit(1, f"Presentation import refused: {exc}\n")


if __name__ == "__main__":
    main()
