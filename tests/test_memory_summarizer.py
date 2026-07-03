"""Summarizer/compaction tests — a fake Anthropic client, no network."""
from types import SimpleNamespace

import pytest

from jarvis.config import get_settings
from jarvis.llm.types import ChatMessage
from jarvis.memory.summarizer import compact, summarize


class _FakeTextBlock:
    def __init__(self, text: str):
        self.type = "text"
        self.text = text


class _FakeMessages:
    def __init__(self, reply: str, error: Exception = None):
        self._reply = reply
        self._error = error
        self.last_call_kwargs = None

    async def create(self, **kwargs):
        self.last_call_kwargs = kwargs
        if self._error is not None:
            raise self._error
        return SimpleNamespace(content=[_FakeTextBlock(self._reply)])


class _FakeClient:
    def __init__(self, reply: str = "summary text", error: Exception = None):
        self.messages = _FakeMessages(reply, error)


def _msgs(n: int, text: str = "word ") -> list:
    return [ChatMessage(role="user" if i % 2 == 0 else "assistant", text=text * 10) for i in range(n)]


@pytest.mark.asyncio
async def test_summarize_uses_router_model_and_returns_text():
    fake = _FakeClient(reply="They discussed dinner plans.")
    result = await summarize(_msgs(4), settings=get_settings(), client=fake)

    assert result == "They discussed dinner plans."
    assert fake.messages.last_call_kwargs["model"] == "claude-haiku-4-5"


@pytest.mark.asyncio
async def test_compact_is_noop_under_threshold():
    history = _msgs(4)
    result = await compact(history, settings=get_settings(), client=_FakeClient())
    assert result == history


@pytest.mark.asyncio
async def test_compact_is_noop_when_history_shorter_than_keep_last():
    # long text but too few turns to ever split into "older"/"recent"
    history = _msgs(3, text="word " * 2000)
    result = await compact(history, settings=get_settings(), client=_FakeClient(), keep_last=6)
    assert result == history


@pytest.mark.asyncio
async def test_compact_summarizes_older_turns_and_keeps_recent_window():
    history = _msgs(20, text="word " * 200)  # well past the token threshold
    fake = _FakeClient(reply="Condensed summary.")

    result = await compact(history, settings=get_settings(), client=fake, keep_last=6, token_threshold=100)

    assert len(result) == 7  # 1 summary message + 6 kept
    assert result[0].role == "user"
    assert "Condensed summary." in result[0].text
    assert result[1:] == history[-6:]


@pytest.mark.asyncio
async def test_compact_falls_back_to_truncation_when_summarize_fails():
    history = _msgs(20, text="word " * 200)
    fake = _FakeClient(error=RuntimeError("no credentials"))

    result = await compact(history, settings=get_settings(), client=fake, keep_last=6, token_threshold=100)

    assert result == history[-6:]
