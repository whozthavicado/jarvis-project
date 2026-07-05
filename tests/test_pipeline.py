"""Pipeline tests — transcripts()'s wiring of VoicedSegment.mean_rms into
WhisperClient.transcribe's low_energy signal. Mic/whisper/watchdog are faked;
no real audio or network involved."""
import pytest

import jarvis.audio.pipeline as pipeline_mod
from jarvis.audio.types import Transcript
from jarvis.audio.vad import VoicedSegment


class _FakeMic:
    def __init__(self, settings=None):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def frames(self):
        async def _gen():
            yield b"\x00\x00"

        return _gen()


class _FakeWatchdog:
    def __init__(self, settings=None):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _FakeWhisper:
    def __init__(self, settings=None):
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def transcribe(self, pcm, *, low_energy=True):
        self.calls.append((pcm, low_energy))
        return Transcript(text="hi", low_energy=low_energy)


def _fake_segment_stream(segments):
    async def _stream(frames, settings=None):
        for seg in segments:
            yield seg

    return _stream


async def test_low_energy_segment_passes_low_energy_true(monkeypatch):
    fake_whisper = _FakeWhisper()
    monkeypatch.setattr(pipeline_mod, "MicCapture", _FakeMic)
    monkeypatch.setattr(pipeline_mod, "WhisperClient", lambda settings=None: fake_whisper)
    monkeypatch.setattr(pipeline_mod, "WhisperWatchdog", _FakeWatchdog)
    monkeypatch.setattr(
        pipeline_mod,
        "segment_stream",
        _fake_segment_stream([VoicedSegment(pcm=b"quiet", mean_rms=100.0)]),
    )

    results = [t async for t in pipeline_mod.transcripts()]

    assert len(fake_whisper.calls) == 1
    assert fake_whisper.calls[0] == (b"quiet", True)
    assert results[0].low_energy is True


async def test_high_energy_segment_passes_low_energy_false(monkeypatch):
    fake_whisper = _FakeWhisper()
    monkeypatch.setattr(pipeline_mod, "MicCapture", _FakeMic)
    monkeypatch.setattr(pipeline_mod, "WhisperClient", lambda settings=None: fake_whisper)
    monkeypatch.setattr(pipeline_mod, "WhisperWatchdog", _FakeWatchdog)
    monkeypatch.setattr(
        pipeline_mod,
        "segment_stream",
        _fake_segment_stream([VoicedSegment(pcm=b"loud", mean_rms=5000.0)]),
    )

    results = [t async for t in pipeline_mod.transcripts()]

    assert fake_whisper.calls[0] == (b"loud", False)
    assert results[0].low_energy is False
