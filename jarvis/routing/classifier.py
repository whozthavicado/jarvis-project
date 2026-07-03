"""Stage 2 routing — the Haiku structured-output classifier (ARCHITECTURE.md §2).

Only reached when Stage 1 heuristics (:mod:`jarvis.routing.heuristics`)
return ``None`` (RULE 5: ambiguous). One Haiku call, ~$0.0005, with
structured JSON output so parsing can't fail on stray prose.

Uses the ``router`` tier from ``config/settings.yaml`` (Haiku 4.5) — not one
of the four conversation tiers, this is purely the classifier's own model.
The ``anthropic`` SDK is imported lazily, same reasoning as the other
providers: this module stays importable with no credentials configured.

Failure here (no credentials, network error, malformed response) is not
fatal to the turn — the caller falls back to a safe default tier rather than
letting a routing failure crash the conversation (see jarvis/routing/router.py).
"""
from __future__ import annotations

import json
from typing import Optional

from jarvis.config import Settings

ROUTER_PROMPT = """You route a spoken user request to one of four model tiers.

T1: one-fact answers, short rewrites, casual chat, classification, a single
    obvious tool call.
T1.5: multi-step tool use, summarizing a document, drafting an email, most
    day-to-day agentic work.
T2: multi-step reasoning, coding, planning, research spanning many tool
    calls.
T3: hardest long-horizon work only — reserve this for requests that
    explicitly ask for maximum effort or are clearly beyond T2.

Pick the cheapest tier that can genuinely handle the request."""

_TIER_BY_LABEL = {
    "T1": "t1_simple",
    "T1.5": "t1_standard",
    "T2": "t2_medium",
    "T3": "t3_complex",
}

_SCHEMA = {
    "type": "object",
    "properties": {
        "tier": {"type": "string", "enum": ["T1", "T1.5", "T2", "T3"]},
        "intent": {"type": "string"},
        "tools_needed": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["tier", "intent", "tools_needed"],
    "additionalProperties": False,
}


async def classify(text: str, settings: Settings, client: Optional[object] = None) -> str:
    """Ask the Haiku router model which tier *text* belongs to.

    Returns a settings.yaml tier key (e.g. "t1_standard"). Raises on
    failure — callers decide the fallback policy (see router.py), this
    function just reports what happened.
    """
    cfg = settings.models["router"]

    if client is None:
        import anthropic  # lazy: requires credentials to actually call

        client = anthropic.AsyncAnthropic()

    response = await client.messages.create(
        model=str(cfg.model),
        max_tokens=int(cfg.get("max_tokens", 1000)),
        system=ROUTER_PROMPT,
        messages=[{"role": "user", "content": text}],
        output_config={"format": {"type": "json_schema", "schema": _SCHEMA}},
    )

    raw = "".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    )
    parsed = json.loads(raw)
    label = parsed["tier"]
    return _TIER_BY_LABEL[label]
