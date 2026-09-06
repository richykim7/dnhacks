"""Read-only paper browser over the graph and its optional frozen-corpus manifest.

No fetches, metadata resolution, model calls or store initialization. Missing local
text/figures stay missing; publisher HTML is only parsed for citation metadata.
"""
from __future__ import annotations

from functools import lru_cache
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.parse import quote
from xml.etree import ElementTree

from . import data, projects


class _Authors(HTMLParser):
    def __init__(self):
        super().__init__()
        self.names = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta" and attrs.get("name", "").lower() == "citation_author":
            name = attrs.get("content", "").strip()
            if name and name not in self.names:
                self.names.append(name)


def _local(root: Path, relative) -> Path | None:
    """Only manifest-declared files inside the corpus's papers directory."""
    if not isinstance(relative, str) or not relative:
        return None
    path = (root / relative).resolve()
    if not path.is_relative_to((root / "papers").resolve()) or not path.is_file():
        return None
    return path


@lru_cache(maxsize=512)
def _authors(path: str, mtime_ns: int, size: int) -> tuple[str, ...]:
    raw = Path(path).read_text(errors="replace")
    if Path(path).suffix.lower() == ".xml":
        try:
            article = ElementTree.fromstring(raw)
        except ElementTree.ParseError:
            return ()
        if article.tag == "pmc-articleset":
            article = article.find("article")
            if article is None:
                return ()
        names = []
        for contributor in article.findall("./front/article-meta/contrib-group/contrib"):
            if contributor.get("contrib-type", "author") != "author":
                continue
            name = contributor.find("name")
            if name is not None:
                value = " ".join("".join(name.find(part).itertext()).strip() for part in ("given-names", "surname") if name.find(part) is not None)
            else:
                collab = contributor.find("collab")
                value = "".join(collab.itertext()).strip() if collab is not None else ""
            if value and value not in names:
                names.append(value)
        return tuple(names)
    parser = _Authors()
    parser.feed(raw)
    return tuple(parser.names)


def _manifest(root):
    path = root / "MANIFEST.json"
    if not path.is_file():
        return {}
    obj = json.loads(path.read_text())
    rows = obj.get("papers") if isinstance(obj.get("papers"), list) else obj.get("papers_meta", [])
    return {str(p["ref"]): p for p in rows if isinstance(p, dict) and "ref" in p}


def _database(pid):
    project = projects.load(pid)
    return Path(project["kg_db"]) if project.get("kg_db") else None


def _rows(db, paper_id=None):
    con = data._connect_ro(db)
    try:
        if "papers" not in data._tables(con):
            return []
        columns = {r[0] for r in con.execute("describe papers").fetchall()}
        wanted = ["paper_id", "source_ref", "source_label", "title", "year", "doi", "url", "is_full_text", "n_chars"]
        if paper_id is not None:
            wanted += ["text", "sections"]
        selected = [f'"{c}"' if c in columns else f'NULL AS "{c}"' for c in wanted]
        selected.append('length(coalesce(text,\'\')) > 0 AS has_text' if "text" in columns else "false AS has_text")
        query = f"select {', '.join(selected)} from papers"
        if paper_id is not None:
            query += " where paper_id = ?"
        return data._rows(con, query + " order by source_ref, paper_id", [paper_id] if paper_id is not None else [])
    finally:
        con.close()


def _decorate(row, manifest, root):
    row = dict(row)
    meta = manifest.get(str(row.get("source_ref")), {})
    raw = _local(root, meta.get("raw_file"))
    recorded_authors = meta.get("authors")
    row["authors"] = ([a for a in recorded_authors if isinstance(a, str) and a.strip()]
                      if isinstance(recorded_authors, list) else
                      list(_authors(str(raw), raw.stat().st_mtime_ns, raw.stat().st_size))
                      if raw and raw.suffix.lower() in (".html", ".htm", ".xml") else [])
    row["category"] = meta.get("category") or None
    row["figure_count"] = sum(_local(root, f.get("path")) is not None for f in meta.get("figures", []))
    row["is_full_text"] = bool(row.get("is_full_text") and row.get("has_text"))
    return row


def list_papers(pid: str) -> dict:
    db = _database(pid)
    if db is None:
        return {"papers": [], "total": 0}
    manifest = _manifest(db.parent)
    rows = [_decorate(row, manifest, db.parent) for row in _rows(db)]
    return {"papers": rows, "total": len(rows)}


def paper_detail(pid: str, paper_id: str) -> dict:
    db = _database(pid)
    rows = _rows(db, paper_id) if db is not None else []
    if not rows:
        raise FileNotFoundError("Paper not found in this collection")
    manifest = _manifest(db.parent)
    row = _decorate(rows[0], manifest, db.parent)
    row["text"] = row.get("text") or ""
    try:
        sections = json.loads(row["sections"]) if row.get("sections") else None
    except (ValueError, TypeError):
        sections = None
    row["sections"] = sections if isinstance(sections, dict) else None
    figures = manifest.get(str(row.get("source_ref")), {}).get("figures", [])
    prefix = f"/api/projects/{quote(pid, safe='')}/papers/{quote(paper_id, safe='')}/figures/"
    row["figures"] = [{"id": f.get("id") or str(i + 1), "label": f.get("label") or f.get("id") or f"Figure {i + 1}",
                       "caption": f.get("caption") or "", "url": prefix + str(i) if _local(db.parent, f.get("path")) else None}
                      for i, f in enumerate(figures)]
    return {"paper": row}


def figure(pid: str, paper_id: str, index: int) -> tuple[bytes, str]:
    db = _database(pid)
    rows = _rows(db, paper_id) if db is not None else []
    if not rows or index < 0:
        raise FileNotFoundError("Figure not found")
    figures = _manifest(db.parent).get(str(rows[0].get("source_ref")), {}).get("figures", [])
    if index >= len(figures):
        raise FileNotFoundError("Figure not found")
    path = _local(db.parent, figures[index].get("path"))
    types = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif"}
    if path is None or path.suffix.lower() not in types:
        raise FileNotFoundError("Local figure image unavailable")
    return path.read_bytes(), types[path.suffix.lower()]
