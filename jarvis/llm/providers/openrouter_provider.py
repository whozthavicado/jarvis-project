"""OpenRouter backend — OpenAI-compatible chat completions, streaming.

Built on ``httpx`` (already a dependency for the whisper client) rather than
pulling in the ``openai`` SDK, to keep the footprint small — consistent with
the project's RAM/dependency-minimalism (see ARCHITECTURE.md §0).

Wire format verified directly against OpenRouter's docs and a live model
lookup (not assumed): ``POST /chat/completions`` with ``Authorization:
Bearer <key>``, SSE chunks shaped like OpenAI's, ``choices[0].delta.content``
for text, ``usage`` on the final chunk, and — the detail that matters most
here — errors that happen *after* streaming has already started arrive as a
normal SSE chunk with an ``error`` field and HTTP 200, not a raised HTTP
exception. That's the case :class:`OpenRouterError` exists for.
"""
from __future__ import annotations

import json
import os
from typing import Any, Callable, Dict, List, Optional

import httpx

from jarvis.llm.parsing import ThinkTagStreamFilter
from jarvis.llm.types import ChatMessage, TurnResult

_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterError(RuntimeError):
    """A mid-stream error reported by OpenRouter itself (HTTP 200, `error` field)."""


class OpenRouterProvider:
    def __init__(
        self,
        model: str,
        max_tokens: int = 1024,
        api_key: Optional[str] = None,
        client: Optional[httpx.AsyncClient] = None,
    ):
        self.model = model
        self.max_tokens = max_tokens
        self._api_key = api_key
        self._client = client  # injectable for tests; lazily created otherwise

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            api_key = self._api_key or os.environ.get("OPENROUTER_API_KEY")
            if not api_key:
                raise RuntimeError(
                    "OPENROUTER_API_KEY is not set (needed for the OpenRouter provider)."
                )
            self._client = httpx.AsyncClient(
                base_url=_BASE_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=30.0,
            )
        return self._client

    async def stream_reply(
        self,
        system_prompt: str,
        messages: List[ChatMessage],
        on_text: Callable[[str], None],
    ) -> TurnResult:
        client = self._get_client()

        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "stream": True,
            "messages": [{"role": "system", "content": system_prompt}]
            + [{"role": m.role, "content": m.text} for m in messages],
        }

        text_parts: List[str] = []
        finish_reason = ""
        model_used = self.model
        usage: Dict[str, Any] = {}

        # Open models often inline chain-of-thought as <think>...</think> in
        # the content stream itself; filter it so it's neither spoken by TTS
        # nor recorded in history (see jarvis/llm/parsing.py).
        def _visible(chunk_text: str) -> None:
            text_parts.append(chunk_text)
            on_text(chunk_text)

        think_filter = ThinkTagStreamFilter(_visible)

        async with client.stream("POST", "/chat/completions", json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[len("data:") :].strip()
                if not data:
                    continue
                if data == "[DONE]":
                    break
                chunk = json.loads(data)

                if chunk.get("error"):
                    err = chunk["error"]
                    message = err.get("message", str(err)) if isinstance(err, dict) else str(err)
                    raise OpenRouterError(message)

                model_used = chunk.get("model") or model_used
                choices = chunk.get("choices") or []
                if choices:
                    delta = choices[0].get("delta") or {}
                    text = delta.get("content")
                    if text:
                        think_filter.feed(text)
                    if choices[0].get("finish_reason"):
                        finish_reason = choices[0]["finish_reason"]
                if chunk.get("usage"):
                    usage = chunk["usage"]

        think_filter.flush()

        return TurnResult(
            text="".join(text_parts),
            model=model_used,
            stop_reason=finish_reason,
            input_tokens=int(usage.get("prompt_tokens", 0) or 0),
            output_tokens=int(usage.get("completion_tokens", 0) or 0),
            cache_read_tokens=0,
            cache_creation_tokens=0,
        )
