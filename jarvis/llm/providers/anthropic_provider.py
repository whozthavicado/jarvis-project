"""Anthropic backend — the Claude API, streaming.

This is the generalized version of Milestone 2's original client.py: same
event handling (forward only text deltas, filter out adaptive-thinking
deltas), but now takes a plain ``system_prompt`` string and a list of
provider-agnostic ``ChatMessage`` instead of pre-built Anthropic content
blocks — the Anthropic-specific wire shape (cache_control, block lists) is
built here, internally, not leaked to callers.

M3-full (ARCHITECTURE.md §5.2) adds two stop_reason behaviors, both
Anthropic-specific wire quirks so they live here rather than in the
tier-agnostic LLMClient:

- ``stop_reason == "max_tokens"``: the model ran out of budget. Retried once
  with doubled ``max_tokens`` -- but *only* if nothing has reached ``on_text``
  yet (e.g. the whole budget went to adaptive-thinking tokens before any
  visible text). If text was already spoken, redoing the call would produce
  duplicate/garbled speech once it hits TTS, so the truncated result is
  returned as-is instead -- same reasoning LLMClient uses for its own
  fallback gate.
- ``stop_reason == "pause_turn"``: the API paused mid-turn on a long
  response. Continued by re-sending the assistant's partial content as the
  next message, up to 5 continuations, concatenating the text and summing
  usage across every hop.

The ``anthropic`` SDK is imported lazily so this module (and the rest of the
package) stays importable without credentials configured.
"""
from __future__ import annotations

from typing import Any, Callable, List, Optional

from jarvis.llm.types import ChatMessage, TurnResult

_MAX_PAUSE_TURN_CONTINUATIONS = 5


class AnthropicProvider:
    def __init__(
        self,
        model: str,
        max_tokens: int = 8000,
        effort: str = "medium",
        thinking: str = "adaptive",
        client: Optional[Any] = None,
    ):
        """*thinking* is the ``thinking.type`` to request, or ``"none"`` to
        omit the parameter entirely — required for Fable 5, where an explicit
        ``thinking`` config 400s (ARCHITECTURE.md §2), and the safe choice
        for the Haiku router classifier."""
        self.model = model
        self.max_tokens = max_tokens
        self.effort = effort
        self.thinking = thinking
        self._client = client  # injectable for tests; lazily created otherwise

    def _get_client(self) -> Any:
        if self._client is None:
            import anthropic  # lazy: requires credentials to actually call

            self._client = anthropic.AsyncAnthropic()
        return self._client

    async def _stream_once(
        self,
        system_prompt: str,
        messages: List[ChatMessage],
        on_text: Callable[[str], None],
        max_tokens: int,
    ) -> TurnResult:
        client = self._get_client()

        system_blocks = [
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ]
        api_messages = [{"role": m.role, "content": m.text} for m in messages]

        request_kwargs: dict = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system_blocks,
            "output_config": {"effort": self.effort},
            "messages": api_messages,
        }
        if self.thinking != "none":
            request_kwargs["thinking"] = {"type": self.thinking}

        async with client.messages.stream(**request_kwargs) as stream:
            async for event in stream:
                if event.type == "content_block_delta":
                    delta = event.delta
                    if getattr(delta, "type", None) == "text_delta":
                        on_text(delta.text)
            final = await stream.get_final_message()

        text = "".join(
            block.text for block in final.content if getattr(block, "type", None) == "text"
        )
        usage = final.usage
        return TurnResult(
            text=text,
            model=final.model,
            stop_reason=final.stop_reason or "",
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
            cache_creation_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
        )

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

        result = await self._stream_once(system_prompt, messages, tracking_on_text, self.max_tokens)

        if result.stop_reason == "max_tokens" and not emitted:
            result = await self._stream_once(
                system_prompt, messages, tracking_on_text, self.max_tokens * 2
            )

        if result.stop_reason != "pause_turn":
            return result

        text_parts = [result.text]
        input_tokens = result.input_tokens
        output_tokens = result.output_tokens
        cache_read_tokens = result.cache_read_tokens
        cache_creation_tokens = result.cache_creation_tokens
        continuation_messages = list(messages)

        for _ in range(_MAX_PAUSE_TURN_CONTINUATIONS):
            continuation_messages = continuation_messages + [
                ChatMessage(role="assistant", text=result.text)
            ]
            result = await self._stream_once(
                system_prompt, continuation_messages, tracking_on_text, self.max_tokens
            )
            text_parts.append(result.text)
            input_tokens += result.input_tokens
            output_tokens += result.output_tokens
            cache_read_tokens += result.cache_read_tokens
            cache_creation_tokens += result.cache_creation_tokens
            if result.stop_reason != "pause_turn":
                break

        return TurnResult(
            text="".join(text_parts),
            model=result.model,
            stop_reason=result.stop_reason,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_creation_tokens=cache_creation_tokens,
        )
