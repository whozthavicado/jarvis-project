"""NvidiaProvider tests — real httpx.AsyncClient wired to httpx.MockTransport,
same approach as test_provider_openrouter.py since NVIDIA NIM is also an
OpenAI-compatible streaming chat completions API (vLLM-based). Unlike
OpenRouter, NIM reports failures as normal HTTP error statuses rather than
an in-band SSE `error` field, so there's no NvidiaError equivalent to test.
"""
import json

import httpx
import pytest

from jarvis.llm.providers.nvidia_provider import NvidiaProvider
from jarvis.llm.types import ChatMessage


def _sse_body(*chunks: dict) -> bytes:
    lines = [f"data: {json.dumps(c)}\n\n" for c in chunks]
    lines.append("data: [DONE]\n\n")
    return "".join(lines).encode()


def _client_with(body: bytes, status: int = 200) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, content=body, headers={"content-type": "text/event-stream"})

    return httpx.AsyncClient(
        base_url="https://integrate.api.nvidia.com/v1", transport=httpx.MockTransport(handler)
    )


@pytest.mark.asyncio
async def test_streams_text_deltas_and_builds_result():
    body = _sse_body(
        {
            "model": "meta/llama-3.1-8b-instruct",
            "choices": [{"delta": {"content": "Hi"}, "finish_reason": None}],
        },
        {
            "choices": [{"delta": {"content": " there."}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 3},
        },
    )
    provider = NvidiaProvider(model="meta/llama-3.1-8b-instruct", client=_client_with(body))

    seen = []
    result = await provider.stream_reply(
        system_prompt="sys", messages=[ChatMessage(role="user", text="hi")], on_text=seen.append
    )

    assert seen == ["Hi", " there."]
    assert result.text == "Hi there."
    assert result.model == "meta/llama-3.1-8b-instruct"
    assert result.stop_reason == "stop"
    assert result.input_tokens == 10
    assert result.output_tokens == 3
    assert result.cache_read_tokens == 0


@pytest.mark.asyncio
async def test_request_shape_sends_system_message_and_include_usage_option():
    body = _sse_body({"choices": [{"delta": {"content": "ok"}, "finish_reason": "stop"}]})
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

    client = httpx.AsyncClient(
        base_url="https://integrate.api.nvidia.com/v1", transport=httpx.MockTransport(handler)
    )
    provider = NvidiaProvider(
        model="meta/llama-3.1-8b-instruct", max_tokens=42, api_key="test-key", client=client
    )

    await provider.stream_reply(
        system_prompt="be helpful",
        messages=[ChatMessage(role="user", text="hi")],
        on_text=lambda _: None,
    )

    payload = captured["payload"]
    assert payload["model"] == "meta/llama-3.1-8b-instruct"
    assert payload["max_tokens"] == 42
    assert payload["stream"] is True
    assert payload["stream_options"] == {"include_usage": True}
    assert payload["messages"][0] == {"role": "system", "content": "be helpful"}
    assert payload["messages"][1] == {"role": "user", "content": "hi"}


@pytest.mark.asyncio
async def test_inline_think_blocks_are_filtered_from_speech_and_text():
    # NVIDIA's reasoning NIMs (DeepSeek-R1, Llama-Nemotron) inline their
    # chain-of-thought as <think>...</think> in content — documented by
    # NVIDIA. It must never reach TTS or the returned text, even when the
    # tags are split across SSE chunks.
    body = _sse_body(
        {"choices": [{"delta": {"content": "<thi"}, "finish_reason": None}]},
        {"choices": [{"delta": {"content": "nk>chain of thought here</th"}, "finish_reason": None}]},
        {"choices": [{"delta": {"content": "ink>The answer"}, "finish_reason": None}]},
        {"choices": [{"delta": {"content": " is four."}, "finish_reason": "stop"}]},
    )
    provider = NvidiaProvider(model="deepseek-ai/deepseek-r1", client=_client_with(body))

    seen = []
    result = await provider.stream_reply(
        system_prompt="sys", messages=[ChatMessage(role="user", text="2+2?")], on_text=seen.append
    )

    assert "".join(seen) == "The answer is four."
    assert result.text == "The answer is four."
    assert "<think>" not in result.text


@pytest.mark.asyncio
async def test_http_error_status_raises():
    client = httpx.AsyncClient(
        base_url="https://integrate.api.nvidia.com/v1",
        transport=httpx.MockTransport(lambda req: httpx.Response(429, content=b"")),
    )
    provider = NvidiaProvider(model="meta/llama-3.1-8b-instruct", client=client)

    with pytest.raises(httpx.HTTPStatusError):
        await provider.stream_reply(
            system_prompt="sys", messages=[ChatMessage(role="user", text="hi")], on_text=lambda _: None
        )


def test_missing_api_key_raises_clear_error(monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    provider = NvidiaProvider(model="meta/llama-3.1-8b-instruct")
    with pytest.raises(RuntimeError, match="NVIDIA_API_KEY"):
        provider._get_client()
