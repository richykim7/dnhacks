"""Projects — an *analysis profile* that scopes the whole console.

A **project** is one investigation: its own literature corpus (a KG DuckDB), its own uploaded
attachments, its own engine runs, its own review queue. Picking a project in the sidebar re-points
every tab at that project's state, so two analyses never bleed into each other.

A directory of JSON files rather than a table: the rest of this repo treats the filesystem as the source
of truth (traces are JSONL, graphs are DuckDB files), and a project record is small and read far more
often than written. One file per project, written atomically (tmp + rename), is the whole storage layer.

    data/projects/<id>/project.json     the record (below)
    data/projects/<id>/kg.duckdb        the corpus knowledge graph this project builds
    data/projects/<id>/attachments/     user-uploaded papers (pdf/txt/xml/md) + their parsed text
    data/projects/<id>/jobs/<job>.json  job record + <job>.jsonl progress stream (see jobs.py)
    data/projects/<id>/corpus_card.md   the per-run framing the explorer reads (written at build time)

Corpora built by scripts (data/corpora/<name>/<name>_kg.duckdb) are **adopted**: surfaced as read-only
projects. An adopted project can be browsed and run against; it cannot
be rebuilt or deleted from the UI, because this module did not create it.
"""

from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PROJECTS = ROOT / "data" / "projects"
CORPORA = ROOT / "data" / "corpora"

# A project id is used as a path segment and as a query-string value. Keep it to a conservative
# charset so it can never escape the projects dir or need escaping anywhere downstream.
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,48}$")

# Spec bounds. These are cost rails, not taste: n_papers drives an LLM extraction per paper, and
# concurrency drives how many of those run at once.
N_PAPERS_MIN, N_PAPERS_MAX = 5, 2000
CONCURRENCY_MIN, CONCURRENCY_MAX = 1, 40
MAX_QUERIES = 60
MAX_SEED_DOIS = 200

STATUSES = ("draft", "building", "ready", "failed")


# --- ids + io ---------------------------------------------------------------

def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower()).strip("-")[:48]
    return s or "analysis"


def _now() -> float:
    return time.time()


def _write_atomic(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False))
    tmp.replace(path)


def project_dir(pid: str) -> Path:
    if not ID_RE.match(pid or ""):
        raise ValueError(f"bad project id: {pid!r}")
    return PROJECTS / pid


def _record_path(pid: str) -> Path:
    return project_dir(pid) / "project.json"


def attachments_dir(pid: str) -> Path:
    return project_dir(pid) / "attachments"


def jobs_dir(pid: str) -> Path:
    return project_dir(pid) / "jobs"


def kg_path(pid: str) -> Path:
    return project_dir(pid) / "kg.duckdb"


def corpus_card_path(pid: str) -> Path:
    return project_dir(pid) / "corpus_card.md"


# --- the spec ---------------------------------------------------------------

def default_spec() -> dict:
    """The corpus definition: what is in the collection, and nothing about what to ask of it.

    There is no `goal` here. A goal is a question, a question belongs to a run, and a corpus outlives
    any number of runs asking different things of it. A goal field here would be written into
    `corpus_card.md` as `## Goal`, which `run_explorer.py` reads as a run's brief when none is passed,
    so defining a corpus would silently set the engine's question. `scope` is the descriptive field
    instead: what this collection covers and what it leaves out."""
    return {
        "scope": "",           # what the corpus covers / excludes — description, never a question
        "theme": "",           # one paragraph; the embedding target relevance triage ranks against
        "queries": [],         # Europe PMC query strings, one discovery channel each
        "seed_dois": [],       # force-included anchors that triage may not drop
        "n_papers": 120,
        "year_min": None,      # inclusive publication-year window; None = unbounded
        "year_max": None,
        "exclude_terms": [],   # drop candidates whose title/abstract matches (holdout builds)
        "full_text_only": False,
        "concurrency": 8,
    }


def _as_str_list(v, field: str, cap: int) -> list[str]:
    if v is None:
        return []
    if isinstance(v, str):
        v = [line for line in v.splitlines()]
    if not isinstance(v, list):
        raise ValueError(f"{field} must be a list of strings")
    out = []
    for item in v:
        s = str(item or "").strip()
        if s:
            out.append(s[:1000])
    if len(out) > cap:
        raise ValueError(f"{field}: at most {cap} entries (got {len(out)})")
    return list(dict.fromkeys(out))       # de-dup, order preserved


def _as_year(v, field: str) -> int | None:
    if v in (None, "", "null"):
        return None
    try:
        y = int(v)
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be a 4-digit year")
    if not 1800 <= y <= 2200:
        raise ValueError(f"{field} out of range: {y}")
    return y


def validate_spec(spec: dict, *, for_build: bool = False) -> dict:
    """Normalize + bound a spec. `for_build=True` additionally demands the fields a build cannot
    run without, so a half-filled draft can still be saved while an unbuildable one is refused."""
    if not isinstance(spec, dict):
        raise ValueError("spec must be an object")
    base = default_spec()
    out = {**base, **{k: v for k, v in spec.items() if k in base}}

    out["scope"] = str(out.get("scope") or "").strip()[:4000]
    out["theme"] = str(out.get("theme") or "").strip()[:4000]
    out["queries"] = _as_str_list(out.get("queries"), "queries", MAX_QUERIES)
    out["seed_dois"] = [d.lower().replace("https://doi.org/", "")
                        for d in _as_str_list(out.get("seed_dois"), "seed_dois", MAX_SEED_DOIS)]
    out["exclude_terms"] = _as_str_list(out.get("exclude_terms"), "exclude_terms", 100)

    try:
        out["n_papers"] = int(out["n_papers"])
    except (TypeError, ValueError):
        raise ValueError("n_papers must be a whole number")
    if not N_PAPERS_MIN <= out["n_papers"] <= N_PAPERS_MAX:
        raise ValueError(f"n_papers must be between {N_PAPERS_MIN} and {N_PAPERS_MAX}")

    try:
        out["concurrency"] = int(out["concurrency"])
    except (TypeError, ValueError):
        raise ValueError("concurrency must be a whole number")
    out["concurrency"] = max(CONCURRENCY_MIN, min(CONCURRENCY_MAX, out["concurrency"]))

    out["year_min"] = _as_year(out.get("year_min"), "year_min")
    out["year_max"] = _as_year(out.get("year_max"), "year_max")
    if out["year_min"] and out["year_max"] and out["year_min"] > out["year_max"]:
        raise ValueError("year_min is after year_max")
    out["full_text_only"] = bool(out.get("full_text_only"))

    if for_build:
        if not out["queries"]:
            raise ValueError("at least one literature query is required to build a corpus")
        if not out["theme"]:
            raise ValueError("a theme is required — relevance triage ranks papers against it")
    return out


# --- records ----------------------------------------------------------------

def _blank(pid: str, name: str) -> dict:
    return {
        "id": pid,
        "name": name,
        "description": "",
        "created": _now(),
        "updated": _now(),
        "status": "draft",
        "spec": default_spec(),
        "attachments": [],
        "chat": [],
        "runs": [],
        "build": {},            # last build summary: {job_id, finished, n_papers, n_claims, kg:{...}}
        "kg_db": None,          # resolved on read
        "adopted": False,
    }


def exists(pid: str) -> bool:
    try:
        return _record_path(pid).is_file()
    except ValueError:
        return False


def create(name: str, description: str = "", spec: dict | None = None) -> dict:
    name = (name or "").strip()
    if not name:
        raise ValueError("a name is required")
    if len(name) > 120:
        raise ValueError("name is too long (max 120 chars)")
    base = slugify(name)
    pid, n = base, 2
    while exists(pid) or (CORPORA / pid).exists():   # never collide with an adopted corpus
        pid = f"{base}-{n}"
        n += 1
    rec = _blank(pid, name)
    rec["description"] = str(description or "").strip()[:4000]
    if spec:
        rec["spec"] = validate_spec(spec)
    project_dir(pid).mkdir(parents=True, exist_ok=True)
    attachments_dir(pid).mkdir(exist_ok=True)
    jobs_dir(pid).mkdir(exist_ok=True)
    _write_atomic(_record_path(pid), rec)
    return load(pid)


def load(pid: str) -> dict:
    """Read one project. Adopted corpora resolve here too, so callers never special-case."""
    path = _record_path(pid)
    if not path.is_file():
        ad = _adopted().get(pid)
        if ad:
            return ad
        raise KeyError(pid)
    try:
        rec = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise KeyError(f"{pid}: unreadable project record ({exc})")
    rec.setdefault("id", pid)
    rec["adopted"] = False
    rec["spec"] = {**default_spec(), **(rec.get("spec") or {})}
    db = kg_path(pid)
    rec["kg_db"] = str(db) if db.exists() else None
    rec["n_attachments"] = len(rec.get("attachments") or [])
    rec["built"] = built_manifest(pid, rec["spec"])
    return rec


def built_manifest(pid: str, cur_spec: dict | None = None) -> dict | None:
    """What the graph on disk was ACTUALLY built from, as opposed to what the spec says now.

    The spec is a plan and it is editable; the graph is a frozen artifact from some earlier version
    of that plan. Reading the build's own manifest keeps the two apart."""
    path = project_dir(pid) / "MANIFEST.json"
    if not path.is_file():
        return None
    try:
        m = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    spec = m.get("spec") or {}
    return {
        "built": m.get("built"), "mode": m.get("mode"),
        "n_papers": m.get("n_papers"), "n_claims": m.get("n_claims"),
        "n_attachments": m.get("n_attachments"),
        "entities": (m.get("kg") or {}).get("entities"),
        "queries": spec.get("queries") or [], "scope": spec.get("scope") or "",
        "theme": spec.get("theme") or "", "year_max": spec.get("year_max"),
        "completeness": (m.get("completeness") or {}).get("completeness"),
        "stale": _spec_drifted(cur_spec, spec) if cur_spec is not None else False,
    }


# Only the fields that change which papers get read. `scope` and `concurrency` are not here: the first
# is prose describing the collection, the second a throughput knob, and marking the graph stale because
# a description was reworded would make the mark meaningless.
_DRIFT_KEYS = ("queries", "theme", "n_papers", "year_min", "year_max",
               "exclude_terms", "full_text_only", "seed_dois")


def _spec_drifted(cur_spec: dict, built_spec: dict) -> bool:
    """True when the saved definition no longer matches the one that produced the graph."""
    cur, was = {**default_spec(), **cur_spec}, {**default_spec(), **built_spec}
    return any(cur.get(k) != was.get(k) for k in _DRIFT_KEYS)


def assert_writable(pid: str) -> None:
    """Presentation namespaces are operator-installed and cannot launch real work."""
    if load(pid).get("presentation_only") is True:
        raise ValueError("This presentation-only collection permits inspection and isolated candidate review only")


def presentation_source(pid: str | None) -> str | None:
    """Resolve one operator-configured display association, never a writable graph alias."""
    if not pid:
        return None
    try:
        rec = load(pid)
        source = rec.get("presentation_source_project")
        if rec.get("presentation_only") is not True or not isinstance(source, str) or source == pid:
            return None
        target = load(source)
        if target.get("presentation_only") is True or not target.get("kg_db"):
            return None
        return source
    except (KeyError, ValueError):
        return None


def matches_run_scope(owner: str | None, requested: str | None) -> bool:
    """Read/review lookup may use a source collection; the manifest retains its private owner."""
    return not requested or requested == owner or requested == presentation_source(owner)


def save(rec: dict) -> dict:
    pid = rec["id"]
    if exists(pid):
        assert_writable(pid)
    if rec.get("adopted"):
        raise ValueError(f"{pid} is an existing corpus adopted read-only; it cannot be edited here")
    rec["updated"] = _now()
    stored = {k: v for k, v in rec.items()
              if k not in ("kg_db", "adopted", "n_attachments", "built")}
    _write_atomic(_record_path(pid), stored)
    return load(pid)


def update(pid: str, patch: dict) -> dict:
    """Merge a partial update. Only whitelisted fields — a client cannot invent record keys."""
    rec = load(pid)
    if rec.get("adopted"):
        raise ValueError(f"{pid} is a read-only adopted corpus")
    if "name" in patch:
        name = str(patch["name"] or "").strip()
        if not name:
            raise ValueError("name cannot be empty")
        rec["name"] = name[:120]
    if "description" in patch:
        rec["description"] = str(patch["description"] or "").strip()[:4000]
    if "spec" in patch:
        rec["spec"] = validate_spec({**rec["spec"], **(patch["spec"] or {})})
    if "status" in patch:
        if patch["status"] not in STATUSES:
            raise ValueError(f"status must be one of {STATUSES}")
        rec["status"] = patch["status"]
    if "build" in patch and isinstance(patch["build"], dict):
        rec["build"] = patch["build"]
    if "runs" in patch:
        rec["runs"] = _as_str_list(patch["runs"], "runs", 500)
    out = save(rec)
    # The card is derived entirely from the record, so it is rewritten whenever the definition changes.
    if "spec" in patch and corpus_card_path(pid).is_file():
        write_corpus_card(pid)
    return out


def delete(pid: str, *, purge: bool = False) -> dict:
    """Remove a project. `purge` also deletes its corpus + attachments from disk.

    A build can be running against this directory, so refuse while a job is alive — deleting the
    files out from under a live extraction loses the work AND leaves a half-written DuckDB."""
    assert_writable(pid)
    rec = load(pid)
    if rec.get("adopted"):
        raise ValueError("adopted corpora are read-only; delete the folder on disk instead")
    from . import jobs
    if any(j.get("status") == "running" for j in jobs.list_jobs(pid)):
        raise RuntimeError("a build is still running for this project — cancel it first")
    if purge:
        shutil.rmtree(project_dir(pid), ignore_errors=True)
    else:
        _record_path(pid).replace(project_dir(pid) / "project.deleted.json")
    return {"ok": True, "id": pid, "purged": bool(purge)}


# --- adopted (pre-existing) corpora -----------------------------------------

def _adopted() -> dict[str, dict]:
    """Corpora built by scripts under data/corpora/, surfaced read-only. Discovered the way the KG
    viewer discovers them (data.kg_sources), so the two never disagree about what corpora exist."""
    out: dict[str, dict] = {}
    found: list[tuple[str, Path, str]] = []
    for p in sorted(CORPORA.glob("*/*_kg.duckdb")):
        found.append((p.parent.name, p, p.parent.name))
    for pid, path, label in found:
        if pid in out or exists(pid):
            continue
        st = path.stat()
        out[pid] = {
            "id": pid, "name": label, "description": "",
            "created": st.st_mtime, "updated": st.st_mtime, "status": "ready",
            "spec": default_spec(), "attachments": [], "chat": [], "runs": [], "build": {},
            "kg_db": str(path), "adopted": True, "n_attachments": 0,
        }
    return out


def list_projects() -> list[dict]:
    """Every project, newest first: real ones then adopted corpora."""
    out = []
    if PROJECTS.exists():
        for d in sorted(PROJECTS.iterdir()):
            if not d.is_dir() or not (d / "project.json").is_file():
                continue
            try:
                out.append(load(d.name))
            except (KeyError, ValueError):
                continue
    out.sort(key=lambda r: -(r.get("updated") or 0))
    return out + sorted(_adopted().values(), key=lambda r: -(r.get("updated") or 0))


_claim_count_cache: dict[str, tuple[tuple, int]] = {}


def claim_count(db: Path) -> int | None:
    """How many claims a graph holds, cheaply and repeatedly.

    The switcher asks this for every project on every page load, so the answer is memoized on the
    file's (mtime, size) — a graph that has not been written cannot have a different count, and a
    graph that HAS been written gets a new key and is re-counted."""
    try:
        st = db.stat()
    except OSError:
        return None
    key = (st.st_mtime, st.st_size)
    hit = _claim_count_cache.get(str(db))
    if hit and hit[0] == key:
        return hit[1]
    try:
        import duckdb
        con = duckdb.connect(str(db), read_only=True)
    except Exception:
        return None      # locked by a live build, or not a database yet — absent, not zero
    try:
        n = int(con.execute("select count(*) from claims").fetchone()[0])
    except Exception:
        return None
    finally:
        con.close()
    _claim_count_cache[str(db)] = (key, n)
    return n


def summaries() -> list[dict]:
    """The switcher payload — small enough to fetch on every page load."""
    out = []
    for r in list_projects():
        if presentation_source(r["id"]):
            continue
        db = Path(r["kg_db"]) if r.get("kg_db") else None
        # The stored build summary is right for a graph this console built; for an adopted corpus
        # there is no build record, so read the graph itself. Showing "0 claims" next to a large
        # corpus is worse than showing nothing — it reads as a measurement, and it is a missing field.
        n = (r.get("build") or {}).get("n_claims")
        if n is None and db is not None:
            n = claim_count(db)
        out.append({"id": r["id"], "name": r["name"], "status": r["status"],
                    "adopted": r.get("adopted", False), "has_kg": bool(db),
                    "presentation_only": r.get("presentation_only") is True,
                    "updated": r.get("updated"), "n_attachments": r.get("n_attachments", 0),
                    "n_claims": n})
    return out


# --- the corpus card (the engine's per-run framing) --------------------------

def write_corpus_card(pid: str) -> Path:
    """Render what this corpus CONTAINS into the corpus_card.md the explorer loads.

    This is the seam that makes a UI-created project *runnable*: `run_explorer.py --db <kg> ` infers
    the card from the DB's directory, so putting the card next to the graph is all the engine needs
    (swap the card, not the code).

    The card describes the collection and does not state a goal: `explorer.goal_from_card()` reads a
    `## Goal` section as the run's brief, so a card that names one makes every run against this corpus
    ask the same question by default. The question comes from the run (`--goal`, or the console's
    launcher); the card tells the engine what it has to work with."""
    rec = load(pid)
    spec = rec["spec"]
    lines = [
        f"# {rec['name']}",
        "",
        "## Field",
        spec.get("theme") or "(no theme set)",
    ]
    if spec.get("scope"):
        lines += ["", "## Scope of this corpus", spec["scope"]]
    if rec.get("description"):
        lines += ["", "## Notes", rec["description"]]
    atts = rec.get("attachments") or []
    if atts:
        lines += ["", "## Attached documents (user-supplied, in the corpus)"]
        lines += [f"- {a['filename']} ({a.get('n_chars', 0):,} chars)" for a in atts]
    if spec.get("year_max"):
        lines += ["", "## Date window",
                  f"Literature restricted to publications through {spec['year_max']}."]
    path = corpus_card_path(pid)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")
    return path
