"""The provider interface every backend implements.

Deliberately a ``Protocol`` (structural typing), not an ABC: a provider is
just "something with this one async method." Nothing needs to inherit from
it — a test stub with a matching ``stream_reply`` works without importing
this module at all.
"""
from __future__ import annotations

from typing import Callable, List, Protocol

from jarvis.llm.types import ChatMessage, TurnResult


class Provider(Protocol):
    async def stream_reply(
        self,
        system_prompt: str,
        messages: List[ChatMessage],
        on_text: Callable[[str], None],
    ) -> TurnResult:
        """Stream one assistant turn, calling on_text with each text delta."""
        ...
