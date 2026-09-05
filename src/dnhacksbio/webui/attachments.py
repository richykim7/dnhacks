"""Attachments — the scientist's own documents, parsed at upload time.

A literature search reaches published, indexed, mostly open-access papers. It does not reach the
preprint a collaborator sent you, the thesis chapter, the internal report, or the paywalled paper
you have a legitimate copy of. Those are often the documents that carry the mechanism you actually
care about, so they get folded into the corpus as first-class documents: the same extractor reads
them, the same claim atoms come out, the same quotes back them.

Parsing happens at UPLOAD time, not at build time. That is the whole design decision here. A PDF
that turns out to be a scanned image yields ~zero characters of text.
"""

from __future__ import annotations

import re
import time
import uuid
from pathlib import Path

from dnhacksbio.litmap import ingest

from . import projects

MAX_BYTES = 40 * 1024 * 1024        # one big PDF; beyond this something is wrong
MAX_PER_PROJECT = 200
# Corpus refs for uploads start here, above anything a fetched-paper ref will reach. The ref is
# assigned once, at upload, and stored; it is the join key between a document and its claims in the
# graph, so it must not move when an earlier attachment is deleted and the list re-indexes.
REF_BASE = 10_000
# What we can actually turn into text. `md` rides the plain-text parser.
EXTS = {"pdf": "pdf", "txt": "txt", "md": "txt", "text": "txt", "xml": "xml", "nxml": "xml"}
# Below this a "successful" parse is really a failure — a scanned PDF, an encrypted file, or a stub.
MIN_TEXT_CHARS = 200

_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_name(filename: str) -> str:
    base = Path(filename or "").name
    return _SAFE.sub("_", base)[:120] or "upload"


def _parse(path: Path, kind: str) -> str:
    parser = ingest._PARSERS.get(kind)
    if parser is None:
        raise ValueError(f"cannot read .{kind} files")
    try:
        return parser(path)
    except ImportError as exc:
        # PyMuPDF is an optional extra (pyproject: litmap). Name the fix rather than the traceback.
        raise ValueError(
            f"PDF support is not installed ({exc}). Install it with `uv sync --extra litmap`, "
            f"or upload a .txt/.xml copy instead.") from exc
    except Exception as exc:
        raise ValueError(f"could not read the file ({type(exc).__name__}: {exc})") from exc


def add(project_id: str, filename: str, data: bytes) -> dict:
    """Store one uploaded document, parse it to text, and register it on the project."""
    rec = projects.load(project_id)
    if rec.get("adopted"):
        raise ValueError("adopted corpora are read-only")
    if not data:
        raise ValueError("the uploaded file is empty")
    if len(data) > MAX_BYTES:
        raise ValueError(f"file is too large ({len(data) / 1e6:.1f} MB, max {MAX_BYTES // 10**6} MB)")
    if len(rec.get("attachments") or []) >= MAX_PER_PROJECT:
        raise ValueError(f"this project already has {MAX_PER_PROJECT} attachments")

    safe = _safe_name(filename)
    ext = safe.rsplit(".", 1)[-1].lower() if "." in safe else ""
    kind = EXTS.get(ext)
    if kind is None:
        raise ValueError(f"unsupported file type '.{ext}' — upload pdf, txt, md or xml")

    aid = uuid.uuid4().hex[:12]
    d = projects.attachments_dir(project_id)
    d.mkdir(parents=True, exist_ok=True)
    raw_path = d / f"{aid}__{safe}"
    raw_path.write_bytes(data)

    try:
        text = _parse(raw_path, kind)
    except ValueError:
        raw_path.unlink(missing_ok=True)
        raise
    if len(text.strip()) < MIN_TEXT_CHARS:
        raw_path.unlink(missing_ok=True)
        raise ValueError(
            f"only {len(text.strip())} characters of text came out of {safe}. If it is a scanned "
            f"PDF it has no text layer — run OCR first, or upload a text version.")

    text_path = d / f"{aid}.txt"
    text_path.write_text(text, encoding="utf-8")

    rec = projects.load(project_id)
    existing = list(rec.get("attachments") or [])
    att = {
        "id": aid, "filename": safe, "ext": kind, "bytes": len(data),
        "n_chars": len(text), "added": time.time(), "ref": next_ref(existing),
        "file": raw_path.name, "text_file": text_path.name,
        "preview": re.sub(r"\s+", " ", text[:400]).strip(),
        "doi": _sniff_doi(text), "year": _sniff_year(text),
    }
    rec["attachments"] = existing + [att]
    projects.save(rec)
    return att


def next_ref(existing: list[dict]) -> int:
    """The next never-used corpus ref. Monotonic over the project's whole history: it counts from the
    highest ref ever assigned, not from the current list length."""
    return max([int(a.get("ref") or 0) for a in existing] + [REF_BASE - 1]) + 1


_DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b")
_YEAR_RE = re.compile(r"\b(19[89]\d|20[0-4]\d)\b")


def _sniff_doi(text: str) -> str:
    m = _DOI_RE.search(text[:8000] or "")
    return m.group(0).rstrip(".,;)") .lower() if m else ""


def _sniff_year(text: str) -> int | None:
    years = [int(y) for y in _YEAR_RE.findall(text[:4000] or "")]
    return max(years) if years else None


def listing(project_id: str) -> list[dict]:
    return list(projects.load(project_id).get("attachments") or [])


def remove(project_id: str, attachment_id: str) -> dict:
    rec = projects.load(project_id)
    if rec.get("adopted"):
        raise ValueError("adopted corpora are read-only")
    atts = list(rec.get("attachments") or [])
    keep = [a for a in atts if a.get("id") != attachment_id]
    if len(keep) == len(atts):
        raise KeyError(attachment_id)
    gone = next(a for a in atts if a.get("id") == attachment_id)
    d = projects.attachments_dir(project_id)
    for key in ("file", "text_file"):
        name = gone.get(key)
        if name:
            (d / name).unlink(missing_ok=True)
    rec["attachments"] = keep
    projects.save(rec)
    return {"ok": True, "id": attachment_id, "remaining": len(keep)}


