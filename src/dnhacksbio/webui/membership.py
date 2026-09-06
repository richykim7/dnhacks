"""Explicit collection membership writes; original script corpora remain untouched.

A per-project inherited flock serializes HTTP mutations with detached build/run/ingestion
workers. DuckDB remains the final cross-tool writer guard. Adoption makes a consistent
private copy while holding the original database's read lock; it never copies a live WAL.
"""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
from uuid import uuid4

from . import projects


@contextmanager
def project_lease(pid: str):
    projects.project_dir(pid)  # validate before paths/environment comparisons
    inherited = os.environ.get("DNHACKS_PROJECT_LEASE_FD")
    if inherited and os.environ.get("DNHACKS_PROJECT_LEASE_ID") == pid:
        fd = int(inherited)
        os.fstat(fd)
        yield fd
        return
    directory = projects.PROJECTS / ".membership-locks"
    directory.mkdir(parents=True, exist_ok=True)
    fd = os.open(directory / f"{pid}.lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("This collection is busy. Wait for its current operation to finish, then retry.") from exc
        yield fd
    finally:
        os.close(fd)


def assert_idle(pid: str):
    projects.assert_writable(pid)
    from . import jobs, data
    if jobs.active_job(pid):
        raise RuntimeError("This collection has an active job. Wait for it to finish before changing papers.")
    if any(run.get("active") for run in data.list_runs(include_all=True, project=pid)):
        raise RuntimeError("An investigation is using this collection. Wait for it to finish before changing papers.")


def write_connection(pid: str):
    projects.assert_writable(pid)
    import duckdb
    rec = projects.load(pid)
    if rec.get("adopted"):
        raise RuntimeError("Create a personal collection copy before changing its papers.")
    root = projects.project_dir(pid)
    db = projects.kg_path(pid)
    if root.is_symlink() or db.is_symlink() or not db.resolve().is_relative_to(root.resolve()):
        raise RuntimeError("This collection points to shared data. Create a private collection before changing its papers.")
    try:
        return duckdb.connect(str(db))
    except duckdb.Error as exc:
        raise RuntimeError("The collection database is in use. Wait for the active process to finish, then retry.") from exc


def ensure_editable(pid: str) -> tuple[dict, bool]:
    """Caller holds original project lease. No writes to an adopted graph or its assets."""
    rec = projects.load(pid)
    assert_idle(pid)
    if not rec.get("adopted"):
        root = projects.project_dir(pid)
        db = projects.kg_path(pid)
        if root.is_symlink() or db.is_symlink() or not db.resolve().is_relative_to(root.resolve()):
            raise RuntimeError("This collection points to shared data. Create a private collection before changing its papers.")
        return rec, False
    import duckdb
    source = Path(rec["kg_db"])
    if source.with_suffix(source.suffix + ".wal").exists():
        raise RuntimeError("This collection has pending database writes. Wait for its current process to close before copying it.")
    try:
        con = duckdb.connect(str(source), read_only=True)
    except duckdb.Error as exc:
        raise RuntimeError("This collection is in use. Its private copy can be created after the current process finishes.") from exc
    new = None
    try:
        new = projects.create(f"{rec['name']} collection"[:120], rec.get("description", ""), rec.get("spec"))
        target = projects.project_dir(new["id"])
        shutil.copy2(source, projects.kg_path(new["id"]))
        # A read-only connection holds a database lock, so no external writer can change it mid-copy.
        for name in ("MANIFEST.json", "corpus_card.md"):
            if (source.parent / name).is_file():
                shutil.copy2(source.parent / name, target / name)
        if (source.parent / "papers").is_dir():
            shutil.copytree(source.parent / "papers", target / "papers")
        new["status"] = "ready"
        new["membership_source"] = pid
        new = projects.save(new)
        return new, True
    except Exception:
        if new:
            shutil.rmtree(projects.project_dir(new["id"]))
        raise
    finally:
        con.close()


def _next_ref(pid: str) -> int:
    rec = projects.load(pid)
    highest = max([int(a.get("ref") or 0) for a in rec.get("attachments", [])] + [9999, int(rec.get("membership_next_ref", 10000)) - 1])
    if projects.kg_path(pid).exists():
        con = write_connection(pid)
        try:
            tables = {r[0] for r in con.execute("show tables").fetchall()}
            for table in ("papers", "evidence", "deferrals"):
                if table in tables:
                    highest = max(highest, int(con.execute(f"select coalesce(max(source_ref),0) from {table}").fetchone()[0]))
        finally:
            con.close()
    rec["membership_next_ref"] = highest + 2
    projects.save(rec)
    return highest + 1


def _launch(pid: str, items: list[dict], fd: int) -> dict:
    from . import jobs
    request = projects.project_dir(pid) / "membership" / f"request-{uuid4().hex}.json"
    projects._write_atomic(request, {"project_id": pid, "items": items})
    return _spawn_request(pid, request, fd)


def _spawn_request(pid, request, fd):
    from . import jobs
    argv = [jobs._python(), "-m", "dnhacksbio.litmap.library_ingest", "--project", pid, "--projects-root", str(projects.PROJECTS.resolve()), "--request", str(request)]
    return jobs._spawn(pid, "membership", argv, extra={"request_path": str(request)}, project_lease_fd=fd)


def add_dois(pid: str, dois) -> dict:
    if not isinstance(dois, list) or not 1 <= len(dois) <= 50 or not all(isinstance(d, str) for d in dois):
        raise ValueError("Provide between 1 and 50 DOI strings.")
    normalized = list(dict.fromkeys(re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", d.strip(), flags=re.I).lower() for d in dois))
    if any(not re.fullmatch(r"10\.\d{4,9}/\S+", d) or len(d) > 500 for d in normalized):
        raise ValueError("Enter complete DOIs, for example 10.1234/article, one per line.")
    with project_lease(pid) as original_fd:
        rec, copied = ensure_editable(pid)
        target = rec["id"]
        with _target_lease(pid, target) as fd:
            existing = set()
            if projects.kg_path(target).exists():
                con = write_connection(target)
                try:
                    if "papers" in {r[0] for r in con.execute("show tables").fetchall()}:
                        existing = {str(r[0]).lower() for r in con.execute("select doi from papers where doi is not null").fetchall()}
                finally:
                    con.close()
            items = [{"ref": _next_ref(target), "doi": doi} for doi in normalized if doi not in existing]
            job = _launch(target, items, fd if fd is not None else original_fd) if items else None
            return {"project_id": target, "copied": copied, "job": job, "duplicates": [d for d in normalized if d in existing]}


@contextmanager
def _target_lease(original, target):
    # Original lease already held; obtain the fresh copy's lease only when needed.
    if original == target:
        yield None
    else:
        with project_lease(target) as fd:
            yield fd


def add_upload(pid: str, filename: str, body: bytes) -> dict:
    from . import attachments
    with project_lease(pid) as original_fd:
        rec, copied = ensure_editable(pid)
        target = rec["id"]
        with _target_lease(pid, target) as target_fd:
            digest = hashlib.sha256(body).hexdigest()
            rec = projects.load(target)
            duplicate = next((a for a in rec.get("attachments", []) if a.get("sha256") == digest), None)
            if duplicate:
                raise ValueError("This document was already uploaded. Retry its processing job if it did not finish.")
            ref = _next_ref(target)
            att = attachments.add(target, filename, body)
            rec = projects.load(target)
            for a in rec["attachments"]:
                if a["id"] == att["id"]:
                    a.update(ref=ref, sha256=digest)
            projects.save(rec)
            job = _launch(target, [{"ref": ref, "attachment_id": att["id"]}], target_fd if target_fd is not None else original_fd)
            return {"project_id": target, "copied": copied, "job": job}


def retry(pid: str, job_id: str) -> dict:
    from . import jobs
    with project_lease(pid) as fd:
        assert_idle(pid)
        job = jobs.get_job(pid, job_id)
        if job.get("kind") != "membership" or job.get("status") not in ("failed", "cancelled"):
            raise ValueError("Only a failed or cancelled paper addition can be retried.")
        request = Path(job.get("request_path", "")).resolve()
        if not request.is_relative_to((projects.project_dir(pid) / "membership").resolve()) or not request.is_file():
            raise ValueError("The saved addition request is unavailable. Add the paper again.")
        return {"project_id": pid, "copied": False, "job": _spawn_request(pid, request, fd)}


def remove_paper(pid: str, paper_id: str) -> dict:
    with project_lease(pid):
        # Validate before copying: a repeated removal must not create empty orphan collections.
        rec = projects.load(pid)
        if rec.get("adopted"):
            import duckdb
            try:
                original = duckdb.connect(rec["kg_db"], read_only=True)
            except duckdb.Error as exc:
                raise RuntimeError("This collection is in use. Retry after the current process finishes.") from exc
            try:
                found = original.execute("select 1 from papers where paper_id=?", [paper_id]).fetchone() if "papers" in {r[0] for r in original.execute("show tables").fetchall()} else None
                if not found:
                    raise FileNotFoundError("Paper not found in this collection")
            finally:
                original.close()
        rec, copied = ensure_editable(pid)
        target = rec["id"]
        with _target_lease(pid, target):
            manifest_path = projects.project_dir(target) / "MANIFEST.json"
            manifest = json.loads(manifest_path.read_text()) if manifest_path.is_file() else None
            if manifest is not None and not isinstance(manifest, dict):
                raise ValueError("The collection manifest is invalid; repair it before changing papers.")
            from dnhacksbio.litmap.store import KGStore
            probe = write_connection(target)
            probe.close()
            store = KGStore(projects.kg_path(target))
            con = store.con
            try:
                tables = {r[0] for r in con.execute("show tables").fetchall()}
                row = con.execute("select source_ref from papers where paper_id=?", [paper_id]).fetchone() if "papers" in tables else None
                if not row:
                    raise FileNotFoundError("Paper not found in this collection")
                ref = row[0]
                con.execute("BEGIN TRANSACTION")
                con.execute("CREATE TABLE IF NOT EXISTS library_removed_sources (source_ref INTEGER PRIMARY KEY, removed_at TIMESTAMP DEFAULT current_timestamp)")
                con.execute("INSERT OR IGNORE INTO library_removed_sources(source_ref) VALUES (?)", [ref])
                # Only claims supported by the removed paper are candidates for deletion.
                con.execute("CREATE TEMP TABLE membership_affected AS SELECT DISTINCT claim_id FROM evidence WHERE source_ref=?", [ref])
                for table in ("evidence_context", "evidence_cites", "evidence", "experiments", "deferrals"):
                    con.execute(f"DELETE FROM {table} WHERE source_ref=?", [ref])
                con.execute("DELETE FROM claims WHERE claim_id IN (SELECT claim_id FROM membership_affected) AND claim_id NOT IN (SELECT claim_id FROM evidence)")
                con.execute("DELETE FROM papers WHERE source_ref=?", [ref])
                con.execute("DELETE FROM claim_vectors WHERE claim_id NOT IN (SELECT claim_id FROM claims)")
                store.refresh_status()
                con.execute("COMMIT")
                counts = store.counts()
                paper_count = con.execute("select count(*) from papers").fetchone()[0]
                columns = {row[0] for row in con.execute("describe papers").fetchall()}
                full_count = con.execute("select count(*) from papers where is_full_text").fetchone()[0] if "is_full_text" in columns else 0
                paper_counts = {"papers": paper_count, "full_text": full_count}
            except Exception:
                try:
                    con.execute("ROLLBACK")
                except Exception:
                    pass
                raise
            finally:
                con.close()
            # Assets and historical job/run records are intentionally retained. Paper listing and
            # retrieval use the transaction's papers table, never an orphaned manifest entry.
            rec = projects.load(target)
            rec["attachments"] = [a for a in rec.get("attachments", []) if a.get("ref") != ref]
            rec["build"] = {**rec.get("build", {}), "n_claims": counts["claims"], "n_papers": paper_count}
            if manifest is not None:
                manifest.update(n_papers=paper_count, n_claims=counts["claims"], n_attachments=len(rec["attachments"]))
                if isinstance(manifest.get("papers"), list):
                    manifest["papers"] = [p for p in manifest["papers"] if isinstance(p, dict) and str(p.get("ref")) != str(ref)]
                elif isinstance(manifest.get("papers"), dict):
                    manifest["papers"] = {**manifest["papers"], **paper_counts}
                if isinstance(manifest.get("kg"), dict):
                    manifest["kg"] = {**manifest["kg"], **counts}
                if isinstance(manifest.get("papers_meta"), list):
                    manifest["papers_meta"] = [p for p in manifest["papers_meta"] if isinstance(p, dict) and str(p.get("ref")) != str(ref)]
                projects._write_atomic(manifest_path, manifest)
            rec["membership_removed_refs"] = list(dict.fromkeys(rec.get("membership_removed_refs", []) + [ref]))
            projects.save(rec)
            refresh_card(target)
            return {"project_id": target, "copied": copied, "removed": paper_id, "ok": True}


def remove_attachment(pid: str, attachment_id: str) -> dict:
    """The legacy document control must not leave an ingested paper in the graph."""
    from . import attachments
    rec = projects.load(pid)
    att = next((a for a in rec.get("attachments", []) if a.get("id") == attachment_id), None)
    if not att:
        raise KeyError(attachment_id)
    if rec.get("kg_db"):
        import duckdb
        try:
            con = duckdb.connect(rec["kg_db"], read_only=True)
        except duckdb.Error as exc:
            raise RuntimeError("This collection is in use. Retry after its current operation finishes.") from exc
        try:
            paper = con.execute("select paper_id from papers where source_ref=?", [att["ref"]]).fetchone() if "papers" in {r[0] for r in con.execute("show tables").fetchall()} else None
        finally:
            con.close()
        if paper:
            return remove_paper(pid, paper[0])
    with project_lease(pid):
        assert_idle(pid)
        return attachments.remove(pid, attachment_id)


def refresh_card(pid: str) -> None:
    """Keep source framing on copied corpora and record authoritative current membership."""
    rec = projects.load(pid)
    card = projects.corpus_card_path(pid)
    if not rec.get("membership_source") or not card.is_file():
        projects.write_corpus_card(pid)
    marker = '<!-- library-membership -->'
    text = card.read_text().split(marker, 1)[0].rstrip()
    import duckdb
    con = duckdb.connect(str(projects.kg_path(pid)), read_only=True)
    try:
        tables = {row[0] for row in con.execute('show tables').fetchall()}
        papers = con.execute('select count(*) from papers').fetchone()[0] if 'papers' in tables else 0
        claims = con.execute('select count(*) from claims').fetchone()[0] if 'claims' in tables else 0
    finally:
        con.close()
    text += (f'\n\n{marker}\n## Current collection membership\n\n'
             f'This collection currently contains {papers} papers and {claims} claims. '
             'These current graph counts supersede counts in the source collection description above. '
             'Library additions and removals apply to this collection; the original source assets remain preserved.\n')
    temp = card.with_suffix('.md.tmp')
    temp.write_text(text)
    temp.replace(card)
