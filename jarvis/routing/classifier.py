"""Stage 2 routing — the tier classifier (ARCHITECTURE.md §2), provider-agnostic.

Only reached when Stage 1 heuristics (:mod:`jarvis.routing.heuristics`)
return ``None`` (RULE 5: ambiguous). One small-model call using the
``router`` tier from ``config/settings.yaml`` — Haiku 4.5 in anthropic mode,
a free OpenRouter/NVIDIA model in free mode. Going through
:class:`~jarvis.llm.client.LLMClient` (rather than any vendor SDK directly)
means the classifier automatically gets the router tier's own fallback chain
and circuit breaker, and flipping tier modes never touches this module.

Structured output: Anthropic's schema-enforced ``output_config`` isn't
available across all backends through the shared Provider interface, so the
"parsing can't fail" guarantee moved from API-level schema enforcement to
prompt-enforced JSON plus :func:`~jarvis.llm.parsing.extract_json_object`,
which digs the first JSON object out of prose, code fences, or think tags.
If even that fails, the caller falls back to a safe default tier rather
than letting a routing failure crash the conversation (see
jarvis/routing/router.py) — same fail-soft contract as before.
"""
from __future__ import annotations

from typing import Optional

from jarvis.config import Settings
from jarvis.llm.client import LLMClient
from jarvis.llm.parsing import extract_json_object
from jarvis.llm.types import ChatMessage

ROUTER_PROMPT = """You route a spoken user request to one of four model tiers.

T1: one-fact answers, short rewrites, casual chat, classification, a single
    obvious tool call.
T1.5: multi-step tool use, summarizing a document, drafting an email, most
    day-to-day agentic work.
T2: multi-step reasoning, coding, planning, research spanning many tool
    calls.
T3: hardest long-horizon work only — reserve this for requests that
    explicitly ask for maximum effort or are clearly beyond T2.

Pick the cheapest tier that can genuinely handle the request.

Respond with ONLY a single-line JSON object — no prose, no code fences:
{"tier": "T1" or "T1.5" or "T2" or "T3", "intent": "<3-6 word summary>", "tools_needed": ["<tool name>", ...]}"""

_TIER_BY_LABEL = {
    "T1": "t1_simple",
    "T1.5": "t1_standard",
    "T2": "t2_medium",
    "T3": "t3_complex",
}


async def classify(text: str, settings: Settings, llm: Optional[LLMClient] = None) -> str:
    """Ask the router-tier model which tier *text* belongs to.

    Returns a settings.yaml tier key (e.g. "t1_standard"). Raises on any
    failure — call errors, unparseable output, unknown label — and callers
    decide the fallback policy (see router.py); this function just reports
    what happened. *llm* is injectable for tests and so the Router can share
    its cached per-tier client.
    """
    if llm is None:
        llm = LLMClient(settings, tier="router")

    result = await llm.stream_reply(
        ROUTER_PROMPT,
        [ChatMessage(role="user", text=text)],
        lambda _chunk: None,  # classifier output is never spoken
    )
    parsed = extract_json_object(result.text)
    label = str(parsed["tier"]).strip().upper()
    return _TIER_BY_LABEL[label]
