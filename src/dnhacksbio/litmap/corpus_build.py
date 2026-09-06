"""Build a literature knowledge graph from a project spec.

The pipeline is fixed and the domain is data (queries, theme, seed DOIs, filters, all from the
project record):

    discover -> dedup -> date/term filter -> relevance triage -> full-text fetch
             -> fold in the user's own attachments -> extract claims (LLM)
             -> KG store -> claim status -> full-text store -> corpus card

Every stage reports into a `jobs.Progress` stream so the console shows what is happening.

  --dry     discovery + triage only, no LLM tokens: does the spec find the right papers?

    uv run python -m dnhacksbio.litmap.corpus_build --project my-analysis --dry
"""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
import re
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dnhacksbio.litmap import find
from dnhacksbio.litmap.ingest import Document
from dnhacksbio.litmap.store import KGStore
from dnhacksbio.webui import jobs, projects

# below this a record is a stub or a failed fetch, not a paper; low enough that a short abstract counts
MIN_DOC_CHARS = 200
# per-query discovery cap; the union across queries is what matters
PER_QUERY_MAX = 180


class BuildError(RuntimeError):
    """A build that cannot proceed, with a message meant for the person who wrote the spec."""


# --- helpers ----------------------------------------------------------------

def _matches_any(text: str, terms: list[str]) -> str | None:
    low = (text or "").lower()
    for t in terms:
        if t.lower() in low:
            return t
    return None


def _rank_by_theme(cands: list[find.Candidate], theme: str, prog: jobs.Progress) -> list[find.Candidate]:
    """Score every candidate by embedding cosine against the project's theme."""
    from dnhacksbio.explorer import embed as E

    texts = [f"{c.title}. {c.abstract}"[:2000] for c in cands]
    sims = E.max_similarity(texts, [theme]) if texts else []
    if sims is None:
        prog.emit("triage", "warn",
                  "relevance ranking DEGRADED: no embedding model available, so the paper set is an "
                  "arbitrary slice of the hits rather than the most relevant ones. "
                  "Install sentence-transformers (uv sync --extra llm) before trusting it.",
                  degraded=True)
        for c in cands:
            c.score = 0.5
    else:
        for c, s in zip(cands, sims):
            c.score = float(s)
    return sorted(cands, key=lambda c: -c.score)


async def _extract_with_progress(docs: list[Document], concurrency: int,
                                 prog: jobs.Progress, field: str = "",
                                 audit_dir: Path | None = None) -> dict[int, dict]:
    """Extract every paper with bounded concurrency, consuming results as they complete so the UI can
    count them. Returns {ref: {claims, experiments, deferrals, ...}}; a failed paper yields an empty
    extraction rather than killing the build."""
    from dnhacksbio.litmap import extract as extract_mod

    sem = asyncio.Semaphore(max(1, concurrency))
    total = len(docs)
    done = 0
    claims = 0
    out: dict[int, dict] = {}

    async def one(d: Document):
        try:
            async with sem:
                return d, await extract_mod.extract_paper(
                    d.text, source_ref=d.ref, source_label=d.label, field=field)
        except Exception as exc:
            return d, exc

    for coro in asyncio.as_completed([one(d) for d in docs]):
        d, res = await coro
        done += 1
        if isinstance(res, Exception):
            out[d.ref] = {"claims": [], "experiments": [], "deferrals": []}
            prog.emit("extract", "warn", f"{d.label}: extraction failed ({type(res).__name__}: {res})",
                      done=done, total=total)
            continue
        out[d.ref] = res
        if audit_dir is not None:
            audit_dir.mkdir(parents=True, exist_ok=True)
            audit_path = audit_dir / f"{d.ref}.json"
            temporary = audit_path.with_suffix(".json.tmp")
            temporary.write_text(json.dumps({
                "source_ref": d.ref, "stats": res.get("stats", {}),
                "metadata": res.get("extraction_metadata", {}), "reader": res.get("raw_extraction"),
                "repair": res.get("repair_audit", {}), "warnings": res.get("warnings", [])
            }, indent=2), encoding="utf-8")
            temporary.replace(audit_path)
        claims += len(res.get("claims", []))
        prog.emit("extract", "progress", f"{d.label}: {len(res.get('claims', []))} claims "
                                         f"({len(res.get('deferrals', []))} deferred)",
                  done=done, total=total, n_claims=claims)
    return out


def _attachment_documents(pid: str, prog: jobs.Progress) -> tuple[list[Document], list[dict]]:
    """The user's own uploads as corpus documents. An attachment goes through the same extractor as a
    fetched paper, so a preprint or an internal report the search could not surface still lands in the
    graph with quotes and provenance. The ref comes from the attachment record, assigned once at upload,
    so deleting one attachment does not shift another onto a neighbour's ref."""
    rec = projects.load(pid)
    docs, meta = [], []
    for att in rec.get("attachments") or []:
        ref = int(att["ref"])
        text_path = projects.attachments_dir(pid) / att["text_file"]
        if not text_path.is_file():
            prog.emit("attach", "warn", f"{att['filename']}: parsed text missing, skipped")
            continue
        text = text_path.read_text(encoding="utf-8", errors="ignore")
        if len(text) < MIN_DOC_CHARS:
            prog.emit("attach", "warn",
                      f"{att['filename']}: only {len(text)} characters of text, skipped")
            continue
        label = re.sub(r"[^A-Za-z0-9]", "", Path(att["filename"]).stem)[:16] or f"upload{ref}"
        docs.append(Document(ref=ref, label=label, ext=att.get("ext", "txt"),
                             path=att["filename"], text=text, n_chars=len(text),
                             source_id=att.get("doi", "")))
        meta.append({"ref": ref, "doi": att.get("doi", ""), "pmid": "", "title": att["filename"],
                     "date": "", "year": att.get("year"), "is_full_text": True, "score": 1.0,
                     "attachment": True})
    return docs, meta


def _write_selected_papers(path: Path, selected: list[tuple[find.Candidate, dict]], queries, completeness):
    papers = [{"doi": c.doi, "pmid": c.pmid, "pmcid": c.pmcid, "title": c.title,
               "year": c.year, "publication_date": c.publication_date, "score": round(c.score, 4),
               "channels": sorted(c.channels), "is_oa": c.is_oa,
               "is_full_text": bool(ft.get("is_full_text")), "source": ft.get("source"),
               "url": ft.get("url"), "license": ft.get("license"),
               "artifact_dir": ft.get("artifact_dir"), "raw_sha256": ft.get("raw_sha256")}
              for c, ft in selected]
    path.write_text(json.dumps({"n_papers": len(papers), "selection": "retrieved",
                               "queries": queries, "completeness": completeness, "papers": papers}, indent=2),
                    encoding="utf-8")


def _fetch_selected(ranked: list[find.Candidate], target: int, full_text_only: bool,
                    artifact_root: Path, prog: jobs.Progress, seed_dois=()) -> list[tuple[find.Candidate, dict]]:
    """Persist retrievals before extraction and refill rejected full-text candidates in ranked order."""
    seed_set = {find.normalize_doi(d) for d in seed_dois}
    seeds = [c for c in ranked if find.normalize_doi(c.doi) in seed_set]
    queue = seeds + [c for c in ranked if c not in seeds]
    accepted, attempted, n_full = [], 0, 0
    required = max(target, len(seeds))
    reports = []
    accepted_ids, accepted_hashes = set(), set()
    while queue and len(accepted) < required:
        batch, queue = queue[:min(10, required - len(accepted))], queue[min(10, required - len(accepted)):]
        with ThreadPoolExecutor(max_workers=10) as ex:
            futures = [ex.submit(find.fetch_fulltext, c, artifact_root) for c in batch]
            for c, future in zip(batch, futures):
                attempted += 1
                try:
                    ft = future.result()
                except Exception as exc:
                    ft = {"text": "", "is_full_text": False, "source": "failed",
                          "attempts": [{"status": "fetch-failed", "error_type": type(exc).__name__}]}
                valid = len(ft.get("text") or "") >= MIN_DOC_CHARS
                identities = find._aliases(c)
                raw_hash = ft.get("raw_sha256")
                duplicate = bool(identities & accepted_ids or (raw_hash and raw_hash in accepted_hashes))
                include = valid and not duplicate and (bool(ft.get("is_full_text")) or not full_text_only)
                reports.append({"key": c.key, "included": include, "is_full_text": bool(ft.get("is_full_text")),
                                "duplicate": duplicate, "attempts": ft.get("attempts", []), "artifact_dir": ft.get("artifact_dir")})
                # Preserve partial progress even if later retrieval or extraction is interrupted.
                artifact_root.mkdir(parents=True, exist_ok=True)
                (artifact_root / "attempts.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")
                if include:
                    accepted_ids.update(identities)
                    if raw_hash:
                        accepted_hashes.add(raw_hash)
                    accepted.append((c, ft))
                    n_full += bool(ft.get("is_full_text"))
                prog.emit("fetch", "progress", f"{attempted} attempted · {len(accepted)}/{required} usable · {n_full} full text",
                          done=attempted, n_full=n_full, n_accepted=len(accepted), target=required)
    if full_text_only and n_full < required:
        raise BuildError(f"full-text minimum not met: {n_full}/{required} readable full texts after "
                         f"{attempted} candidates. Retrieval artifacts are saved; broaden discovery or fix "
                         "failed routes before extraction. No extraction was started.")
    return accepted


# --- the pipeline -----------------------------------------------------------

async def build(project_id: str, prog: jobs.Progress, *, dry: bool = False) -> dict:
    t0 = time.time()
    rec = projects.load(project_id)
    if rec.get("adopted"):
        raise BuildError("this corpus was built outside the console and cannot be rebuilt here")
    spec = projects.validate_spec(rec["spec"], for_build=True)
    out_dir = projects.project_dir(project_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    db = projects.kg_path(project_id)

    prog.start("plan", f"{rec['name']}: {len(spec['queries'])} queries, target {spec['n_papers']} papers",
               dry=dry, n_queries=len(spec["queries"]), n_papers=spec["n_papers"])
    prog.done("plan", f"{len(spec['queries'])} queries · target {spec['n_papers']} papers"
                      + (f" · {len(spec['seed_dois'])} seed DOIs" if spec["seed_dois"] else ""))

    # ---- discover: each query is an independent capture channel -----------------------------
    prog.start("discover", f"searching Europe PMC across {len(spec['queries'])} queries",
               total=len(spec["queries"]))
    allc: list[find.Candidate] = []
    for i, q in enumerate(spec["queries"]):
        hits = find.europepmc_search(q, max_results=PER_QUERY_MAX, channel=f"q{i}")
        allc += hits
        prog.emit("discover", "progress", f"{q[:80]} → {len(hits)} hits",
                  done=i + 1, total=len(spec["queries"]), n_hits=len(allc))
    oa_hits = find.openalex_search(spec["theme"], max_results=PER_QUERY_MAX, channel="openalex-theme")
    allc += oa_hits
    prog.emit("discover", "progress", f"OpenAlex theme search → {len(oa_hits)} hits", n_hits=len(allc))
    for j, doi in enumerate(spec["seed_dois"]):
        allc += find.europepmc_search(f'DOI:"{doi}"', max_results=2, channel="seed")
        seed = find.openalex_by_doi(doi)
        if seed:
            seed.channels.add("seed")
            allc.append(seed)
    if spec["seed_dois"]:
        prog.emit("discover", "progress", f"{len(spec['seed_dois'])} seed DOIs force-included")
    if not allc:
        raise BuildError(
            "no papers found. Every query returned nothing — check the query syntax (Europe PMC "
            "uses AND/OR and quoted phrases) or broaden the terms.")
    prog.done("discover", f"{len(allc)} raw hits", n_hits=len(allc))

    # ---- dedup + completeness ---------------------------------------------------------------
    merged = find.dedup_candidates(allc)
    completeness = find.estimate_completeness({k: c.channels for k, c in merged.items()})
    prog.done("dedup", f"{len(merged)} unique papers", n_unique=len(merged),
              completeness=completeness)

    # ---- filter: date window + excluded terms -----------------------------------------------
    kept, dropped_year, dropped_term = [], 0, 0
    for c in merged.values():
        y = c.year
        if spec["year_min"] and (y is None or y < spec["year_min"]):
            dropped_year += 1
            continue
        if spec["year_max"] and (y is None or y > spec["year_max"]):
            dropped_year += 1
            continue
        if spec["exclude_terms"] and _matches_any(f"{c.title} {c.abstract}", spec["exclude_terms"]):
            dropped_term += 1
            continue
        kept.append(c)
    prog.done("filter", f"{len(kept)} kept · {dropped_year} outside the date window · "
                        f"{dropped_term} matched an excluded term",
              n_kept=len(kept), dropped_year=dropped_year, dropped_term=dropped_term)
    if not kept:
        raise BuildError("every paper was filtered out — loosen the date window or the excluded terms.")

    att_docs, att_meta = _attachment_documents(project_id, prog)

    # ---- triage: rank against the project's theme -------------------------------------------
    prog.start("triage", f"ranking {len(kept)} papers against the theme")
    ranked = _rank_by_theme(kept, spec["theme"], prog)
    top = ranked[:spec["n_papers"]]
    seed_set = {d.lower() for d in spec["seed_dois"]}
    picked = {(c.doi or "").lower() for c in top}
    forced = [c for c in ranked if (c.doi or "").lower() in seed_set and (c.doi or "").lower() not in picked]
    if forced:
        top = forced + top
    span = f"{top[-1].score:.3f}..{top[0].score:.3f}" if top else "—"
    prog.done("triage", f"selected {len(top)} papers (relevance {span})"
                        + (f", {len(forced)} seed papers force-added" if forced else ""),
              n_selected=len(top), score_range=span, n_forced=len(forced))

    paper_list = [{"doi": c.doi, "pmid": c.pmid, "title": c.title, "year": c.year,
                   "score": round(c.score, 4), "is_oa": c.is_oa,
                   "channels": sorted(c.channels)} for c in top]
    (out_dir / "paper_list.json").write_text(json.dumps(
        {"n_papers": len(top), "selection": "proposed", "queries": spec["queries"], "completeness": completeness,
         "papers": paper_list}, indent=2, default=str))

    if dry:
        summary = {"dry": True, "n_candidates": len(merged), "n_selected": len(top),
                   "completeness": completeness, "score_range": span,
                   "papers": paper_list[:50], "elapsed_s": round(time.time() - t0, 1)}
        prog.emit("finish", "done",
                  f"dry run complete — {len(top)} papers selected from {len(merged)} candidates. "
                  f"No LLM tokens spent. Review the list, then build for real.", summary=summary)
        return summary

    # ---- fetch full text --------------------------------------------------------------------
    prog.start("fetch", f"fetching full text for {len(top)} papers", total=len(top))
    selected = _fetch_selected(ranked, spec["n_papers"], spec["full_text_only"],
                               out_dir / "retrieval", prog, spec["seed_dois"])
    _write_selected_papers(out_dir / "paper_list.json", selected, spec["queries"], completeness)
    top = [c for c, _ in selected]
    fetched = [ft for _, ft in selected]
    n_full = sum(bool(ft.get("is_full_text")) for ft in fetched)
    prog.done("fetch", f"{n_full} full text · {len(top) - n_full} abstract only", n_full=n_full)

    # ---- documents ---------------------------------------------------------------------------
    docs, meta = [], []
    for j, (c, ft) in enumerate(zip(top, fetched)):
        text = (ft or {}).get("text") or ""
        if len(text) < MIN_DOC_CHARS:
            continue
        if spec["full_text_only"] and not ft.get("is_full_text"):
            continue
        ref = j + 1
        yr = c.year
        tok = re.sub(r"[^A-Za-z]", "", (c.title.split() or ["paper"])[0])[:12] or "paper"
        docs.append(Document(ref=ref, label=f"{tok}{yr or ''}", ext=ft.get("source", "txt"),
                             path=c.doi or str(ref), text=text, n_chars=len(text),
                             source_id=c.doi or ""))
        meta.append({"ref": ref, "doi": c.doi, "pmid": c.pmid, "pmcid": c.pmcid, "title": c.title,
                     "year": yr, "publication_date": c.publication_date,
                     "license": ft.get("license", ""), "url": ft.get("url", ""),
                     "artifact_dir": ft.get("artifact_dir"), "figures": ft.get("figures", []),
                     "parser": ft.get("parser"), "raw_sha256": ft.get("raw_sha256"),
                     "is_full_text": bool(ft.get("is_full_text")),
                     "score": round(c.score, 4), "attachment": False})

    if att_docs:
        prog.done("attach", f"{len(att_docs)} uploaded document(s) folded into the corpus",
                  n_attachments=len(att_docs))
    # A local copy of an already retrieved paper must not inflate counts or overwrite its source_ref.
    paper_ids = {find.normalize_doi(m.get("doi") or "") for m in meta if m.get("doi")}
    unique_att_docs, unique_att_meta = [], []
    for d, m in zip(att_docs, att_meta):
        doi = find.normalize_doi(m.get("doi") or "")
        if doi and doi in paper_ids:
            prog.emit("attach", "warn", f"{d.label}: duplicate DOI already in corpus, skipped")
            continue
        if doi:
            paper_ids.add(doi)
        unique_att_docs.append(d)
        unique_att_meta.append(m)
    att_docs, att_meta = unique_att_docs, unique_att_meta
    docs += att_docs
    meta += att_meta
    if not docs:
        raise BuildError("no paper yielded usable text — the fetch step came back empty for all of them.")

    # ---- extract -----------------------------------------------------------------------------
    prog.start("extract", f"reading {len(docs)} papers with the extraction model "
                          f"({spec['concurrency']} at a time) — this is the slow, paid step",
               total=len(docs))
    audit_dir = out_dir / "extraction_audits" / uuid.uuid4().hex
    extractions = await _extract_with_progress(docs, spec["concurrency"], prog,
                                               spec.get("theme", ""), audit_dir=audit_dir)
    n_claims = sum(len(e.get("claims", [])) for e in extractions.values())
    n_empty = sum(1 for e in extractions.values() if not e.get("claims"))
    prog.done("extract", f"{n_claims} claims from {len(docs) - n_empty} papers "
                         f"({n_empty} produced none)", n_claims=n_claims, n_empty=n_empty)
    if n_claims == 0:
        raise BuildError(
            "extraction returned zero claims from every paper. That usually means the LLM seam is "
            "unavailable (no Claude CLI / API access) rather than a bad corpus — check the job log.")

    # ---- store ------------------------------------------------------------------------------
    prog.start("store", "writing claims into the knowledge graph")
    store = KGStore(db_path=db, fresh=True)
    try:
        for ref, pe in extractions.items():
            store.write_paper(ref, pe.get("claims", []), pe.get("experiments", []),
                              pe.get("deferrals", []))
        rollup = store.refresh_status()
        prog.done("store", f"{rollup.get('claims', n_claims)} claims stored, "
                           f"{rollup.get('disputed_claims', 0)} disputed", **{
            k: v for k, v in rollup.items() if isinstance(v, (int, float))})

        # ---- full text alongside the graph ---------------------------------------------------
        prog.start("papers", "storing full text next to the graph")
        from dnhacksbio.explorer.fulltext import FullTextStore
        ft_store = FullTextStore(con=store.con)
        by_ref = {m["ref"]: m for m in meta}
        for d in docs:
            m = by_ref.get(d.ref, {})
            ft_store.add_paper(source_ref=d.ref, source_label=d.label, doi=m.get("doi", ""),
                               pmid=m.get("pmid", ""), pmcid=m.get("pmcid", ""), title=m.get("title", d.label),
                               license=m.get("license", ""), url=m.get("url", ""),
                               year=m.get("year"), text=d.text,
                               is_full_text=bool(m.get("is_full_text")))
        paper_counts = ft_store.counts()
        kg_counts = store.counts()
        prog.done("papers", f"{paper_counts.get('papers', len(docs))} papers stored", **{
            k: v for k, v in paper_counts.items() if isinstance(v, (int, float))})
    finally:
        store.close()

    # ---- the corpus card the engine reads ----------------------------------------------------
    card = projects.write_corpus_card(project_id)
    prog.done("card", f"corpus card written → {card.name}")

    manifest = {"project": project_id, "name": rec["name"], "mode": "build",
                "built": time.time(), "n_papers": len(docs), "n_claims": n_claims,
                "n_attachments": len(att_docs), "kg": kg_counts, "papers": paper_counts,
                "completeness": completeness, "spec": spec, "papers_meta": meta}
    (out_dir / "MANIFEST.json").write_text(json.dumps(manifest, indent=2, default=str))

    summary = {"mode": "build", "n_papers": len(docs), "n_claims": n_claims,
               "n_attachments": len(att_docs), "kg": kg_counts, "papers": paper_counts,
               "completeness": completeness, "elapsed_s": round(time.time() - t0, 1)}
    prog.emit("finish", "done",
              f"corpus built — {len(docs)} papers, {n_claims} claims, "
              f"{kg_counts.get('entities', 0)} entities", summary=summary)
    return summary


# --- entry point ------------------------------------------------------------

def _finish_project(project_id: str, status: str, summary: dict | None, job_id: str | None) -> None:
    """Stamp the outcome onto the project record so the console shows it without re-reading logs."""
    try:
        patch = {"status": status}
        if summary is not None:
            patch["build"] = {**summary, "finished": time.time(), "job_id": job_id}
        projects.update(project_id, patch)
    except (KeyError, ValueError, OSError):
        pass


async def _main() -> int:
    ap = argparse.ArgumentParser(description="Build a project's literature knowledge graph")
    ap.add_argument("--project", required=True, help="project id (data/projects/<id>)")
    ap.add_argument("--progress", default="", help="path to append JSONL progress events to")
    ap.add_argument("--dry", action="store_true",
                    help="discovery + triage only; stop before the paid extraction step")
    args = ap.parse_args()

    prog_path = args.progress or (projects.jobs_dir(args.project) / "manual.jsonl")
    prog = jobs.Progress(prog_path)
    job_id = Path(prog_path).stem
    try:
        summary = await build(args.project, prog, dry=args.dry)
        if not args.dry:
            _finish_project(args.project, "ready", summary, job_id)
        else:
            _finish_project(args.project, "draft", None, job_id)
        return 0
    except BuildError as exc:
        prog.emit("fail", "error", str(exc))
        _finish_project(args.project, "failed", None, job_id)
        return 2
    except KeyboardInterrupt:
        prog.emit("fail", "error", "cancelled")
        _finish_project(args.project, "failed", None, job_id)
        return 130
    except Exception as exc:
        traceback.print_exc()
        prog.emit("fail", "error", f"{type(exc).__name__}: {exc}")
        _finish_project(args.project, "failed", None, job_id)
        return 1
    finally:
        prog.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
