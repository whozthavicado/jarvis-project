"""Shared LLM value types."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TurnResult:
    """The outcome of one streamed model turn.

    Attributes:
        text: The complete assistant reply (concatenated text blocks).
        model: The model ID that actually produced the response.
        stop_reason: e.g. "end_turn", "max_tokens", "refusal".
        input_tokens: Uncached input tokens billed this turn.
        output_tokens: Output tokens billed this turn.
        cache_read_tokens: Tokens served from cache (~0.1x cost).
        cache_creation_tokens: Tokens written to cache (~1.25x cost).
    """

    text: str
    model: str
    stop_reason: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0

    @property
    def refused(self) -> bool:
        return self.stop_reason == "refusal"
