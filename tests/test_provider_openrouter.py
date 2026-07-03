"""OpenRouterProvider tests — real httpx.AsyncClient wired to httpx.MockTransport
(httpx's own supported no-network testing mechanism), so we're exercising the
real streaming/SSE-parsing code path, not a hand-rolled substitute for httpx
itself. Wire shapes here match what was verified against OpenRouter's docs
and a live model lookup (see the provider-strategy research this session).
"""
import json

import httpx
import pytest

from jarvis.llm.providers.openrouter_provider import OpenRouterError, OpenRouterProvider
from jarvis.llm.types import ChatMessage


def _sse_body(*chunks: dict) -> bytes:
    lines = [f"data: {json.dumps(c)}\n\n" for c in chunks]
    lines.append("data: [DONE]\n\n")
    return "".join(lines).encode()


def _client_with(body: bytes, status: int = 200) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, content=body, headers={"content-type": "text/event-stream"})

    return httpx.AsyncClient(
        base_url="https://openrouter.ai/api/v1", transport=httpx.MockTransport(handler)
    )


@pytest.mark.asyncio
async def test_streams_text_deltas_and_builds_result():
    body = _sse_body(
        {
            "model": "google/gemma-4-31b-it:free",
            "choices": [{"delta": {"content": "Hi"}, "finish_reason": None}],
        },
        {
            "choices": [{"delta": {"content": " there."}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 3},
        },
    )
    provider = OpenRouterProvider(
        model="google/gemma-4-31b-it:free", client=_client_with(body)
    )

    seen = []
    result = await provider.stream_reply(
        system_prompt="sys", messages=[ChatMessage(role="user", text="hi")], on_text=seen.append
    )

    assert seen == ["Hi", " there."]
    assert result.text == "Hi there."
    assert result.model == "google/gemma-4-31b-it:free"
    assert result.stop_reason == "stop"
    assert result.input_tokens == 10
    assert result.output_tokens == 3
    assert result.cache_read_tokens == 0  # OpenRouter has no cache-read concept


@pytest.mark.asyncio
async def test_request_shape_sends_system_as_first_message():
    body = _sse_body({"choices": [{"delta": {"content": "ok"}, "finish_reason": "stop"}]})
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

    client = httpx.AsyncClient(
        base_url="https://openrouter.ai/api/v1", transport=httpx.MockTransport(handler)
    )
    provider = OpenRouterProvider(model="x:free", max_tokens=42, api_key="test-key", client=client)

    await provider.stream_reply(
        system_prompt="be helpful",
        messages=[ChatMessage(role="user", text="hi")],
        on_text=lambda _: None,
    )

    payload = captured["payload"]
    assert payload["model"] == "x:free"
    assert payload["max_tokens"] == 42
    assert payload["stream"] is True
    assert payload["messages"][0] == {"role": "system", "content": "be helpful"}
    assert payload["messages"][1] == {"role": "user", "content": "hi"}


@pytest.mark.asyncio
async def test_mid_stream_error_raises_and_preserves_already_emitted_text():
    # OpenRouter signals a mid-stream failure as a normal SSE chunk with an
    # "error" field and HTTP 200 — not a raised HTTP status. See the docstring
    # in openrouter_provider.py for why this needed explicit verification.
    body = (
        b'data: {"choices":[{"delta":{"content":"partial"},"finish_reason":null}]}\n\n'
        b'data: {"error":{"message":"rate limited","code":429},"choices":[]}\n\n'
        b"data: [DONE]\n\n"
    )
    provider = OpenRouterProvider(model="x:free", client=_client_with(body))

    seen = []
    with pytest.raises(OpenRouterError, match="rate limited"):
        await provider.stream_reply(
            system_prompt="sys", messages=[ChatMessage(role="user", text="hi")], on_text=seen.append
        )
    assert seen == ["partial"]


@pytest.mark.asyncio
async def test_http_error_status_raises():
    client = httpx.AsyncClient(
        base_url="https://openrouter.ai/api/v1",
        transport=httpx.MockTransport(lambda req: httpx.Response(429, content=b"")),
    )
    provider = OpenRouterProvider(model="x:free", client=client)

    with pytest.raises(httpx.HTTPStatusError):
        await provider.stream_reply(
            system_prompt="sys", messages=[ChatMessage(role="user", text="hi")], on_text=lambda _: None
        )


def test_missing_api_key_raises_clear_error(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    provider = OpenRouterProvider(model="x:free")
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        provider._get_client()
