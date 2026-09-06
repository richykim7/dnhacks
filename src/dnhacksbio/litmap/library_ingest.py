"""Explicit, resumable additions to one privately owned Library graph.

Only the detached membership job calls this module; inspection never starts work.
Each new ref checkpoints conversion and extraction before publishing. Retrying an
index failure reuses both, and never sends the existing corpus to the extractor.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path

from dnhacksbio.webui import projects


def _save(path: Path, value) -> None:
    def serial(obj):
        if hasattr(obj, "model_dump"):
            return obj.model_dump(mode="json")
        raise TypeError(type(obj).__name__)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, default=serial, indent=2), encoding="utf-8")
    tmp.replace(path)


def _read(path: Path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def _source(pid: str, item: dict, dest: Path) -> dict:
    from dnhacksbio.litmap import find
    from dnhacksbio.litmap.document_parse import parse_document_bytes
    from dnhacksbio.webui import attachments
    root = projects.project_dir(pid)
    cached = _read(dest / "source.json")
    if cached:
        return cached
    if item.get("doi"):
        doi = find.normalize_doi(item["doi"])
        candidate = find.openalex_by_doi(doi)
        if candidate is None:
            matches = find.europepmc_search(f'DOI:"{doi}"', max_results=1)
            candidate = next((c for c in matches if find.normalize_doi(c.doi) == doi), None)
        if candidate is None:
            raise ValueError(f"Could not resolve {doi}. Check the DOI or upload a full-text document.")
        result = find.fetch_fulltext(candidate, root / "papers" / "library_sources")
        if not result.get("is_full_text"):
            raise ValueError(f"Full text unavailable for {doi}. Upload a PDF, text or XML copy.")
        base = find._artifact_dir(root / "papers" / "library_sources", candidate)
        meta = {"doi": doi, "title": candidate.title, "year": candidate.year,
                "pmid": candidate.pmid, "pmcid": candidate.pmcid,
                "url": result.get("url", ""), "license": result.get("license", ""),
                "raw_file": str((base / result["raw_file"]).relative_to(root)) if result.get("raw_file") else None}
    else:
        att = next((a for a in projects.load(pid).get("attachments", [])
                    if a["id"] == item.get("attachment_id")), None)
        if not att:
            raise ValueError("The uploaded document is missing. Upload it again.")
        raw = (projects.attachments_dir(pid) / att["file"]).resolve()
        if not raw.is_relative_to(projects.attachments_dir(pid).resolve()):
            raise ValueError("Document path is outside this collection")
        data = raw.read_bytes()
        base = dest / "assets"
        base.mkdir(parents=True, exist_ok=True)
        result = parse_document_bytes(data, att["ext"], base)
        if result.get("needs_ocr") or len(result.get("text", "").strip()) < attachments.MIN_TEXT_CHARS:
            raise ValueError("The document has unreadable pages. Run OCR or upload a text/XML copy.")
        result["raw_sha256"] = hashlib.sha256(data).hexdigest()
        local_raw = dest / f"source.{att['ext']}"
        local_raw.write_bytes(data)
        meta = {"doi": att.get("doi", ""), "title": att["filename"], "year": att.get("year"),
                "attachment_id": att["id"], "raw_file": str(local_raw.relative_to(root))}
    # Preserve local JATS citation metadata when present, without another lookup.
    xml_bytes = None
    if not item.get("doi") and att["ext"] == "xml":
        xml_bytes = data
    elif result.get("raw_file", "").endswith(".xml"):
        xml_path = (base / result["raw_file"]).resolve()
        if xml_path.is_relative_to(base.resolve()) and xml_path.is_file():
            xml_bytes = xml_path.read_bytes()
    if xml_bytes:
        import xml.etree.ElementTree as ET
        tree = ET.fromstring(xml_bytes)
        local = lambda node: node.tag.rsplit("}", 1)[-1]
        authors = []
        for node in tree.iter():
            if local(node) == "contrib" and node.get("contrib-type") == "author":
                parts = {local(n): " ".join(n.itertext()).strip() for n in node.iter()
                         if local(n) in {"given-names", "surname"}}
                name = " ".join(parts.get(k, "") for k in ("given-names", "surname")).strip()
                if name:
                    authors.append(name)
        if authors:
            meta["authors"] = authors
        title = next((" ".join(n.itertext()).strip() for n in tree.iter()
                      if local(n) == "article-title"), "")
        if title:
            meta["title"] = title
    figures = [{**f, "path": str((base / f["path"]).relative_to(root)) if f.get("path") else None}
               for f in result.get("figures", [])]
    source = {**meta, "ref": int(item["ref"]), "text": result["text"], "figures": figures,
              "is_full_text": True, "raw_sha256": result.get("raw_sha256"),
              "text_sha256": hashlib.sha256(result["text"].encode()).hexdigest()}
    _save(dest / "source.json", source)
    return source


def _duplicate(store, source):
    doi = source.get("doi", "").strip().lower()
    rows = store.con.execute("SELECT source_ref, doi, text FROM papers").fetchall()
    for ref, existing_doi, text in rows:
        if ref == source["ref"]:
            continue
        if (doi and doi == (existing_doi or "").strip().lower()) or (
                hashlib.sha256((text or "").encode()).hexdigest() == source["text_sha256"]):
            return ref
    return None


def _manifest(root, source, store):
    path = root / "MANIFEST.json"
    manifest = _read(path, {})
    # Script corpora keep metadata in papers; console builds use papers for
    # counts and papers_meta for metadata. Preserve each existing shape.
    existing = manifest.get("papers")
    rows = existing if isinstance(existing, list) else manifest.get("papers_meta", [])
    rows = [p for p in rows if isinstance(p, dict) and p.get("ref") != source["ref"]]
    rows.append({k: v for k, v in source.items() if k != "text"})
    from dnhacksbio.explorer.fulltext import FullTextStore
    paper_counts = FullTextStore(con=store.con).counts()
    kg_counts = store.counts()
    manifest.update(papers=({**existing, **paper_counts} if isinstance(existing, dict) else rows),
                    papers_meta=rows, n_papers=paper_counts["papers"],
                    n_claims=kg_counts["claims"], kg=kg_counts)
    _save(path, manifest)


async def ingest(project_id: str, items: list[dict], prog) -> dict:
    """Caller holds membership.project_lease for the entire operation."""
    from dnhacksbio.litmap.store import KGStore
    from dnhacksbio.explorer.fulltext import FullTextStore
    from dnhacksbio.litmap.schema import Claim, Experiment, Deferral
    from dnhacksbio.litmap import extract
    rec = projects.load(project_id)
    root = projects.project_dir(project_id).resolve()
    db = projects.kg_path(project_id).resolve()
    if rec.get("adopted") or not db.is_relative_to(root) or (
            rec.get("kg_db") and Path(rec["kg_db"]).resolve() != db):
        raise ValueError("Create a private collection copy before changing membership")
    # Fail on an active graph writer before acquisition or model work.
    probe = KGStore(db)
    FullTextStore(con=probe.con)
    removed = {int(r) for r in rec.get("membership_removed_refs", [])}
    if probe.con.execute("SELECT count(*) FROM information_schema.tables WHERE table_name='library_removed_sources'").fetchone()[0]:
        removed.update(row[0] for row in probe.con.execute("SELECT source_ref FROM library_removed_sources").fetchall())
    probe.close()
    completed = skipped = 0
    failures = []
    for i, item in enumerate(items):
        ref = int(item["ref"])
        dest = root / "papers" / "library_ingest" / str(ref)
        stage = "acquire"
        if ref in removed:
            skipped += 1
            prog.done("removed", "Paper was removed since this request; leaving it removed", ref=ref)
            continue
        try:
            prior = _read(dest / "status.json", {})
            if prior.get("stage") == "done":
                completed += 1
                prog.done("paper", "Already completed in this request", ref=ref, done=i + 1, total=len(items))
                continue
            prog.start(stage, f"Preparing paper {i + 1} of {len(items)}", ref=ref)
            source = _source(project_id, item, dest)
            store = KGStore(db)
            try:
                duplicate = _duplicate(store, source)
            finally:
                store.close()
            if duplicate is not None:
                skipped += 1
                prog.done("duplicate", "Paper is already in this collection", ref=ref, existing_ref=duplicate)
                continue
            stage = "extract"
            result = _read(dest / "extraction.json")
            if result is None:
                prog.start(stage, "Extracting this paper's claims with the configured model", ref=ref)
                kwargs = {}
                saved_reader = _read(dest / "reader.json")
                if saved_reader is not None:
                    kwargs["raw_extraction"] = saved_reader
                result = await extract.extract_paper(source["text"], source_ref=ref,
                    source_label=source["title"], field=rec.get("spec", {}).get("theme", ""), **kwargs)
                reasons = [d.get("reason", "") if isinstance(d, dict) else d.reason
                           for d in result.get("deferrals", [])]
                incomplete = (result.get("stats", {}).get("pass1_failed") or
                              any("pass 1 truncated" in r for r in reasons) or
                              (result.get("raw_extraction") or {}).get("_salvaged"))
                if incomplete:
                    _save(dest / "failed-extraction.json", result)
                    raise RuntimeError("Extraction did not complete. Check the job log and retry.")
                if result.get("raw_extraction"):
                    _save(dest / "reader.json", result["raw_extraction"])
                if any("Repair unavailable:" in r for r in reasons):
                    _save(dest / "failed-extraction.json", result)
                    raise RuntimeError("Claim validation was unavailable. Retry will reuse the completed reader output.")
                _save(dest / "extraction.json", result)
            else:
                prog.done(stage, "Reusing this paper's saved extraction", ref=ref)
            claims = [Claim.model_validate(c) for c in result.get("claims", [])]
            experiments = [Experiment.model_validate(e) for e in result.get("experiments", [])]
            deferrals = [Deferral.model_validate(d) for d in result.get("deferrals", [])]
            if any(e.source_ref != ref for e in experiments) or any(d.source_ref != ref for d in deferrals) or any(
                    ev.source_ref != ref for c in claims for ev in c.evidence):
                raise ValueError("Saved extraction has inconsistent source provenance")
            stage = "store"
            prog.start(stage, "Updating this collection's graph and full text", ref=ref)
            store = KGStore(db)
            try:
                store.con.execute("BEGIN TRANSACTION")
                try:
                    # The shared replacement writer sweeps every evidence-free
                    # claim. Membership edits must retain unrelated imported or
                    # engine history which already had no paper evidence.
                    store.con.execute("CREATE TEMP TABLE library_unrelated_claims AS "
                                      "SELECT * FROM claims WHERE claim_id NOT IN "
                                      "(SELECT DISTINCT claim_id FROM evidence)")
                    store.write_paper(ref, claims, experiments, deferrals)
                    store.con.execute("INSERT INTO claims SELECT * FROM library_unrelated_claims "
                                      "WHERE claim_id NOT IN (SELECT claim_id FROM claims)")
                    store.con.execute("DROP TABLE library_unrelated_claims")
                    papers = FullTextStore(con=store.con)
                    paper_id = papers.add_paper(source_ref=ref, source_label=source["title"],
                        doi=source.get("doi", ""), title=source["title"], year=source.get("year"),
                        pmid=source.get("pmid", ""), pmcid=source.get("pmcid", ""),
                        text=source["text"], license=source.get("license", ""), url=source.get("url", ""),
                        is_full_text=True, resolve_identity=False)
                    store.refresh_status()
                    store.con.execute("COMMIT")
                except BaseException:
                    store.con.execute("ROLLBACK")
                    raise
                _manifest(root, source, store)
                stage = "index"
                prog.start(stage, "Updating new or changed claim embeddings", ref=ref)
                indexed = store.embed_claims()
                paper_vec = store.con.execute("SELECT embedding FROM papers WHERE paper_id=?", [paper_id]).fetchone()
                if indexed["n_failed"] or not paper_vec or not paper_vec[0]:
                    raise RuntimeError("Semantic indexing is incomplete. Check embedding model availability and retry; saved extraction will be reused.")
            finally:
                store.close()
            completed += 1
            _save(dest / "status.json", {"stage": "done", "ref": ref, "paper_id": paper_id})
            prog.done("paper", source["title"], ref=ref, done=i + 1, total=len(items))
        except Exception as exc:
            failures.append({"ref": ref, "stage": stage, "error": str(exc)})
            _save(dest / "status.json", failures[-1])
            prog.error(stage, str(exc), ref=ref)
    summary = {"added": completed, "duplicates": skipped, "failed": failures}
    # Reflect a first addition even when the optional index stage needs retry.
    rec = projects.load(project_id)
    rec["kg_db"] = str(db)
    rec["status"] = "ready" if completed else rec.get("status", "draft")
    projects.save(rec)
    from dnhacksbio.webui.membership import refresh_card
    refresh_card(project_id)
    if failures:
        prog.error("fail", f"{len(failures)} paper(s) need attention; retry resumes saved work.", summary=summary)
    else:
        prog.done("finish", "Collection updated", summary=summary)
    return summary


def main():
    from dnhacksbio.webui.jobs import Progress
    from dnhacksbio.webui.membership import project_lease
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--projects-root", type=Path, required=True,
                        help="Explicit project data root inherited from the launching server")
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--progress", type=Path, required=True)
    args = parser.parse_args()
    # Server previews may bind PROJECTS to private data at runtime. A child imports
    # fresh module globals, so require that exact root rather than falling back to
    # the checkout's default data directory (which may contain a running study).
    projects.PROJECTS = args.projects_root.resolve(strict=True)
    owned = projects.project_dir(args.project)
    if owned.is_symlink() or not (owned / "project.json").is_file():
        parser.error("The requested private collection does not exist under --projects-root")
    owned = owned.resolve()
    if not owned.is_relative_to(projects.PROJECTS):
        parser.error("The collection is outside --projects-root")
    if not args.request.resolve().is_relative_to(owned) or not args.progress.resolve().is_relative_to(owned):
        parser.error("Request and progress files must belong to this collection")
    prog = Progress(args.progress)
    try:
        request = _read(args.request)
        if request.get("project_id", args.project) != args.project:
            raise ValueError("Membership request belongs to a different collection")
        with project_lease(args.project):
            result = asyncio.run(ingest(args.project, request["items"], prog))
        return 1 if result["failed"] else 0
    except Exception as exc:
        prog.error("fail", str(exc))
        return 1
    finally:
        prog.close()


if __name__ == "__main__":
    raise SystemExit(main())
