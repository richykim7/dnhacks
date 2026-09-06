"""Ingest: load a local full-text corpus into clean text with provenance.

.txt is read directly, .pdf uses structured PyMuPDF4LLM parsing, .xml preserves JATS structure. The filename
convention `<ref#>_<shortname>.<ext>` supplies provenance: the numeric prefix is the reference number
every extracted claim traces back to.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from pathlib import Path

CORPUS_DIR = Path("corpus/fulltext")
MAX_CHARS = None     # no truncation: the extractor reads the whole paper

_TAG = re.compile(r"<[^>]+>")
_WS_LINES = re.compile(r"\n[ \t]*\n(?:[ \t]*\n)+")
_NAV_HINTS = (
    "skip to main content", "an official website", "here's how you know",
    "the .gov means it", "https://", "cookie", "javascript", "sign in", "log in to",
)


@dataclass
class Document:
    ref: int              # reference number (== filename prefix)
    label: str            # short name, e.g. "Smith2018"
    ext: str              # txt | pdf | xml
    path: str
    text: str
    n_chars: int
    source_id: str = ""   # DOI/PMID if resolved (may be empty; ref+label is provenance)


def _clean(text: str) -> str:
    text = html.unescape(text)
    # drop obvious web/nav boilerplate lines (conservative: only very clear hits, short lines)
    kept = []
    for line in text.splitlines():
        s = line.strip()
        low = s.lower()
        if len(s) < 60 and any(h in low for h in _NAV_HINTS):
            continue
        kept.append(line)
    text = "\n".join(kept)
    text = _WS_LINES.sub("\n\n", text).strip()
    return text


def _parse_txt(path: Path) -> str:
    return _clean(path.read_text(encoding="utf-8", errors="ignore"))


def _parse_pdf(path: Path) -> str:
    from dnhacksbio.litmap.document_parse import parse_document_bytes
    parsed = parse_document_bytes(path.read_bytes(), "pdf", path.parent / f"{path.stem}_assets")
    if parsed["needs_ocr"]:
        raise ValueError("PDF contains unreadable pages; OCR or source inspection required")
    return _clean(parsed["text"])


def _parse_xml(path: Path) -> str:
    from dnhacksbio.litmap.document_parse import parse_document_bytes
    return _clean(parse_document_bytes(path.read_bytes(), "xml")["text"])


_PARSERS = {"txt": _parse_txt, "pdf": _parse_pdf, "xml": _parse_xml}


def load_corpus(corpus_dir: Path | str = CORPUS_DIR, cap: int | None = MAX_CHARS) -> list[Document]:
    """Load every full-text file into a Document. Raises if the corpus dir is empty (fail loud)."""
    d = Path(corpus_dir)
    files = sorted(p for p in d.iterdir() if p.suffix.lstrip(".") in _PARSERS)
    if not files:
        raise FileNotFoundError(f"no full-text files under {d}")
    docs: list[Document] = []
    for p in files:
        m = re.match(r"(\d+)_(.+)", p.stem)
        if not m:
            continue
        ref, label = int(m.group(1)), m.group(2)
        ext = p.suffix.lstrip(".")
        try:
            text = _PARSERS[ext](p)
        except Exception as e:
            text = f"[PARSE-ERROR {ext}: {e}]"
        docs.append(Document(ref=ref, label=label, ext=ext, path=str(p),
                             text=text[:cap], n_chars=len(text)))
    return docs
