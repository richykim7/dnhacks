"""Structured local document parsing. External figure URLs are never fetched here."""
from __future__ import annotations

import hashlib
from html.parser import HTMLParser
from importlib.metadata import version
from pathlib import Path
import re
import shutil
import tempfile
import threading
import xml.etree.ElementTree as ET

_PDF_LOCK = threading.Lock()  # PyMuPDF must not run concurrently in fetch threads.


def _tag(el):
    return el.tag.rsplit("}", 1)[-1].lower()


def _words(el):
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip()


def _render(el):
    tag = _tag(el)
    if tag in {"script", "style", "nav", "footer", "header"}:
        return ""
    if tag in {"table", "table-wrap"}:
        rows = []
        for row in el.iter():
            if _tag(row) in {"tr"}:
                cells = [_words(c).replace("|", "\\|") for c in row if _tag(c) in {"td", "th"}]
                if cells:
                    rows.append("| " + " | ".join(cells) + " |")
        if rows:
            n = len(rows[0].split("|")) - 2
            table = "\n".join([rows[0], "| " + " | ".join(["---"] * n) + " |", *rows[1:]])
            captions = [_words(c) for c in el if _tag(c) in {"label", "caption"}]
            return "\n\n" + "\n".join(captions + [table]) + "\n\n"
    text = el.text or ""
    for child in el:
        text += _render(child) + (child.tail or "")
    if tag in {"title", "article-title", "h1", "h2", "h3", "h4", "h5", "h6"}:
        return "\n\n## " + re.sub(r"\s+", " ", text).strip() + "\n\n"
    if tag in {"p", "sec", "abstract", "body", "article", "section", "div", "fig", "figure", "caption", "figcaption", "ref", "li", "ref-list"}:
        return "\n\n" + text.strip() + "\n\n"
    if tag == "br":
        return "\n"
    return text


class _HTMLTree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = ET.Element("document")
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        el = ET.SubElement(self.stack[-1], tag, {k: v or "" for k, v in attrs})
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.append(el)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        el = self.stack[-1]
        if len(el):
            el[-1].tail = (el[-1].tail or "") + data
        else:
            el.text = (el.text or "") + data


def _structured(data, fmt):
    raw = data.decode("utf-8", errors="replace")
    if fmt == "xml":
        if re.search(r"<!ENTITY", raw, re.I):
            raise ValueError("XML entity declarations are not supported")
        root = ET.fromstring(raw)
        body = next((el for el in root.iter() if _tag(el) == "body"), None)
        sections = [el for el in root.iter() if _tag(el) in {"article-title", "abstract", "body", "back"}]
        # Abstracts nested in back/body must not be serialized twice.
        selected = []
        for el in sections:
            if not any(el in tuple(prior.iter())[1:] for prior in selected):
                selected.append(el)
    else:
        parser = _HTMLTree()
        parser.feed(raw)
        root = parser.root
        body = next((el for el in root.iter() if _tag(el) == "article"), None)
        if body is None:
            body = next((el for el in root.iter() if el.get("id") in {"article-body", "main-content", "mc"}
                         or "article-body" in el.get("class", "").split()), None)
        if body is None:
            raise ValueError("HTML has no identifiable article body")
        selected = [body]
    markdown = "\n\n".join(_render(el).strip() for el in selected)
    markdown = re.sub(r"\n[ \t]*\n(?:[ \t]*\n)+", "\n\n", markdown).strip()
    figures = []
    scope = body if body is not None else root
    for el in scope.iter():
        if _tag(el) not in {"fig", "figure"}:
            continue
        caption = next((_words(c) for c in el.iter() if _tag(c) in {"caption", "figcaption"}), None)
        label = next((_words(c) for c in el if _tag(c) == "label"), None)
        graphics = [c for c in el.iter() if _tag(c) in {"graphic", "img"}]
        for graphic in graphics or [None]:
            url = None if graphic is None else (graphic.get("{http://www.w3.org/1999/xlink}href")
                                                 or graphic.get("href") or graphic.get("src"))
            figures.append({"id": el.get("id"), "label": label, "caption": caption,
                            "caption_source": "document" if caption else None,
                            "url": url, "path": None, "page": None, "bbox": None,
                            "kind": "document_figure"})
    return {"text": markdown, "markdown": markdown, "figures": figures,
            "parser": "stdlib-jats" if fmt == "xml" else "stdlib-article-html",
            "parser_version": "1", "pages": None, "warnings": [], "has_body": body is not None,
            "needs_ocr": False, "unreadable_pages": [],
            "figures_status": "referenced" if figures else "none"}


def _pdf(data, output_dir):
    import pymupdf
    import pymupdf4llm

    warnings = []
    with _PDF_LOCK, tempfile.TemporaryDirectory(prefix="dnhacks-pdf-") as tmp:
        scratch = Path(tmp)
        # Use a controlled filename: PDF metadata never determines filesystem paths.
        source = scratch / "source.pdf"
        source.write_bytes(data)
        with pymupdf.open(source) as doc:
            unreadable = []
            for page in doc:
                native = page.get_text().strip()
                image_area = max((pymupdf.Rect(i["bbox"]).get_area() for i in page.get_image_info()), default=0)
                # Scans sometimes have only a native page number/header. Flag that case too.
                if not native or (len(native) < 80 and image_area > page.rect.get_area() * 0.7):
                    unreadable.append(page.number + 1)
            pages = len(doc)
        # OCR is opt-in, uses the locally installed Tesseract engine, and never downloads models.
        import os
        use_ocr = os.environ.get("DNHACKS_PDF_OCR", "").lower() in {"1", "true"}
        if use_ocr and not shutil.which("tesseract"):
            warnings.append("OCR requested but Tesseract is not installed")
            use_ocr = False
        ocr_function = None
        if use_ocr:
            # Pin the installed CPU Tesseract backend rather than auto-selecting other OCR models.
            try:
                tessdata = pymupdf.get_tessdata()
                if not tessdata or not (Path(tessdata) / "eng.traineddata").is_file():
                    raise ValueError("English OCR language data is unavailable")
                from pymupdf4llm.ocr.tesseract_api import exec_ocr
                ocr_function = exec_ocr
            except (RuntimeError, ValueError, FileNotFoundError):
                warnings.append("Tesseract language data unavailable; OCR was not performed")
                use_ocr = False
        chunks = pymupdf4llm.to_markdown(str(source), filename="source.pdf", page_chunks=True,
                    write_images=True, image_path=str(scratch), use_ocr=use_ocr, ocr_function=ocr_function, show_progress=False)
        figures = []
        markdown_parts = []
        for chunk in chunks:
            page = chunk["metadata"]["page_number"]
            text = chunk["text"]
            original_text = text
            for box in chunk.get("page_boxes", []):
                if box["class"] not in {"picture", "formula"}:
                    continue
                start, end = box["pos"]
                region = original_text[start:end]
                for match in re.finditer(r"!\[[^\]]*\]\(([^)]+)\)", region):
                    generated = Path(match.group(1)).resolve()
                    if not generated.is_relative_to(scratch.resolve()) or not generated.is_file():
                        raise ValueError("PDF parser returned an invalid image path")
                    rel = None
                    if output_dir is not None:
                        dest = Path(output_dir).resolve()
                        dest.mkdir(parents=True, exist_ok=True)
                        name = f"figure-{hashlib.sha256(generated.read_bytes()).hexdigest()[:20]}.png"
                        target = dest / name
                        if target.is_symlink():
                            raise ValueError("Figure destination must not be a symlink")
                        shutil.copyfile(generated, target)
                        rel = name
                    figures.append({"path": rel, "page": page, "bbox": list(box["bbox"]),
                                    "caption": None, "caption_source": None,
                                    "kind": "formula_region" if box["class"] == "formula" else "detected_picture_region"})
                    text = text.replace(match.group(1), rel or "image-not-persisted")
            # OCR success is observable only from actual non-image text on the page.
            plain = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text).strip()
            if use_ocr and len(plain) >= 80 and page in unreadable:
                unreadable.remove(page)
            markdown_parts.append(text)
        markdown = "\n\n".join(markdown_parts).strip()
        text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", markdown).strip()
        if unreadable:
            warnings.append("Pages without readable text; OCR or source inspection required: " + ", ".join(map(str, unreadable)))
        if not text:
            raise ValueError("PDF yielded no readable text; OCR is required for scanned documents")
        if figures and output_dir is None:
            warnings.append("Picture regions detected but not persisted because no output directory was supplied")
        return {"text": text, "markdown": markdown, "figures": figures,
                "parser": "pymupdf4llm", "parser_version": version("pymupdf4llm"),
                "pages": pages, "warnings": warnings, "needs_ocr": bool(unreadable),
                "unreadable_pages": unreadable,
                "figures_status": ("extracted" if output_dir is not None else "not_extracted") if figures else "none"}


def parse_document_bytes(data: bytes, format: str, output_dir: Path | None = None) -> dict:
    """Return structured text and provenance; PDF picture paths are output-dir-relative.

    ``needs_ocr`` blocks treating partially unreadable PDFs as complete full text. XML/HTML
    figures retain source references; callers own downloading and resolving relative URLs.
    """
    fmt = format.lower().lstrip(".")
    if fmt == "pdf":
        return _pdf(data, output_dir)
    if fmt in {"xml", "jats", "html", "htm"}:
        return _structured(data, "xml" if fmt in {"xml", "jats"} else "html")
    if fmt in {"txt", "md"}:
        text = data.decode("utf-8", errors="replace").strip()
        return {"text": text, "markdown": text, "figures": [], "parser": "utf8",
                "parser_version": "1", "pages": None, "warnings": [],
                "needs_ocr": False, "unreadable_pages": [], "figures_status": "not_extracted"}
    raise ValueError(f"Unsupported document format: {fmt}")
