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

M2 adds per-turn routing across T1-T3 via an optional ``router``
(:class:`jarvis.routing.Router`). When one is passed, ``handle_turn``
resolves a tier fresh each turn (Stage 1 heuristics, Stage 2 Haiku
classifier) instead of using the session's fixed construction-time tier —
conversation history still lives on the one ``Session``, but which
model/system-prompt answers a given turn can now vary turn to turn. Without
a router, behavior is unchanged from before: one tier, fixed for the whole
session, exactly as ``llm`` and ``session`` were built for.

M5 adds persistent memory (ARCHITECTURE.md §4): ``converse`` now builds its
``Session`` against the process-wide MemoryStore
(:func:`jarvis.memory.get_store`), so every turn is logged to SQLite, the
first turn's context block picks up the core digest + FTS recall, and each
turn compacts the session's history once it's grown large. The session is
closed out (Haiku summary + sessions.ended_at) when the listen loop ends.

M3-full adds the daily budget guard (ARCHITECTURE.md §5.5) via an optional
``budget``. Hard cap hit: the turn is forced onto ``t1_simple`` (the $0
tier) if a router is available to do that rerouting, and a spoken notice
leads the reply. Soft cap hit on a T2+ tier: the turn proceeds on its
resolved tier, but with a spoken heads-up first -- there's no voice
confirmation channel yet, so "requires confirmation" is implemented here as
"is surfaced audibly", not a yes/no gate. Without a ``budget``, behavior is
unchanged (unlimited), which is what every pre-M3-full test still exercises.

Hardening adds offline mode (ARCHITECTURE.md §5.1's last rung) via an
optional ``offline`` ConnectivityMonitor. A T0 grammar match still runs --
it never leaves the machine -- but an LLM-bound turn while offline
short-circuits to a spoken "I'm offline" notice instead of paying a connect
timeout, and (like T0) never touches session history. A turn that dies on a
transport-level error marks the monitor offline so the *next* turn
short-circuits immediately; recovery is automatic once the monitor's cache
TTL expires and a probe succeeds. Without ``offline``, behavior is unchanged.
"""
from __future__ import annotations

from typing import Callable, Optional

from jarvis.audio import Transcript, transcripts
from jarvis.config import Settings, get_settings
from jarvis.core.budget import BudgetGuard, get_budget_guard
from jarvis.core.offline import ConnectivityMonitor, get_connectivity_monitor
from jarvis.core.session import Session
from jarvis.llm import LLMClient, TurnResult
from jarvis.memory import get_store
from jarvis.routing import Router, match as match_t0
from jarvis.speech import Speaker
from jarvis.tools import execute as execute_tool
from jarvis.tools.registry import ConfirmFn

_HARD_CAP_NOTICE = "Running in reduced mode — today's budget is used up: "
_SOFT_CAP_NOTICE = "Heads up, we're near today's budget for the heavier models — continuing anyway: "
_BUDGET_FALLBACK_TIER = "t1_simple"
_OFFLINE_NOTICE = "I'm offline — I can still control the Mac."


def _is_connection_error(exc: Exception) -> bool:
    """Transport-level failure = evidence we're offline (§5.1's last rung)."""
    import anthropic
    import httpx

    return isinstance(exc, (anthropic.APIConnectionError, httpx.TransportError))


def _fallback_text_for(exc: Exception) -> str:
    """Map an LLM-call failure to a short, speakable apology."""
    import anthropic
    import httpx

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
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code in (401, 403):
            return "My model backend rejected my credentials — check the API key setup."
        if code == 429:
            return "I'm being rate limited. Give me a moment and try again."
        return "Something went wrong on the server side. Let's try that again."
    if isinstance(exc, httpx.TransportError):
        return "I can't reach the cloud right now."
    return "Something went wrong there. Let's try that again."


async def handle_turn(
    session: Session,
    llm: LLMClient,
    transcript: Transcript,
    on_text: Callable[[str], None],
    tool_confirm: Optional[ConfirmFn] = None,
    router: Optional[Router] = None,
    budget: Optional[BudgetGuard] = None,
    offline: Optional[ConnectivityMonitor] = None,
) -> Optional[TurnResult]:
    """Process one user turn against *session*, streaming the reply to on_text.

    Returns the TurnResult on success, or None if the call failed (a spoken
    fallback has already been sent to on_text in that case). Split out from
    :func:`converse` so it's unit-testable without real audio or TTS.

    A T0 grammar match (RULE 0) short-circuits this entirely: the matched
    tool runs locally, its result is spoken, and neither the LLM nor the
    session's history is touched — that turn returns a synthetic TurnResult
    with model="t0" so callers can tell T0 turns apart from real LLM turns.

    If *router* is given, it (not ``llm``/``session.system_prompt``) decides
    which tier and LLMClient handle this specific turn — ``llm`` is then only
    used as history's tier-agnostic bookkeeping; per M2 (ARCHITECTURE.md
    §2), routing runs fresh every turn, not once per session.
    """
    t0_call = match_t0(transcript.text)
    if t0_call is not None:
        result = await execute_tool(t0_call, confirm=tool_confirm)
        on_text(result.content)
        return TurnResult(text=result.content, model="t0", stop_reason="t0_command")

    if offline is not None and not await offline.is_online():
        on_text(_OFFLINE_NOTICE)
        return TurnResult(text=_OFFLINE_NOTICE, model="offline", stop_reason="offline")

    session.add_user_turn(transcript.text)

    if router is not None:
        tier = await router.resolve(transcript.text)
        turn_llm = router.llm_for(tier)
        system_prompt = router.system_prompt_for(tier)
    else:
        tier = llm.tier
        turn_llm = llm
        system_prompt = session.system_prompt

    notice = ""
    if budget is not None:
        if budget.hard_cap_hit():
            notice = _HARD_CAP_NOTICE
            if router is not None and tier != _BUDGET_FALLBACK_TIER:
                tier = _BUDGET_FALLBACK_TIER
                turn_llm = router.llm_for(tier)
                system_prompt = router.system_prompt_for(tier)
        elif budget.needs_confirmation(tier):
            notice = _SOFT_CAP_NOTICE

    if notice:
        on_text(notice)

    try:
        result = await turn_llm.stream_reply(system_prompt, session.messages, on_text)
    except Exception as exc:  # noqa: BLE001 - deliberately broad; see _fallback_text_for
        if offline is not None and _is_connection_error(exc):
            offline.mark_offline()
        on_text(_fallback_text_for(exc))
        return None

    if result.refused or not result.text:
        on_text("I'd rather not answer that.")
        return result

    if budget is not None:
        budget.record(result)

    session.add_assistant_turn(result.text)
    await session.compact_if_needed()
    return result


async def converse(
    settings: Optional[Settings] = None,
    tier: str = "t1_standard",
    on_turn: Optional[Callable[[Transcript, Optional[TurnResult]], None]] = None,
    route: bool = True,
) -> None:
    """Run the live listen -> reply -> speak loop until cancelled.

    Args:
        settings: override settings (defaults to global config).
        tier: fallback tier used when *route* is False, and for the
            session's own construction-time system prompt (unused for the
            actual LLM call when routing is on — see *route*).
        on_turn: optional callback fired after each turn (transcript, result)
            for logging/printing; result is None if the turn errored.
        route: when True (default), each turn is routed independently across
            T1-T3 by a :class:`jarvis.routing.Router` (ARCHITECTURE.md §2).
            Set False to pin the whole conversation to *tier*, as before M2.
    """
    s = settings or get_settings()
    session = Session(tier=tier, store=get_store(s))
    llm = LLMClient(s, tier=tier)
    router = Router(s) if route else None
    budget = get_budget_guard(s)
    offline = get_connectivity_monitor(s)

    try:
        async with Speaker(s) as speaker:
            async for t in transcripts(s):
                result = await handle_turn(
                    session,
                    llm,
                    t,
                    speaker.feed,
                    router=router,
                    budget=budget,
                    offline=offline,
                )
                await speaker.flush()
                if on_turn is not None:
                    on_turn(t, result)
    finally:
        await session.close(s)
