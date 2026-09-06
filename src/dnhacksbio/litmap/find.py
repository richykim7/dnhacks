"""Literature discovery and open-access full text.

Europe PMC and OpenAlex supply bounded discovery channels. Full-text routes retain raw sources,
parsed text, figures and route diagnostics before extraction. Discovery channels are correlated;
full-text availability is checked separately from the capture-recapture estimate.
"""
from __future__ import annotations

import time
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import quote, urlparse
import warnings
from dataclasses import dataclass, field

import requests

POLITE_EMAIL = os.environ.get("LITERATURE_CONTACT_EMAIL", "research@example.org")
UA = {"User-Agent": f"dnhacksbio/0.1 (mailto:{POLITE_EMAIL})"}
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
IDCONV = "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/"


@dataclass
class Candidate:
    key: str                    # canonical id (DOI preferred, else "PMID:x" / "PMC:x")
    doi: str = ""
    pmid: str = ""
    pmcid: str = ""
    title: str = ""
    abstract: str = ""
    year: int | None = None
    is_oa: bool = False
    channels: set = field(default_factory=set)   # which discovery channels found it (capture-recapture)
    locations: list[dict] = field(default_factory=list)
    publication_date: str = ""
    openalex_id: str = ""
    score: float = 0.0          # relevance score


def normalize_doi(doi: str) -> str:
    return _re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", doi.strip(), flags=_re.I).lower()


def _cand_key(doi: str, pmid: str, pmcid: str) -> str:
    if doi:
        return normalize_doi(doi)
    if pmid:
        return f"PMID:{pmid}"
    return f"PMC:{pmcid.upper().removeprefix('PMC')}" if pmcid else ""


def _request(url: str, *, params=None, attempts=None, timeout=30, max_bytes=40 * 1024 * 1024):
    """Bounded streaming and retries; credentials never appear in diagnostics."""
    for retry in range(3):
        response = None
        try:
            response = requests.get(url, params=params or {}, headers=UA, timeout=timeout, stream=True)
            status = response.status_code
            if status == 200:
                chunks, size = [], 0
                for chunk in response.iter_content(chunk_size=65536):
                    size += len(chunk)
                    if size > max_bytes:
                        if attempts is not None:
                            attempts.append({"url": url, "status": "download-too-large", "limit_bytes": max_bytes})
                        return None
                    chunks.append(chunk)
                response._content = b"".join(chunks)
                response._content_consumed = True
                return response
            reason = f"http-{status}"
            transient = status == 429 or status >= 500
        except requests.RequestException as exc:
            reason, transient = type(exc).__name__, True
        finally:
            if response is not None:
                response.close()
        if attempts is not None:
            attempts.append({"url": url, "status": reason, "attempt": retry + 1})
        if not transient:
            break
        if retry < 2:
            time.sleep(0.25 * 2 ** retry)
    return None


def _json_request(url: str, *, params=None, attempts=None):
    response = _request(url, params=params, attempts=attempts)
    if response is None:
        return {}
    try:
        data = response.json()
        return data if isinstance(data, dict) else {}
    except ValueError:
        if attempts is not None:
            attempts.append({"url": url, "status": "invalid-json"})
        return {}


# ----- Channel A: Europe PMC tight-query search ---------------------------------------------------
def europepmc_search(query: str, max_results: int = 400, channel: str = "epmc") -> list[Candidate]:
    """Paginated Europe PMC search (cursorMark). Returns candidates with title+abstract+OA flag."""
    out: list[Candidate] = []
    cursor = "*"
    while len(out) < max_results:
        params = {"query": query, "format": "json", "pageSize": 100, "cursorMark": cursor,
                  "resultType": "core"}
        errors = []
        data = _json_request(EPMC, params=params, attempts=errors)
        if errors:
            warnings.warn(f"Europe PMC discovery: {errors[-1]['status']}", RuntimeWarning)
        results = data.get("resultList", {}).get("result", [])
        if not results:
            break
        for d in results:
            doi = (d.get("doi") or "").strip()
            pmid = str(d.get("pmid") or "")
            pmcid = str(d.get("pmcid") or "")
            key = _cand_key(doi, pmid, pmcid)
            if not key:
                continue
            out.append(Candidate(
                key=key, doi=normalize_doi(doi), pmid=pmid, pmcid=pmcid,
                publication_date=d.get("firstPublicationDate", ""),
                title=d.get("title", ""), abstract=d.get("abstractText", ""),
                year=int(d["pubYear"]) if str(d.get("pubYear", "")).isdigit() else None,
                is_oa=(d.get("isOpenAccess") == "Y"), channels={channel}))
        nxt = data.get("nextCursorMark")
        if not nxt or nxt == cursor:
            break
        cursor = nxt
        time.sleep(0.2)
    return out[:max_results]


def _aliases(c: Candidate) -> set[str]:
    return {v for v in (normalize_doi(c.doi) if c.doi else "",
                       f"PMID:{c.pmid}" if c.pmid else "",
                       f"PMC:{c.pmcid.upper().removeprefix('PMC')}" if c.pmcid else "",
                       c.openalex_id, c.key) if v}


def dedup_candidates(cands: list[Candidate]) -> dict[str, Candidate]:
    groups: list[tuple[set[str], Candidate]] = []
    for c in cands:
        aliases = _aliases(c)
        matches = [(ids, old) for ids, old in groups if ids & aliases]
        for ids, old in matches:
            aliases |= ids
            c.channels |= old.channels
            for field_name in ("doi", "pmid", "pmcid", "title", "abstract", "year",
                               "publication_date", "openalex_id"):
                if not getattr(c, field_name):
                    setattr(c, field_name, getattr(old, field_name))
            c.is_oa |= old.is_oa
            c.locations = old.locations + [loc for loc in c.locations if loc not in old.locations]
        groups = [(ids, old) for ids, old in groups if not ids & aliases]
        c.doi = normalize_doi(c.doi)
        c.key = _cand_key(c.doi, c.pmid, c.pmcid) or c.openalex_id or c.key
        groups.append((aliases | {c.key}, c))
    return {c.key: c for _, c in groups}


OPENALEX = "https://api.openalex.org/works"


def _openalex_params(**kwargs) -> dict:
    if os.environ.get("OPENALEX_API_KEY"):
        kwargs["api_key"] = os.environ["OPENALEX_API_KEY"]
    return kwargs


def _openalex_candidate(work: dict, channel: str) -> Candidate:
    ids = work.get("ids") or {}
    doi = normalize_doi(work.get("doi") or ids.get("doi") or "")
    pmid = (ids.get("pmid") or "").rstrip("/").rsplit("/", 1)[-1]
    pmcid = (ids.get("pmcid") or "").rstrip("/").rsplit("/", 1)[-1]
    positions = [(pos, token) for token, pos_list in (work.get("abstract_inverted_index") or {}).items()
                 for pos in pos_list]
    return Candidate(key=_cand_key(doi, pmid, pmcid) or work.get("id", ""), doi=doi,
                     pmid=pmid, pmcid=pmcid, title=work.get("title") or "",
                     abstract=" ".join(token for _, token in sorted(positions)),
                     year=work.get("publication_year"), publication_date=work.get("publication_date") or "",
                     is_oa=bool((work.get("open_access") or {}).get("is_oa")), channels={channel},
                     openalex_id=work.get("id") or "", locations=work.get("locations") or [])


def openalex_search(query: str, max_results: int = 180, channel: str = "openalex") -> list[Candidate]:
    # Europe PMC fielded query syntax is not OpenAlex syntax. Use the plain project theme for this channel.
    out, cursor = [], "*"
    while len(out) < max_results:
        errors = []
        data = _json_request(OPENALEX, params=_openalex_params(search=query, per_page=100, cursor=cursor),
                             attempts=errors)
        if errors:
            warnings.warn(f"OpenAlex discovery: {errors[-1]['status']}", RuntimeWarning)
        rows = data.get("results") or []
        out.extend(c for w in rows if (c := _openalex_candidate(w, channel)).key)
        nxt = (data.get("meta") or {}).get("next_cursor")
        if not rows or not nxt or nxt == cursor:
            break
        cursor = nxt
    return out[:max_results]


def openalex_by_doi(doi: str, attempts=None) -> Candidate | None:
    work = _json_request(f"{OPENALEX}/https://doi.org/{quote(normalize_doi(doi), safe='/')}",
                         params=_openalex_params(), attempts=attempts)
    if normalize_doi(work.get("doi") or "") != normalize_doi(doi):
        return None
    return _openalex_candidate(work, "openalex-doi")


import html as _html
import re as _re
import xml.etree.ElementTree as _ET

_TAG = _re.compile(r"<[^>]+>")


def _jats_license(xml: str) -> str:
    m = _re.search(r"<license[^>]*>(.*?)</license>", xml, _re.S)
    return _re.sub(r"\s+", " ", _TAG.sub(" ", m.group(1))).strip()[:60] if m else ""


def _resolve_pmcid(doi: str = "", pmid: str = "", attempts=None) -> str:
    for idv in (doi, pmid):
        if not idv:
            continue
        data = _json_request(IDCONV, params={"ids": idv, "format": "json", "tool": "litmap",
                                           "email": POLITE_EMAIL}, attempts=attempts)
        for record in data.get("records", []):
            if record.get("pmcid"):
                return record["pmcid"]
    return ""


def _title_overlap(title: str, text: str) -> float:
    """Fraction of the expected title's tokens present in the head of the fetched text, used to verify
    a PMCID fetch is the right article. 1.0 when there is no title to check against."""
    it = set(_re.sub(r"[^a-z0-9]+", " ", (title or "").lower()).split())
    if not it:
        return 1.0
    tt = set(_re.sub(r"[^a-z0-9]+", " ", (text[:4000] or "").lower()).split())
    return len(it & tt) / len(it)


def _has_body(data: bytes, kind: str, text: str) -> bool:
    """Conservative completeness gate: a long abstract or publisher landing page is insufficient."""
    if len(text.strip()) < 1500:
        return False
    if kind == "xml":
        try:
            root = _ET.fromstring(data)
            return any(len(" ".join(el.itertext()).strip()) > 800
                       for el in root.iter() if el.tag.rsplit("}", 1)[-1] == "body")
        except _ET.ParseError:
            return False
    plain = text.replace("**", "").replace("__", "")
    headings = _re.findall(r"(?im)^\s*(?:#+\s*)?(?:\d+[. ]+)?"
                           r"(introduction|background|materials and methods|methods|results|"
                           r"discussion|results and discussion|conclusions?|references|bibliography)\s*[:.]*\s*$", plain)
    return len(set(h.lower() for h in headings)) >= 2


def _artifact_dir(root: Path, cand: Candidate) -> Path:
    path = root / hashlib.sha256(cand.key.encode()).hexdigest()[:20]
    path.mkdir(parents=True, exist_ok=True)
    return path


def _save_result(root: Path | None, cand: Candidate, result: dict) -> dict:
    if root is not None:
        dest = _artifact_dir(root, cand)
        # Atomic replacement leaves the previous complete manifest usable after interruption.
        tmp = dest / "retrieval.json.tmp"
        tmp.write_text(json.dumps({"candidate": {"key": cand.key, "doi": cand.doi, "pmid": cand.pmid,
                         "pmcid": cand.pmcid, "title": cand.title, "year": cand.year,
                         "publication_date": cand.publication_date, "channels": sorted(cand.channels)},
                         **result}, indent=2), encoding="utf-8")
        tmp.replace(dest / "retrieval.json")
    return result


def _figure_matches(href: str, name: Path) -> bool:
    requested = Path(urlparse(href).path)
    return requested.name == name.name if requested.suffix else requested.stem == name.stem


def _epmc_figure_assets(pmcid: str, figures: list[dict], dest: Path, attempts: list[dict]) -> None:
    """Europe PMC supplementaryFiles includes inline images as well as supplements."""
    import io
    import zipfile
    url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/supplementaryFiles"
    response = _request(url, attempts=attempts, timeout=60, max_bytes=100 * 1024 * 1024)
    if response is None:
        return
    digest = hashlib.sha256(response.content).hexdigest()
    archive_name = f"{digest}.zip"
    (dest / archive_name).write_bytes(response.content)
    try:
        total_bytes = 0
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            for member in archive.infolist():
                name = Path(member.filename)
                if (member.is_dir() or member.file_size > 20 * 1024 * 1024
                        or name.suffix.lower() not in {".jpg", ".jpeg", ".png", ".gif", ".tif", ".tiff", ".webp"}):
                    continue
                matching = [f for f in figures if not f.get("path") and _figure_matches(f.get("url") or "", name)]
                if not matching:
                    continue
                total_bytes += member.file_size
                if total_bytes > 100 * 1024 * 1024:
                    attempts.append({"url": url, "status": "figure-expansion-limit"})
                    break
                # No extract()/extractall(): archive paths and symlinks are never materialized.
                with archive.open(member) as stream:
                    content = stream.read(20 * 1024 * 1024 + 1)
                if len(content) > 20 * 1024 * 1024:
                    continue
                image_digest = hashlib.sha256(content).hexdigest()
                filename = f"figure-{image_digest}{name.suffix.lower()}"
                (dest / filename).write_bytes(content)
                for figure in matching:
                    figure.update(path=filename, sha256=image_digest, retrieval_status="downloaded",
                                  archive_file=archive_name, archive_member=member.filename, archive_url=url)
        attempts.append({"url": url, "status": "figure-package-read", "raw_sha256": digest})
    except (zipfile.BadZipFile, OSError, RuntimeError) as exc:
        attempts.append({"url": url, "status": "invalid-figure-package", "error_type": type(exc).__name__})


def _pmc_figure_assets(pmcid: str, figures: list[dict], dest: Path, attempts: list[dict]) -> None:
    """Read only matching image members; never extract archive paths, links or executables."""
    import io
    import tarfile
    if not pmcid or not any(f.get("url") and not f.get("path") for f in figures):
        return
    _epmc_figure_assets(pmcid, figures, dest, attempts)
    if all(f.get("path") or not f.get("url") for f in figures):
        return
    service = f"https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi?id={pmcid}"
    response = _request(service, attempts=attempts)
    if response is None:
        return
    try:
        links = _ET.fromstring(response.content).iter("link")
        archive_url = next((el.get("href", "") for el in links if el.get("format") == "tgz"), "")
    except _ET.ParseError:
        archive_url = ""
    archive_url = archive_url.replace("ftp://ftp.ncbi.nlm.nih.gov/", "https://ftp.ncbi.nlm.nih.gov/")
    if not archive_url.startswith("https://ftp.ncbi.nlm.nih.gov/"):
        attempts.append({"url": service, "status": "no-oa-figure-package"})
        return
    response = _request(archive_url, attempts=attempts, timeout=60, max_bytes=100 * 1024 * 1024)
    if response is None:
        return
    if len(response.content) > 100 * 1024 * 1024:
        attempts.append({"url": archive_url, "status": "figure-package-too-large"})
        return
    digest = hashlib.sha256(response.content).hexdigest()
    archive_name = f"{digest}.tar.gz"
    (dest / archive_name).write_bytes(response.content)
    try:
        with tarfile.open(fileobj=io.BytesIO(response.content), mode="r:gz") as archive:
            for member in archive:
                if not member.isfile() or member.size > 20 * 1024 * 1024:
                    continue
                name = Path(member.name)
                if name.suffix.lower() not in {".jpg", ".jpeg", ".png", ".gif", ".tif", ".tiff", ".webp"}:
                    continue
                matching = [f for f in figures if not f.get("path") and
                            _figure_matches(f.get("url") or "", name)]
                if not matching:
                    continue
                stream = archive.extractfile(member)
                if stream is None:
                    continue
                content = stream.read(20 * 1024 * 1024 + 1)
                if len(content) > 20 * 1024 * 1024:
                    continue
                image_digest = hashlib.sha256(content).hexdigest()
                filename = f"figure-{image_digest}{name.suffix.lower()}"
                (dest / filename).write_bytes(content)
                for figure in matching:
                    figure.update(path=filename, sha256=image_digest, retrieval_status="downloaded",
                                  archive_file=archive_name, archive_member=member.name, archive_url=archive_url)
        attempts.append({"url": archive_url, "status": "figure-package-read", "raw_sha256": digest})
    except (tarfile.TarError, OSError) as exc:
        attempts.append({"url": archive_url, "status": "invalid-figure-package", "error_type": type(exc).__name__})


def _landing_pdf_urls(data: bytes, base_url: str) -> list[str]:
    from html.parser import HTMLParser
    from urllib.parse import urljoin
    class Links(HTMLParser):
        def __init__(self):
            super().__init__()
            self.urls = []
        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            href = ""
            if tag == "meta" and (attrs.get("name") or "").lower() == "citation_pdf_url":
                href = attrs.get("content") or ""
            elif tag in {"link", "a"} and (attrs.get("type") or "").lower() == "application/pdf":
                href = attrs.get("href") or ""
            if href:
                resolved = urljoin(base_url, href)
                if urlparse(resolved).scheme in {"http", "https"} and resolved not in self.urls:
                    self.urls.append(resolved)
    parser = Links()
    parser.feed(data.decode("utf-8", errors="replace"))
    return parser.urls[:5]


def fetch_fulltext(cand: Candidate, artifact_root: Path | str | None = None) -> dict:
    from dnhacksbio.litmap.document_parse import parse_document_bytes
    from urllib.parse import urljoin

    root = Path(artifact_root) if artifact_root is not None else None
    dest = _artifact_dir(root, cand) if root else None
    if dest and (dest / "retrieval.json").is_file():
        try:
            cached = json.loads((dest / "retrieval.json").read_text(encoding="utf-8"))
            if (cached.get("cache_version") == 1 and cached.get("is_full_text")
                    and cached.get("candidate", {}).get("key") == cand.key
                    and hashlib.sha256((dest / cached["raw_file"]).read_bytes()).hexdigest() == cached["raw_sha256"]
                    and (dest / cached["parsed_file"]).read_text(encoding="utf-8") == cached["text"]
                    and _title_overlap(cand.title, cached["text"]) >= 0.5
                    and all(f.get("path") and (dest / f["path"]).is_file() for f in cached.get("figures", []))):
                cand.pmcid = cached.get("pmcid") or cand.pmcid
                cached["cache_hit"] = True
                return cached
        except (OSError, ValueError, KeyError, TypeError):
            pass
    attempts: list[dict] = []
    seen: set[str] = set()

    def attempt(url: str, kind: str, source: str, license: str = ""):
        if not url or url in seen or urlparse(url).scheme not in {"https", "http"}:
            return None
        seen.add(url)
        response = _request(url, attempts=attempts, timeout=45)
        if response is None:
            return None
        data = response.content
        digest = hashlib.sha256(data).hexdigest()
        content_type = response.headers.get("Content-Type", "").lower()
        actual_kind = ("pdf" if data.lstrip().startswith(b"%PDF-") else
                       "xml" if "xml" in content_type and "html" not in content_type else
                       "html" if "html" in content_type else kind)
        # Persist every retrieved source, including rejected parses, before attempting parsing.
        raw_name = f"{digest}.{actual_kind}"
        if dest:
            (dest / raw_name).write_bytes(data)
        def linked_pdf():
            if actual_kind != "html":
                return None
            for pdf_url in _landing_pdf_urls(data, getattr(response, "url", None) or url):
                found = attempt(pdf_url, "pdf", source + ":linked-pdf", license)
                if found:
                    return found
            return None
        try:
            assets = dest / f"{digest}_assets" if dest else None
            if assets:
                assets.mkdir(exist_ok=True)
            parsed = parse_document_bytes(data, actual_kind, output_dir=assets)
            text = parsed.get("text") or ""
        except Exception as exc:
            attempts.append({"url": url, "status": "parse-failed", "error_type": type(exc).__name__,
                             "raw_sha256": digest, "raw_file": raw_name if dest else None})
            return linked_pdf()
        accepted = (_has_body(data, actual_kind, text) and _title_overlap(cand.title, text[:4000]) >= 0.5
                    and not parsed.get("needs_ocr") and not parsed.get("unreadable_pages"))
        attempts.append({"url": url, "status": "accepted" if accepted else "incomplete-or-identity-mismatch",
                         "raw_sha256": digest, "raw_file": raw_name if dest else None,
                         "n_chars": len(text), "parser": parsed.get("parser"),
                         "warnings": parsed.get("warnings", [])})
        # Keep parsed text even when rejected, for diagnosis without repeating the download.
        if dest:
            (dest / f"{digest}.txt").write_text(text, encoding="utf-8")
            (dest / f"{digest}.md").write_text(parsed.get("markdown") or text, encoding="utf-8")
        if not accepted:
            return linked_pdf()
        markdown = parsed.get("markdown") or text
        figures = parsed.get("figures") or []
        if dest and actual_kind == "xml":
            _pmc_figure_assets(cand.pmcid, figures, assets, attempts)
        for figure in figures:
            if figure.get("path") and assets:
                original_path = figure["path"]
                figure["path"] = str(Path(assets.name) / original_path)
                markdown = markdown.replace(f"]({original_path})", f"]({figure['path']})")
            href = figure.get("url")
            if not href or figure.get("path") or not dest:
                continue
            # Relative JATS graphics IDs do not identify a downloadable file. Retain explicitly unresolved.
            if not urlparse(href).scheme and not href.startswith("/"):
                figure["retrieval_status"] = "unresolved-relative-reference"
                continue
            figure_url = urljoin(url, href)
            figure_response = _request(figure_url, attempts=attempts)
            mime = figure_response.headers.get("Content-Type", "").split(";")[0].lower() if figure_response else ""
            image_suffixes = {"image/jpeg": "jpg", "image/png": "png", "image/gif": "gif",
                              "image/tiff": "tiff", "image/webp": "webp"}
            if figure_response is not None and mime in image_suffixes:
                figure_data = figure_response.content
                figure_digest = hashlib.sha256(figure_data).hexdigest()
                suffix = image_suffixes[mime]
                name = f"figure-{figure_digest}.{suffix}"
                (dest / name).write_bytes(figure_data)
                figure.update(path=name, url=figure_url, sha256=figure_digest, retrieval_status="downloaded")
            else:
                figure["retrieval_status"] = "unavailable"
        if actual_kind in {"xml", "html"}:
            for figure in figures:
                if figure.get("path"):
                    caption = figure.get("caption") or figure.get("label") or "Figure"
                    caption = str(caption).replace("[", "(").replace("]", ")")
                    markdown += f"\n\n![{caption}]({figure['path']})\n"
        if dest:
            (dest / f"{digest}.md").write_text(markdown, encoding="utf-8")
        if actual_kind == "xml":
            license = _jats_license(data.decode("utf-8", errors="replace")) or license
        return _save_result(root, cand, {"text": text, "markdown": markdown,
                            "source": source, "is_full_text": True, "license": license, "url": url,
                            "pmcid": cand.pmcid, "raw_file": raw_name if dest else None,
                            "raw_sha256": digest, "parsed_file": f"{digest}.txt" if dest else None,
                            "parser": parsed.get("parser"), "parser_version": parsed.get("parser_version"),
                            "figures": figures, "figures_status": ("extracted" if figures and all(f.get("path") for f in figures)
                                else "partial" if any(f.get("path") for f in figures)
                                else parsed.get("figures_status")),
                            "attempts": attempts, "retrieved_at": time.time(), "cache_version": 1,
                            "artifact_dir": str(dest) if dest else None})

    pmcid = cand.pmcid or _resolve_pmcid(cand.doi, cand.pmid, attempts)
    pmc = f"PMC{pmcid.upper().removeprefix('PMC')}" if pmcid else ""
    cand.pmcid = pmc
    if pmc:
        routes = [(f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmc}/fullTextXML", "xml", "epmc-oa"),
                  (f"{EUTILS}/efetch.fcgi?db=pmc&id={pmc.removeprefix('PMC')}&rettype=full&retmode=xml",
                   "xml", "pmc-efetch"),
                  (f"https://pmc.ncbi.nlm.nih.gov/articles/{pmc}/", "html", "pmc-html")]
        for url, kind, source in routes:
            result = attempt(url, kind, source, "pmc-license-unverified")
            if result:
                return result
    locations = list(cand.locations)
    if cand.doi:
        mapped = openalex_by_doi(cand.doi, attempts)
        if mapped:
            locations += mapped.locations
        up = _json_request(f"https://api.unpaywall.org/v2/{quote(cand.doi, safe='/')}",
                           params={"email": POLITE_EMAIL}, attempts=attempts)
        if up.get("is_oa"):
            for loc in [up.get("best_oa_location")] + (up.get("oa_locations") or []):
                if loc:
                    locations.append({"is_oa": True, "pdf_url": loc.get("url_for_pdf"),
                                      "landing_page_url": loc.get("url_for_landing_page"),
                                      "license": loc.get("license"), "provider": "unpaywall"})
    # Try every OA direct PDF, then every OA landing page; never stop at one broken location.
    for field_name, kind in (("pdf_url", "pdf"), ("landing_page_url", "html")):
        for loc in locations:
            if not loc.get("is_oa"):
                continue
            result = attempt(loc.get(field_name) or "", kind, loc.get("provider") or "openalex",
                             loc.get("license") or "oa-license-unverified")
            if result:
                return result
    return _save_result(root, cand, {"text": f"{cand.title}. {cand.abstract}".strip(), "source": "abstract",
                         "is_full_text": False, "license": "metadata-open", "url": "",
                         "attempts": attempts, "retrieved_at": time.time(),
                         "artifact_dir": str(dest) if dest else None})


# ----- Capture-recapture completeness (Chao2 incidence estimator) ---------------------------------
def estimate_completeness(channels_by_paper: dict[str, set]) -> dict:
    """Chao2 incidence estimate of the field size, a floor: correlated channels inflate overlap and bias
    the total down. Q1/Q2 are papers found by exactly one/two channels; small-sample corrected, with a
    log-normal 95% CI never below the observed count."""
    import math
    s_obs = len(channels_by_paper)
    counts = [len(ch) for ch in channels_by_paper.values()]
    q1 = sum(c == 1 for c in counts)
    q2 = sum(c == 2 for c in counts)
    t = len({c for chs in channels_by_paper.values() for c in chs})
    corr = (t - 1) / t if t else 1.0
    f0_bc = corr * q1 * (q1 - 1) / (2 * (q2 + 1))          # bias-corrected missing (defined at q2=0)
    if q2 > 0:
        f0 = corr * q1 * q1 / (2 * q2)
        r = q1 / q2
        var = q2 * (0.5 * r ** 2 + r ** 3 + 0.25 * r ** 4)
    else:
        f0, var = f0_bc, f0_bc
    s_hat = s_obs + f0
    if f0 > 0 and var > 0:
        k = math.exp(1.96 * math.sqrt(math.log(1 + var / f0 ** 2)))
        ci = (round(s_obs + f0 / k), round(s_obs + f0 * k))
    else:
        ci = (round(s_hat), round(s_hat))
    return {"observed": s_obs, "estimated_total": round(s_hat), "missing_est": round(f0),
            "completeness": round(s_obs / s_hat, 3) if s_hat else 1.0, "ci95": ci,
            "Q1": q1, "Q2": q2, "channels": t}
