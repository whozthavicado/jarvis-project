"""LLMClient tests — tier -> provider selection and the same-turn fallback,
using simple stub Provider objects (not a real SDK). AnthropicProvider and
OpenRouterProvider each have their own dedicated test file; this one is
about LLMClient's own logic: picking a provider and, if configured, falling
back to another one — but only when it's safe to do so.
"""
import pytest

from jarvis.config import get_settings
from jarvis.llm.client import LLMClient
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


@pytest.mark.asyncio
async def test_uses_primary_provider_when_it_succeeds():
    primary = _StubProvider(result=_result("hi"))
    fallback = _StubProvider(result=_result("fallback"))
    client = LLMClient(provider=primary, fallback_provider=fallback)

    seen = []
    result = await client.stream_reply("sys", [ChatMessage(role="user", text="hi")], seen.append)

    assert result.text == "hi"
    assert seen == ["hi"]
    assert primary.calls == 1
    assert fallback.calls == 0


@pytest.mark.asyncio
async def test_falls_back_when_primary_fails_before_emitting_any_text():
    primary = _StubProvider(error=RuntimeError("boom"))
    fallback = _StubProvider(result=_result("fallback reply"))
    client = LLMClient(provider=primary, fallback_provider=fallback)

    seen = []
    result = await client.stream_reply("sys", [ChatMessage(role="user", text="hi")], seen.append)

    assert result.text == "fallback reply"
    assert seen == ["fallback reply"]
    assert primary.calls == 1
    assert fallback.calls == 1


@pytest.mark.asyncio
async def test_does_not_fall_back_after_partial_text_already_emitted():
    primary = _PartialThenFailProvider("partial...", RuntimeError("mid-stream failure"))
    fallback = _StubProvider(result=_result("fallback reply"))
    client = LLMClient(provider=primary, fallback_provider=fallback)

    seen = []
    with pytest.raises(RuntimeError, match="mid-stream failure"):
        await client.stream_reply("sys", [ChatMessage(role="user", text="hi")], seen.append)

    # Not garbled with a fallback attempt — the caller (orchestrator) handles
    # this failure with its own spoken apology instead.
    assert seen == ["partial..."]
    assert fallback.calls == 0


@pytest.mark.asyncio
async def test_no_fallback_configured_reraises_immediately():
    primary = _StubProvider(error=ValueError("nope"))
    client = LLMClient(provider=primary)  # no fallback_provider, no fallback in settings for this tier

    with pytest.raises(ValueError, match="nope"):
        await client.stream_reply("sys", [], lambda _: None)


def test_t1_simple_resolves_configured_fallback_to_t1_standard():
    from jarvis.llm.providers import AnthropicProvider, OpenRouterProvider

    client = LLMClient(get_settings(), tier="t1_simple")
    assert isinstance(client._provider, OpenRouterProvider)
    assert isinstance(client._fallback_provider, AnthropicProvider)
    assert client._fallback_provider.model == "claude-sonnet-5"


def test_t1_standard_has_no_configured_fallback():
    client = LLMClient(get_settings(), tier="t1_standard")
    assert client._fallback_provider is None
