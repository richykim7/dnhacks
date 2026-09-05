"""The onboarding assistant — natural language in, a corpus spec out.

Designing a literature corpus is the part of this system a domain scientist is best at and a search
box is worst at. You know the field, the labs, the two mechanisms that matter and the one review
everybody cites; what you do not want to do is hand-translate that into fifteen Europe PMC boolean
queries and a list of DOIs.

So the onboarding step is a conversation. Each turn the model sees the project, the spec as it
currently stands, and the chat so far, and answers two things at once:

  1. a reply to the person — questions, pushback, an explanation of what it changed and why;
  2. a **spec patch** — the concrete fields it proposes, in a fenced JSON block.

The patch is a *proposal*, never an application: it comes back to the browser next to the reply and the
person accepts or edits it. The model proposes, the human decides, and the decision is what gets written.
"""

from __future__ import annotations

import json
import re

from dnhacksbio import llm

from . import projects

# Designing the discovery strategy is the judgment-heavy step: the queries decide which papers can ever
# enter the graph. So this runs on the judgment model, not the bulk-tier extraction model.
MODEL = llm.OPUS

MAX_TURNS_KEPT = 24         # chat history handed back to the model
MAX_MSG_CHARS = 4000

SYSTEM = """\
You are a research-librarian collaborator helping a working scientist define a LITERATURE CORPUS for \
an automated discovery engine. The corpus becomes a knowledge graph: every paper is read by an \
extractor that pulls out directional claims (subject -> predicate -> object) with verbatim quotes, and \
the engine then reasons over that graph and runs its own computational experiments against it.

Your job is the collection, not the question. A corpus is built once and then asked many different \
questions by many different runs, so nothing you produce states what the engine should find out. The \
scientist may tell you the question they care about, and you should use it to choose queries, since it \
is the best signal about which mechanisms must be covered, but it goes no further than your reasoning. \
Never write it into the spec, and if they expect it to become the engine's instruction, say that the \
question is set when they start a run.

What that means:
- The corpus must cover the mechanisms the scientist wants reasoned about, including the adjacent \
fields where a transferable mechanism lives. A corpus of only the obvious papers produces only the \
obvious conclusions.
- It must be bounded. A vague query returning 40k hits is worse than five sharp ones, because relevance \
triage then discards most of what was fetched.
- Each query is an independent discovery channel. Overlap between channels is useful: it lets \
capture-recapture estimate whether the corpus is saturated. Aim for 6-20 queries that overlap partially \
rather than one large disjunction.

Query syntax is Europe PMC: boolean AND / OR / NOT, "quoted phrases" for multi-word terms, \
parentheses for grouping, AUTH:"Lastname I" for an author, TITLE:"..." to restrict to titles. \
Prefer gene symbols AND their common synonyms in an OR group (e.g. (BRCA1 OR BRCC1 OR RNF53)).

Behaviour
- Ask at most two clarifying questions per turn, and only when the answer would change the queries. \
If the scientist has given you enough, stop asking and propose.
- Push back when the scope is incoherent, unbuildable, or so broad that the triage step will dominate. \
Say so plainly and propose the narrower version.
- Explain your choices in one short paragraph, without bullet lists or restating what they told you.

Output format
Write your reply as normal prose. Then, if you have concrete changes to propose, append one fenced \
JSON block with only the fields you are changing:

```json
{
  "scope": "one or two sentences describing what this collection covers and what it leaves out; a \
description of the corpus, never a question and never an instruction",
  "theme": "one dense paragraph naming the entities, mechanisms and contexts; this is the text that \
relevance-ranks every candidate paper, so it should read like an abstract of the ideal paper",
  "queries": ["...", "..."],
  "seed_dois": ["10.1038/..."],
  "n_papers": 150,
  "year_min": null,
  "year_max": null,
  "exclude_terms": []
}
```

Only include a DOI in seed_dois if you are confident it is real and correct; a wrong DOI silently \
fetches the wrong paper. If you are unsure, name the paper in your prose and let them supply it.
Never invent a finding, a paper, or an author's involvement in a topic.\
"""

_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)

# Only these may be proposed. The model cannot reach concurrency, an id, a path, or anything else.
PATCHABLE = ("scope", "theme", "queries", "seed_dois", "n_papers", "year_min", "year_max",
             "exclude_terms")


class AssistantUnavailable(RuntimeError):
    """The LLM seam is not reachable. The manual path still works, so say that."""


def _split_reply(text: str) -> tuple[str, dict | None]:
    """Separate the prose reply from the proposed spec patch."""
    m = _FENCE.search(text or "")
    if not m:
        return (text or "").strip(), None
    prose = (text[:m.start()] + text[m.end():]).strip()
    try:
        patch = json.loads(m.group(1))
    except ValueError:
        try:
            patch = llm.parse_json(m.group(1))
        except Exception:
            return (text or "").strip(), None
    if not isinstance(patch, dict):
        return prose, None
    return prose, {k: v for k, v in patch.items() if k in PATCHABLE}


def _context(rec: dict) -> str:
    spec = rec.get("spec") or {}
    atts = rec.get("attachments") or []
    lines = [
        f"PROJECT: {rec.get('name')}",
        f"DESCRIPTION: {rec.get('description') or '(none yet)'}",
        "",
        "CURRENT SPEC:",
        json.dumps({k: spec.get(k) for k in PATCHABLE}, indent=2),
    ]
    if atts:
        lines += ["", "Documents the scientist has already uploaded (already in the corpus; do not "
                      "spend queries rediscovering them, but do cover their surrounding literature):"]
        lines += [f"- {a['filename']} — {a.get('preview', '')[:300]}" for a in atts[:20]]
    return "\n".join(lines)


def _transcript(chat: list[dict], user_msg: str) -> str:
    turns = [t for t in (chat or []) if t.get("role") in ("user", "assistant")][-MAX_TURNS_KEPT:]
    lines = []
    for t in turns:
        who = "SCIENTIST" if t["role"] == "user" else "YOU"
        lines.append(f"{who}: {str(t.get('content') or '')[:MAX_MSG_CHARS]}")
    lines.append(f"SCIENTIST: {user_msg[:MAX_MSG_CHARS]}")
    return "\n\n".join(lines)


async def _ask(prompt: str) -> str:
    try:
        return await llm.acomplete(prompt, model=MODEL, system=SYSTEM, effort="medium", max_turns=4)
    except Exception as exc:
        raise AssistantUnavailable(
            f"the assistant could not be reached ({type(exc).__name__}: {exc}). "
            "You can still write the queries and theme by hand — the assistant is a shortcut, "
            "not a requirement."
        ) from exc


async def chat(project_id: str, message: str) -> dict:
    """One conversational turn. Appends both sides to the project's stored chat and returns
    {reply, patch, chat}. The patch is not applied; the browser shows it for approval."""
    message = (message or "").strip()
    if not message:
        raise ValueError("say something to the assistant")
    if len(message) > MAX_MSG_CHARS:
        raise ValueError(f"message too long (max {MAX_MSG_CHARS} characters)")
    rec = projects.load(project_id)
    if rec.get("adopted"):
        raise ValueError("this corpus was built outside the console and has no spec to design")

    prompt = (f"{_context(rec)}\n\n--- CONVERSATION SO FAR ---\n{_transcript(rec.get('chat'), message)}"
              f"\n\nYOU:")
    raw = await _ask(prompt)
    reply, patch = _split_reply(raw)

    if patch:
        # Validate the proposal against the same rules a hand-typed spec must satisfy.
        try:
            projects.validate_spec({**rec["spec"], **patch})
        except ValueError as exc:
            reply += f"\n\n(Its proposal did not validate: {exc} — adjust before applying.)"

    # Re-read before writing. Only the chat list is ours to change here.
    fresh = projects.load(project_id)
    chat_log = list(fresh.get("chat") or [])
    chat_log.append({"role": "user", "content": message, "ts": projects._now()})
    chat_log.append({"role": "assistant", "content": reply, "patch": patch, "ts": projects._now()})
    fresh["chat"] = chat_log[-200:]
    projects.save(fresh)
    return {"reply": reply, "patch": patch, "chat": fresh["chat"]}


async def suggest(description: str, name: str = "") -> dict:
    """One-shot: a free-text description in, a first full spec out. Powers the wizard's opening step
    so somebody who just wants to get going never has to see a query box empty."""
    description = (description or "").strip()
    if len(description) < 10:
        raise ValueError("describe the analysis in a sentence or two first")
    prompt = (
        f"PROJECT: {name or '(unnamed)'}\n\n"
        f"The scientist describes the analysis they want:\n\n\"{description[:MAX_MSG_CHARS]}\"\n\n"
        "Propose a complete first corpus spec for this. Write two or three sentences explaining the "
        "shape of the corpus you chose and what you left out, then the JSON block with "
        "scope, theme, queries, n_papers and (only if you are confident) seed_dois. If their "
        "description is phrased as a question, treat it as a signal about coverage — build the "
        "collection that could answer it, and do not restate the question anywhere in the spec."
        "\n\nYOU:"
    )
    raw = await _ask(prompt)
    reply, patch = _split_reply(raw)
    if not patch:
        raise AssistantUnavailable(
            "the assistant replied but proposed no spec. Try describing the field in more detail, "
            "or write the queries by hand.")
    projects.validate_spec({**projects.default_spec(), **patch})
    return {"reply": reply, "patch": patch}


def apply_patch(project_id: str, patch: dict) -> dict:
    """The human's accept action: merge an approved proposal into the stored spec."""
    if not isinstance(patch, dict):
        raise ValueError("patch must be an object")
    clean = {k: v for k, v in patch.items() if k in PATCHABLE}
    if not clean:
        raise ValueError("nothing in that proposal is a spec field")
    return projects.update(project_id, {"spec": clean})
