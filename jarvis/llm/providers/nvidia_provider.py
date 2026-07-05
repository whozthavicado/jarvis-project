"""NVIDIA NIM backend — OpenAI-compatible chat completions, streaming.

NVIDIA's hosted API catalog (build.nvidia.com / integrate.api.nvidia.com)
serves 80+ models behind vLLM's OpenAI-compatible server, free with rate
limits, via a free NVIDIA Developer Program key. Built on ``httpx`` (already
a dependency), same as OpenRouterProvider, and used the same way: a second,
independent free option in the fallback chain (see ``config/settings.yaml``
-> ``fallbacks``). For ``t1_simple`` specifically, NVIDIA is actually the
*primary* provider (not the fallback) as of 2026-07-04 -- OpenRouter's free
``google/gemma-4-31b-it:free`` was found live to be persistently
rate-limited, so the two were swapped for that one tier; every other tier
still has OpenRouter primary / NVIDIA fallback.

Wire format per NVIDIA's own NIM API reference and the underlying vLLM
OpenAI-compatible server docs, live-verified 2026-07-04 against a real
NVIDIA_API_KEY (``python -m scripts.milestone2 --check --tier t1_simple``,
or any other tier -- every free-mode tier's NVIDIA-backed hop was checked):

- ``POST {base_url}/chat/completions``, ``Authorization: Bearer <key>``,
  standard OpenAI-shaped streaming (``choices[0].delta.content``,
  ``finish_reason``, ``[DONE]`` sentinel).
- Unlike OpenRouter, a vLLM-based server reports failures as a normal HTTP
  error status, not an in-band SSE ``error`` field -- so this provider
  doesn't need an OpenRouterError-style exception; ``httpx``'s own
  ``raise_for_status()`` is enough.
- ``stream_options: {"include_usage": true}`` is sent to ask for a final
  usage chunk (the OpenAI/vLLM convention) since it's otherwise omitted
  during streaming; if a given NIM model ignores the option, usage just
  stays at 0, same graceful-omission handling OpenRouterProvider already has.
"""
from __future__ import annotations

import json
import os
from typing import Any, Callable, Dict, List, Optional

import httpx

from jarvis.llm.parsing import ThinkTagStreamFilter
from jarvis.llm.types import ChatMessage, TurnResult

_BASE_URL = "https://integrate.api.nvidia.com/v1"


class NvidiaProvider:
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
            api_key = self._api_key or os.environ.get("NVIDIA_API_KEY")
            if not api_key:
                raise RuntimeError(
                    "NVIDIA_API_KEY is not set (needed for the NVIDIA NIM provider)."
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
            "stream_options": {"include_usage": True},
            "messages": [{"role": "system", "content": system_prompt}]
            + [{"role": m.role, "content": m.text} for m in messages],
        }

        text_parts: List[str] = []
        finish_reason = ""
        model_used = self.model
        usage: Dict[str, Any] = {}

        # NVIDIA's reasoning NIMs (DeepSeek-R1, Llama-Nemotron) inline their
        # chain-of-thought as <think>...</think> in the content stream — NVIDIA
        # documents this explicitly. Filter it so it's neither spoken by TTS
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
