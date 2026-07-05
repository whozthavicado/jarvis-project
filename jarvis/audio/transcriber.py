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
# whisper.cpp emits bracketed/parenthesized non-speech markers on silence or
# noise, e.g. "[BLANK_AUDIO]", "(silence)", "[SOUND]" — treat a transcript
# that is *only* one such tag as a hallucination, same as empty/punctuation-only.
_TAG_ONLY = re.compile(r"^[\[(][a-z0-9_'\- ]+[\])]$", re.IGNORECASE)


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

    def _is_hallucination(self, text: str, *, low_energy: bool = True) -> bool:
        """Empty/punctuation-only/bracketed-tag transcripts are always
        rejected, regardless of energy -- they're unambiguous non-speech
        markers (silence, or whisper tagging a real loud non-speech sound
        like "[XBOX SOUND]"), not something a quiet room could produce that
        a loud one couldn't. Only the literal blocklist match (ARCHITECTURE.md
        §5.4: "...when VAD energy was low") is gated on *low_energy* --
        phrases like "thank you"/"bye" are real things a user might actually
        say at any volume, and are only suspicious as a whisper hallucination
        artifact when the segment was quiet. Defaults to True so any caller
        that doesn't pass an energy signal keeps the old, unconditional
        blocklist behavior unchanged; ``transcribe`` is the one real call
        site updated to pass the pipeline's actual computed signal.
        """
        t = text.strip().lower()
        if not t:
            return True
        if _PUNCT_ONLY.match(t):
            return True
        if _TAG_ONLY.match(t):
            return True
        if not low_energy:
            return False
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

    async def transcribe(self, pcm: bytes, *, low_energy: bool = True) -> Transcript:
        """Transcribe one PCM segment. Returns a (possibly rejected) Transcript.

        ``low_energy`` (keyword-only, defaults True) is the pipeline's
        VAD-derived signal for whether this segment was quiet enough that
        the hallucination guard should apply -- see ``_is_hallucination``.
        """
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

        if self._is_hallucination(text, low_energy=low_energy):
            return Transcript(
                text="",
                duration_ms=duration,
                rejected=True,
                reason="hallucination_or_empty",
                low_energy=low_energy,
            )
        return Transcript(text=text, duration_ms=duration, low_energy=low_energy)
