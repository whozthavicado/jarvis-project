"""Output post-processing for models we don't fully control (M "free mode").

Anthropic models put chain-of-thought in typed ``thinking`` deltas that
AnthropicProvider already filters out. Open models served by OpenRouter /
NVIDIA NIM often inline it in the *content* stream as ``<think>...</think>``
(NVIDIA documents exactly this for its reasoning NIMs, e.g. DeepSeek-R1 and
Llama-Nemotron). For a voice assistant that pipes streamed text straight
into TTS, a leaked think block means Z.E.R.O speaks its chain of thought out
loud — so filtering is a correctness requirement here, not cosmetics.

Three tools, used by the OpenRouter/NVIDIA providers and the router
classifier:

- :class:`ThinkTagStreamFilter` — stateful streaming filter that suppresses
  think spans as chunks arrive, correctly handling tags split across chunk
  boundaries (holds back at most ``len("<think>") - 1`` chars of real text).
- :func:`strip_think` — the offline equivalent for complete strings.
- :func:`extract_json_object` — pull the first parseable JSON object out of
  a model reply that may wrap it in prose, code fences, or think tags. This
  replaces Anthropic's schema-enforced ``output_config`` for the routing
  classifier: free-tier backends can't guarantee schema-constrained output
  through our shared Provider interface, so the guarantee moves from "the
  API can't return non-JSON" to "we can dig the JSON out of almost anything,
  and the caller fails soft if we can't" (see jarvis/routing/router.py).
"""
from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict

_OPEN = "<think>"
_CLOSE = "</think>"

# An unclosed trailing <think> (stream cut off mid-thought) is dropped too.
_THINK_RE = re.compile(r"<think>.*?(?:</think>|\Z)", re.DOTALL)


def strip_think(text: str) -> str:
    """Remove ``<think>...</think>`` spans (and an unclosed trailing one)."""
    return _THINK_RE.sub("", text)


def extract_json_object(text: str) -> Dict[str, Any]:
    """First parseable JSON object in *text*, however it's wrapped.

    Scans every ``{`` and attempts a ``raw_decode`` from it, so prose before,
    prose after, markdown code fences, and think tags around the object all
    parse fine. Raises ``ValueError`` if nothing decodes — callers treat that
    like any other classifier failure (fail soft to a default tier).
    """
    cleaned = strip_think(text)
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", cleaned):
        try:
            obj, _end = decoder.raw_decode(cleaned, match.start())
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    raise ValueError(f"No JSON object found in model reply: {cleaned[:200]!r}")


class ThinkTagStreamFilter:
    """Suppress ``<think>...</think>`` spans from a stream of text chunks.

    Feed raw deltas via :meth:`feed`; visible text is forwarded to *emit* as
    soon as it's provably outside a think span. Call :meth:`flush` after the
    stream ends so a trailing partial-tag lookalike (e.g. the reply genuinely
    ends with ``"a <thin"``) isn't swallowed. Content inside an unclosed
    think span at stream end is dropped — it was chain-of-thought.
    """

    def __init__(self, emit: Callable[[str], None]):
        self._emit = emit
        self._buf = ""
        self._in_think = False

    def feed(self, chunk: str) -> None:
        self._buf += chunk
        while True:
            if self._in_think:
                idx = self._buf.find(_CLOSE)
                if idx == -1:
                    # Discard the thought, but keep a tail short enough that a
                    # close tag split across chunks can still be recognized.
                    self._buf = self._buf[-(len(_CLOSE) - 1):]
                    return
                self._buf = self._buf[idx + len(_CLOSE):]
                self._in_think = False
            else:
                idx = self._buf.find(_OPEN)
                if idx != -1:
                    if idx:
                        self._emit(self._buf[:idx])
                    self._buf = self._buf[idx + len(_OPEN):]
                    self._in_think = True
                    continue
                # No full open tag: emit everything except a trailing prefix
                # of one (it may complete in the next chunk).
                keep = self._partial_tag_suffix_len(self._buf)
                if len(self._buf) > keep:
                    cut = len(self._buf) - keep
                    self._emit(self._buf[:cut])
                    self._buf = self._buf[cut:]
                return

    @staticmethod
    def _partial_tag_suffix_len(buf: str) -> int:
        for n in range(min(len(buf), len(_OPEN) - 1), 0, -1):
            if buf.endswith(_OPEN[:n]):
                return n
        return 0

    def flush(self) -> None:
        if not self._in_think and self._buf:
            self._emit(self._buf)
        self._buf = ""
