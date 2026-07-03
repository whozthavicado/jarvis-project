"""M3-minimal main loop: listen -> Sonnet 5 (streaming) -> speak.

This is the first end-to-end voice *conversation* (ARCHITECTURE.md §8 step 2)
— unlike Milestone 1's echo, replies come from the model and conversation
history accumulates across turns. Still single-tier (Sonnet 5 only): no
routing (M2), no tools (M4), no memory (M5), no fallback ladder (M3 full).
A failed turn degrades to a spoken apology and the loop keeps listening
rather than crashing the whole session — the full error taxonomy from
ARCHITECTURE.md §5 lands with the fallback ladder in a later milestone.
"""
from __future__ import annotations

from typing import Callable, Optional

from jarvis.audio import Transcript, transcripts
from jarvis.config import Settings, get_settings
from jarvis.core.session import Session
from jarvis.llm import LLMClient, TurnResult
from jarvis.speech import Speaker


def _fallback_text_for(exc: Exception) -> str:
    """Map an LLM-call failure to a short, speakable apology."""
    import anthropic

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
    return "Something went wrong there. Let's try that again."


async def handle_turn(
    session: Session,
    llm: LLMClient,
    transcript: Transcript,
    on_text: Callable[[str], None],
) -> Optional[TurnResult]:
    """Process one user turn against *session*, streaming the reply to on_text.

    Returns the TurnResult on success, or None if the call failed (a spoken
    fallback has already been sent to on_text in that case). Split out from
    :func:`converse` so it's unit-testable without real audio or TTS.
    """
    session.add_user_turn(transcript.text)
    try:
        result = await llm.stream_reply(session.system_blocks, session.messages, on_text)
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
    tier: str = "sonnet",
    on_turn: Optional[Callable[[Transcript, Optional[TurnResult]], None]] = None,
) -> None:
    """Run the live listen -> reply -> speak loop until cancelled.

    Args:
        settings: override settings (defaults to global config).
        tier: which Layer B addendum to use (only "sonnet" exists so far).
        on_turn: optional callback fired after each turn (transcript, result)
            for logging/printing; result is None if the turn errored.
    """
    s = settings or get_settings()
    session = Session(tier=tier)
    llm = LLMClient(s)

    async with Speaker(s) as speaker:
        async for t in transcripts(s):
            result = await handle_turn(session, llm, t, speaker.feed)
            await speaker.flush()
            if on_turn is not None:
                on_turn(t, result)
