"""The LLM seam. All in-loop model calls go through here.

Path: the Claude Agent SDK over the installed `claude` CLI login; no API key. Prompt caching is automatic
(the SDK inserts cache_control on system prompt, tools and history). The lever we control is session
shape: a resumable `Session` caches its growing context turn over turn. `ResultMessage.usage` is read to
report real cache hit rates. Model routing: OPUS for scientific judgment, SONNET for bulk extraction.
"""
from __future__ import annotations

import asyncio
import base64
import struct
import json
import os
import re
from dataclasses import dataclass, field

from claude_agent_sdk import (AssistantMessage, ClaudeAgentOptions, ClaudeSDKClient,
                              ResultMessage, TextBlock, ThinkingBlock, query)

# Pinned model ids.
OPUS = "claude-opus-5"
SONNET = "claude-sonnet-5"


@dataclass
class UsageLedger:
    """Accumulates token usage across every call in a run → token and cache-hit reporting."""
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read: int = 0
    cache_creation: int = 0
    by_model: dict = field(default_factory=dict)

    def add(self, model: str, u: dict) -> None:
        self.calls += 1
        self.input_tokens += u.get("input_tokens", 0) or 0
        self.output_tokens += u.get("output_tokens", 0) or 0
        self.cache_read += u.get("cache_read_input_tokens", 0) or 0
        self.cache_creation += u.get("cache_creation_input_tokens", 0) or 0
        m = self.by_model.setdefault(model, {"calls": 0, "in": 0, "out": 0, "cache_read": 0})
        m["calls"] += 1
        m["in"] += u.get("input_tokens", 0) or 0
        m["out"] += u.get("output_tokens", 0) or 0
        m["cache_read"] += u.get("cache_read_input_tokens", 0) or 0

    def summary(self) -> dict:
        cached_in = self.cache_read + self.cache_creation
        total_in = self.input_tokens + cached_in
        hit = self.cache_read / total_in if total_in else 0.0
        return {"calls": self.calls, "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens, "cache_read": self.cache_read,
                "cache_creation": self.cache_creation, "cache_hit_rate": round(hit, 3),
                "by_model": self.by_model}


# a process-global ledger so every call is accounted for; the orchestrator reads it at the end
LEDGER = UsageLedger()

MAX_OUTPUT_TOKENS = 64000  # Legacy ingestion diagnostic; not a global SDK output override.



def _opts(model: str, system: str | None, effort: str, max_turns: int, thinking=None,
          resume: str | None = None, *, tools_disabled: bool = False,
          max_output_tokens: int | None = None, cwd: str | None = None) -> ClaudeAgentOptions:
    # `resume` re-opens an existing session by its UUID (the transcript on disk) instead of starting
    # fresh. A forked child branch is entered this way: fork_session() copies the parent transcript into a
    # new UUID, and resuming that UUID gives the child the cached ancestor context.
    return ClaudeAgentOptions(
        model=model, system_prompt=system, effort=effort, max_turns=max_turns,
        allowed_tools=[], permission_mode="bypassPermissions", setting_sources=[], thinking=thinking,
        resume=resume, tools=[] if tools_disabled else None,
        strict_mcp_config=tools_disabled, cwd=cwd,
        env=({"CLAUDE_CODE_MAX_OUTPUT_TOKENS": str(max_output_tokens)}
             if max_output_tokens is not None else {}))


def _block_to_dict(b) -> dict:
    """Serialize one content block to a plain JSON-able dict for the raw transcript."""
    if isinstance(b, TextBlock):
        return {"type": "text", "text": b.text}
    if isinstance(b, ThinkingBlock):
        return {"type": "thinking", "thinking": b.thinking}
    d = {"type": type(b).__name__}
    for a in ("name", "input", "id", "tool_use_id", "content"):        # tool-use / tool-result blocks
        if hasattr(b, a):
            d[a] = getattr(b, a)
    return d


def _msg_to_dict(msg) -> dict:
    """Serialize one SDK message (assistant/result/user/system) for the guaranteed-faithful transcript."""
    if isinstance(msg, AssistantMessage):
        return {"type": "AssistantMessage", "content": [_block_to_dict(b) for b in msg.content]}
    if isinstance(msg, ResultMessage):
        return {"type": "ResultMessage", "usage": msg.usage}
    d = {"type": type(msg).__name__}
    c = getattr(msg, "content", None)
    if c is not None:
        d["content"] = [_block_to_dict(b) for b in c] if isinstance(c, list) else str(c)
    return d


def image_prompt(prompt: str, images: list[bytes] | None):
    """SDK image-bearing user message; paths and prose are never treated as pixels."""
    if not images:
        return prompt
    if not isinstance(images, list) or len(images) > 2:
        raise ValueError("Vision observation accepts one or two PNG images")
    content = [{"type": "text", "text": prompt}]
    for raw in images:
        if not isinstance(raw, bytes) or len(raw) > 8 * 1024 * 1024 or len(raw) < 33 or raw[:8] != b"\x89PNG\r\n\x1a\n" or raw[12:16] != b"IHDR":
            raise ValueError("Vision observation requires bounded PNG bytes")
        width, height = struct.unpack(">II", raw[16:24])
        if not 1 <= width <= 1920 or not 1 <= height <= 1080:
            raise ValueError("Vision image dimensions exceed 1920 by 1080")
        content.append({"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                                  "data": base64.b64encode(raw).decode()}})
    async def stream():
        yield {"type": "user", "message": {"role": "user", "content": content},
               "parent_tool_use_id": None}
    return stream()


async def acomplete(prompt: str, *, model: str = OPUS, system: str | None = None,
                    effort: str = "medium", max_turns: int = 6, thinking: bool = False,
                    capture: dict | None = None, tools_disabled: bool = False,
                    max_output_tokens: int | None = None, max_attempts: int = 3,
                    cwd: str | None = None, images: list[bytes] | None = None) -> str:
    """One-shot completion. Returns the final text; records usage in the global LEDGER. Retries transient
    SDK errors.

    `thinking=True` turns on extended thinking so the model's reasoning is produced as thinking blocks
    rather than only the self-reported field a caller might ask it to write.
    Pass a `capture` dict to receive {text, thinking, messages}: `thinking` is the concatenated thinking
    blocks; `messages` is the raw SDK message stream (the faithful record of the exchange).
    Controlled experiments can disable all tools/MCP servers, use an empty cwd,
    and set per-call output and attempt ceilings without changing process-global settings.
    `allowed_tools=[]` alone is not a tool-disable switch in the SDK."""
    if type(max_attempts) is not int or max_attempts < 1:
        raise ValueError("max_attempts must be a positive integer")
    if max_output_tokens is not None and (type(max_output_tokens) is not int or max_output_tokens < 1):
        raise ValueError("max_output_tokens must be a positive integer")
    tconf = {"type": "adaptive"} if thinking else None
    last = None
    for attempt in range(max_attempts):
        if capture is not None:
            capture["attempts"] = attempt + 1
        try:
            text, think, msgs = "", "", []
            async for msg in query(prompt=image_prompt(prompt, images), options=_opts(
                    model, system, effort, max_turns, tconf, tools_disabled=tools_disabled,
                    max_output_tokens=max_output_tokens, cwd=cwd)):
                if isinstance(msg, AssistantMessage):
                    for b in msg.content:
                        if isinstance(b, TextBlock):
                            text += b.text
                        elif isinstance(b, ThinkingBlock):
                            think += b.thinking
                elif isinstance(msg, ResultMessage):
                    LEDGER.add(model, msg.usage or {})
                if capture is not None:
                    msgs.append(_msg_to_dict(msg))
            if text.strip():
                if capture is not None:
                    capture.update(text=text.strip(), thinking=think, messages=msgs)
                return text.strip()
            last = RuntimeError("empty completion")
        except Exception as e:
            last = e
        if attempt + 1 < max_attempts:
            await asyncio.sleep(1.5 * (attempt + 1))
    raise last


class Session:
    """A resumable conversation: context caches turn over turn, so each `ask` pays only for the new tokens
    while the model keeps its full history in view. This is the explorer's working memory (one session per
    run; fork it for a divergent branch, see claude_agent_sdk.fork_session).
    Use as: `async with Session(system=..., model=OPUS, thinking=True) as s: r = await s.ask("...")`."""

    def __init__(self, system: str | None = None, model: str = OPUS, effort: str = "high",
                 max_turns: int = 6, thinking: bool = False, resume: str | None = None,
                 tools_disabled: bool = False, max_output_tokens: int | None = None):
        self.model = model
        # Did the last `ask` hit the output ceiling? A response cut off mid-token is an unknown answer,
        # not a shorter one, so truncation is surfaced rather than salvaged silently.
        self.truncated = False
        # The live session UUID the SDK assigns this conversation, learned from the response messages on
        # the first ask (None until then). It is the handle a divergent branch forks from
        # (claude_agent_sdk.fork_session(session_id)), distinct from the path-encoded run_id.
        self.session_id: str | None = None
        tconf = {"type": "adaptive"} if thinking else None
        self._output_limit = max_output_tokens
        self._client = ClaudeSDKClient(_opts(model, system, effort, max_turns, tconf, resume=resume,
                                            tools_disabled=tools_disabled, max_output_tokens=max_output_tokens))

    async def __aenter__(self):
        await self._client.connect()
        return self

    async def __aexit__(self, *exc):
        await self._client.disconnect()

    async def ask(self, prompt: str, capture: dict | None = None, *, images: list[bytes] | None = None) -> str:
        """One turn on the persistent conversation. Records usage in the global LEDGER. Pass a `capture`
        dict to receive {text, thinking, messages} (same shape as acomplete) for the reasoning trace."""
        text, think, msgs = "", "", []
        self.truncated = False
        await self._client.query(image_prompt(prompt, images))
        async for msg in self._client.receive_response():
            # every SDK message carries the live session UUID; capture it so a running branch knows its own
            # fork handle (the first non-None wins and is stable for the session's life).
            sid = getattr(msg, "session_id", None)
            if sid and not self.session_id:
                self.session_id = sid
            if isinstance(msg, AssistantMessage):
                for b in msg.content:
                    if isinstance(b, TextBlock):
                        text += b.text
                    elif isinstance(b, ThinkingBlock):
                        think += b.thinking
            elif isinstance(msg, ResultMessage):
                LEDGER.add(self.model, msg.usage or {})
                if self._output_limit is not None and (msg.usage or {}).get("output_tokens", 0) >= self._output_limit:
                    self.truncated = True
            if capture is not None:
                msgs.append(_msg_to_dict(msg))
        if capture is not None:
            capture.update(text=text.strip(), thinking=think, messages=msgs)
        return text.strip()


# --- structured-output helpers ------------------------------------------------------------------
_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def parse_json(text: str):
    """Robustly pull a JSON object/array out of a model reply (handles ```json fences + stray prose)."""
    m = _JSON_FENCE.search(text)
    if m:
        text = m.group(1)
    # find the outermost {...} or [...]
    for opener, closer in (("{", "}"), ("[", "]")):
        i, j = text.find(opener), text.rfind(closer)
        if i != -1 and j != -1 and j > i:
            try:
                return json.loads(text[i:j + 1])
            except json.JSONDecodeError:
                continue
    return json.loads(text)  # last resort: raise informative error
