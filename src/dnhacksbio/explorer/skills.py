"""Skill library loader — the explorer's menu of methods.

A skill is a `skills/<name>/SKILL.md` file: informational + rigorous guidance (what the method is, when to
use it, the statistical invariants to honor, a worked example), not a frozen function: the explorer reads
the skill and writes its own code. This module lets the agent discover and read them: list what is
available, search by question, and pull the full guidance before writing an experiment.
"""
from __future__ import annotations

import re
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parents[3] / "skills"

_FIELD = {
    "one_line": re.compile(r"^\*\*One line:\*\*\s*(.+)$", re.M | re.I),
    "category": re.compile(r"^\*\*Category:\*\*\s*(.+)$", re.M | re.I),
    "open_source": re.compile(r"^\*\*Open-source:\*\*\s*(.+)$", re.M | re.I),
    "install": re.compile(r"^\*\*Install:\*\*\s*(.+)$", re.M | re.I),
}


def _parse_header(text: str) -> dict:
    out = {}
    for k, rx in _FIELD.items():
        m = rx.search(text)
        out[k] = m.group(1).strip() if m else ""
    return out


def _skill_dirs() -> list[Path]:
    if not SKILLS_DIR.exists():
        return []
    return sorted(d for d in SKILLS_DIR.iterdir() if d.is_dir() and (d / "SKILL.md").exists())


def list_skills() -> list[dict]:
    """Every skill's header (name + one-liner + category + library/license). Cheap to hand the explorer as
    its menu."""
    out = []
    for d in _skill_dirs():
        hdr = _parse_header((d / "SKILL.md").read_text(errors="replace"))
        out.append({"name": d.name, **hdr})
    return out


def get_skill(name: str) -> str | None:
    """The full SKILL.md text — what the explorer reads before writing code for that method."""
    p = SKILLS_DIR / name / "SKILL.md"
    return p.read_text(errors="replace") if p.exists() else None


def search_skills(query: str, limit: int = 8) -> list[dict]:
    """Rank skills by relevance to a free-text question (keyword over name+one-liner+category). Simple and
    dependency-free; the explorer uses it to find which method fits an idea."""
    q = set(re.findall(r"[a-z0-9]+", query.lower()))
    scored = []
    for s in list_skills():
        hay = f"{s['name']} {s.get('one_line', '')} {s.get('category', '')}".lower()
        toks = set(re.findall(r"[a-z0-9]+", hay))
        score = len(q & toks) + (2 if any(w in s["name"].lower() for w in q) else 0)
        if score:
            scored.append((score, s))
    scored.sort(key=lambda t: t[0], reverse=True)
    return [s for _, s in scored[:limit]]
