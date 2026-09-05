"""The engine's architecture, as a machine-checked object.

The SHAPE (nodes) is hand-authored below. The FACTS on each node (action names, thresholds, fork
budgets, model ids) are extracted from source with pure `ast`, no imports: if a symbol is renamed or
deleted, `build()` raises `ArchitectureDrift` and the test that calls it fails.
"""
from __future__ import annotations

import ast
import functools
from pathlib import Path

SRC = Path(__file__).resolve().parents[1]          # src/dnhacksbio
ROOT = SRC.parents[1]                              # repo root


class ArchitectureDrift(RuntimeError):
    """A fact this module claims about the engine could not be found in the source."""


# --------------------------------------------------------------------------------------------------
# source probes — every one of these raises rather than guessing
# --------------------------------------------------------------------------------------------------

@functools.lru_cache(maxsize=None)
def _tree(rel: str) -> ast.Module:
    p = SRC / rel
    if not p.exists():
        raise ArchitectureDrift(f"{rel} no longer exists under {SRC}")
    return ast.parse(p.read_text(encoding="utf-8"), filename=str(p))


def const(rel: str, name: str):
    """A module-level literal assignment, e.g. MAX_DEPTH = 3."""
    for node in _tree(rel).body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == name:
                    try:
                        return ast.literal_eval(node.value)
                    except ValueError as exc:
                        raise ArchitectureDrift(f"{rel}:{name} is no longer a literal ({exc})") from exc
    raise ArchitectureDrift(f"{rel} has no module-level constant {name!r}")


def _find_def(rel: str, name: str) -> ast.AST:
    for node in ast.walk(_tree(rel)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == name:
            return node
    raise ArchitectureDrift(f"{rel} has no definition named {name!r}")


def dispatch_actions(rel: str = "explorer/explorer.py", fn: str = "_dispatch") -> list[str]:
    """Every action name the dispatcher can route: the `{"name": handler}` lookup table plus the
    `if name == "..."` branches for the async/special ones."""
    node = _find_def(rel, fn)
    found: list[str] = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Dict):
            for k in sub.keys:
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    found.append(k.value)
        elif isinstance(sub, ast.Compare) and isinstance(sub.ops[0], ast.Eq):
            for c in sub.comparators:
                if isinstance(c, ast.Constant) and isinstance(c.value, str):
                    found.append(c.value)
    out = sorted(set(found))
    if len(out) < 10:
        raise ArchitectureDrift(f"{rel}:{fn} yielded only {len(out)} actions ({out}) — parse assumption broke")
    return out


def default_arg(rel: str, fn: str, arg: str):
    """The literal default of a (keyword) argument, e.g. run_many(max_parallel=4)."""
    node = _find_def(rel, fn)
    a = node.args
    pairs = list(zip(a.args[len(a.args) - len(a.defaults):], a.defaults)) + \
        [(k, d) for k, d in zip(a.kwonlyargs, a.kw_defaults) if d is not None]
    for name, dflt in pairs:
        if name.arg == arg:
            try:
                return ast.literal_eval(dflt)
            except ValueError as exc:
                raise ArchitectureDrift(f"{rel}:{fn}({arg}=) default is not a literal") from exc
    raise ArchitectureDrift(f"{rel}:{fn} has no defaulted argument {arg!r}")


def counted_dir(rel_to_root: str, marker: str) -> int:
    d = ROOT / rel_to_root
    if not d.is_dir():
        raise ArchitectureDrift(f"{rel_to_root}/ is missing")
    n = sum(1 for x in d.iterdir() if x.is_dir() and (x / marker).exists())
    if n == 0:
        raise ArchitectureDrift(f"{rel_to_root}/ contains no */{marker}")
    return n


# --------------------------------------------------------------------------------------------------
# The shape is hand-authored. Facts inside it are probes.
# --------------------------------------------------------------------------------------------------

# Layout as bands: every edge is a straight horizontal hop to the next box in its band, so no router is
# needed. Three sections: knowledge graph (built offline), engine (the live search tree, rendered from
# run data, not boxes), verification (the route out). A box must be a stage or a gate; the tested
# layer and claim status are not boxes.
_KG_BAND = {"find": 1, "extract": 2, "kg": 3, "semantic": 4}
_VERIFY_BAND = {"queue": 1, "falsifier": 2, "promote": 3, "master": 4}
_POS = {**{k: (1, v) for k, v in _KG_BAND.items()},
        **{k: (2, v) for k, v in _VERIFY_BAND.items()}}
# Resources the engine READS, drawn as a strip with no arrows: not stages.
_STRIP = ("corpus_card", "papers", "skills", "explog", "sandbox")


def build() -> dict:
    """The architecture as nodes, with every label verified against source."""
    actions = dispatch_actions()
    structural = [a for a in actions if a in ("neighbors", "subgraph", "path")]

    nodes = [
        {"id": "find", "label": "Find papers", "lane": "kg",
         "source": "litmap/find.py",
         "detail": ["Europe PMC search + OpenAlex reference-snowball, deduped by MiniLM",
                    "Chao2 capture-recapture decides when the corpus is saturated"]},

        {"id": "extract", "label": "Extract claims", "lane": "kg",
         "source": "litmap/ingest.py + litmap/extract.py + litmap/schema.py",
         "detail": ["pdf/xml/txt -> text, then the bulk model -> typed directional claims",
                    "every claim carries a VERBATIM quote; Pydantic-validated, unfillable rows deferred",
                    "entities grounded to CURIEs (litmap/grounding.py); citations resolved to sources "
                    "(litmap/attribution.py); the claim spine is the identity key"]},

        {"id": "semantic", "label": "Semantic index", "lane": "kg",
         "source": "scripts/embed_kg.py · store.embed_claims",
         "detail": ["one MiniLM vector per edge, built at BUILD time and never inside the loop",
                    "a re-extraction invalidates it (the vector is keyed by an edge-text hash)"]},

        {"id": "corpus_card", "label": "Corpus card", "lane": "input",
         "source": "explorer/explorer.py · load_corpus_card",
         "detail": ["describes the CORPUS: field, scope, mounted /data tables, domain notes",
                    "the run supplies the question; a console-written card states no goal",
                    "swap the card → new investigation, engine code unchanged"]},

        {"id": "kg", "label": "Knowledge graph", "lane": "kg",
         "source": "litmap/graph.py · ClaimGraph + litmap/store.py · KGStore",
         "detail": [f"read 3 ways: semantic (hybrid) · structural ({', '.join(structural)}) · digest",
                    "claims + evidence + context + citations = the literature graph (spine-keyed, "
                    "one row per finding, evidence stacked); engine_tests = per-lineage tested layer",
                    "vectors built at BUILD time (scripts/embed_kg.py), never in the loop"]},

        {"id": "papers", "label": "Full-text papers", "lane": "input",
         "source": "explorer/fulltext.py · FullTextStore",
         "detail": ["local corpus + Europe PMC fetch (needs network)"]},

        {"id": "explog", "label": "Exploration log", "lane": "input",
         "source": "explorer/exploration.py · ExplorationLog",
         "detail": ["durable memory: a typed tree, which is the search tree",
                    f"kinds: {' | '.join(const('explorer/exploration.py', 'KINDS'))}",
                    "keyword + MiniLM indexed, so a restart searches prior thinking"]},

        {"id": "skills", "label": "Skills", "lane": "input",
         "source": "explorer/skills.py + skills/<name>/SKILL.md",
         "detail": [f"{counted_dir('skills', 'SKILL.md')} method guides: invariants plus a worked example",
                    "the agent writes its own code within the guardrails, not routing to frozen functions",
                    "experimental-rigor is injected into every state"]},

        {"id": "engine", "label": "Engine", "lane": "engine",
         "source": "explorer/explorer.py · Explorer.run / _act_fork",
         "detail": [f"{len(actions)} actions: {', '.join(actions)}",
                    "N agents run concurrently, each in its own state, which is why the engine is drawn as "
                    "a live search tree and not as stages: 'roam -> write -> execute' is a sequence inside "
                    "one agent's step, never across the engine",
                    "working memory = one resumable llm.Session; turn N sends only what is new",
                    "the model has allowed_tools=[]; it returns text and the engine dispatches it",
                    "fork = expand -> judge -> continue top-K -> prune, plus one adversarial branch",
                    f"MAX_DEPTH={const('explorer/explorer.py', 'MAX_DEPTH')} · "
                    f"tree-wide budget {const('explorer/explorer.py', 'MAX_LIVE_BRANCHES')} · "
                    f"<={const('explorer/explorer.py', 'MAX_BRANCHES_PER_FORK')}/fork · "
                    f"child steps {const('explorer/explorer.py', 'CHILD_MAX_STEPS')} · "
                    f"BEAM_K={const('explorer/explorer.py', 'BEAM_K')}",
                    "promise judging is a search heuristic, never a soundness verdict"]},

        {"id": "sandbox", "label": "Experiment sandbox", "lane": "input",
         "source": "explorer/sandbox.py · run_code / run_many",
         "detail": ["the only path from engine to code execution",
                    "ephemeral container per experiment · /data read-only · non-root · mem/cpu/pid caps",
                    "network none by default · in-container timeout hard-kill",
                    f"run_many runs {default_arg('explorer/sandbox.py', 'run_many', 'max_parallel')} "
                    f"experiments concurrently, which is how several paths are followed at once"]},

        {"id": "queue", "label": "Submissions queue", "lane": "verify",
         "source": "explorer/verifyqueue.py · VerifyQueue",
         "detail": ["decouples fast self-judged exploration from slow strict verification",
                    "a worker drains it concurrently; the explorer never blocks on it"]},

        {"id": "falsifier", "label": "Falsifier  (no answer key)", "lane": "verify",
         "source": "falsifier.py · soundness_floor_tool",
         "detail": ["soundness only: it has no oracle, and survived is not true",
                    "order: estimable → power → direction → null → robustness",
                    f"n ≥ {const('falsifier.py', 'MIN_GROUP')} · "
                    f"p_null ≤ {const('falsifier.py', 'P_PERM_CLEAR_NULL')} · "
                    "trust boundary: only a ToolResult marked 'audited-statistic' may ground a kill; "
                    "an exploratory tool's number passes through ungated",
                    "no second model in this path · a kill is an append, never a delete"]},

        {"id": "promote", "label": "Promotion gate", "lane": "human",
         "source": "litmap/promote.py + webui/",
         "detail": ["the human gate, the route out of the engine; nothing reaches master without a person",
                    "validated: copied into master with provenance; rejected: a correction back to the agent"]},

        {"id": "master", "label": "Master graph", "lane": "verify",
         "source": "litmap_master_kg.duckdb",
         "detail": ["human-validated edges only"]},
    ]

    # A VIRTUAL node has no box: the live search tree renders it from run data, so it is excluded from
    # the layout check rather than from the graph.
    _VIRTUAL = {"engine"}
    ids = {n["id"] for n in nodes} - _VIRTUAL
    placed = set(_POS) | set(_STRIP)
    if ids != placed:
        raise ArchitectureDrift(f"layout and nodes disagree on: {sorted(ids ^ placed)} — a node was added "
                                f"to one and not the other, so it would silently float or vanish")
    for n in nodes:
        if n["id"] in _VIRTUAL:
            continue                       # rendered as the live search tree, so it has no band/order
        if n["id"] in _STRIP:
            n["strip"] = True
        else:
            n["band"], n["order"] = _POS[n["id"]]

    return {"nodes": nodes}


