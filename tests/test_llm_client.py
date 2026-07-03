"""LLMClient tests — tier -> provider selection, the transient-only fallback
gate, multi-hop settings-driven chains, and the circuit breaker (M3-full,
ARCHITECTURE.md §5.1/§5.2). Uses simple stub Provider objects, not a real SDK.
"""
import httpx
import pytest
import anthropic

from jarvis.config import Settings, get_settings
from jarvis.llm.client import LLMClient
from jarvis.llm.fallbacks import CircuitBreaker
from jarvis.llm.types import ChatMessage, TurnResult


class _StubProvider:
    def __init__(self, result: TurnResult = None, error: Exception = None):
        self._result = result
        self._error = error
        self.calls = 0

    async def stream_reply(self, system_prompt, messages, on_text):
        self.calls += 1
        if self._error is not None:
            raise self._error
        if self._result.text:  # a real stream emits no deltas for empty content
            on_text(self._result.text)
        return self._result


class _PartialThenFailProvider:
    """Emits some text, then fails mid-stream — the case fallback must NOT retry."""

    def __init__(self, partial_text: str, error: Exception):
        self.partial_text = partial_text
        self.error = error
        self.calls = 0

    async def stream_reply(self, system_prompt, messages, on_text):
        self.calls += 1
        on_text(self.partial_text)
        raise self.error


def _result(text="ok", model="stub-model") -> TurnResult:
    return TurnResult(text=text, model=model, stop_reason="end_turn")


def _req() -> httpx.Request:
    return httpx.Request("POST", "https://api.anthropic.com/v1/messages")


def _connection_error() -> anthropic.APIConnectionError:
    return anthropic.APIConnectionError(request=_req())


def _bad_request_error() -> anthropic.APIStatusError:
    resp = httpx.Response(status_code=400, request=_req())
    return anthropic.APIStatusError("bad request", response=resp, body=None)


@pytest.mark.asyncio
async def test_uses_primary_provider_when_it_succeeds():
    primary = _StubProvider(result=_result("hi"))
    fallback = _StubProvider(result=_result("fallback"))
    client = LLMClient(provider=primary, fallback_provider=fallback, circuit_breaker=CircuitBreaker())

    seen = []
    result = await client.stream_reply("sys", [ChatMessage(role="user", text="hi")], seen.append)

    assert result.text == "hi"
    assert seen == ["hi"]
    assert primary.calls == 1
    assert fallback.calls == 0


@pytest.mark.asyncio
async def test_falls_back_when_primary_fails_transiently_before_emitting_any_text():
    primary = _StubProvider(error=_connection_error())
    fallback = _StubProvider(result=_result("fallback reply"))
    client = LLMClient(provider=primary, fallback_provider=fallback, circuit_breaker=CircuitBreaker())

    seen = []
    result = await client.stream_reply("sys", [ChatMessage(role="user", text="hi")], seen.append)

    assert result.text == "fallback reply"
    assert seen == ["fallback reply"]
    assert primary.calls == 1
    assert fallback.calls == 1


@pytest.mark.asyncio
async def test_does_not_fall_back_after_partial_text_already_emitted():
    primary = _PartialThenFailProvider("partial...", _connection_error())
    fallback = _StubProvider(result=_result("fallback reply"))
    client = LLMClient(provider=primary, fallback_provider=fallback, circuit_breaker=CircuitBreaker())

    seen = []
    with pytest.raises(anthropic.APIConnectionError):
        await client.stream_reply("sys", [ChatMessage(role="user", text="hi")], seen.append)

    # Not garbled with a fallback attempt — the caller (orchestrator) handles
    # this failure with its own spoken apology instead.
    assert seen == ["partial..."]
    assert fallback.calls == 0


@pytest.mark.asyncio
async def test_does_not_fall_back_on_a_non_transient_error_even_before_emitting():
    primary = _StubProvider(error=_bad_request_error())
    fallback = _StubProvider(result=_result("fallback reply"))
    client = LLMClient(provider=primary, fallback_provider=fallback, circuit_breaker=CircuitBreaker())

    with pytest.raises(anthropic.APIStatusError):
        await client.stream_reply("sys", [ChatMessage(role="user", text="hi")], lambda _: None)

    assert fallback.calls == 0


@pytest.mark.asyncio
async def test_no_fallback_configured_reraises_immediately():
    primary = _StubProvider(error=ValueError("nope"))
    client = LLMClient(provider=primary, circuit_breaker=CircuitBreaker())

    with pytest.raises(ValueError, match="nope"):
        await client.stream_reply("sys", [], lambda _: None)


@pytest.mark.asyncio
async def test_circuit_breaker_trips_after_three_failures_and_skips_primary():
    primary = _StubProvider(error=_connection_error())
    fallback = _StubProvider(result=_result("fallback reply"))
    breaker = CircuitBreaker(failure_threshold=3)
    client = LLMClient(provider=primary, fallback_provider=fallback, circuit_breaker=breaker)

    for _ in range(3):
        await client.stream_reply("sys", [], lambda _: None)

    assert primary.calls == 3
    assert breaker.is_open(client.tier)

    # A 4th call should skip the tripped primary entirely and go straight to fallback.
    result = await client.stream_reply("sys", [], lambda _: None)
    assert result.text == "fallback reply"
    assert primary.calls == 3  # unchanged -- primary was never called this time


def test_t1_simple_resolves_configured_fallback_chain_to_t1_standard():
    from jarvis.llm.providers import AnthropicProvider, OpenRouterProvider

    client = LLMClient(get_settings(), tier="t1_simple", circuit_breaker=CircuitBreaker())
    assert client._chain == ["t1_simple", "t1_standard"]
    assert isinstance(client._providers["t1_simple"], OpenRouterProvider)
    assert isinstance(client._provider_for("t1_standard"), AnthropicProvider)
    assert client._provider_for("t1_standard").model == "claude-sonnet-5"


def test_t1_standard_has_no_configured_fallback():
    client = LLMClient(get_settings(), tier="t1_standard", circuit_breaker=CircuitBreaker())
    assert client._chain == ["t1_standard"]


def test_t3_complex_degrades_through_two_hops():
    client = LLMClient(get_settings(), tier="t3_complex", circuit_breaker=CircuitBreaker())
    assert client._chain == ["t3_complex", "t2_medium", "t1_standard"]


def test_chain_walking_stops_on_a_cycle():
    s = Settings({"fallbacks": {"a": "b", "b": "a"}})
    from jarvis.llm.fallbacks import fallback_chain

    assert fallback_chain(s, "a") == ["b"]
