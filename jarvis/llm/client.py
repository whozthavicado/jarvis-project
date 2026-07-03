"""Tier-aware LLM facade: picks a Provider from config, streams through it.

Callers (Session/orchestrator) never touch a specific vendor's SDK — they
call ``LLMClient.stream_reply(system_prompt, messages, on_text)`` and it's a
config change (``config/settings.yaml`` -> ``models.<tier>``), not a code
change, to swap which provider/model backs a tier. See jarvis/llm/factory.py
for how a tier resolves to a Provider instance.

Fallback: a tier can name a ``fallbacks.<tier>`` entry in settings pointing
at another tier to retry on failure. Currently only "t1_simple" (OpenRouter
free) has one, pointing at "t1_standard" (Sonnet 5, paid) — the free-model
catalog rotates and can be rate-limited or withdrawn with little notice (see
the OpenRouter research behind this design), so treat that failure as
expected, not exceptional.

The fallback is deliberately conservative about streaming: it only retries
if the primary provider failed *before* emitting any text. If a few words
had already reached ``on_text`` (a mid-stream failure) and we retried, the
fallback's reply would be interleaved with the primary's leftover fragment —
audibly garbled once it hits TTS. In that case we just let the exception
propagate (the caller's existing spoken-fallback handling, see
jarvis/core/orchestrator.py, still degrades gracefully — it just won't be a
seamless retry).
"""
from __future__ import annotations

from typing import Callable, List, Optional

from jarvis.config import Settings, get_settings
from jarvis.llm.factory import build_provider
from jarvis.llm.providers import Provider
from jarvis.llm.types import ChatMessage, TurnResult


def _resolve_fallback_tier(settings: Settings, tier: str) -> Optional[str]:
    fallbacks = settings.get("fallbacks", {})
    if tier in fallbacks:
        return str(fallbacks[tier])
    return None


class LLMClient:
    def __init__(
        self,
        settings: Optional[Settings] = None,
        tier: str = "t1_standard",
        provider: Optional[Provider] = None,
        fallback_provider: Optional[Provider] = None,
    ):
        s = settings or get_settings()
        self.tier = tier
        self._provider: Provider = provider or build_provider(s, tier)

        if fallback_provider is not None:
            self._fallback_provider: Optional[Provider] = fallback_provider
        else:
            fallback_tier = _resolve_fallback_tier(s, tier)
            self._fallback_provider = build_provider(s, fallback_tier) if fallback_tier else None

    async def stream_reply(
        self,
        system_prompt: str,
        messages: List[ChatMessage],
        on_text: Callable[[str], None],
    ) -> TurnResult:
        emitted = False

        def tracking_on_text(chunk: str) -> None:
            nonlocal emitted
            emitted = True
            on_text(chunk)

        try:
            return await self._provider.stream_reply(system_prompt, messages, tracking_on_text)
        except Exception:
            if self._fallback_provider is None or emitted:
                raise
            return await self._fallback_provider.stream_reply(system_prompt, messages, on_text)
