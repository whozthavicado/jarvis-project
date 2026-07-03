"""Whisper transcription client.

Talks to a persistent ``whisper.cpp`` server (the ``server`` binary) over HTTP so
the model loads once and stays resident. Wraps raw PCM segments in a WAV
container and POSTs them to ``/inference``.

Includes a hallucination guard: Whisper emits stock artifacts ("thank you.",
"subtitles by ...") on silence/near-silence, which we drop.
"""
from __future__ import annotations

import io
import re
import wave
from typing import Optional

import httpx

from jarvis.config import Settings, get_settings
from jarvis.audio.types import Transcript

_PUNCT_ONLY = re.compile(r"^[\W_]+$", re.UNICODE)


def pcm_to_wav(pcm: bytes, sample_rate: int, channels: int = 1) -> bytes:
    """Wrap int16 PCM bytes in a WAV container (in-memory)."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # int16
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()


def clean_text(raw: str) -> str:
    return raw.strip()


class WhisperClient:
    """Async client for a running whisper.cpp server."""

    def __init__(self, settings: Optional[Settings] = None):
        s = settings or get_settings()
        self.sample_rate = int(s.audio.sample_rate)
        self.channels = int(s.audio.channels)
        self.base_url = str(s.whisper.server_url).rstrip("/")
        self.endpoint = str(s.whisper.endpoint)
        self.timeout_s = float(s.whisper.timeout_s)
        self.language = str(s.whisper.language)
        self.blocklist = {
            b.strip().lower() for b in s.whisper.get("hallucination_blocklist", [])
        }
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "WhisperClient":
        self._client = httpx.AsyncClient(timeout=self.timeout_s)
        return self

    async def __aexit__(self, *exc) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _duration_ms(self, pcm: bytes) -> int:
        n_samples = len(pcm) // (2 * self.channels)
        return int(n_samples / self.sample_rate * 1000)

    def _is_hallucination(self, text: str) -> bool:
        t = text.strip().lower()
        if not t:
            return True
        if _PUNCT_ONLY.match(t):
            return True
        return t in self.blocklist

    async def health(self) -> bool:
        """Return True if the whisper server answers. Never raises."""
        client = self._client or httpx.AsyncClient(timeout=3.0)
        try:
            resp = await client.get(self.base_url + "/", timeout=3.0)
            return resp.status_code < 500
        except Exception:
            return False
        finally:
            if self._client is None:
                await client.aclose()

    async def transcribe(self, pcm: bytes) -> Transcript:
        """Transcribe one PCM segment. Returns a (possibly rejected) Transcript."""
        if self._client is None:
            raise RuntimeError("WhisperClient must be used as an async context manager")

        duration = self._duration_ms(pcm)
        wav = pcm_to_wav(pcm, self.sample_rate, self.channels)

        files = {"file": ("segment.wav", wav, "audio/wav")}
        data = {"response_format": "json", "temperature": "0.0"}
        if self.language and self.language != "auto":
            data["language"] = self.language

        resp = await self._client.post(
            self.base_url + self.endpoint, files=files, data=data
        )
        resp.raise_for_status()
        payload = resp.json()
        text = clean_text(payload.get("text", ""))

        if self._is_hallucination(text):
            return Transcript(
                text="",
                duration_ms=duration,
                rejected=True,
                reason="hallucination_or_empty",
            )
        return Transcript(text=text, duration_ms=duration)
