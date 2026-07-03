"""AnthropicProvider's M3-full stop_reason handling (ARCHITECTURE.md §5.2):
max_tokens retry (only if nothing emitted yet) and pause_turn continuation
(cap 5 hops). Separate from test_provider_anthropic.py because these need a
fake client that returns a *different* response on each successive call.
"""
import pytest
from anthropic.types.message import Message
from anthropic.types.text_block import TextBlock
from anthropic.types.usage import Usage
from anthropic.types.raw_content_block_delta_event import RawContentBlockDeltaEvent
from anthropic.types.text_delta import TextDelta

from jarvis.llm.providers.anthropic_provider import AnthropicProvider
from jarvis.llm.types import ChatMessage


def _text_delta_event(text: str, index: int = 0) -> RawContentBlockDeltaEvent:
    return RawContentBlockDeltaEvent(
        type="content_block_delta", index=index, delta=TextDelta(type="text_delta", text=text)
    )


def _message(text: str, stop_reason: str, model: str = "claude-sonnet-5") -> Message:
    return Message(
        id="msg_test",
        type="message",
        role="assistant",
        model=model,
        content=[TextBlock(type="text", text=text, citations=None)],
        stop_reason=stop_reason,
        stop_sequence=None,
        usage=Usage(
            input_tokens=10,
            output_tokens=5,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=0,
        ),
    )


def _turn(text: str, stop_reason: str, emit: bool = True):
    """One queued (events, final) pair. emit=False means no delta events are
    streamed even though the final message has text -- simulates a budget
    that ran out entirely on adaptive-thinking tokens before any visible text."""
    events = [_text_delta_event(text)] if (emit and text) else []
    return events, _message(text, stop_reason=stop_reason)


class _FakeStream:
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


class _SequentialFakeMessages:
    """Returns each queued (events, final) pair in order, one per ``stream()`` call."""

    def __init__(self, turns):
        self._turns = list(turns)
        self.calls = []

    def stream(self, **kwargs):
        self.calls.append(kwargs)
        events, final = self._turns.pop(0)
        return _FakeStream(events, final)


class _FakeClient:
    def __init__(self, turns):
        self.messages = _SequentialFakeMessages(turns)


@pytest.mark.asyncio
async def test_max_tokens_with_no_emitted_text_retries_with_doubled_budget():
    # All budget went to thinking; the visible text block is empty and
    # nothing reached on_text -- safe to retry with a bigger budget.
    turns = [
        _turn("", stop_reason="max_tokens"),
        _turn("Here's the answer.", stop_reason="end_turn"),
    ]
    fake = _FakeClient(turns)
    provider = AnthropicProvider(model="claude-sonnet-5", max_tokens=100, client=fake)

    seen = []
    result = await provider.stream_reply("sys", [ChatMessage(role="user", text="hi")], seen.append)

    assert result.text == "Here's the answer."
    assert result.stop_reason == "end_turn"
    assert len(fake.messages.calls) == 2
    assert fake.messages.calls[0]["max_tokens"] == 100
    assert fake.messages.calls[1]["max_tokens"] == 200


@pytest.mark.asyncio
async def test_max_tokens_with_emitted_text_is_not_retried():
    turns = [_turn("Partial answer that got cut off", stop_reason="max_tokens")]
    fake = _FakeClient(turns)
    provider = AnthropicProvider(model="claude-sonnet-5", max_tokens=100, client=fake)

    result = await provider.stream_reply("sys", [ChatMessage(role="user", text="hi")], lambda _: None)

    assert result.stop_reason == "max_tokens"
    assert result.text == "Partial answer that got cut off"
    assert len(fake.messages.calls) == 1  # no retry -- text was already "spoken"


@pytest.mark.asyncio
async def test_pause_turn_continues_and_concatenates_text_and_usage():
    turns = [
        _turn("Part one. ", stop_reason="pause_turn"),
        _turn("Part two.", stop_reason="end_turn"),
    ]
    fake = _FakeClient(turns)
    provider = AnthropicProvider(model="claude-sonnet-5", client=fake)

    seen = []
    result = await provider.stream_reply("sys", [ChatMessage(role="user", text="hi")], seen.append)

    assert result.text == "Part one. Part two."
    assert result.stop_reason == "end_turn"
    assert result.input_tokens == 20  # 10 + 10
    assert result.output_tokens == 10  # 5 + 5
    assert len(fake.messages.calls) == 2
    # the continuation call includes the partial assistant reply as context
    continuation_messages = fake.messages.calls[1]["messages"]
    assert continuation_messages[-1] == {"role": "assistant", "content": "Part one. "}


@pytest.mark.asyncio
async def test_pause_turn_stops_after_five_continuations():
    turns = [_turn(f"chunk{i} ", stop_reason="pause_turn") for i in range(6)]
    fake = _FakeClient(turns)
    provider = AnthropicProvider(model="claude-sonnet-5", client=fake)

    result = await provider.stream_reply("sys", [ChatMessage(role="user", text="hi")], lambda _: None)

    assert result.stop_reason == "pause_turn"  # gave up, still paused
    assert len(fake.messages.calls) == 6  # 1 initial + 5 continuations, capped
