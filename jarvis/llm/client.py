"""Tier-aware LLM facade: picks a Provider from config, streams through it,
falls back across a chain of tiers on transient failures.

Callers (Session/orchestrator) never touch a specific vendor's SDK — they
call ``LLMClient.stream_reply(system_prompt, messages, on_text)`` and it's a
config change (``config/settings.yaml`` -> ``models.<tier>``), not a code
change, to swap which provider/model backs a tier. See jarvis/llm/factory.py
for how a tier resolves to a Provider instance.

Fallback (ARCHITECTURE.md §5.1/§5.2, M3-full): a tier can name a
``fallbacks.<tier>`` entry in settings pointing at another tier to retry on
failure, and that chain can be more than one hop (jarvis/llm/fallbacks.py's
``fallback_chain`` walks the map repeatedly -- e.g. t3_complex → t2_medium →
t1_standard). Each hop is gated by two things:

- ``is_transient``: only rate limits, connection/timeout errors, and 5xx/529
  responses are worth retrying against a different tier -- a 400 (bad
  request, our bug) or an auth error propagates immediately instead of
  wasting a turn on a fallback that can't help.
- **Nothing has streamed yet.** If a few words already reached ``on_text``
  (a mid-stream failure) and we retried, the fallback's reply would be
  interleaved with the primary's leftover fragment -- audibly garbled once
  it hits TTS. In that case the exception propagates and the caller's
  existing spoken-fallback handling (jarvis/core/orchestrator.py) degrades
  gracefully instead.

A process-wide :class:`~jarvis.llm.fallbacks.CircuitBreaker` tracks
consecutive failures per tier across every LLMClient/Router instance: three
in a row trips it for 5 minutes, and later calls skip straight past that
tier in the chain without even trying it.
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional

from jarvis.config import Settings, get_settings
from jarvis.llm.factory import build_provider
from jarvis.llm.fallbacks import CircuitBreaker, fallback_chain, get_circuit_breaker, is_transient
from jarvis.llm.providers import Provider
from jarvis.llm.types import ChatMessage, TurnResult

_EXPLICIT_FALLBACK_KEY = "__explicit_fallback__"


class LLMClient:
    def __init__(
        self,
        settings: Optional[Settings] = None,
        tier: str = "t1_standard",
        provider: Optional[Provider] = None,
        fallback_provider: Optional[Provider] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
    ):
        """
        Args:
            fallback_provider: an explicit single-hop override -- mainly for
                tests/manual wiring. When given, it's the only fallback tried
                (settings.fallbacks is ignored). Production call sites
                (Router, converse()) never pass this; they rely on the
                settings-driven, possibly multi-hop chain instead.
        """
        s = settings or get_settings()
        self.tier = tier
        self._settings = s
        self._breaker = circuit_breaker or get_circuit_breaker()
        self._providers: Dict[str, Provider] = {tier: provider or build_provider(s, tier)}

        if fallback_provider is not None:
            self._chain: List[str] = [tier, _EXPLICIT_FALLBACK_KEY]
            self._providers[_EXPLICIT_FALLBACK_KEY] = fallback_provider
        else:
            self._chain = [tier] + fallback_chain(s, tier)

    def _provider_for(self, tier: str) -> Provider:
        if tier not in self._providers:
            self._providers[tier] = build_provider(self._settings, tier)
        return self._providers[tier]

    async def stream_reply(
        self,
        system_prompt: str,
        messages: List[ChatMessage],
        on_text: Callable[[str], None],
    ) -> TurnResult:
        last_exc: Optional[Exception] = None

        for tier in self._chain:
            if self._breaker.is_open(tier):
                continue

            provider = self._provider_for(tier)
            emitted = False

            def tracking_on_text(chunk: str) -> None:
                nonlocal emitted
                emitted = True
                on_text(chunk)

            try:
                result = await provider.stream_reply(system_prompt, messages, tracking_on_text)
            except Exception as exc:  # noqa: BLE001 - classified by is_transient below
                self._breaker.record_failure(tier)
                last_exc = exc
                if emitted or not is_transient(exc):
                    raise
                continue

            self._breaker.record_success(tier)
            return result

        # Every tier in the chain was circuit-open, or the chain was empty.
        if last_exc is not None:
            raise last_exc
        raise RuntimeError(f"No available tier for {self.tier!r}: every tier's circuit is open")
