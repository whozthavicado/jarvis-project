"""Session summaries + history compaction (ARCHITECTURE.md §4.2, M5),
provider-agnostic since the free-mode restructure.

Two related jobs, both riding the ``router`` tier's small-model config from
``config/settings.yaml`` (the same one jarvis/routing/classifier.py uses --
summarization isn't a conversation tier, so it doesn't need its own
settings.models entry). In anthropic mode that's Haiku 4.5; in free mode a
free OpenRouter/NVIDIA model. Calls go through
:class:`~jarvis.llm.client.LLMClient`, so the summarizer inherits the router
tier's fallback chain and circuit breaker, and never imports a vendor SDK.

- ``summarize``: one small-model call condensing a batch of turns to <=150
  tokens, used both at session end (see Session.close) and by ``compact``.
- ``compact``: "when history exceeds ~6K tokens, replace turns older than
  the last 6 with a summary block" -- a fixed window plus one summary, not
  server-side compaction, for predictable token cost at this scale.
"""
from __future__ import annotations

from typing import List, Optional

from jarvis.config import Settings, get_settings
from jarvis.llm.client import LLMClient
from jarvis.llm.parsing import strip_think
from jarvis.llm.types import ChatMessage

SUMMARIZER_PROMPT = (
    "Summarize this excerpt of a spoken conversation in 150 tokens or fewer. "
    "Preserve names, decisions, and facts that matter for continuing the "
    "conversation later. Plain prose, no markdown."
)

_CHARS_PER_TOKEN = 4  # rough approximation, good enough for a compaction trigger


def _approx_tokens(messages: List[ChatMessage]) -> int:
    return sum(len(m.text) for m in messages) // _CHARS_PER_TOKEN


async def summarize(
    messages: List[ChatMessage],
    settings: Optional[Settings] = None,
    llm: Optional[LLMClient] = None,
) -> str:
    """One router-tier call summarizing *messages*. Raises on failure --
    callers (Session.close, compact) decide what a summarization failure
    means for them; this function just reports what happened."""
    s = settings or get_settings()
    if llm is None:
        llm = LLMClient(s, tier="router")

    transcript = "\n".join(f"{m.role}: {m.text}" for m in messages)
    result = await llm.stream_reply(
        SUMMARIZER_PROMPT,
        [ChatMessage(role="user", text=transcript)],
        lambda _chunk: None,  # summaries are stored, never spoken
    )
    return strip_think(result.text).strip()


async def compact(
    history: List[ChatMessage],
    settings: Optional[Settings] = None,
    llm: Optional[LLMClient] = None,
    keep_last: int = 6,
    token_threshold: int = 6000,
) -> List[ChatMessage]:
    """Return *history*, compacted if it's grown past *token_threshold*.

    If summarization itself fails (no credentials, network error), falls
    back to plain truncation -- dropping the older turns without a summary
    block -- rather than raising. A degraded conversation window beats
    crashing the turn, consistent with the rest of the codebase's fail-soft
    posture (see orchestrator.py's _fallback_text_for).
    """
    if len(history) <= keep_last or _approx_tokens(history) <= token_threshold:
        return history

    older, recent = history[:-keep_last], history[-keep_last:]
    try:
        summary_text = await summarize(older, settings=settings, llm=llm)
    except Exception:  # noqa: BLE001 - see docstring
        return recent

    summary_message = ChatMessage(
        role="user",
        text=f"<summary of earlier conversation>\n{summary_text}\n</summary>",
    )
    return [summary_message] + recent
