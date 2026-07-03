"""Microphone capture.

Streams 16-bit mono PCM from the default input device in fixed-size frames and
bridges the PortAudio callback thread to asyncio via a thread-safe queue.

``sounddevice`` is imported lazily so the rest of the package (and the test
suite) can be imported on machines without PortAudio.
"""
from __future__ import annotations

import asyncio
from typing import AsyncIterator, Optional

from jarvis.config import Settings, get_settings


class MicCapture:
    """Async source of raw PCM frames from the microphone.

    Usage::

        async with MicCapture() as mic:
            async for frame in mic.frames():
                ...   # frame: bytes of int16 PCM, frame_ms long
    """

    def __init__(self, settings: Optional[Settings] = None):
        s = settings or get_settings()
        self.sample_rate: int = int(s.audio.sample_rate)
        self.channels: int = int(s.audio.channels)
        self.frame_ms: int = int(s.audio.frame_ms)
        self.device = s.audio.get("device")
        self.frame_samples: int = self.sample_rate * self.frame_ms // 1000

        self._queue: "asyncio.Queue[bytes]" = asyncio.Queue(maxsize=64)
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._stream = None  # sounddevice.RawInputStream

    def _callback(self, indata, frames, time_info, status) -> None:
        # Runs on the PortAudio thread. Never block here; hand off to the loop.
        if self._loop is None:
            return
        data = bytes(indata)
        try:
            self._loop.call_soon_threadsafe(self._queue.put_nowait, data)
        except RuntimeError:
            # Loop is closing; drop the frame.
            pass

    def start(self) -> None:
        import sounddevice as sd  # lazy: requires PortAudio

        self._loop = asyncio.get_running_loop()
        self._stream = sd.RawInputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="int16",
            blocksize=self.frame_samples,
            device=self.device,
            callback=self._callback,
        )
        self._stream.start()

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    async def frames(self) -> AsyncIterator[bytes]:
        """Yield PCM frames until :meth:`stop` is called."""
        while self._stream is not None:
            yield await self._queue.get()

    async def __aenter__(self) -> "MicCapture":
        self.start()
        return self

    async def __aexit__(self, *exc) -> None:
        self.stop()
