"""Model fallback ladder + per-tier circuit breaker (ARCHITECTURE.md §5.1/§5.2, M3-full).

Two pieces LLMClient (client.py) composes on every call:

- ``is_transient``: whether a failure is worth falling back on at all. Per
  the §5.2 error taxonomy, rate limits, connection/timeout issues, and
  5xx/529 server errors are transient (the next tier might just work); a 4xx
  like a bad API key or a malformed request is not (fmt. "400
  invalid_request_error: bug, not transient — never retry") -- retrying
  those against a *different* tier wastes a turn and produces a confusing
  double failure, so LLMClient lets them propagate immediately instead.

- ``CircuitBreaker``: "3 consecutive failures → mark model down for 5
  minutes, route around it, re-probe after" (§5.2). Process-wide (see
  ``get_circuit_breaker``) so it's shared across every LLMClient/Router
  instance in the process, not reset every time a new one is built.

``fallback_chain`` walks ``settings.yaml``'s ``fallbacks`` map repeatedly
from a starting tier, so a tier can degrade through more than one hop (e.g.
t3_complex → t3_complex_nvidia → t2_medium) -- a cycle guard stops it from
bouncing back and forth between two tiers that fall back to each other.
Like ``models``, the ``fallbacks`` map can be namespaced per tier mode
(``fallbacks.free.<tier>`` / ``fallbacks.anthropic.<tier>``) because the
free chains hop through NVIDIA-twin tiers that don't belong in the paid
ladder; a flat map (tier -> tier strings) still works and applies to every
mode.
"""
from __future__ import annotations

import time
from typing import Dict, List, Mapping, Optional

import httpx

from jarvis.config import Settings, get_settings, get_tier_mode

_FAILURE_THRESHOLD = 3
_COOLDOWN_SECONDS = 300.0  # 5 minutes
_MAX_CHAIN_HOPS = 3


def is_transient(exc: Exception) -> bool:
    """Whether *exc* is worth falling back on (ARCHITECTURE.md §5.2).

    Covers both exception families the providers raise: the ``anthropic``
    SDK's typed errors, and raw ``httpx`` errors from the OpenRouter/NVIDIA
    providers (429/5xx statuses via ``raise_for_status``, plus transport
    errors — connect failures, timeouts, dropped reads). Free-tier backends
    rate-limit *routinely*, so classifying an httpx 429 as transient is what
    makes the whole free fallback ladder actually fire.
    """
    import anthropic

    from jarvis.llm.providers import OpenRouterError

    if isinstance(exc, anthropic.RateLimitError):
        return True
    if isinstance(exc, anthropic.APIConnectionError):  # covers APITimeoutError too
        return True
    if isinstance(exc, anthropic.APIStatusError):
        return exc.status_code >= 500  # 5xx/529 -- not 401/403/400
    if isinstance(exc, OpenRouterError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return code == 429 or code >= 500  # not 401/403/400/404
    if isinstance(exc, httpx.TransportError):  # connect/read/write/pool timeouts & failures
        return True
    return False


def _resolve_fallback_map(settings: Settings) -> Mapping:
    """The tier -> fallback-tier map for the active tier mode.

    Namespaced shape picks the active mode's map; flat shape (all values are
    tier-name strings) applies to every mode; a namespaced map with no entry
    for the active mode just means "no fallbacks configured".
    """
    fallbacks = settings.get("fallbacks", {})
    if not fallbacks:
        return {}
    entry = fallbacks.get(get_tier_mode(settings))
    if isinstance(entry, Mapping):
        return entry
    if all(isinstance(v, str) for v in fallbacks.values()):
        return fallbacks  # flat map
    return {}


def fallback_chain(
    settings: Settings, tier: str, max_hops: int = _MAX_CHAIN_HOPS
) -> List[str]:
    """Ordered tiers to try after *tier*, walking the active fallback map."""
    fallbacks = _resolve_fallback_map(settings)
    chain: List[str] = []
    seen = {tier}
    current = tier
    while len(chain) < max_hops:
        next_tier = fallbacks.get(current)
        if next_tier is None:
            break
        next_tier = str(next_tier)
        if next_tier in seen:
            break  # cycle guard (e.g. two tiers that fall back to each other)
        chain.append(next_tier)
        seen.add(next_tier)
        current = next_tier
    return chain


class CircuitBreaker:
    """Per-tier consecutive-failure tracking (ARCHITECTURE.md §5.2)."""

    def __init__(
        self,
        failure_threshold: int = _FAILURE_THRESHOLD,
        cooldown_s: float = _COOLDOWN_SECONDS,
    ):
        self._failure_threshold = failure_threshold
        self._cooldown_s = cooldown_s
        self._failures: Dict[str, int] = {}
        self._tripped_until: Dict[str, float] = {}

    def is_open(self, tier: str) -> bool:
        """True if *tier* is currently tripped and should be routed around."""
        until = self._tripped_until.get(tier)
        if until is None:
            return False
        if time.monotonic() >= until:
            # Cooldown elapsed: clear the trip and let one probe through.
            del self._tripped_until[tier]
            self._failures[tier] = 0
            return False
        return True

    def record_success(self, tier: str) -> None:
        self._failures[tier] = 0
        self._tripped_until.pop(tier, None)

    def record_failure(self, tier: str) -> None:
        count = self._failures.get(tier, 0) + 1
        self._failures[tier] = count
        if count >= self._failure_threshold:
            self._tripped_until[tier] = time.monotonic() + self._cooldown_s


_breaker: Optional[CircuitBreaker] = None


def get_circuit_breaker() -> CircuitBreaker:
    """Process-wide CircuitBreaker singleton."""
    global _breaker
    if _breaker is None:
        _breaker = CircuitBreaker()
    return _breaker
