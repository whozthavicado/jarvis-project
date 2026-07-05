"""Minimal pub/sub for the dashboard live-backend integration.

See docs/superpowers/specs/2026-07-04-zero-live-backend-integration-design.md.
Lives here (not in jarvis/server.py, where the design spec originally placed
it) because jarvis/core/orchestrator.py needs the type to accept an optional
``broadcaster`` param on ``handle_turn`` -- and jarvis/server.py itself
imports from orchestrator.py, so defining Broadcaster there would be
circular. jarvis/server.py re-exports it for callers that expect it there.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, Set


class Broadcaster:
    """publish(event) pushes to every subscribed queue; a slow or abandoned
    subscriber drops its own oldest queued event rather than blocking
    others or growing unboundedly."""

    def __init__(self, maxsize: int = 100):
        self._maxsize = maxsize
        self._subscribers: "Set[asyncio.Queue[Dict[str, Any]]]" = set()

    def subscribe(self) -> "asyncio.Queue[Dict[str, Any]]":
        q: "asyncio.Queue[Dict[str, Any]]" = asyncio.Queue(maxsize=self._maxsize)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: "asyncio.Queue[Dict[str, Any]]") -> None:
        self._subscribers.discard(q)

    def publish(self, event: Dict[str, Any]) -> None:
        for q in list(self._subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    q.put_nowait(event)
                except asyncio.QueueFull:
                    pass  # lost a race with another producer; not worth retrying
