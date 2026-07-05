"""Transcriber tests — WAV framing + hallucination guard, no network."""
import io
import wave

import pytest

from jarvis.config import get_settings
from jarvis.audio.transcriber import WhisperClient, pcm_to_wav


def test_pcm_to_wav_roundtrips():
    pcm = b"\x01\x02" * 16000  # 1 s of 16 kHz int16 mono
    wav = pcm_to_wav(pcm, sample_rate=16000, channels=1)
    with wave.open(io.BytesIO(wav), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 16000
        assert wf.readframes(wf.getnframes()) == pcm


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        return None


class _FakePoster:
    """Stands in for httpx.AsyncClient.post with a canned JSON body."""

    def __init__(self, text):
        self._text = text
        self.calls = 0

    async def post(self, *args, **kwargs):
        self.calls += 1
        return _FakeResponse({"text": self._text})


def _client_with(text):
    w = WhisperClient(get_settings())
    w._client = _FakePoster(text)
    return w


@pytest.mark.asyncio
async def test_real_speech_passes_through():
    w = _client_with("  turn on the lights  ")
    pcm = b"\x10\x00" * 8000  # 0.5 s
    t = await w.transcribe(pcm)
    assert t.usable
    assert t.text == "turn on the lights"
    assert t.duration_ms == 500


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bogus",
    [
        "",
        "   ",
        "...",
        "Thank you.",
        "you",
        "[BLANK_AUDIO]",
        "[blank_audio]",
        "(silence)",
        "[SOUND]",
        "thank you for watching",
        "please subscribe",
        "like and subscribe",
        "www.opensubtitles.org",
        "bye",
        "goodbye",
        "[laughs]",
        "(inaudible)",
        "[music - 1]",
        "[speaker's note]",
    ],
)
async def test_hallucinations_are_rejected(bogus):
    w = _client_with(bogus)
    t = await w.transcribe(b"\x00\x00" * 8000)
    assert t.rejected
    assert not t.usable
    assert t.reason == "hallucination_or_empty"


@pytest.mark.asyncio
async def test_requires_context_manager():
    w = WhisperClient(get_settings())  # no _client set
    with pytest.raises(RuntimeError):
        await w.transcribe(b"\x00\x00" * 100)
