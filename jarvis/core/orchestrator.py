"""Main loop: listen -> T0 grammar or LLM (streaming, tier-selected) -> speak.

This is still single-tier per session (no automatic routing yet — that's the
M2 module, a later milestone): the caller picks a tier for the whole
conversation. What's new since Milestone 2's first cut is that a tier's
provider is no longer hardcoded to Anthropic — see jarvis/llm/factory.py.
A failed turn degrades to a spoken apology and the loop keeps listening
rather than crashing the whole session; LLMClient itself may have already
tried a same-turn fallback (e.g. OpenRouter free -> Sonnet 5) before this
code ever sees an exception — see jarvis/llm/client.py.

M4 adds RULE 0 (ARCHITECTURE.md §2): before any of that, a transcript is
checked against the T0 command grammar. A match executes a tool locally
with no API call and no session/history mutation at all — T0 turns are not
part of the conversation the LLM sees.
"""
from __future__ import annotations

from typing import Callable, Optional

from jarvis.audio import Transcript, transcripts
from jarvis.config import Settings, get_settings
from jarvis.core.session import Session
from jarvis.llm import LLMClient, TurnResult
from jarvis.routing import match as match_t0
from jarvis.speech import Speaker
from jarvis.tools import execute as execute_tool
from jarvis.tools.registry import ConfirmFn


def _fallback_text_for(exc: Exception) -> str:
    """Map an LLM-call failure to a short, speakable apology."""
    import anthropic

    from jarvis.llm.providers import OpenRouterError

    if isinstance(exc, anthropic.AuthenticationError):
        return "I can't reach Claude — my API credentials aren't set up."
    if isinstance(exc, anthropic.PermissionDeniedError):
        return "I'm not authorized to use that model right now."
    if isinstance(exc, anthropic.RateLimitError):
        return "I'm being rate limited. Give me a moment and try again."
    if isinstance(exc, anthropic.APIConnectionError):
        return "I can't reach the cloud right now."
    if isinstance(exc, anthropic.APIStatusError):
        return "Something went wrong on the server side. Let's try that again."
    if isinstance(exc, OpenRouterError):
        return "My free model backend had trouble with that. Let's try again."
    return "Something went wrong there. Let's try that again."


async def handle_turn(
    session: Session,
    llm: LLMClient,
    transcript: Transcript,
    on_text: Callable[[str], None],
    tool_confirm: Optional[ConfirmFn] = None,
) -> Optional[TurnResult]:
    """Process one user turn against *session*, streaming the reply to on_text.

    Returns the TurnResult on success, or None if the call failed (a spoken
    fallback has already been sent to on_text in that case). Split out from
    :func:`converse` so it's unit-testable without real audio or TTS.

    A T0 grammar match (RULE 0) short-circuits this entirely: the matched
    tool runs locally, its result is spoken, and neither the LLM nor the
    session's history is touched — that turn returns a synthetic TurnResult
    with model="t0" so callers can tell T0 turns apart from real LLM turns.
    """
    t0_call = match_t0(transcript.text)
    if t0_call is not None:
        result = await execute_tool(t0_call, confirm=tool_confirm)
        on_text(result.content)
        return TurnResult(text=result.content, model="t0", stop_reason="t0_command")

    session.add_user_turn(transcript.text)
    try:
        result = await llm.stream_reply(session.system_prompt, session.messages, on_text)
    except Exception as exc:  # noqa: BLE001 - deliberately broad; see _fallback_text_for
        on_text(_fallback_text_for(exc))
        return None

    if result.refused or not result.text:
        on_text("I'd rather not answer that.")
        return result

    session.add_assistant_turn(result.text)
    return result


async def converse(
    settings: Optional[Settings] = None,
    tier: str = "t1_standard",
    on_turn: Optional[Callable[[Transcript, Optional[TurnResult]], None]] = None,
) -> None:
    """Run the live listen -> reply -> speak loop until cancelled.

    Args:
        settings: override settings (defaults to global config).
        tier: which configured tier to converse on (see
            config/settings.yaml -> models). No automatic routing between
            tiers yet — that's a later milestone.
        on_turn: optional callback fired after each turn (transcript, result)
            for logging/printing; result is None if the turn errored.
    """
    s = settings or get_settings()
    session = Session(tier=tier)
    llm = LLMClient(s, tier=tier)

    async with Speaker(s) as speaker:
        async for t in transcripts(s):
            result = await handle_turn(session, llm, t, speaker.feed)
            await speaker.flush()
            if on_turn is not None:
                on_turn(t, result)
