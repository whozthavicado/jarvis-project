"""Anthropic backend — the Claude API, streaming.

This is the generalized version of Milestone 2's original client.py: same
event handling (forward only text deltas, filter out adaptive-thinking
deltas), but now takes a plain ``system_prompt`` string and a list of
provider-agnostic ``ChatMessage`` instead of pre-built Anthropic content
blocks — the Anthropic-specific wire shape (cache_control, block lists) is
built here, internally, not leaked to callers.

The ``anthropic`` SDK is imported lazily so this module (and the rest of the
package) stays importable without credentials configured.
"""
from __future__ import annotations

from typing import Any, Callable, List, Optional

from jarvis.llm.types import ChatMessage, TurnResult


class AnthropicProvider:
    def __init__(
        self,
        model: str,
        max_tokens: int = 8000,
        effort: str = "medium",
        client: Optional[Any] = None,
    ):
        self.model = model
        self.max_tokens = max_tokens
        self.effort = effort
        self._client = client  # injectable for tests; lazily created otherwise

    def _get_client(self) -> Any:
        if self._client is None:
            import anthropic  # lazy: requires credentials to actually call

            self._client = anthropic.AsyncAnthropic()
        return self._client

    async def stream_reply(
        self,
        system_prompt: str,
        messages: List[ChatMessage],
        on_text: Callable[[str], None],
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

        async with client.messages.stream(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system_blocks,
            thinking={"type": "adaptive"},
            output_config={"effort": self.effort},
            messages=api_messages,
        ) as stream:
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
