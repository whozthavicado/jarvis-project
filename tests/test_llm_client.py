"""LLMClient tests — a fake Anthropic client built from the real SDK's own
event/message types, so the fake can't silently drift from the real shape.
No network or credentials required.
"""
import pytest
from anthropic.types.message import Message
from anthropic.types.text_block import TextBlock
from anthropic.types.usage import Usage
from anthropic.types.raw_content_block_delta_event import RawContentBlockDeltaEvent
from anthropic.types.text_delta import TextDelta
from anthropic.types.thinking_delta import ThinkingDelta

from jarvis.llm.client import LLMClient


def _text_delta_event(text: str, index: int = 0) -> RawContentBlockDeltaEvent:
    return RawContentBlockDeltaEvent(
        type="content_block_delta", index=index, delta=TextDelta(type="text_delta", text=text)
    )


def _thinking_delta_event(text: str, index: int = 0) -> RawContentBlockDeltaEvent:
    return RawContentBlockDeltaEvent(
        type="content_block_delta",
        index=index,
        delta=ThinkingDelta(type="thinking_delta", thinking=text),
    )


def _final_message(text: str, stop_reason: str = "end_turn") -> Message:
    return Message(
        id="msg_test",
        type="message",
        role="assistant",
        model="claude-sonnet-5",
        content=[TextBlock(type="text", text=text, citations=None)],
        stop_reason=stop_reason,
        stop_sequence=None,
        usage=Usage(
            input_tokens=42,
            output_tokens=7,
            cache_read_input_tokens=100,
            cache_creation_input_tokens=0,
        ),
    )


class _FakeStream:
    """Mimics anthropic's AsyncMessageStream: async-iterable + get_final_message()."""

    def __init__(self, events, final):
        self._events = events
        self._final = final

    def __aiter__(self):
        return self._aiter()

    async def _aiter(self):
        for e in self._events:
            yield e

    async def get_final_message(self):
        return self._final

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _FakeMessages:
    def __init__(self, events, final):
        self._events = events
        self._final = final
        self.last_call_kwargs = None

    def stream(self, **kwargs):
        self.last_call_kwargs = kwargs
        return _FakeStream(self._events, self._final)


class _FakeAnthropicClient:
    def __init__(self, events, final):
        self.messages = _FakeMessages(events, final)


@pytest.mark.asyncio
async def test_forwards_only_text_deltas_and_builds_result():
    events = [
        _thinking_delta_event("pondering..."),
        _text_delta_event("Hello, "),
        _text_delta_event("world."),
    ]
    fake = _FakeAnthropicClient(events, _final_message("Hello, world."))
    client = LLMClient(client=fake)

    seen = []
    result = await client.stream_reply(
        system_blocks=[{"type": "text", "text": "sys"}],
        messages=[{"role": "user", "content": "hi"}],
        on_text=seen.append,
    )

    # Only text deltas reach the caller — thinking is filtered out.
    assert seen == ["Hello, ", "world."]
    assert result.text == "Hello, world."
    assert result.model == "claude-sonnet-5"
    assert result.stop_reason == "end_turn"
    assert result.input_tokens == 42
    assert result.output_tokens == 7
    assert result.cache_read_tokens == 100
    assert not result.refused


@pytest.mark.asyncio
async def test_request_uses_configured_model_and_effort():
    fake = _FakeAnthropicClient([], _final_message("ok"))
    client = LLMClient(client=fake)

    await client.stream_reply(
        system_blocks=[{"type": "text", "text": "sys"}],
        messages=[{"role": "user", "content": "hi"}],
        on_text=lambda _: None,
    )

    kwargs = fake.messages.last_call_kwargs
    assert kwargs["model"] == "claude-sonnet-5"
    assert kwargs["output_config"] == {"effort": "medium"}
    assert kwargs["thinking"] == {"type": "adaptive"}
    assert kwargs["max_tokens"] == 8000


@pytest.mark.asyncio
async def test_refusal_is_surfaced_on_result():
    fake = _FakeAnthropicClient([], _final_message("", stop_reason="refusal"))
    client = LLMClient(client=fake)

    result = await client.stream_reply(
        system_blocks=[{"type": "text", "text": "sys"}],
        messages=[{"role": "user", "content": "hi"}],
        on_text=lambda _: None,
    )
    assert result.refused
    assert result.text == ""
