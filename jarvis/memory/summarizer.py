"""Haiku session summaries + history compaction (ARCHITECTURE.md §4.2, M5).

Two related jobs, both riding the ``router`` tier's Haiku config from
``config/settings.yaml`` (the same classifier-only model
jarvis/routing/classifier.py uses -- summarization isn't a conversation
tier, so it doesn't need its own settings.models entry):

- ``summarize``: one ~$0.001 call condensing a batch of turns to <=150
  tokens, used both at session end (see Session.close) and by ``compact``.
- ``compact``: "when history exceeds ~6K tokens, replace turns older than
  the last 6 with a Haiku-generated summary block" -- a fixed window plus
  one summary, not server-side compaction, for predictable token cost at
  this scale.

The ``anthropic`` SDK is imported lazily, same reasoning as elsewhere in
jarvis/llm and jarvis/routing: this module stays importable with no
credentials configured.
"""
from __future__ import annotations

from typing import List, Optional

from jarvis.config import Settings, get_settings
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
    client: Optional[object] = None,
) -> str:
    """One Haiku call summarizing *messages*. Raises on failure -- callers
    (Session.close, compact) decide what a summarization failure means for
    them; this function just reports what happened."""
    s = settings or get_settings()
    cfg = s.models["router"]

    if client is None:
        import anthropic  # lazy: requires credentials to actually call

        client = anthropic.AsyncAnthropic()

    transcript = "\n".join(f"{m.role}: {m.text}" for m in messages)
    response = await client.messages.create(
        model=str(cfg.model),
        max_tokens=200,
        system=SUMMARIZER_PROMPT,
        messages=[{"role": "user", "content": transcript}],
    )
    return "".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    ).strip()


async def compact(
    history: List[ChatMessage],
    settings: Optional[Settings] = None,
    client: Optional[object] = None,
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
        summary_text = await summarize(older, settings=settings, client=client)
    except Exception:  # noqa: BLE001 - see docstring
        return recent

    summary_message = ChatMessage(
        role="user",
        text=f"<summary of earlier conversation>\n{summary_text}\n</summary>",
    )
    return [summary_message] + recent
