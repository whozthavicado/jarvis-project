"""Streaming Claude client — M3 minimal (ARCHITECTURE.md §8 step 2).

Single model only (Sonnet 5), no tools, no fallback ladder. Those arrive in
later milestones (M4 tools, M2 routing, M3 full). This module's job right now
is exactly one thing: stream a reply and hand text deltas to a callback
(typically ``Speaker.feed``) as they arrive, so the assistant starts speaking
before the full response has finished generating.

The ``anthropic`` SDK is imported lazily so the rest of the package stays
importable without credentials configured, and a client can be injected for
testing (see tests/test_llm_client.py).
"""
from __future__ import annotations

from typing import Any, Callable, List, Optional

from jarvis.config import Settings, get_settings
from jarvis.llm.types import TurnResult


class LLMClient:
    """Streams one conversational turn through a single Claude model.

    Usage::

        client = LLMClient()
        result = await client.stream_reply(
            system_blocks=build_system_blocks("sonnet"),
            messages=history,
            on_text=speaker.feed,
        )
    """

    def __init__(self, settings: Optional[Settings] = None, client: Optional[Any] = None):
        s = settings or get_settings()
        self.model: str = str(s.models.t1_standard)  # Sonnet 5 for M3 minimal
        self.max_tokens: int = 8000
        self.effort: str = "medium"
        self._client = client  # injectable for tests; lazily created otherwise

    def _get_client(self) -> Any:
        if self._client is None:
            import anthropic  # lazy: requires credentials to actually call

            self._client = anthropic.AsyncAnthropic()
        return self._client

    async def stream_reply(
        self,
        system_blocks: List[dict],
        messages: List[dict],
        on_text: Callable[[str], None],
    ) -> TurnResult:
        """Stream one assistant turn.

        Args:
            system_blocks: cacheable system prompt (see jarvis.llm.prompts).
            messages: full conversation history, ending in the latest user turn.
            on_text: called with each streamed text delta (not thinking deltas).

        Returns:
            TurnResult with the complete text and usage/stop-reason metadata.
        """
        client = self._get_client()

        async with client.messages.stream(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system_blocks,
            thinking={"type": "adaptive"},
            output_config={"effort": self.effort},
            messages=messages,
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
