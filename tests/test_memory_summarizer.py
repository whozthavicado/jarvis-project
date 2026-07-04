"""Summarizer/compaction tests — a stub LLMClient, no vendor SDK, no network.

Provider-agnostic since the free-mode restructure: the summarizer talks to
whatever backs the "router" tier through the LLMClient interface.
"""
import pytest

from jarvis.config import get_settings
from jarvis.llm.types import ChatMessage, TurnResult
from jarvis.memory.summarizer import SUMMARIZER_PROMPT, compact, summarize


class _StubLLM:
    def __init__(self, reply: str = "summary text", error: Exception = None):
        self._reply = reply
        self._error = error
        self.calls = []

    async def stream_reply(self, system_prompt, messages, on_text):
        self.calls.append((system_prompt, messages))
        if self._error is not None:
            raise self._error
        return TurnResult(text=self._reply, model="stub-router", stop_reason="stop")


def _msgs(n: int, text: str = "word ") -> list:
    return [ChatMessage(role="user" if i % 2 == 0 else "assistant", text=text * 10) for i in range(n)]


@pytest.mark.asyncio
async def test_summarize_sends_prompt_and_transcript_and_returns_text():
    llm = _StubLLM(reply="They discussed dinner plans.")
    result = await summarize(_msgs(4), settings=get_settings(), llm=llm)

    assert result == "They discussed dinner plans."
    system_prompt, messages = llm.calls[0]
    assert system_prompt == SUMMARIZER_PROMPT
    assert messages[0].role == "user"
    assert "user: " in messages[0].text and "assistant: " in messages[0].text


@pytest.mark.asyncio
async def test_summarize_strips_think_tags_from_reasoning_models():
    llm = _StubLLM(reply="<think>Let me condense this...</think>A concise summary.")
    result = await summarize(_msgs(4), settings=get_settings(), llm=llm)
    assert result == "A concise summary."


@pytest.mark.asyncio
async def test_compact_is_noop_under_threshold():
    history = _msgs(4)
    result = await compact(history, settings=get_settings(), llm=_StubLLM())
    assert result == history


@pytest.mark.asyncio
async def test_compact_is_noop_when_history_shorter_than_keep_last():
    # long text but too few turns to ever split into "older"/"recent"
    history = _msgs(3, text="word " * 2000)
    result = await compact(history, settings=get_settings(), llm=_StubLLM(), keep_last=6)
    assert result == history


@pytest.mark.asyncio
async def test_compact_summarizes_older_turns_and_keeps_recent_window():
    history = _msgs(20, text="word " * 200)  # well past the token threshold
    llm = _StubLLM(reply="Condensed summary.")

    result = await compact(history, settings=get_settings(), llm=llm, keep_last=6, token_threshold=100)

    assert len(result) == 7  # 1 summary message + 6 kept
    assert result[0].role == "user"
    assert "Condensed summary." in result[0].text
    assert result[1:] == history[-6:]


@pytest.mark.asyncio
async def test_compact_falls_back_to_truncation_when_summarize_fails():
    history = _msgs(20, text="word " * 200)
    llm = _StubLLM(error=RuntimeError("no credentials"))

    result = await compact(history, settings=get_settings(), llm=llm, keep_last=6, token_threshold=100)

    assert result == history[-6:]
