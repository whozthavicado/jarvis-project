"""MicCapture queue behavior — no PortAudio/hardware required.

Exercises the ``_put`` overflow path directly: on a live device the PortAudio
callback thread schedules ``_put`` via ``call_soon_threadsafe``, but the
drop-oldest logic itself is plain asyncio.Queue manipulation and is fully
testable without a real audio stream.
"""
import asyncio

import pytest

from jarvis.audio.capture import MicCapture


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
