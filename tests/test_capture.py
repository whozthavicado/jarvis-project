"""MicCapture queue behavior — no PortAudio/hardware required.

Exercises the ``_put`` overflow path directly: on a live device the PortAudio
callback thread schedules ``_put`` via ``call_soon_threadsafe``, but the
drop-oldest logic itself is plain asyncio.Queue manipulation and is fully
testable without a real audio stream.
"""
import asyncio

import pytest

from jarvis.audio.capture import MicCapture
from jarvis.config import Settings


@pytest.mark.asyncio
async def test_put_under_capacity_just_enqueues():
    mic = MicCapture()
    mic._put(b"frame-1")
    mic._put(b"frame-2")
    assert mic.dropped_frames == 0
    assert mic._queue.qsize() == 2


@pytest.mark.asyncio
async def test_put_over_capacity_drops_oldest_without_raising():
    mic = MicCapture()
    mic._queue = asyncio.Queue(maxsize=2)  # tiny, to force overflow quickly

    mic._put(b"a")
    mic._put(b"b")
    mic._put(b"c")  # queue is full: must drop "a", keep "b" + "c"

    assert mic.dropped_frames == 1
    assert mic._queue.qsize() == 2
    first = mic._queue.get_nowait()
    second = mic._queue.get_nowait()
    assert (first, second) == (b"b", b"c")


@pytest.mark.asyncio
async def test_queue_sized_for_several_seconds_of_audio():
    # frame_ms=30 by default; queue should comfortably exceed 1s of buffering
    # (regression guard for the original 64-frame / ~1.9s overflow bug).
    mic = MicCapture()
    assert mic._queue.maxsize >= 1000 // mic.frame_ms * 5  # >= 5 seconds


def _settings_with(device, device_fallback):
    return Settings(
        {
            "audio": {
                "sample_rate": 16000,
                "channels": 1,
                "frame_ms": 30,
                "device": device,
                "device_fallback": device_fallback,
            }
        }
    )


def test_no_fallback_configured_skips_probing_entirely():
    calls = []

    def probe(device, sample_rate, channels, duration_ms):
        calls.append(device)
        return 0.0  # would fail if it were ever consulted

    mic = MicCapture(_settings_with(device=None, device_fallback=[]), probe=probe)
    resolved = mic._resolve_device()

    assert resolved is None
    assert calls == []  # zero probe calls -- no behavior change without fallback configured


def test_primary_device_used_when_it_passes_the_probe():
    def probe(device, sample_rate, channels, duration_ms):
        return 100.0 if device is None else 0.0

    mic = MicCapture(_settings_with(device=None, device_fallback=[3]), probe=probe)
    assert mic._resolve_device() is None


def test_falls_back_to_next_candidate_when_primary_is_silent():
    def probe(device, sample_rate, channels, duration_ms):
        return 0.0 if device is None else 100.0

    mic = MicCapture(_settings_with(device=None, device_fallback=[3]), probe=probe)
    assert mic._resolve_device() == 3


def test_falls_back_to_primary_when_every_candidate_is_silent():
    def probe(device, sample_rate, channels, duration_ms):
        return 0.0

    mic = MicCapture(_settings_with(device=None, device_fallback=[3, 1]), probe=probe)
    assert mic._resolve_device() is None  # degraded, not a crash


def test_probe_exception_is_treated_like_silence_and_never_raises():
    def probe(device, sample_rate, channels, duration_ms):
        if device == 3:
            raise RuntimeError("device unavailable")
        return 100.0 if device == 1 else 0.0

    mic = MicCapture(_settings_with(device=None, device_fallback=[3, 1]), probe=probe)
    assert mic._resolve_device() == 1


def test_duplicate_candidate_matching_primary_is_not_probed_twice():
    calls = []

    def probe(device, sample_rate, channels, duration_ms):
        calls.append(device)
        return 100.0

    mic = MicCapture(_settings_with(device=3, device_fallback=[3]), probe=probe)
    resolved = mic._resolve_device()

    assert resolved == 3
    assert calls == []  # candidates collapse to just [3] == just the primary -> no probing
