"""The explorer agent: a curious computational biologist that roams the graph and reads papers, follows
intuitions, writes and runs its own code in parallel sandboxes, does divergent tree search over
experiments, judges its own results, and hands the good ones to the verification pipeline while it keeps
going.

A ReAct loop over a resumable LLM session: each step the agent sees its state (frontier, last observation,
open questions, skill menu) and emits one JSON action; we execute it and feed back the observation. Memory
is offloaded to the exploration log and the full-text store, so the agent searches its memory rather than
carrying it all. Divergence lives in `run_experiments` (several experiments at once, run as parallel
sandbox jobs) and in `fork` (one generation of beam search over forked sessions, with a mandated
adversarial branch). Every experiment whose code prints a `RESULT: {json}` line carries the standardized
fields the falsifier needs, so a `submit` flows straight into verification. `complete_fn`, `sandbox_run`,
`fork_fn` and `judge_fn` are injectable so the machinery is tested with fakes.
"""
from __future__ import annotations

import ast
import asyncio
import json
import math
import os
import re
import time
import threading
from uuid import uuid4
from pathlib import Path

from dnhacksbio import llm
from dnhacksbio.explorer import embed as EMB
from dnhacksbio.explorer import lineage as LIN
from dnhacksbio.explorer import skills as SK
from dnhacksbio.explorer.runtime import Journal, process_identity, safe_id
from dnhacksbio.explorer.budget import BudgetUnavailable
from dnhacksbio.explorer.control import ControlStore, REPORT_PROMPT, validate_report, validate_decision
from dnhacksbio.explorer.exploration import ExplorationLog
from dnhacksbio.explorer.fulltext import FullTextStore
from dnhacksbio.explorer.sandbox import SandboxPool
from dnhacksbio.explorer.verifyqueue import VerifyQueue
from dnhacksbio.litmap.store import KGStore

_REPO = Path(__file__).resolve().parents[3]   # repo root (…/src/dnhacksbio/explorer/explorer.py -> repo)
_RESULT_RX = re.compile(r"RESULT:\s*(\{.*\})", re.S)

# --- fork / divergence budget -------------------------------------------------------------
# Anti-runaway lives in two knobs, both driven by a branch's DEPTH (read straight off its path-encoded
# run_id): hard caps below, plus a soft depth-scaled nudge (_depth_nudge) that pushes deep branches to
# conclude rather than spawn.
MAX_DEPTH = 6               # deepest fork level (root = depth 0); a fork at this depth is refused. A fork
                            #   copies the parent transcript, so a deep leaf opens holding its whole ancestry
                            #   and will hit SDK auto-compaction if this is raised much further.
MAX_LIVE_BRANCHES = 72      # tree-wide total fork budget the whole investigation draws down. A spine burns
                            #   ~4 per level and BEAM_K survivors per batch may each split. Concurrency is
                            #   bounded separately by SandboxPool, so this costs steps and tokens, never
                            #   machine capacity.
MAX_BRANCHES_PER_FORK = 3   # a single fork action may request at most this many branches
CHILD_MAX_STEPS = 18        # step budget a forked child gets per generation. A leaf must be able to finish
                            #   one discover -> inspect -> analyse -> submit arc inside it.
BEAM_K = 2                  # survivors a fork's judge keeps to continue (deepen); the rest are pruned
MAX_CONTINUATIONS = 6       # continuation rounds one survivor may receive. Deepening is not terminal: a
                            #   survivor is resumed while each round still produces something new.
BRANCH_TOTAL_STEPS = 96     # cumulative per-branch step cap across its leaf phase and every continuation.
                            #   Moves with MAX_CONTINUATIONS so the round count, not a silent step
                            #   ceiling, is what ends a line that is still producing.
MAX_HYPOTHESIS = 2000       # sanity bound on a stored hypothesis, not a display cap


class ForkBudget:
    """One tree-wide fork allowance the whole investigation draws down, shared by reference across every
    branch, so total forks are bounded no matter how the tree splits. asyncio is single-threaded, so the
    read-modify in take() is atomic between awaits."""

    def __init__(self, total: int = MAX_LIVE_BRANCHES):
        self.remaining = int(total)

    def take(self, k: int) -> int:
        """Consume up to k branches; return how many were actually granted (0 if the pool is exhausted)."""
        g = max(0, min(int(k), self.remaining))
        self.remaining -= g
        return g

    def refund(self, k: int = 1) -> None:
        """Return an unused grant (e.g. a branch that failed to fork) to the pool."""
        self.remaining += int(k)


def _shown(n: int, total: int, unit: str = "rows") -> str:
    """Declare a read-side cap to the agent; an unannounced cap reads as completeness and invites false
    absence claims."""
    if n >= total:
        return f"(all {total} {unit})"
    return f"(showing {n} of {total} {unit}; truncated, ask for a higher limit before concluding absence)"


def _depth_nudge(depth: int) -> str:
    return ("Propose distinct concurrent subquestions in a checkpoint report. "
            "The parent decides and orchestration executes approved forks. "
            + ("Maximum fork depth reached; propose sequential work or completion." if depth >= MAX_DEPTH else ""))


def _leaf_brief(run_id: str, angle: str, hypothesis: str) -> str:
    return (f"You are child {run_id}, with your inherited context intact. Objective: {angle}. {hypothesis}\n"
            "Do useful research and submit eligible findings at any point. You have a bounded research "
            "round, followed by a mandatory report. Useful unfinished work and falsifications are valid "
            "progress. checkpoint pauses for parent allocation; done requests completion. "
            "fork proposes subquestions for parent approval. Neither action launches research itself.")


def _adversarial_brief(run_id: str) -> str:
    return _leaf_brief(run_id, "Try to falsify the leading hypothesis with a decisive experiment", "")


def _continue_brief(run_id: str, depth: int, budget_remaining: int, rounds_left: int = 0) -> str:
    return (f"Parent authorized another bounded round for {run_id}. Preserve your context and findings. "
            "Report unfinished work candidly. Every further grant requires a fresh parent decision. "
            + _depth_nudge(depth))

_SYS = (
    "You are a curious, rigorous computational biologist exploring a knowledge graph and its full-text "
    "literature to find something new rather than to re-confirm established facts. You roam the graph, "
    "read papers, follow hunches and unusual juxtapositions, and design your own experiments, writing "
    "Python that runs against public datasets. You think divergently: for a question you devise several "
    "experiments at once, including long shots, run them in parallel, and follow whichever paths look "
    "alive, deepening the promising ones and dropping the dead ones. You avoid spending effort "
    "re-validating what is already well established. When an experiment looks real by your own "
    "judgment, you submit it for independent verification and keep exploring. You never fabricate "
    "numbers: every experiment computes a real effect, a real permutation null, an effect size and a "
    "robustness check, following the rigor guidance in the skills. "
    "Absence rule: a retrieval that reports itself truncated, or that you capped with a limit, is "
    "evidence of presence only. Finding something in a partial list is real; not finding it there proves "
    "nothing. Never call a hypothesis novel, unprecedented, untested or a gap in the literature on the "
    "strength of a capped search. Widen the limit or page through the rest first, and if you still "
    "assert absence, say which searches you completed to justify it.")

_PROTOCOL = """\
Respond with exactly one JSON object for your next action, and no prose outside it:

  {"intent": "<brief user-facing next task and purpose, 1-320 characters; not private reasoning>", "action": "<name>", "args": { ... }}

Actions:
- search_kg      {"query": "<entity or free text>"}            -> claims/edges (exact keyword hits plus
                   semantically related edges a keyword match would miss) and what is already tested. The
                   KG carries context (polarity, object function, mechanism); read it rather than name-matching.
- neighbors      {"entity": "<id or name>"}                     -> every KG edge touching that entity (its
                   1-hop neighbourhood), from the graph's actual structure
- subgraph       {"entity": "<id or name>", "hops": 1}          -> the induced neighbourhood out to `hops` (<=3)
- path           {"a": "<id/name>", "b": "<id/name>"}           -> the shortest claim-edge path between two
                   entities (None = no asserted path = a candidate untested bridge)
- recall         {"query": "<free text>"}                       -> search your own episodic memory across all
                   past runs on this corpus (ideas, experiments, observations, dead-ends logged before), so
                   you build on them instead of redoing them
- search_papers  {"query": "<free text>"}                       -> semantically relevant papers already in memory (ids + titles)
- find_datasets  {"query": "<free text>", "limit": 8}           -> search public data repositories (GEO,
                   ArrayExpress) for real datasets; returns candidates and a download URL. Use short keyword
                   queries of 2-4 terms (gene symbols plus disease or tissue, e.g. "EGFR GRB2 <disease>"),
                   not a sentence: the repositories AND every word. Download the chosen one to /cache in a
                   run_experiments step, inspect it, then analyse. Discovery only; needs network.
- fetch_papers   {"query": "<free text>", "limit": 5}           -> search Europe PMC, pull new papers' open-
                   access full text into memory, and return their ids and titles. Use when the local corpus
                   lacks what you need, then read_paper the returned ids. This stores text for reading only;
                   it does not add claims to the graph. Needs network.
- read_paper     {"paper_id": "<id>", "max_chars": 30000, "offset": 0}  -> a paper's text, local or just
                   fetched. Long papers come back truncated and say so; call again with the offset given to
                   read on. A truncated read never supports "the paper does not mention X".
- binder         {"operation": "<operation>", "experiment_id": "<owned ID>", "args": {...}} -> scoped exploratory binder records, receipts and actual scene/vision tools; get_skill binder-interface first
- spindle        {"operation": "<operation>", "experiment_id": "<owned ID>", "args": {...}} -> provisional native spindle jobs and scoped scene/vision workflow; get_skill spindle-interface first
- search_skills  {"query": "<method or question>"}              -> which methods fit; then get_skill for the how
- tissue         {"experiment_id":"<id>","operation":"<operation>","args":{...}} -> conditional spatial model; get_skill tissue-interface first
- get_skill      {"name": "<skill>"}                            -> full method guidance, rigor invariants and an example
- private_experiment {"method_id":"paired-pathway-v1|dependency-chronos-v1|biomarker_auc.v1", "spec":{...}, "input":{"cohort_id":"...","manifest_sha256":"..."}}
                   -> submit an operator-registered experiment with runner-owned provenance; load the corresponding experiment skill first.
                      Returns only a receipt. Never manufacture RESULT or submit that receipt to legacy verification.
- run_experiments{"experiments": [ {"hypothesis","subject","object","method","expected_sign":-1|0|1,"code"}, ... ]}
                   -> runs each `code` in a parallel sandbox. Your code must print one line with json.dumps:
                      print("RESULT:", json.dumps({"effect":..,"p_null":..,"null_model":"..","n_units":..,"robust":true}))
                      `p_null` is a probability in [0,1] and every number is finite; a malformed RESULT is
                      rejected and the experiment records no result. Everything else you print is handed
                      back to you, on success and on failure.
                   -> Exception: expression-experiment, dependency-experiment and drug-response-experiment
                      commands return only a receipt.
                      Record that receipt and continue; no RESULT is expected and it is not a finding
                      to submit for verification. Do not add statistics to this command's output.
                   -> `/cache` is shared with every other branch: use it only for raw downloads named by
                      their accession (GEOparse destdir, pip). `/scratch` is private to this branch: write
                      every derived file there.
                   -> Propose several divergent experiments here; this is where divergence happens.
- log            {"kind":"idea|observation|dead-end|open-question|note","title":"..","body":"..","score":0..1}
- submit         {"entry_id":<experiment entry id>}             -> send a self-judged experiment to verification
- fork           {"branches":[{"hypothesis":"..","angle":".."}, ...]} -> propose a split, pause and report.
                   The parent chooses concrete subquestions; code executes approved forks.
- reflect        {"note":".."} -> save an ordinary research synthesis.
- checkpoint     {} -> pause research and produce your mandatory report for parent allocation.
- done           {} -> request completion through the same validated reporting phase.

Rigor contract. Every experiment you run must satisfy all of these. Independent verification re-derives
soundness from your reported numbers and rejects anything that fails before a human sees it, so build them
in from the first line of code. The full recipe is in the experimental-rigor section above.
  - Exchangeable unit: permute or resample at the unit that is actually independent (cell line, donor,
    shuffled region), never the raw measurement or a pseudoreplicate such as cells from one donor. Name it
    in null_model.
  - Permutation null: get p_null by shuffling that unit and report it as Phipson-Smyth (ge+1)/(n_perm+1),
    so it is never exactly 0. p_null must be <= 0.05.
  - Direction: if the hypothesis predicts a sign (expected_sign +1 or -1), the observed effect must match it.
  - Robustness: re-check under leave-one-group-out (lineage, batch, decile, platform) and set robust=true
    only if the sign is stable. A finding that flips when one group is dropped is an artifact.
  - Enough units: n_units >= 8 per group. Underpowered results are rejected, not kept.
  - No tuning to significance: decide the analysis before seeing the result and never sweep parameters
    until p < 0.05.
  - Control: include a negative control where you can (a pair or label that should show nothing).

Your experiment code runs in a sandbox: any datasets mounted for this run are read-only at /data. Which
datasets are available for this run, and their catalogs, are described in the corpus context section
above when present; how to use a method rigorously lives in the skills (search_skills, then get_skill).
Read both before writing analysis code. If no data is mounted, use the KG, the papers and, only when
network is enabled (see the sandbox note), public data you fetch. Write self-contained code; dnhacksbio is
not installed in the sandbox. Branch off promising nodes in the frontier and abandon dead ones.

Make progress: if a search returns little, do not repeat it; switch tactics (read a paper, or design and
run experiments). Within a few steps you should be logging ideas and running experiments, not only
searching. Every roam should end in a concrete testable hypothesis.
"""


def load_corpus_card(card: str | None) -> str:
    """Resolve a corpus card to its markdown text. `card` may be a file path or the text itself; None or
    empty gives "" (no corpus context injected). The card is the only place run-specific framing lives
    (the goal, which datasets are mounted at /data and their catalogs, domain notes), so the reasoning code
    stays corpus-agnostic and the same engine runs any investigation by swapping the card."""
    if not card:
        return ""
    try:
        p = Path(str(card))
        if len(str(card)) < 1024 and p.exists() and p.is_file():
            return p.read_text(errors="replace")
    except (OSError, ValueError):
        pass
    return str(card)


def goal_from_card(card_text: str) -> str | None:
    """Pull the run's goal out of a corpus card. Supports a `## Goal` section (text until the next heading)
    or an inline `**Goal:**` line. Returns None if the card states no goal (caller falls back to a default)."""
    if not card_text:
        return None
    m = re.search(r"^#+\s*Goal\b[^\n]*\n(.+?)(?=\n#+\s|\Z)", card_text, re.S | re.I | re.M)
    if m and m.group(1).strip():
        return m.group(1).strip()
    m = re.search(r"^\*\*Goal:\*\*\s*(.+)$", card_text, re.M | re.I)
    return m.group(1).strip() if m and m.group(1).strip() else None


class Explorer:
    def __init__(self, run_id: str, goal: str, *, db_path=None, model: str = llm.OPUS,
                 complete_fn=None, sandbox_run=None, max_parallel: int = 4, freeze_year: int | None = None,
                 corpus_card: str | None = None, network: str = "none",
                 cache_dir: str | None = None, cross_run_memory: bool = True,
                 share_from: "Explorer | None" = None, fork_budget: "ForkBudget | None" = None,
                 resume_sid: str | None = None, branch_brief: str | None = None, fork_fn=None,
                 fork_enabled: bool = True, judge_fn=None, trace_dir: str | None = None,
                 project_id: str | None = None, branch_objective: str | None = None,
                 allocation_fn=None, subtree_budget=None):
        self.run_id = safe_id(run_id)
        self.goal = goal
        self.model = model
        self.freeze_year = freeze_year   # when set, the engine sees only literature <= this year
        # The per-run framing (goal, which /data tables are mounted and their catalogs, domain notes) lives
        # in a markdown card, not in code, so this engine runs any corpus by swapping the card.
        self.corpus_card = load_corpus_card(corpus_card)
        self.network = network           # sandbox network for experiments: "none" (isolated) | "bridge" (internet)
        # Host dir mounted read-write at /cache in every experiment (persists downloads); anchored to the
        # repo so it is an absolute path regardless of cwd (docker -v reads a relative path as a named volume).
        self.cache_dir = cache_dir or str(_REPO / "data" / "cache" / "explorer")
        # Per-branch scratch, derived from run_id and not inherited by children: /cache is shared across
        # the fork tree, right for accession-keyed downloads and wrong for derived artifacts.
        self.scratch_dir = str(Path(self.cache_dir) / "scratch" / run_id.replace(LIN.SEP, "_"))
        # Cross-run episodic memory: when True the auto-views (frontier, corrections, open questions,
        # feedback) span every run in this DB, and each step recalls the goal-relevant past entries, so a
        # new run remembers prior runs' work. Point runs at one persistent per-corpus DB for this to
        # accumulate. False = strict per-run isolation.
        self.cross_run_memory = cross_run_memory
        # One shared connection: graph, papers, exploration log and verification queue are one memory DB.
        # A forked child reuses its parent's stores and fork budget (share_from); every branch of an
        # investigation writes to the same durable layer, and isolation is a read-scope concern (_scope).
        if share_from is not None:
            self.kg = share_from.kg
            self.log = share_from.log
            self.papers = share_from.papers
            self.vq = share_from.vq
            self.fork_budget = share_from.fork_budget
            self.sandbox_pool = share_from.sandbox_pool   # containers are a machine resource: one pool per tree
            # Edge embeddings are the same for the whole investigation, so they are embedded once and the
            # cache is shared down every branch.
            self._edge_vec_cache = share_from._edge_vec_cache
        else:
            self.kg = KGStore(db_path)
            self.log = ExplorationLog(con=self.kg.con)
            self.papers = FullTextStore(con=self.kg.con)
            self.vq = VerifyQueue(kg=self.kg)
            # the tree-wide fork pool: created once at the root, then shared by reference down every branch
            self.fork_budget = fork_budget if fork_budget is not None else ForkBudget()
            self.sandbox_pool = SandboxPool()      # same shape, for the resource that consumes the machine
            self._edge_vec_cache = {"built": False, "vecs": {}}   # claim_id -> vector; lazily filled once
        self.max_parallel = max_parallel
        # Tests inject a fake complete_fn (string in, string out); the real path goes through llm.acomplete
        # with extended thinking enabled and full-message capture, so the model's own thinking blocks and
        # the raw SDK transcript are recorded, not only the self-reported "thought" field.
        self._inject_complete = complete_fn
        self._sandbox_run = sandbox_run            # None -> real Docker (lazy import in _act_run)
        self.steps = 0
        self._round_max_steps = 0                  # this round's step allowance, and the step count it began
        self._steps_at_round_start = 0             # at — set by run(), read by _budget_line to tell the agent
        self.transcript: list[dict] = []           # rolling short-term memory of recent (action, observation)
        # Where the per-step trace lands. A parameter, so a trial run keeps its traces beside its
        # own database.
        td = Path(trace_dir) if trace_dir else Path("data/processed")
        td.mkdir(parents=True, exist_ok=True)
        self._reasoning_path = str(td / f"reasoning_{run_id}.jsonl")   # per-step reasoning (+ real thinking)
        self._transcript_path = str(td / f"transcript_{run_id}.jsonl")  # raw SDK message stream per step
        self._trace_dir = str(td)
        self._last_capture: dict = {}
        self._session_connected = False
        self._session = None                    # persistent resumable session (opened in run(); None in tests)
        self._seen_fb: set = set()              # feedback ids already surfaced (per-turn delta dedup)
        self._seen_corr: set = set()            # correction ids already surfaced
        # divergence wiring (recursive beam search):
        self._resume_sid = resume_sid           # if set, run() resumes this sdk session (a forked child)
        self._branch_brief = branch_brief       # a forked child's turn-1 message (leaf angle, or continue brief)
        self._fork_fn = fork_fn                 # None -> real claude_agent_sdk.fork_session (lazy in _act_fork)
        self._forks_spawned = 0                 # per-branch child-index counter -> unique child run_ids
        # A freshly forked leaf runs with fork disabled (it completes and reports); a leaf judged
        # promising is promoted, at which point the orchestrator sets this True and resumes it.
        self._fork_enabled = fork_enabled
        self._inject_judge = judge_fn           # None -> real Opus promise-judge (assess-promise skill)
        self.session_id: str | None = None      # this branch's live sdk session id after run() (for resume)
        # Structured record of the last fork this branch orchestrated (set in _act_fork, consumed by step()
        # into the reasoning trace so the UI reads the beam tree as data rather than from observation text).
        self._fork_meta: dict | None = None
        self._has_forked = False       # a node splits once; the tree grows through survivors
        self.journal = share_from.journal if share_from else Journal(td)
        self.control = share_from.control if share_from else ControlStore(td)
        if share_from is None:
            existing_budget = self.control.budgets(self.run_id)
            if subtree_budget is not None or not existing_budget:
                self.control.freeze_budget(self.run_id, subtree_budget)
        elif subtree_budget is not None:
            self.control.freeze_budget(self.run_id, subtree_budget)
        self._allocation_fn = allocation_fn if allocation_fn is not None else (share_from._allocation_fn if share_from else None)
        self._report_reason = "allowance_exhausted"
        self.vq.runtime_journal = self.journal
        if share_from:
            project_id = share_from.manifest.get("project_id")
        elif project_id is None and db_path:
            db = Path(db_path).resolve()
            if db.parent.parent.name in {"projects", "corpora"}:
                project_id = db.parent.name
        self.manifest = self.journal.register(run_id, goal, objective=branch_objective or "",
                                             project=project_id, config={"model": model, "network": network})
        self.goal = self.manifest["original_question"]
        self.attempt_id = ""
        self._operation_id = None
        self._delivered: set[str] = set()
        self._pending_skills: dict[str, dict] = {}
        self._skill_snapshots: dict[str, dict] = {}
        self._skill_errors: dict[str, str] = {}
        self._pending_feedback: list[dict] = []
        self._cancel_sandbox = threading.Event()
        self._degraded = False
        self.model_timeout_s = 600
        existing = [m["run_id"] for m in self.journal.manifests() if m.get("parent_run_id") == run_id]
        self._forks_spawned = max([int(r.rsplit("~", 1)[-1]) for r in existing if r.rsplit("~", 1)[-1].isdigit()] or [0])

    def _event(self, kind: str, payload: dict | None = None, **kw):
        try:
            return self.journal.append(self.run_id, self.attempt_id, kind, payload,
                                       operation_id=self._operation_id, **kw)
        except Exception:
            self._degraded = True
            self.journal.degraded = True
            self._cancel_sandbox.set()
            print(f"[{self.run_id}] AUDIT STORAGE FAILURE: protected execution halted", flush=True)
            raise

    def _begin_attempt(self):
        self.attempt_id = uuid4().hex
        self._delivered.clear()
        self._pending_skills.clear()
        self._cancel_sandbox = threading.Event()
        self._degraded = False
        self._operation_id = None
        self._event("attempt.started", {**self.manifest, "pid": os.getpid(),
                                       "process_identity": process_identity(),
                                       "resumed": bool(self._resume_sid), "protocol_version": 1})
        # Pin registry contents, including complete references, for this attempt.
        self._skill_snapshots, self._skill_errors = {}, {}
        for s in SK.list_skills():
            try:
                self._skill_snapshots[s["name"]] = SK.snapshot(s["name"])
            except (OSError, ValueError) as exc:
                self._skill_errors[s["name"]] = str(exc)
        if "agent-runtime" not in self._skill_snapshots:
            raise ValueError("Mandatory runtime skill unavailable: " + self._skill_errors.get("agent-runtime", "missing"))
        self._pending_skills["agent-runtime"] = self._skill_snapshots["agent-runtime"]

    async def _heartbeat(self):
        while True:
            self._event("heartbeat")
            await asyncio.sleep(5)

    # --- lineage read-scope -----------------------------------------------------------------------
    def _scope(self):
        """The durable-memory read scope for this branch (see exploration._run_filter / lineage.scope_sql):
          - cross_run_memory=True (default): my lineage (self + ancestors) + genuinely prior separate runs,
            never my concurrent siblings/cousins. For an un-forked root run this is effectively global.
          - cross_run_memory=False: strict single-run isolation (exact run_id match).
        Literature claims are not scoped by this; only the log and engine_tests are lineage-scoped."""
        return LIN.scope_sql(self.run_id) if self.cross_run_memory else self.run_id

    # --- state the agent sees each step -----------------------------------------------------------
    def _state(self) -> str:
        scope = self._scope()
        frontier = self.log.frontier(scope, limit=8)
        oq = self.log.open_questions(scope)[:5]
        fb = self.log.feedback_entries(scope, limit=6)
        corr = self.log.corrections(scope)
        self._pending_feedback = [{"entry_id": e["entry_id"], "version": self.journal.blob(json.dumps(e, default=str))}
                                  for e in [*fb, *corr]]
        # Passive recall: the goal-relevant entries from this lineage and prior runs (not already on the
        # frontier), so the agent remembers what it has tried before.
        recalled = []
        if self.cross_run_memory:
            fids = {e["entry_id"] for e in frontier}
            recalled = [e for e in self.log.search_semantic(self.goal, limit=8, scope=scope)
                        if e["entry_id"] not in fids and e["kind"] in ("experiment", "observation", "idea",
                        "dead-end")][:5]
        menu = SK.list_skills()
        fl = "\n".join(f"  #{e['entry_id']} [{e['kind']}/{e['status']} score={e.get('score')}] {e['title']}"
                       for e in frontier) or "  (empty — start by roaming the graph / reading a paper)"
        rcl = "\n".join(f"  #{e['entry_id']} [{e['kind']}/{e['status']}] {e['title']} :: "
                        f"{(e.get('result') or e.get('body') or '')[:160]}" for e in recalled)
        fbl = "\n".join(f"  #{e['entry_id']} [{e['status']}] {e['title']} :: "
                        f"{((e.get('body') or '').strip().splitlines() or [''])[-1][:120]}" for e in fb)
        corl = "\n".join(f"  ⚠ {c['title']}: {(c.get('body') or '')[:600]}" for c in corr)
        sk = ", ".join(s["name"] for s in menu) or "(none yet)"
        parts = [f"GOAL: {self.goal}\nstep {self.steps}"]
        if self.corpus_card:
            parts.append("CORPUS CONTEXT (the datasets and domain framing for this run; dataset availability "
                         "and catalogs live here, the method guidance lives in the skills. Read this before "
                         "writing analysis code):\n" + self.corpus_card)
        # A compact overview of the shared literature graph (hubs, contested edges, coverage) so the agent
        # knows its shape without spending actions to discover it.
        try:
            dg = self.kg.digest()
            if dg.get("n_claims"):
                hubs = ", ".join(f"{e}({d})" for e, d in dg["top_hubs"][:10])
                disp = "; ".join(f"{s} {p} {o}" + (f"/{f}" if f else "") for s, p, o, f in dg["disputed"][:6])
                parts.append(
                    "KNOWLEDGE-GRAPH MAP (the shared literature graph you roam; read it with "
                    "search_kg / neighbors / subgraph / path):\n"
                    f"  {dg['n_claims']} claims · {dg['n_entities']} entities · {dg['n_disputed']} disputed · "
                    f"{dg['engine_tests']} engine-tested ({dg['engine_candidates']} candidates)\n"
                    f"  hubs (most-connected entities): {hubs}"
                    + (f"\n  contested edges: {disp}" if disp else "")
                    + "\n  two hubs with no asserted `path` between them are candidate untested bridges.")
        except Exception:
            pass
        if self.transcript:
            recent = "\n".join(
                f"  step {t['step']}: {t['action']}"
                + (f" (thought: {t['thought']})" if t.get('thought') else "")
                + f"\n     → observed: {t['obs']}" for t in self.transcript[-5:])
            parts.append("RECENT STEPS (what you just did and saw; build on this, do not repeat the same "
                         "action, and move toward logging an idea and running an experiment):\n" + recent)
        if corl:
            parts.append("CORRECTIONS FROM HUMAN REVIEW (these reshape your model; follow them):\n" + corl)
        if fbl:
            parts.append("VERIFICATION FEEDBACK (act on these: needs-retry = fix the experiment and rerun; "
                         "reframe = the opposite may be true, test that; dead = abandon; validated = build "
                         "on it):\n" + fbl)
        parts.append("EXPLORATION FRONTIER (promising open nodes; branch off these, or start fresh):\n" + fl)
        if rcl:
            parts.append("RECALLED MEMORY (goal-relevant things you or prior runs already explored on this "
                         "corpus; build on these rather than repeating them, and use the `recall` action "
                         "to search deeper):\n" + rcl)
        parts.append(f"OPEN QUESTIONS: {[q['title'] for q in oq]}")
        parts.append(f"SKILLS AVAILABLE: {sk}")
        if self.network and self.network != "none":
            parts.append(
                "SANDBOX: network is enabled for your experiment code. When no dataset is mounted at /data, "
                "find and download real public data yourself rather than only simulating. Discover datasets "
                "through repository search APIs (NCBI GEO/SRA E-utilities, EBI ArrayExpress/BioStudies, "
                "DepMap, PRIDE, Ensembl, UCSC) or the find_datasets action, download the file, inspect its "
                "structure first (list archive members, head the table, print an AnnData's .obs/.var, check "
                "dtypes and shape), then parse it adaptively. For GEO expression data GEOparse is "
                "pre-installed: load with `GEOparse.get_GEO(geo='GSExxxx', destdir='/cache')`, which "
                "resolves the right series-matrix file, handles multi-platform series and gives probe-to-"
                "symbol annotation via .gpls. anndata, h5py, pandas and pyarrow are also pre-installed. For "
                "other parsers install at runtime with `pip install --target=/cache/pkgs <pkg>` and then "
                "`sys.path.insert(0, '/cache/pkgs')`. Prefer local /data when it is mounted; when it is not, finding the right real "
                "dataset is part of the job, and simulation is a fallback or plausibility check, not a "
                "substitute. /work is wiped after each experiment; /cache persists across all your "
                "experiments, so download datasets and install packages there and fetch once. Each run has a "
                "generous but finite wall-clock and memory budget. Fail gracefully on network errors.")
        else:
            parts.append("SANDBOX: network access is disabled for your experiment code; use only the "
                         "datasets mounted at /data plus the KG and papers.")
        # Experimental rigor is a universal contract, not a menu skill, so it is injected into every state.
        rigor = SK.get_skill("experimental-rigor")
        if rigor:
            parts.append("EXPERIMENTAL RIGOR (mandatory for every experiment; the verifier enforces it and "
                         "rejects what fails). Follow it whenever you write run_experiments code:\n" + rigor)
        d = LIN.depth(self.run_id)
        parts.append(f"FORK POSITION: you are at fork-depth {d} (tree-wide branch budget remaining: "
                     f"{self.control.remaining(self.run_id)}). {_depth_nudge(d)}")
        parts.append(_PROTOCOL)
        return "\n\n".join(parts)

    async def _complete_capturing(self, prompt: str) -> str:
        """Get the model's next-action text for this turn, capturing its thinking blocks and raw SDK
        messages into self._last_capture. The path is the run's persistent resumable Session; a
        test-injected complete_fn bypasses it, and a direct step() with no open session falls back to a
        one-shot acomplete."""
        if self._degraded or getattr(self.journal, "degraded", False):
            raise RuntimeError("Audit storage unavailable")
        # Explicitly re-supply previously required guidance on each request. SDK context
        # compaction may have summarized old messages; a delivery ledger alone cannot
        # establish that those messages are still in the current context.
        for name in self._delivered:
            self._pending_skills.setdefault(name, self._skill_snapshots[name])
        if sum(len(s["content"].encode()) for s in self._pending_skills.values()) > 200_000:
            raise ValueError("Required instruction set exceeds context delivery capacity; execution stopped")
        for name, skill in self._pending_skills.items():
            prompt = skill["content"] + "\n\n" + prompt
            ref = self.journal.blob(skill["content"])
            self._event("instructions.delivered", {"name": name, "sha256": skill["sha256"],
                        "files": [{k: f[k] for k in ("path", "sha256")} for f in skill["files"]],
                        "content": ref, "delivery": "model_request_context"})
            self._delivered.add(name)
        self._pending_skills.clear()
        if self._pending_feedback:
            self._event("feedback.delivered", {"items": self._pending_feedback})
            self._pending_feedback = []
        self._event("model.started", {"phase": "model", "label": "Choosing the next research action"})
        if self._inject_complete is not None:
            self._last_capture = {}
            text = await asyncio.wait_for(self._inject_complete(prompt), timeout=self.model_timeout_s)
            self._event("model.ended")
            return text
        cap: dict = {}
        if self._session is not None:
            if not self._session_connected:
                await self._session.__aenter__()
                self._session_connected = True
            text = await asyncio.wait_for(self._session.ask(prompt, capture=cap), timeout=self.model_timeout_s)
        else:
            text = await asyncio.wait_for(llm.acomplete(prompt, model=self.model, system=_SYS, effort="high",
                                       max_turns=1, tools_disabled=True, thinking=True, capture=cap), timeout=self.model_timeout_s)
        self._last_capture = cap
        if self.control.get(self.run_id):
            self.control.cost(self.run_id, "research", 0., _capture_usage(cap))
        self._event("model.ended")
        return text

    def _snapshot_seen(self) -> None:
        """After the opening message (which already shows the current feedback and corrections), mark them
        seen so the per-turn deltas only surface ones that arrive later."""
        scope = self._scope()
        self._seen_fb = {_feedback_version(e) for e in self.log.feedback_entries(scope, limit=6)}
        self._seen_corr = {c["entry_id"] for c in self.log.corrections(scope, limit=5)}

    def _tree_evidence_block(self, limit: int = 30) -> str:
        """The tree's adjudicated results, verbatim, for the node about to synthesize. Branch digests are
        prose an agent wrote about its own line, so deep findings are routed here directly and the node is
        asked to reconcile against them."""
        try:
            rows = self.vq.adjudicated(self.run_id, limit=limit)
        except Exception as e:                       # never let bookkeeping break a fork's return path
            return f"\n(tree evidence unavailable: {type(e).__name__})"
        if not rows:
            return ""
        lines = [f"  [{r['run_id']}] {(r['hypothesis'] or '')[:260]}" for r in rows]
        return ("\n\nVERIFIED CANDIDATES ACROSS THIS INVESTIGATION TREE (adjudicated results, most recent "
                f"first, including branches below you whose digests you never saw; {len(rows)} shown):\n"
                + "\n".join(lines)
                + "\nReconcile your synthesis against these. They outrank the prose digests above: each was "
                "adjudicated by the falsifier, whereas a digest is one branch's account of itself. If your "
                "bottom line contradicts any of them, say so and say why.")

    def _budget_line(self) -> str:
        state = self.control.get(self.run_id)
        left = max(0, state["allowance"] - state["used"]) if state else self._round_max_steps
        limits = self.control.budgets(self.run_id)
        if limits:
            left = min(left, *(b["action_holds"].get(self.run_id, 0) for b in limits))
        shared = " ".join(f"Subtree {b['run_id']}: {b['contract']['actions'] - b['actions']} total actions and "
                          f"{max(0., b['contract']['seconds'] - b['spent']):.1f} accounted seconds remain, shared with descendants."
                          for b in limits)
        return (shared + f" RESEARCH ALLOWANCE: {left} actions remain before mandatory reporting. "
                "checkpoint reports early; done requests completion; neither means automatic pruning. "
                + ("Wrap up current work and prepare to report unfinished progress." if left <= 3 else ""))

    def _turn_message(self, obs: str) -> str:
        """The per-turn message on the resumable session: only what is new since the last turn (the result
        of the last action, any verification or human feedback that arrived meanwhile, and a compact current
        frontier). The session already holds the goal, corpus card, protocol, rigor, skills menu and
        history, so they are not resent."""
        scope = self._scope()
        parts = [f"OBSERVATION (result of your last action):\n{obs}"]
        if bl := self._budget_line():
            parts.append(bl)
        new_fb = [e for e in self.log.feedback_entries(scope, limit=10) if _feedback_version(e) not in self._seen_fb]
        if new_fb:
            self._seen_fb.update(_feedback_version(e) for e in new_fb)
            parts.append("NEW VERIFICATION FEEDBACK (act on these: needs-retry = fix the experiment and "
                         "rerun; reframe = the opposite may be true, test that; dead = abandon; validated = "
                         "build on it):\n"
                         + "\n".join(f"  #{e['entry_id']} [{e['status']}] {e['title']} :: "
                                     f"{((e.get('body') or '').strip().splitlines() or [''])[-1][:140]}"
                                     for e in new_fb))
        new_corr = [c for c in self.log.corrections(scope, limit=10) if c["entry_id"] not in self._seen_corr]
        self._pending_feedback = [{"entry_id": e["entry_id"], "version": self.journal.blob(json.dumps(e, default=str))}
                                  for e in [*new_fb, *new_corr]]
        if new_corr:
            self._seen_corr.update(c["entry_id"] for c in new_corr)
            parts.append("NEW CORRECTIONS FROM HUMAN REVIEW (these reshape your model; follow them):\n"
                         + "\n".join(f"  ⚠ {c['title']}: {(c.get('body') or '')[:400]}" for c in new_corr))
        fr = self.log.frontier(scope, limit=6)
        if fr:
            parts.append("CURRENT FRONTIER (open or promising nodes; branch off these, or start fresh):\n"
                         + "\n".join(f"  #{e['entry_id']} [{e['kind']}/{e['status']} score={e.get('score')}] "
                                     f"{e['title']}" for e in fr))
        oq = self.log.open_questions(scope)[:5]
        if oq:
            parts.append(f"OPEN QUESTIONS: {[q['title'] for q in oq]}")
        parts.append("Respond with your next action as one JSON object, per the protocol.")
        return "\n\n".join(parts)

    @staticmethod
    def _as_action(raw: str) -> dict | None:
        try:
            obj = llm.parse_json(raw)
        except Exception:
            return None
        if (not isinstance(obj, dict) or not isinstance(obj.get("action"), str)
                or not isinstance(obj.get("args", {}), dict)
                or not isinstance(obj.get("intent"), str) or not 1 <= len(obj["intent"].strip()) <= 320):
            return None
        obj.setdefault("args", {})
        return obj

    async def _next_action(self, message: str) -> dict:
        """One action for this turn. An unparseable reply retries the turn with the failure named rather
        than silently costing a scarce step."""
        raw = await self._complete_capturing(message)
        obj = self._as_action(raw)
        if obj is not None:
            return obj
        self._event("protocol.repair", {"reason": "Missing or invalid action, args, or concise intent"})
        retry = ("Your last reply was not a valid JSON action object with a concise intent, so nothing ran and no step was "
                 "consumed. Reply with one JSON object and nothing else, no prose and no code fence "
                 'around anything but the object: {"intent": "brief task and purpose, 1-320 characters", "action": "<name>", "args": {...}}. '
                 f"For reference, your last reply began: {(raw or '')[:300]!r}")
        obj = self._as_action(await self._complete_capturing(retry))
        if obj is not None:
            return obj
        raise ValueError("Action protocol error after one repair; nothing dispatched")

    # --- action handlers (each returns a short observation string) --------------------------------
    @staticmethod
    def _fmt_edge(e: dict) -> str:
        """One claim edge as the model reads it: labels first, resolved ids in brackets."""
        s_lab, o_lab = e.get("subject_label") or e["subject_id"], e.get("object_label") or e["object_id"]
        s_id = f" [{e['subject_id']}]" if e["subject_id"] != s_lab else ""
        o_id = f" [{e['object_id']}]" if e["object_id"] != o_lab else ""
        return (f"{s_lab}{s_id} -{e['predicate']}({e['polarity']})-> "
                f"{o_lab}{o_id}{('/' + e['object_function']) if e.get('object_function') else ''} "
                f"[{e.get('status')}, {e.get('n_sources')}src]")

    def _ensure_edge_vecs(self, edges: list[dict]) -> dict:
        """{claim_id: vector} for the KG edges, read once per investigation from the index the build
        persisted (`scripts/embed_kg.py`) and shared across the fork tree. Embedding belongs at build time;
        a missing index is embedded once and persisted here, with a notice, because it stalls the loop."""
        c = self._edge_vec_cache
        if not c["built"]:
            c["built"] = True
            vecs = self.kg.claim_vectors(edges) if edges else {}
            n_missing = len(edges) - len(vecs)
            if n_missing:
                print(f"[explorer] {n_missing}/{len(edges)} KG edges have no current embedding — embedding "
                      f"now (run `scripts/embed_kg.py --db ...` at build time to avoid this stall)",
                      flush=True)
                vecs = self.kg.claim_vectors(edges, embed_missing=True)
            c["vecs"].update(vecs)
        return c["vecs"]

    def _kg_semantic(self, query: str, edges: list[dict], limit: int) -> list[dict]:
        """Rank KG edges by meaning (cosine to the query) rather than substring, so 'chromatin opening' can
        surface an 'increases DNA binding' edge with no shared token. Empty if no model is available."""
        qv = EMB.embed_one(query)
        if not qv:
            return []
        vecs = self._ensure_edge_vecs(edges)
        if not vecs:
            return []
        rows = [(e, vecs.get(e["claim_id"])) for e in edges]
        ranked = EMB.rank(qv, rows, vec_key=lambda r: r[1], top_k=limit)
        return [r[0] for _, r in ranked]

    def _act_search_kg(self, args) -> str:
        q = str(args.get("query", "")).strip()
        toks = [t for t in re.findall(r"[A-Za-z0-9]+", q.upper()) if len(t) > 1]
        all_edges = self.kg.edges()
        if self.freeze_year:    # freeze: only claims first-mentioned on/before the freeze year
            all_edges = [e for e in all_edges
                         if e.get("first_year") and 0 < e["first_year"] <= self.freeze_year]

        def _match(e):
            hay = " ".join(str(e.get(k, "")) for k in
                           ("subject_id", "object_id", "subject_label", "object_label",
                            "object_function", "predicate")).upper()
            return any(t in hay for t in toks)

        # Hybrid retrieval: exact keyword hits first, then semantically related edges the keyword match misses.
        keyword = [e for e in all_edges if _match(e)] if toks else []
        semantic = self._kg_semantic(q, all_edges, limit=12) if q else []
        chosen, seen, note = [], set(), ""
        for e in keyword + semantic:
            if e["claim_id"] not in seen:
                seen.add(e["claim_id"]); chosen.append(e)
        if not chosen:          # nothing matched -> hand back leads: contested + best-attested edges
            note = " (no direct match; showing contested/high-evidence leads instead)"
            chosen = sorted(all_edges, key=lambda e: ((e.get("status") == "disputed"), e.get("n_sources") or 0),
                            reverse=True)
        n_kw = len(keyword)
        n_pool = len(chosen)
        edges = chosen[:15]
        # engine_tests (the tested layer) is scoped to this lineage, so each branch reads its own working
        # graph on the shared literature substrate (the KG edges above stay global).
        tested_all = [t for t in self.kg.engine_tests(scope=self._scope())
                      if (not toks) or any(x in (t.get("subject", "") + t.get("object", "")).upper() for x in toks)]
        tested = tested_all[:12]
        lines = [self._fmt_edge(e) for e in edges]
        tl = [f"TESTED {t['subject']}~{t['object']} ({t['method']}) -> {t['status']}"
              f"{'/' + (t.get('novelty_verdict') or '') if t.get('novelty_verdict') else ''}" for t in tested]
        hint = (f" (top {n_kw} exact + semantically-related)" if n_kw and len(edges) > n_kw
                else ("" if n_kw else " (semantic)")) if not note else ""
        # The keyword arm is a filter, so its total is the one that could support a false "nothing matched".
        kw_note = ("" if not toks else
                   f"\n[keyword matches: {n_kw} total"
                   + (f", {min(n_kw, 15)} shown, truncated" if n_kw > 15 else "")
                   + ". A capped search is not evidence of absence.]")
        return (f"KG edges{note}{hint} {_shown(len(edges), n_pool, 'edges')}:\n"
                + ("\n".join(lines) or "(none)") + kw_note
                + f"\nAlready tested {_shown(len(tested), len(tested_all), 'tests')}:\n"
                + ("\n".join(tl) or "(none — open frontier)")
                + "\n(structural reads available: neighbors / subgraph / path)")

    def _act_neighbors(self, args) -> str:
        ent = str(args.get("entity", "")).strip()
        if not ent:
            return "(neighbors needs an 'entity')"
        lim = int(args.get("limit", 40))
        all_edges = self.kg.neighbors(ent)                  # whole neighbourhood; this action owns the budget
        if not all_edges:
            return f"(no KG edges touch {ent!r} — not in the literature graph, or try a different name)"
        edges = all_edges[:lim]
        return (f"1-hop neighbourhood of {ent} {_shown(len(edges), len(all_edges), 'edges')}:\n"
                + "\n".join(self._fmt_edge(e) for e in edges))

    def _act_subgraph(self, args) -> str:
        ent = str(args.get("entity", "")).strip()
        if not ent:
            return "(subgraph needs an 'entity')"
        hops = min(max(int(args.get("hops", 1) or 1), 1), 3)
        lim = int(args.get("limit", 60))
        all_edges = self.kg.subgraph_around(ent, hops=hops)  # whole induced neighbourhood
        if not all_edges:
            return f"(no subgraph around {ent!r} — not in the literature graph)"
        edges = all_edges[:lim]
        return (f"{hops}-hop subgraph around {ent} {_shown(len(edges), len(all_edges), 'edges')}:\n"
                + "\n".join(self._fmt_edge(e) for e in edges))

    def _act_path(self, args) -> str:
        a, b = str(args.get("a", "")).strip(), str(args.get("b", "")).strip()
        if not a or not b:
            return "(path needs 'a' and 'b')"
        path = self.kg.path_between(a, b)
        if path is None:
            return f"(no path between {a!r} and {b!r} within the KG — an untested bridge? maybe a lead)"
        if not path:
            return f"({a} and {b} resolve to the same node)"
        return f"shortest KG path {a} … {b} ({len(path)} hops):\n" + "\n".join(self._fmt_edge(e) for e in path)

    def _act_search_papers(self, args) -> str:
        lim = int(args.get("limit", 8))
        hits = self.papers.search_semantic(str(args.get("query", "")), limit=lim, max_year=self.freeze_year)
        if not hits:
            return "(no papers)"
        # A similarity RANKING, not a filter: everything is scored, so "N of M" would misread as truncation.
        return (f"top {len(hits)} papers by similarity (ask for a higher limit to see more):\n"
                + "\n".join(f"{h['paper_id']} ({h.get('year')}) {h.get('title', '')}" for h in hits))

    def _act_read_paper(self, args) -> str:
        budget = int(args.get("max_chars", 30000))
        offset = max(0, int(args.get("offset", 0)))
        doc = self.papers.read(str(args.get("paper_id", "")), max_year=self.freeze_year)   # whole text
        if not doc:
            return "(paper not found)"
        full = doc["text"] or ""
        body = full[offset:offset + budget]
        head = f"# {doc['title']} ({doc.get('year')})\n"
        if len(full) > offset + len(body):
            head += (f"[showing chars {offset}-{offset + len(body)} of {len(full)}; this paper is truncated. "
                     f"Call read_paper again with offset={offset + len(body)} for the rest. Do not conclude "
                     f"the paper omits something you have not read.]\n")
        elif offset:
            head += f"[showing chars {offset}-{offset + len(body)} of {len(full)}; end of paper.]\n"
        return head + body

    async def _act_fetch_papers(self, args) -> str:
        """Find new papers on the web, fetch their open-access full text, and store the readable text in
        the same FullTextStore that search_papers and read_paper use. This does not run the claim-extraction
        pipeline. Reuses litmap.find (Europe PMC search plus title-verified full-text fetch)."""
        if not self.network or self.network == "none":
            return "(fetch_papers needs network — this run has it disabled; use the local corpus instead)"
        q = str(args.get("query", "")).strip()
        if not q:
            return "(fetch_papers needs a 'query')"
        limit = max(1, min(int(args.get("limit", 5)), 12))

        def _work() -> list[dict]:
            from dnhacksbio.litmap import find
            cands = list(find.dedup_candidates(find.europepmc_search(q, max_results=max(limit * 3, 15))).values())
            # prefer likely-OA (full text is fetchable); Europe PMC returns relevance-ranked within that
            cands.sort(key=lambda c: (not c.is_oa,))
            out = []
            for c in cands[:limit]:
                r = find.fetch_fulltext(c)
                pid = self.papers.add_paper(doi=c.doi, pmid=c.pmid, pmcid=c.pmcid, title=c.title,
                                            year=c.year, text=r["text"], url=r.get("url", ""),
                                            license=r.get("license", ""), is_full_text=r.get("is_full_text", False))
                out.append({"pid": pid, "title": c.title, "year": c.year,
                            "full": r.get("is_full_text", False), "n": len(r.get("text", ""))})
            return out

        import asyncio as _aio
        try:
            added = await _aio.to_thread(_work)     # blocking HTTP off the event loop (verify worker keeps draining)
        except Exception as e:
            return f"(fetch failed: {type(e).__name__}: {e})"
        if not added:
            return "(no papers found for that query)"
        return "fetched into memory (read them with read_paper):\n" + "\n".join(
            f"  {a['pid']} ({a['year']}) [{'FULL' if a['full'] else 'abstract-only'}, {a['n']}c] {a['title'][:90]}"
            for a in added)

    async def _act_find_datasets(self, args) -> str:
        """Discover public datasets (GEO, ArrayExpress) matching a query: candidates with metadata and a
        download URL, without downloading. The agent downloads, inspects and parses the chosen one in a
        run_experiments step, into /cache so it persists."""
        if not self.network or self.network == "none":
            return "(find_datasets needs network — this run has it disabled)"
        q = str(args.get("query", "")).strip()
        if not q:
            return "(find_datasets needs a 'query')"
        limit = max(1, min(int(args.get("limit", 8)), 20))
        import asyncio as _aio
        try:
            from dnhacksbio.explorer import datasets as DS
            hits = await _aio.to_thread(DS.search_datasets, q, limit)
        except Exception as e:
            return f"(dataset search failed: {type(e).__name__}: {e})"
        if not hits:
            return "(no datasets found — try different terms or a different repository)"
        return ("candidate datasets — in a run_experiments step, load the chosen one with "
                "`GEOparse.get_GEO(geo='<accession>', destdir='/cache')` (pre-installed; robustly resolves "
                "the right file, handles multi-platform series, and gives probe annotation), then analyse:\n"
                + "\n".join(
                    f"  [{h['repo']}] {h['accession']} ({h['organism']}, {h['n_samples']} samples, {h['type']}) "
                    f"{h['title'][:80]}\n       {h['summary'][:120]}\n       download: {h['url']}" for h in hits))

    def _act_recall(self, args) -> str:
        """Search the explorer's own episodic memory across all runs on this corpus (ideas, experiments,
        observations and dead-ends logged before), the active counterpart to the recalled-memory block in
        the state."""
        q = str(args.get("query", "")).strip()
        if not q:
            return "(recall needs a 'query')"
        hits = self.log.search_semantic(q, limit=int(args.get("limit", 8)), scope=self._scope())
        if not hits:
            return "(no matching memory — nothing like this has been explored yet)"
        return "recalled from episodic memory (this lineage and prior runs, siblings excluded):\n" + "\n".join(
            f"  #{h['entry_id']} [{h['kind']}/{h['status']}] {h['title']} :: "
            f"{(h.get('result') or h.get('body') or '')[:180]}" for h in hits)

    def _act_search_skills(self, args) -> str:
        hits = SK.search_skills(str(args.get("query", "")))
        return "\n".join(f"{s['name']}: {s.get('one_line', '')}" for s in hits) or "(no matching skill)"

    def _act_get_skill(self, args) -> str:
        name = str(args.get("name", ""))
        skill = self._skill_snapshots.get(name)
        if not skill:
            return "(skill unavailable: " + self._skill_errors.get(name, "no such registered skill") + ")"
        self._pending_skills[name] = skill
        return f"Complete {name} guidance will accompany the next model request (version {skill['sha256']})."

    async def _act_tissue(self, args) -> str:
        if "tissue-interface" not in self._delivered:
            return "(tissue blocked: get_skill tissue-interface and receive its guidance first)"
        from dnhacksbio.tissue.tools import operate
        scope = {"project_id": self.manifest["project_id"], "run_id": self.run_id,
                 "experiment_id": str(args.get("experiment_id", ""))}
        try:
            result = await operate(self.journal, scope, str(args.get("operation", "")), args.get("args", {}))
        except (ValueError, FileNotFoundError, KeyError, IndexError, TimeoutError, RuntimeError) as exc:
            result = {"status": "failed", "operation": args.get("operation"), "error": str(exc)[:2000]}
        return json.dumps(result, allow_nan=False)

    async def _act_run_experiments(self, args) -> str:
        exps = [e for e in (args.get("experiments") or []) if isinstance(e, dict) and e.get("code")]
        if not exps:
            return "(no experiments provided)"
        if len(exps) > 8:
            return "(at most 8 experiments per action)"
        for e in exps:
            method = e.get("method_id")
            if method == "binder-interface":
                self._event("policy.rejected", {"reason": "Binder guide is not an audited method", "method_id": method})
                return "(binder-interface is an exploratory tool guide; use method_id exploratory)"
            required = "agent-runtime" if method == "exploratory" else method
            if not required or required not in self._skill_snapshots or required not in self._delivered:
                self._event("policy.rejected", {"reason": "Method guidance not delivered", "method_id": method})
                return "(experiment blocked: declare a registered method_id and get_skill first; custom methods use exploratory)"
        identities = [uuid4().hex for _ in exps]
        for e, expid in zip(exps, identities):
            self._event("experiment.queued", {"status": "queued", "title": e.get("hypothesis", ""),
                        "method": e.get("method", ""), "method_id": e["method_id"],
                        "code": self.journal.blob(e["code"])}, experiment_id=expid)
        run = self._sandbox_run
        if run is None:
            from dnhacksbio.explorer.sandbox import run_many
            def progress(index, kind, payload):
                self._event(kind, payload, experiment_id=identities[index])
            def scoped_codes(codes):
                return ["import os as _runtime_os\n_runtime_os.environ['DNHACKS_EXPERIMENT_SCOPE'] = "
                        + repr(json.dumps({"project_id": self.manifest.get("project_id"),
                                           "run_id": self.run_id, "experiment_id": expid})) + "\nexec(compile(" + repr(code) + ", '<experiment>', 'exec'))"
                        for code, expid in zip(codes, identities)]
            run = lambda codes: run_many(scoped_codes(codes), max_parallel=self.max_parallel, timeout=600,
                                         network=self.network, cache_dir=self.cache_dir,
                                         scratch_dir=self.scratch_dir, pool=self.sandbox_pool,
                                         progress=progress, journal=self.journal,
                                         cancel=self._cancel_sandbox)
        # Off the event loop: this is the longest blocking call in the engine (up to the sandbox timeout),
        # and every concurrent branch and the verify worker must keep running meanwhile.
        worker = asyncio.create_task(asyncio.to_thread(run, [e["code"] for e in exps]))
        cancelled = False
        try:
            results = await asyncio.shield(worker)
        except asyncio.CancelledError:
            self._cancel_sandbox.set()
            cancelled = True
            results = await worker  # collect final diagnostics before ending the attempt
        except Exception as exc:
            for expid in identities:
                self._event("experiment.finished", {"status": "failed", "error": str(exc)}, experiment_id=expid)
            raise
        obs = []
        if len(results) != len(exps):
            raise ValueError("Sandbox returned an incomplete experiment batch")
        for e, r, expid in zip(exps, results, identities):
            parsed = _parse_result(getattr(r, "stdout", "") or "") if getattr(r, "ok", False) else None
            # Store the hypothesis whole: the title is the claim, read back by frontier(), the promise judge
            # and the promotion records. Truncate at the point of display, if a consumer needs it.
            eid = self.log.log("experiment", e.get("hypothesis", "")[:MAX_HYPOTHESIS], "",
                               run_id=self.run_id,
                               status="promising" if parsed else "open",
                               provenance={"subject": e.get("subject"), "object": e.get("object"),
                                           "method": e.get("method"), "method_id": e["method_id"],
                                           "experiment_id": expid, "expected_sign": e.get("expected_sign")},
                               code=e["code"], result=json.dumps(parsed) if parsed else
                               (getattr(r, "stdout", "") or getattr(r, "stderr", ""))[:800])
            ok = getattr(r, "ok", False)
            self._event("experiment.finished", {"entry_id": eid, "status": "completed" if ok else "failed",
                        "result": parsed, "exit_code": getattr(r, "exit_code", None),
                        "timed_out": getattr(r, "timed_out", False),
                        "stdout": self.journal.blob(getattr(r, "stdout", "") or ""),
                        "stderr": self.journal.blob(getattr(r, "stderr", "") or ""),
                        "exploratory": e["method_id"] == "exploratory"}, experiment_id=expid)
            for artifact in getattr(r, "artifacts", None) or []:
                if artifact.get("kind") == "binder_bundle" and artifact.get("binder_scope") != {
                        "project_id": self.manifest.get("project_id"), "run_id": self.run_id,
                        "experiment_id": expid}:
                    artifact = {"artifact_id": artifact["artifact_id"], "status": "rejected",
                                "failure_reason": "Binder bundle belongs to a different experiment scope"}
                self._event("artifact", {**artifact, "schema_version": 1, "run_id": self.run_id,
                            "investigation_id": LIN.root(self.run_id), "attempt_id": self.attempt_id,
                            "experiment_id": expid}, experiment_id=expid, producer="collector")
            if parsed:
                # Front-load the key stats so they survive observation truncation.
                summary = (f"effect={parsed.get('effect')} "
                           f"p_null={parsed.get('p_null')} robust={parsed.get('robust')}")
                # Hand back what the code printed too, so diagnostics have a channel other than the
                # statistics fields.
                summary += _diagnostics(parsed, getattr(r, "stdout", "") or "")
            else:
                # a failed/RESULT-less experiment: hand back the tail of the output (the traceback lands
                # at the end) so the agent can debug and retry.
                why = _result_rejection(getattr(r, "stdout", "") or "")
                head = f"RESULT rejected: {why}; no result recorded." if why else "no RESULT line;"
                summary = (f"{head} stdout/err tail:\n"
                           + (getattr(r, "stdout", "") or getattr(r, "stderr", ""))[-4000:])
            obs.append(f"#experiment {eid} [{'ran' if ok else 'FAILED'}] {e.get('subject')}~{e.get('object')} "
                       f"({e.get('method')}): {summary}")
        if cancelled:
            raise asyncio.CancelledError()
        return "\n".join(obs)

    def _act_log(self, args) -> str:
        eid = self.log.log(str(args.get("kind", "note")), str(args.get("title", "")),
                           str(args.get("body", "")), run_id=self.run_id,
                           status=str(args.get("status", "open")), score=args.get("score"),
                           provenance=args.get("provenance") or {})
        return f"logged #{eid}"

    def _mine_to_submit(self) -> str:
        """The ids this branch may actually submit, for a refusal message. A bare 'no' makes the agent guess
        again; the ids make the retry informed."""
        av = self.log.submittable(self.run_id)
        if not av:
            return " You have no experiment with a parsed RESULT yet — run one first."
        return " Yours with a RESULT: " + ", ".join(f"#{e['entry_id']} {e['title'][:48]}" for e in av)

    def _act_submit(self, args) -> str:
        entry = self.log.get(int(args.get("entry_id", -1))) if args.get("entry_id") is not None else None
        if not entry or entry["kind"] != "experiment":
            return "(submit needs the entry_id of an experiment entry with a RESULT." + self._mine_to_submit() + ")"
        # A forked child inherits a transcript full of entry ids it never ran. `log.get()` is not
        # run-scoped, so isolation has to hold on writes too, not only on reads.
        if entry.get("run_id") and entry["run_id"] != self.run_id:
            return (f"(#{entry['entry_id']} belongs to branch {entry['run_id']}, not to you ({self.run_id}); "
                    f"submit only experiments you ran.{self._mine_to_submit()})")
        try:
            result = json.loads(entry.get("result") or "{}")
        except Exception:
            result = {}
        if "p_null" not in result:
            return ("(that experiment has no parsed RESULT to verify — re-run so its code prints a valid "
                    "RESULT line." + self._mine_to_submit() + ")")
        prov = entry.get("provenance") or {}
        if prov.get("method_id") == "exploratory":
            return "(exploratory method cannot be submitted as audited; register and validate a method first)"
        sid = self.vq.submit(run_id=self.run_id,
                             hypothesis=entry["title"],
                             subject=prov.get("subject", ""), object=prov.get("object", ""),
                             method=prov.get("method", ""), expected_sign=int(prov.get("expected_sign", 0) or 0),
                             result=result, code=entry.get("code", ""),
                             provenance={"exploration_entry": entry["entry_id"],
                                         "experiment_id": prov.get("experiment_id"), "attempt_id": self.attempt_id})
        self.log.update(entry["entry_id"], status="submitted")
        if prov.get("experiment_id"):
            self._event("experiment.submitted", {"verification": "pending", "submission_id": sid},
                        experiment_id=prov["experiment_id"])
        return f"submitted #{entry['entry_id']} for verification (submission {sid})"

    def _spawn_child(self, run_id: str, resume_sid: str | None, brief: str, objective: str = "") -> "Explorer":
        """Build a child leaf branch that shares this branch's DB and fork budget (share_from=self),
        resumes the forked session (inheriting our cached context), and opens on a divergence briefing with
        fork disabled (a leaf earns forking by being promoted). It inherits our injected
        complete_fn/sandbox/judge and run config. corpus_card is not re-passed: the resumed session holds
        it. `cache_dir` is inherited; `scratch_dir` is not, so siblings cannot overwrite each other."""
        return Explorer(
            run_id=run_id, goal=self.goal, model=self.model, complete_fn=self._inject_complete,
            sandbox_run=self._sandbox_run, max_parallel=self.max_parallel, freeze_year=self.freeze_year,
            corpus_card=None, network=self.network, cache_dir=self.cache_dir,
            cross_run_memory=self.cross_run_memory, share_from=self, resume_sid=resume_sid,
            branch_brief=brief, fork_fn=self._fork_fn, fork_enabled=False, judge_fn=self._inject_judge,
            trace_dir=self._trace_dir, branch_objective=objective or "Explore an independent branch")

    def _branch_digest(self, run_id: str, angle: str = "", hypothesis: str = "",
                       adversarial: bool = False) -> dict:
        """Collect a branch's own findings into a structured digest the orchestrator judges and hands to the
        controller. Reads only that exact run_id's log entries: this is orchestration (the handler reading a
        branch it owns), not the agent's lineage-scoped memory. The branch's `reflect` summary becomes the
        explanation; its promising and submitted experiments, with their RESULT numbers, become the key
        results, so a promoted branch's synthesis after seeing its children's results is captured too."""
        rows = self.log._rows("WHERE run_id=? ORDER BY entry_id", [run_id])
        exps = [r for r in rows if r["kind"] == "experiment"]
        submitted = [r for r in exps if r["status"] == "submitted"]
        promising = [r for r in exps if r["status"] == "promising"]
        # Count submissions from the queue, not the entry status: verification feedback rewrites
        # `status=='submitted'` when a verdict lands, and this count feeds the judge's fallback sort and
        # the continuation loop's progress test.
        n_submitted = len(submitted)
        try:
            n_submitted = max(n_submitted, self.vq.con.execute(
                "SELECT COUNT(*) FROM verification_queue WHERE run_id = ?", [run_id]).fetchone()[0])
        except Exception:                      # queue unavailable (tests inject a bare log); entry status
            pass                               #   is the fallback
        key = []
        for r in submitted + promising:
            try:
                d = json.loads(r.get("result") or "{}")
            except Exception:
                d = {}
            key.append({"title": r["title"], "status": r["status"],
                        "effect": d.get("effect"),
                        "p_null": d.get("p_null"), "robust": d.get("robust")})
        refl = [r for r in rows if r["kind"] == "note" and (r.get("title") or "").lower().startswith("reflect")]
        explanation = (refl[-1].get("body") if refl else "") or ""
        return {"run_id": run_id, "angle": angle, "hypothesis": hypothesis, "adversarial": adversarial,
                "n_experiments": len(exps), "n_submitted": n_submitted,
                "key_results": key[:6], "explanation": explanation[:800],
                "dead": (not exps) or all(r["status"] == "dead" for r in exps)}

    def _judge_context(self) -> str:
        """What has already been tried in this investigation, and what has survived verification so far.
        The judge is a clean call that never sees the parent's conversation (the parent has a stake in its
        own leading hypothesis), so it is given these two facts and nothing else. Both halves are
        hard-bounded so the digests stay the bulk of the prompt."""
        parts = []
        prior = [r for r in self.log._rows(
            "WHERE kind='note' AND title LIKE 'fork judge:%' ORDER BY entry_id DESC")][:1]
        if prior:
            parts.append("ALREADY EXPLORED (the previous generation's branches and how they were ranked). "
                         "Use it to avoid re-spending compute on an angle already covered or already found "
                         "to be a dead end. It is not a precedent to follow: a line dropped last generation "
                         "may deserve another attempt from a different angle.\n"
                         + (prior[0].get("body") or "")[:1200])
        try:
            tested = self.kg.engine_tests(scope=LIN.tree_sql(self.run_id))
        except Exception:
            tested = []
        if tested:
            rows = [f"  {t.get('run_id')}: {t.get('status')}"
                    f"{' (' + str(t.get('kill_reason')) + ')' if t.get('kill_reason') else ''}"
                    f" — {str(t.get('hypothesis') or '')[:90]}" for t in tested[-12:]]
            parts.append("VERIFICATION SO FAR across this investigation (the falsifier's soundness verdicts). "
                         "A `candidate` survived the soundness floor; any other status is a kill, and the "
                         "status names its kind: `invalid` (the numbers cannot be trusted; fix and re-run), "
                         "`underpowered` (could not decide; needs more units), `inconclusive` (ran and found "
                         "nothing; the claim is neither supported nor refuted), `refuted` (the data "
                         "contradicted the claim; the inverse may be a lead). Verification is asynchronous "
                         "and lags behind exploration, so a branch with nothing listed here is unverified, "
                         "which is not the same as unsound; do not penalise a branch for absence.\n"
                         + "\n".join(rows))
        return ("\n\n" + "\n\n".join(parts)) if parts else ""

    async def _judge_promise(self, digests: list[dict], k: int) -> list[dict]:
        """Rank forked branches by how much more compute they deserve (the assess-promise rubric) and mark
        the top k to continue. A search heuristic, never a soundness verdict, which stays with the
        falsifier. A clean model call seeded with the goal, the batch digests and the rubric; injectable
        (judge_fn) for tests. Returns [{run_id, keep, rank, reason}]; on any failure it degrades to keeping
        the branches with the most submissions and experiments, so the search never stalls."""
        ids = [d["run_id"] for d in digests]
        if self._inject_judge is not None:
            return self._inject_judge(digests, k)

        def _fallback() -> list[dict]:
            order = sorted(digests, key=lambda d: (d["n_submitted"], d["n_experiments"], not d["dead"]),
                           reverse=True)
            keep = {d["run_id"] for d in order[:k]}
            return [{"run_id": d["run_id"], "keep": d["run_id"] in keep,
                     "rank": order.index(d) + 1, "reason": "fallback: ranked by submissions/experiments"}
                    for d in digests]

        rubric = SK.get_skill("assess-promise") or ""
        prompt = (f"GOAL of the investigation:\n{self.goal}\n\n"
                  f"You are ranking {len(digests)} sibling exploration branches that each approached the "
                  f"goal from a different angle, to decide which {k} are most worth continuing with more "
                  f"compute. This is a search heuristic, not a verdict on truth. Rank them comparatively "
                  f"per the rubric.\n"
                  f"One branch may be flagged adversarial:true; its job was to falsify the leading "
                  f"hypothesis, not extend it. Judge it by how decisive and informative its attack was: a "
                  f"clean falsification and a leading line that survived a well-designed attack are both "
                  f"high-value outcomes, so do not penalise it for having no new finding.\n\n"
                  f"RUBRIC:\n{rubric}"
                  f"{self._judge_context()}\n\n"
                  f"BRANCH DIGESTS (JSON), the items you are ranking:\n"
                  f"{json.dumps(digests, indent=1, default=str)}\n\n"
                  f"Respond with only a JSON array, one object per branch, most promising first:\n"
                  f'[{{"run_id":"..","keep":true,"rank":1,"reason":".."}}, ...]  '
                  f"with exactly {k} of them keep=true.")
        try:
            cap: dict = {}
            raw = await llm.acomplete(prompt, model=llm.OPUS, effort="high", max_turns=6, thinking=True,
                                      capture=cap)
            arr = llm.parse_json(raw)
            if not isinstance(arr, list) or not arr:
                return _fallback()
            by_id = {str(v.get("run_id")): v for v in arr if isinstance(v, dict)}
            # The ranking is what survives; the model's own `keep` flags are ignored so the count is enforced here.
            # Sort by its rank and take exactly k, so the beam width is enforced by the engine.
            ranked = sorted(ids, key=lambda i: by_id.get(i, {}).get("rank", 999))
            keep = set(ranked[:k])
            out = []
            for i in ids:
                v = by_id.get(i, {})
                out.append({"run_id": i, "keep": i in keep, "rank": v.get("rank"),
                            "reason": str(v.get("reason", ""))})
            return out
        except Exception:
            return _fallback()

    def _persist_judge(self, verdicts: list[dict], digests: list[dict]) -> None:
        """Write the promise judge's ranking to the exploration log the moment it is decided, since the
        structured beam record only reaches disk when the whole fork returns. Best-effort: a logging
        failure must never take down a fork."""
        try:
            angles = {d["run_id"]: (d.get("angle") or d.get("hypothesis") or "") for d in digests}
            body = "\n".join(
                f"{v.get('rank')}. {v['run_id']} {'keep' if v.get('keep') else 'prune'} "
                f":: {angles.get(v['run_id'], '')[:160]} — {str(v.get('reason', ''))[:400]}"
                for v in sorted(verdicts, key=lambda x: x.get("rank") or 99))
            self.log.log("note", f"fork judge: kept {sum(1 for v in verdicts if v.get('keep'))}"
                                 f"/{len(verdicts)} branches", body, run_id=self.run_id, status="open",
                         provenance={"kind": "judge", "parent": self.run_id,
                                     "verdicts": verdicts, "depth": LIN.depth(self.run_id)})
        except Exception as e:                       # bookkeeping must not break a live fork
            print(f"[fork] could not persist judge verdicts: {type(e).__name__}: {e}", flush=True)

    async def _act_fork(self, args) -> str:
        self._report_reason = "fork_proposal"
        if self.control.get(self.run_id):
            self.control.patch(self.run_id, status="reporting", report_reason=self._report_reason)
        return "Research paused. Include proposed subquestions and evidence in your checkpoint report."

    async def _report(self):
        state = self.control.get(self.run_id)
        if state["status"] == "reporting_blocked":
            return
        self.control.patch(self.run_id, status="reporting")
        self._event("lifecycle", {"lifecycle": "reporting", "reason": self._report_reason})
        # Disconnect the research client, then reopen the SAME transcript with tools disabled
        # and a smaller output/time ceiling. No research dispatch exists in this loop.
        if self._session is not None:
            sid = self._session.session_id or self._resume_sid
            if sid:
                self.session_id = sid
                self._persist_session(sid)
                self.control.patch(self.run_id, session_id=sid)
            if self._session_connected:
                await self._session.__aexit__()
            self._session_connected = False
            self._session = None
        report_session = None
        if self._inject_complete is None:
            sid = self.session_id or self._resume_sid
            if not sid and state["total_actions"] > 0:
                self.control.patch(self.run_id, status="reporting_blocked")
                self._event("lifecycle", {"lifecycle": "reporting_blocked", "reason": "No saved child session"})
                return
            report_session = llm.Session(system=_SYS, model=self.model, resume=sid,
                                         max_turns=1, tools_disabled=True, max_output_tokens=4096)
        error = ""
        report_connected = False
        try:
            for attempt in range(state["report_attempts"], 3):
                self.control.patch(self.run_id, report_attempts=attempt + 1)
                started = time.monotonic()
                cap = {}
                report_cost_saved = False
                try:
                    prompt = REPORT_PROMPT + "\nObjective: " + self.manifest["branch_objective"] + "\nTrigger: " + self._report_reason + "\n" + error
                    self._event("model.started", {"phase": "report", "label": "Writing mandatory report"})
                    async def ask_report():
                        nonlocal report_connected
                        if report_session and not report_connected:
                            await report_session.__aenter__()
                            report_connected = True
                        return await (self._inject_complete(prompt) if self._inject_complete
                            else report_session.ask(prompt, capture=cap))
                    raw = await self._funded("report", ask_report)
                    report = validate_report(json.loads(raw))
                    if report_session and report_session.truncated:
                        raise ValueError("Report output limit reached")
                    self.control.cost(self.run_id, "report", time.monotonic() - started, _capture_usage(cap))
                    report_cost_saved = True
                    saved = self.control.save_report(self.run_id, report)
                    self._event("checkpoint.report", {"version": saved["version"], "report": report,
                                                      "total_actions": saved["total_actions"], "costs": saved["costs"],
                                                      "budget_scopes": self.control.budgets(self.run_id)})
                    self._event("lifecycle", {"lifecycle": "awaiting_parent", "reason": "Valid child report saved"})
                    return
                except (ValueError, TypeError) as exc:
                    error = "Repair the report format: " + str(exc)
                except Exception as exc:
                    error = f"Report generation unavailable ({type(exc).__name__}); progress remains paused"
                    break
                finally:
                    if not report_cost_saved:
                        self.control.cost(self.run_id, "report", time.monotonic() - started, _capture_usage(cap))
                    self._event("model.ended", {"phase": "report"})
        except Exception:
            error = "Report session unavailable; progress remains paused"
        finally:
            if report_session:
                if report_session.session_id:
                    self.session_id = report_session.session_id
                    self._persist_session(self.session_id)
                    self.control.patch(self.run_id, session_id=self.session_id)
                try:
                    if report_connected:
                        await report_session.__aexit__()
                except Exception:
                    pass
        self.control.patch(self.run_id, status="reporting_blocked")
        self._event("lifecycle", {"lifecycle": "reporting_blocked", "reason": error or "Report repair allowance exhausted"})

    def _allocation_records(self):
        """Ordinary branch evidence for allocation, with explicit bounded coverage."""
        rows = self.log._rows("WHERE run_id=? ORDER BY entry_id DESC", [self.run_id])
        items, size = [], 0
        for row in rows:
            item = {k: row.get(k) for k in ("entry_id", "kind", "title", "body", "code", "result", "status")}
            length = len(json.dumps(item, default=str))
            if size + length > 100000:
                break
            items.append(item)
            size += length
        return {"records": items, "shown": len(items), "total": len(rows), "truncated": len(items) < len(rows)}

    async def _funded(self, phase, call):
        op = self.control.reserve_operation(self.run_id, phase)
        started, interrupted = time.monotonic(), False
        try:
            return await asyncio.wait_for(call(), timeout=op["seconds"]) if op else await call()
        except (asyncio.CancelledError, TimeoutError):
            interrupted = True
            raise
        finally:
            saved = self.control.settle_operation(op, time.monotonic() - started, interrupted)
            if saved:
                self._event("budget.operation", saved)

    async def _parent_decision(self, child):
        return await child._funded("judge", lambda: self._parent_decision_inner(child))

    async def _parent_decision_inner(self, child):
        state = self.control.get(child.run_id)
        context = {"objective": child.manifest["branch_objective"], "report": state["report"],
                   "report_version": state["version"], "current_round_objective": state.get("objective"),
                   "supporting_records": child._allocation_records(),
                   "subtree_budgets": child.control.budgets(child.run_id),
                   "actions_used": state["total_actions"], "rounds": state["rounds"],
                   "max_branch_actions": BRANCH_TOTAL_STEPS, "max_rounds": MAX_CONTINUATIONS,
                   "depth": LIN.depth(child.run_id), "max_depth": MAX_DEPTH}
        prompt = ("You are the parent allocation controller. Inspect the objective, report and evidence. "
                  "Choose continue, fork, finish or prune. Do not demand a positive result each round: "
                  "credible unfinished work, preparation and useful falsification deserve fair consideration. "
                  "Do not rank by experiment counts or enforce a survival quota. Fork only for distinct "
                  "useful concurrent subquestions with feasible inputs. Return one JSON object: "
                  "action, reason; for continue also objective and allowance (1..18); for fork also allowance "
                  "and branches (2..3 objects with objective, information_gain, feasibility). Respect caps.\n"
                  + json.dumps(context, default=str))
        started = time.monotonic()
        cap = {}
        try:
            if self._allocation_fn:
                import inspect
                result = self._allocation_fn(context)
                if inspect.isawaitable(result):
                    result = await result
            else:
                raw = await llm.acomplete(prompt, model=self.model, tools_disabled=True,
                    max_output_tokens=4096, max_turns=1, max_attempts=1, capture=cap)
                result = json.loads(raw)
            return validate_decision(result)
        finally:
            self.control.cost(child.run_id, "judge", time.monotonic() - started, _capture_usage(cap))

    async def _allocate(self, child):
        """Serialize a node's controller, including restart/partial-fork execution."""
        import fcntl
        lock_path = self.control.path.parent / ("allocation-" + child.run_id + ".lock")
        with lock_path.open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return
            return await self._allocate_unlocked(child)

    async def _allocate_unlocked(self, child):
        """One child can report/receive allocation without waiting for siblings."""
        while True:
            state = self.control.get(child.run_id)
            if state["status"] in {"forking", "fork_blocked", "waiting"}:
                await child._execute_fork(self.control.decision(state["decision_id"]))
                return
            if state["status"] != "awaiting_parent":
                return
            if not self.control.research_available(child.run_id):
                self.control.patch(child.run_id, status="completed", terminal_reason="budget_endpoint")
                child._event("lifecycle", {"lifecycle": "completed", "reason": "Fixed shared budget reached after mandatory report"})
                self.control.finalize_budgets(child.run_id)
                return
            try:
                decision = await self._parent_decision(child)
                record = self.control.decide(child.run_id, state["version"], decision)
            except Exception:
                child._event("lifecycle", {"lifecycle": "awaiting_parent", "reason": "Parent allocation unavailable or exceeds caps; revised decision required"})
                return
            child._event("branch.decision", record)
            action = decision["action"]
            if action == "continue":
                child._resume_sid = child.session_id or state["session_id"]
                child._branch_brief = "Parent authorized objective: " + decision["objective"]
                await child.run(max_steps=decision["allowance"])
            elif action == "fork":
                await child._execute_fork(record)
                return
            else:
                child._event("lifecycle", {"lifecycle": "completed" if action == "finish" else "pruned", "reason": decision["reason"]})
                return

    async def _execute_fork(self, record):
        """Execute the persisted exact approval. Ambiguous interrupted SDK forks stay blocked."""
        tasks = []
        for item in record["children"]:
            rid, spec = item["run_id"], item["spec"]
            sid = item["session_id"]
            if item["status"] in {"launching", "failed"}:
                continue  # Never repeat a possibly completed SDK fork after a crash.
            if item["status"] == "reserved":
                if not self.control.claim_launch(record["decision_id"], rid):
                    continue
                try:
                    fork_fn = self._fork_fn
                    if fork_fn is None:
                        from claude_agent_sdk import fork_session
                        fork_fn = lambda parent_sid: fork_session(parent_sid, directory=os.getcwd())
                    async def launch():
                        return fork_fn(self.session_id or self._resume_sid)
                    sid = getattr(await self._funded("fork", launch), "session_id", None)
                    if self._inject_complete is None and not sid:
                        raise RuntimeError("No fork session")
                    self.control.launch_state(record["decision_id"], rid, "launched", sid)
                except Exception:
                    self.control.launch_state(record["decision_id"], rid, "failed")
                    continue
            c = self._spawn_child(rid, sid, _leaf_brief(rid, spec["objective"], ""), spec["objective"])
            cstate = self.control.start(rid, record["decision"]["allowance"])
            c._resume_sid = cstate["session_id"] or sid
            async def work(c=c):
                state = c.control.get(c.run_id)
                if state["status"] in {"working", "reporting"}:
                    await c.run(max_steps=record["decision"]["allowance"])
                try:
                    await self._allocate(c)
                finally:
                    self.control.finalize_budgets(c.run_id)
            tasks.append(work())
        self._event("lifecycle", {"lifecycle": "waiting", "reason": "Authorized descendants executing"})
        results = await asyncio.gather(*tasks, return_exceptions=True)
        latest = self.control.decision(record["decision_id"])
        blocked = latest["status"] != "executed" or any(isinstance(x, BaseException) for x in results)
        statuses = [self.control.get(i["run_id"]) for i in latest["children"]]
        settled = all(s and s["status"] in {"completed", "pruned"} for s in statuses)
        status = "fork_blocked" if blocked else ("completed" if settled else "waiting")
        self.control.patch(self.run_id, status=status)
        self._event("lifecycle", {"lifecycle": status, "reason": "Descendant allocation settled" if settled else "Descendant work paused; operator/controller resumption required"})

    async def _dispatch(self, action: dict) -> str:
        if self._degraded or getattr(self.journal, "degraded", False) or "agent-runtime" not in self._delivered:
            raise RuntimeError("Mandatory runtime instructions not delivered; dispatch blocked")
        state = self.control.get(self.run_id)
        if state and state["status"] != "working":
            raise RuntimeError("Research paused; dispatch prohibited")
        name, args = action.get("action"), action.get("args", {})
        if name == "private_experiment":
            from .private_experiments import dispatch
            return await dispatch(self, args)
        if name == 'inhibitor':
            if 'inhibitor-interface' not in self._delivered:
                return self._act_get_skill({'name':'inhibitor-interface'})
            from dnhacksbio.inhibitor.service import Workbench
            wb=Workbench(self.journal,self.run_id,args['experiment_id'],self.manifest.get('project_id'))
            if args.get('operation')=='inspect_scene_capture':
                from dnhacksbio.inhibitor.review import inspect
                observation,cap=await inspect(wb,args['capture_id'],args.get('question','Describe geometry and occlusion; propose a grounded numerical countercheck.'),self.model)
                self.control.cost(self.run_id,'research',0.,_capture_usage(cap))
                return observation
            return json.dumps(await asyncio.to_thread(wb.dispatch,args,'agent'),allow_nan=False)
        h = {"search_kg": self._act_search_kg, "search_papers": self._act_search_papers,
             "read_paper": self._act_read_paper, "search_skills": self._act_search_skills,
             "get_skill": self._act_get_skill, "log": self._act_log, "submit": self._act_submit,
             "recall": self._act_recall, "neighbors": self._act_neighbors,
             "subgraph": self._act_subgraph, "path": self._act_path}
        if name == "tissue":
            return await self._act_tissue(args)
        if name == "binder":
            if "binder-interface" not in self._delivered:
                return "(binder blocked: get_skill binder-interface before dispatch)"
            from dnhacksbio.binder.runtime import dispatch
            usage={}
            try:
                result=await dispatch(self.journal,self.manifest.get("project_id"),self.run_id,args,usage_capture=usage)
                return json.dumps(result,allow_nan=False)
            except (ValueError,KeyError,TypeError,FileNotFoundError,RuntimeError,TimeoutError) as exc:
                return json.dumps({"error":str(exc)})
            finally:
                if usage:self.control.cost(self.run_id,"research",0.,_capture_usage(usage))
        if name == "spindle":
            if "spindle-interface" not in self._delivered:
                return "(spindle blocked: get_skill spindle-interface before dispatch)"
            from dnhacksbio.spindle.runtime import dispatch
            try:
                result=await dispatch(self.journal,self.manifest.get("project_id"),self.run_id,args)
                return json.dumps(result,allow_nan=False)
            except (ValueError,KeyError,FileNotFoundError,RuntimeError,TimeoutError) as exc:
                return json.dumps({"error":str(exc)})
        if name == "run_experiments":
            return await self._act_run_experiments(args)
        if name == "fetch_papers":
            return await self._act_fetch_papers(args)
        if name == "find_datasets":
            return await self._act_find_datasets(args)
        if name == "fork":
            return await self._act_fork(args)
        if name == "reflect":
            self.log.log("note", "reflection", str(args.get("note", "")), run_id=self.run_id)
            return "noted"
        if name in {"done", "checkpoint"}:
            self._report_reason = "completion_request" if name == "done" else "voluntary_checkpoint"
            if state:
                self.control.patch(self.run_id, status="reporting", report_reason=self._report_reason)
            return "Research paused for mandatory report"
        fn = h.get(name)
        return fn(args) if fn else f"(unknown action {name!r})"

    async def step(self, message: str) -> tuple[dict, str]:
        self.control.start(self.run_id, CHILD_MAX_STEPS)
        return await self._funded("research", lambda: self._step(message))

    async def _step(self, message: str) -> tuple[dict, str]:
        """One think→act→observe cycle on the persistent session. `message` is turn 1's full standing
        context or a turn-2+ delta (last observation + any new feedback). Returns (action, observation)."""
        state = self.control.get(self.run_id)
        if state:
            state = self.control.consume(self.run_id)
            self.steps = state["total_actions"]
        else:
            self.steps += 1
        if not self.attempt_id:
            self._begin_attempt()
        self._operation_id = uuid4().hex
        # Wall-clock the whole think→act→observe cycle: monotonic for a robust
        # duration, epoch for "when". Both land in the reasoning trace so the UI
        # can show per-step latency without a separate profiling pass.
        _t0 = time.monotonic()
        action = await self._next_action(message)
        self._event("intent", {"intent": action["intent"]}, producer="agent")
        self._event("tool.started", {"phase": "tool", "action": action["action"],
                                    "label": action["action"].replace("_", " "),
                                    "inputs": self.journal.blob(json.dumps(action["args"]))})
        try:
            if action["action"] == "fork":
                self._event("lifecycle", {"lifecycle": "waiting", "reason": "Waiting for child research branches"})
            obs = await self._dispatch(action)
            if action["action"] == "fork":
                self._event("lifecycle", {"lifecycle": "running", "reason": "Child research returned"})
        except BaseException as exc:
            self._event("tool.failed", {"error": f"{type(exc).__name__}: {exc}"})
            raise
        self._event("tool.ended", {"action": action["action"], "observation": self.journal.blob(str(obs))})
        # Keep the rolling transcript bounded to the last 6 steps, but do not truncate each observation:
        # only these few steps are re-shown, so full text is affordable and the numbers/errors survive.
        self.transcript.append({"step": self.steps, "action": action.get("action", ""),
                                "thought": str(action.get("thought", "")), "obs": str(obs)})
        self.transcript = self.transcript[-6:]
        # Durable reasoning trace: the model's own thinking blocks, its self-reported "thought", the action
        # and the full observation.
        cap = self._last_capture or {}
        rec = {"step": self.steps, "run_id": self.run_id,
               "ts": time.time(),                          # end-of-step epoch seconds
               "dt_s": round(time.monotonic() - _t0, 3),   # step wall-clock duration
               "reasoning": action["intent"],
               "action": action.get("action", ""), "args": action.get("args", {}),
               "observation": str(obs)}
        if self._fork_meta is not None:                    # a fork step: attach the structured beam tree
            rec["fork"] = self._fork_meta
            self._fork_meta = None
        try:
            with open(self._reasoning_path, "a") as f:
                f.write(json.dumps(rec, default=str) + "\n")
        except Exception:
            pass
        # raw SDK message stream for this step: the guaranteed-faithful record of the actual API exchange
        if cap.get("messages"):
            try:
                with open(self._transcript_path, "a") as f:
                    f.write(json.dumps({"step": self.steps, "run_id": self.run_id,
                                        "messages": cap["messages"]}, default=str) + "\n")
            except Exception:
                pass
        return action, obs

    async def run(self, max_steps: int = 18) -> dict:
        import fcntl
        lock_path = self.control.path.parent / ("worker-" + self.run_id + ".lock")
        with lock_path.open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return {"status": "already_running", "steps": self.steps}
            return await self._run_round(max_steps)

    async def _run_round(self, max_steps: int) -> dict:
        state = self.control.start(self.run_id, min(max_steps, CHILD_MAX_STEPS))
        self.steps = state["total_actions"]
        self._report_reason = state.get("report_reason", "allowance_exhausted")
        self._resume_sid = state["session_id"] or self._resume_sid
        if state["status"] not in {"working", "reporting"}:
            return self._run_summary()
        heartbeat = None
        try:
            self._begin_attempt()
            heartbeat = asyncio.create_task(self._heartbeat())
            if self._inject_complete is None:
                self._session = llm.Session(system=_SYS, model=self.model, effort="high", max_turns=1,
                                            thinking=True, resume=self._resume_sid, tools_disabled=True)
                self._session_connected = False
            self._round_max_steps = state["allowance"]
            self._steps_at_round_start = self.steps - state["used"]
            message = (self._branch_brief or self._state()) + "\n" + self._budget_line()
            if state.get("objective"):
                message += "\nCurrent parent-authorized objective: " + state["objective"]
            self._snapshot_seen()
            if state["status"] == "working":
                for _ in range(max(0, state["allowance"] - state["used"])):
                    if heartbeat.done():
                        heartbeat.result()
                    if not self.control.research_available(self.run_id):
                        self._report_reason = "subtree_budget_exhausted"
                        self.control.patch(self.run_id, status="reporting", report_reason=self._report_reason)
                        break
                    started = time.monotonic()
                    try:
                        action, obs = await self.step(message)
                    except BudgetUnavailable:
                        self._report_reason = "subtree_budget_exhausted"
                        self.control.patch(self.run_id, status="reporting", report_reason=self._report_reason)
                        break
                    finally:
                        self.control.cost(self.run_id, "research", time.monotonic() - started)
                    if self._session and self._session.session_id:
                        self.session_id = self._session.session_id
                        self.control.patch(self.run_id, session_id=self.session_id)
                        self._persist_session(self.session_id)
                    if action["action"] in {"done", "checkpoint", "fork"}:
                        break
                    message = self._turn_message(obs)
            await self._report()
        except BaseException as exc:
            self._cancel_sandbox.set()
            status = "cancelled" if isinstance(exc, asyncio.CancelledError) else "failed"
            self.control.patch(self.run_id, status=status)
            if not self._degraded:
                self._event("lifecycle", {"lifecycle": status, "reason": type(exc).__name__})
            raise
        finally:
            if heartbeat:
                heartbeat.cancel()
                await asyncio.gather(heartbeat, return_exceptions=True)
            if self._session:
                if self._session_connected:
                    await self._session.__aexit__()
                self._session_connected = False
                self._session = None
        return self._run_summary()

    def _run_summary(self):
        state = self.control.get(self.run_id)
        return {"steps": state["total_actions"], "status": state["status"],
                "report_version": state["version"], "log": self.log.counts(), "queue": self.vq.counts()}

    async def run_investigation(self, max_steps: int = 18):
        """Root uses the same allocation controller as every child."""
        try:
            await self.run(max_steps)
            await self._allocate(self)
        finally:
            self.control.finalize_budgets(self.run_id)
        return self._run_summary()

    def _persist_session(self, sid: str) -> None:
        """Record run_id -> sdk_session_id on disk, so a stopped run can be resumed. The SDK's own
        transcripts persist as files under ~/.claude/projects/<cwd-slug>/, so the id is the only missing
        piece. Lives beside the traces."""
        p = sessions_path(self._trace_dir, self.run_id)
        try:
            m = json.loads(p.read_text()) if p.exists() else {}
        except Exception:
            m = {}
        m[self.run_id] = sid
        try:
            p.write_text(json.dumps(m, indent=1, sort_keys=True))
        except Exception as e:
            print(f"[{self.run_id}] could not persist session id: {type(e).__name__}: {e}", flush=True)

    def close(self) -> None:
        self.kg.close()          # the one owning connection; log/papers/vq attached to it, so no-ops


def sessions_path(trace_dir: str | Path, run_id: str) -> Path:
    """Where a fork tree's run_id -> session_id map lives. One file per investigation (keyed by root), so
    resuming any branch reads the same map its siblings wrote."""
    return Path(trace_dir) / f"sessions_{LIN.root(run_id)}.json"


def load_session_id(trace_dir: str | Path, run_id: str) -> str | None:
    """The sdk session id for a previous run of `run_id`, or None if it was never recorded."""
    p = sessions_path(trace_dir, run_id)
    try:
        return json.loads(p.read_text()).get(run_id) if p.exists() else None
    except Exception:
        return None


DIAG_CAP = 1200          # chars of the experiment's own prints handed back on success


def _finite(x) -> bool:
    """True iff x is a real, comparable number (not None, not bool, not NaN/inf)."""
    if x is None or isinstance(x, bool):
        return False
    try:
        return math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def _feedback_version(entry: dict) -> tuple:
    """A later verdict on the same entry must be delivered, even at the same timestamp."""
    return (entry["entry_id"], str(entry.get("updated_at", "")), entry.get("status"), entry.get("body"))


def _result_problem(d: dict) -> str | None:
    """Why this RESULT is not a usable audited statistic, or None if it is. Validate at the door: a value
    we cannot interpret is not a weak result, it is not a result."""
    from dnhacksbio.methods import result_problem
    return result_problem(d)


def _parse_result(stdout: str) -> dict | None:
    """Pull the standardized RESULT the experiment prints. Tolerant of form (real JSON or a Python dict
    repr), strict about values (`_result_problem`): a malformed RESULT returns None, so the entry logs as
    'open' with the reason handed back."""
    m = _RESULT_RX.search(stdout or "")
    if not m:
        return None
    raw = m.group(1)
    for parse in (json.loads, ast.literal_eval):
        try:
            d = parse(raw)
            if isinstance(d, dict) and "p_null" in d:
                return None if _result_problem(d) else d
        except Exception:
            continue
    return None


def _result_rejection(stdout: str) -> str:
    """If a RESULT line was present but invalid, say exactly what was wrong."""
    m = _RESULT_RX.search(stdout or "")
    if not m:
        return ""
    for parse in (json.loads, ast.literal_eval):
        try:
            d = parse(m.group(1))
            if isinstance(d, dict):
                if "p_null" not in d:
                    return "RESULT is missing the required `p_null` field"
                return _result_problem(d) or ""
        except Exception:
            continue
    return "RESULT line is not parseable as a JSON object"


def _diagnostics(parsed: dict, stdout: str) -> str:
    """The supporting context for a successful experiment: the design fields that make a number readable,
    plus everything the code printed besides its RESULT line."""
    out = []
    for k in ("n_units", "null_model"):
        if parsed.get(k) not in (None, ""):
            out.append(f"{k}={str(parsed[k])[:220]}")
    if parsed.get("detail") not in (None, "", {}, []):
        out.append(f"detail={json.dumps(parsed['detail'], default=str)[:400]}")
    s = stdout or ""
    m = _RESULT_RX.search(s)
    if m:
        s = s[:m.start()] + s[m.end():]          # the agent's own prints, minus the RESULT line
    s = s.strip()
    tail = f"\n  printed: {s[-DIAG_CAP:]}" if s else ""
    return ((" " + " ".join(out)) if out else "") + tail


def _capture_usage(capture):
    result = {"input_tokens": 0, "output_tokens": 0}
    for message in capture.get("messages", []):
        if message.get("type") == "ResultMessage":
            u = message.get("usage") or {}
            result["input_tokens"] += sum(u.get(k, 0) or 0 for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
            result["output_tokens"] += u.get("output_tokens", 0) or 0
    return result
