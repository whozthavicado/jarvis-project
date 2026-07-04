"""Offline mode (ARCHITECTURE.md §5.1, last rung of the ladder).

With no network, T0 grammar commands still work (they never leave the
machine); everything that needs a model gets a spoken "I'm offline" notice
instead of a hang-then-error. :class:`ConnectivityMonitor` is the cached
verdict behind that decision: a cheap TCP connect probe (default
1.1.1.1:443, ~1.5 s timeout) whose result is held for ``cache_ttl_s`` so a
listen loop never probes more than a couple of times a minute.

The orchestrator also feeds observations back in: when an LLM call dies on a
transport-level error, ``mark_offline()`` records it, so the *next* turn
short-circuits to the offline notice immediately rather than paying the
connect timeout again. Once the TTL expires the monitor re-probes and
recovery is automatic.
"""
from __future__ import annotations

import asyncio
import time
from typing import Awaitable, Callable, Optional

from jarvis.config import Settings, get_settings


async def _tcp_probe(host: str, port: int, timeout_s: float) -> bool:
    """True if a TCP connection to host:port succeeds within timeout_s."""
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout_s
        )
    except Exception:  # noqa: BLE001 - any failure here just means "offline"
        return False
    writer.close()
    try:
        await writer.wait_closed()
    except Exception:  # noqa: BLE001 - already have our answer
        pass
    return True


class ConnectivityMonitor:
    """Cached are-we-online verdict, probe-based with observation feedback."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        probe: Optional[Callable[[], Awaitable[bool]]] = None,
    ):
        s = settings or get_settings()
        cfg = s.get("offline", Settings({}))
        host = str(cfg.get("probe_host", "1.1.1.1"))
        port = int(cfg.get("probe_port", 443))
        timeout_s = float(cfg.get("probe_timeout_s", 1.5))
        self.cache_ttl_s = float(cfg.get("cache_ttl_s", 30))

        self._probe = probe or (lambda: _tcp_probe(host, port, timeout_s))
        self._clock = time.monotonic
        self._verdict: Optional[bool] = None
        self._checked_at = 0.0

    async def is_online(self) -> bool:
        now = self._clock()
        if self._verdict is not None and now - self._checked_at < self.cache_ttl_s:
            return self._verdict
        self._verdict = await self._probe()
        self._checked_at = now
        return self._verdict

    def mark_offline(self) -> None:
        """Record an observed connection failure without paying for a probe."""
        self._verdict = False
        self._checked_at = self._clock()


_monitor: Optional[ConnectivityMonitor] = None


def get_connectivity_monitor(settings: Optional[Settings] = None) -> ConnectivityMonitor:
    """Process-wide ConnectivityMonitor singleton, backed by settings -> offline.*."""
    global _monitor
    if _monitor is None:
        _monitor = ConnectivityMonitor(settings)
    return _monitor
