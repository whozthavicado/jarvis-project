"""Orchestrator tests — handle_turn's success/failure/refusal paths and the
error -> spoken-fallback classification. No real LLM or audio involved.
"""
import httpx
import pytest
import anthropic

from jarvis.audio.types import Transcript
from jarvis.core.orchestrator import _fallback_text_for, handle_turn
from jarvis.core.session import Session
from jarvis.llm.types import TurnResult


def _req() -> httpx.Request:
    return httpx.Request("POST", "https://api.anthropic.com/v1/messages")


def _resp(status: int) -> httpx.Response:
    return httpx.Response(status_code=status, request=_req())


class _StubLLM:
    """Stands in for LLMClient — either returns a fixed TurnResult or raises."""

    def __init__(self, result: TurnResult = None, error: Exception = None):
        self._result = result
        self._error = error
        self.calls = []

    async def stream_reply(self, system_blocks, messages, on_text):
        self.calls.append((system_blocks, messages))
        if self._error is not None:
            raise self._error
        if self._result.text:  # a real stream emits no deltas for empty content
            on_text(self._result.text)
        return self._result


def _ok_result(text="Hello there.") -> TurnResult:
    return TurnResult(text=text, model="claude-sonnet-5", stop_reason="end_turn")


@pytest.mark.asyncio
async def test_successful_turn_updates_session_and_streams_text():
    session = Session(tier="sonnet")
    llm = _StubLLM(result=_ok_result("Hi, how can I help?"))
    seen = []

    result = await handle_turn(session, llm, Transcript(text="hello"), seen.append)

    assert result.text == "Hi, how can I help?"
    assert seen == ["Hi, how can I help?"]
    # user turn + assistant turn both landed in history
    assert len(session.history) == 2
    assert session.history[0]["role"] == "user"
    assert session.history[1] == {"role": "assistant", "content": "Hi, how can I help?"}


@pytest.mark.asyncio
async def test_failed_turn_speaks_fallback_and_leaves_no_assistant_turn():
    session = Session(tier="sonnet")
    llm = _StubLLM(error=anthropic.APIConnectionError(request=_req()))
    seen = []

    result = await handle_turn(session, llm, Transcript(text="hello"), seen.append)

    assert result is None
    assert len(seen) == 1 and "reach the cloud" in seen[0]
    # user turn is preserved (so context isn't lost), no assistant reply added
    assert len(session.history) == 1
    assert session.history[0]["role"] == "user"


@pytest.mark.asyncio
async def test_refusal_speaks_a_generic_decline_but_result_is_returned():
    session = Session(tier="sonnet")
    llm = _StubLLM(result=TurnResult(text="", model="claude-sonnet-5", stop_reason="refusal"))
    seen = []

    result = await handle_turn(session, llm, Transcript(text="hello"), seen.append)

    assert result is not None and result.refused
    assert seen == ["I'd rather not answer that."]
    # refusal shouldn't be recorded as if the model had actually said something
    assert len(session.history) == 1


@pytest.mark.parametrize(
    "exc,expected_snippet",
    [
        (anthropic.AuthenticationError("bad key", response=_resp(401), body=None), "credentials"),
        (anthropic.PermissionDeniedError("nope", response=_resp(403), body=None), "not authorized"),
        (anthropic.RateLimitError("slow down", response=_resp(429), body=None), "rate limited"),
        (anthropic.APIConnectionError(request=_req()), "reach the cloud"),
        (anthropic.APIStatusError("boom", response=_resp(500), body=None), "server side"),
        (ValueError("unexpected bug"), "try that again"),
    ],
)
def test_fallback_text_classifies_common_failures(exc, expected_snippet):
    assert expected_snippet in _fallback_text_for(exc)
