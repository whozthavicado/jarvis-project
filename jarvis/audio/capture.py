"""Microphone capture.

Streams 16-bit mono PCM from the default input device in fixed-size frames and
bridges the PortAudio callback thread to asyncio via a thread-safe queue.

``sounddevice`` is imported lazily so the rest of the package (and the test
suite) can be imported on machines without PortAudio.

Device fallback: a Bluetooth input (AirPods, etc.) can appear connected and
selected while actually producing silence -- macOS doesn't always force a
headset from A2DP into HFP mic mode just because an app opened an input
stream. ``audio.device_fallback`` (settings.yaml) names candidate devices to
try, in order, if the primary ``audio.device`` looks silent at startup. This
is a one-time startup probe, not continuous monitoring -- switching devices
mid-stream would be a much larger, riskier change for a problem that's
almost always present (or absent) for the whole session.
"""
from __future__ import annotations

import asyncio
import math
from typing import Any, AsyncIterator, Callable, List, Optional

from jarvis.config import Settings, get_settings

_DEFAULT_PROBE_MS = 300
_DEFAULT_PROBE_RMS_THRESHOLD = 50.0


def _probe_rms(device: Any, sample_rate: int, channels: int, duration_ms: int) -> float:
    """Record a short blocking clip from *device* and return its RMS.

    Real hardware access -- never called in tests directly; MicCapture takes
    an injectable ``probe`` callable instead.
    """
    import sounddevice as sd  # lazy: requires PortAudio

    n_samples = max(1, sample_rate * duration_ms // 1000)
    rec = sd.rec(n_samples, samplerate=sample_rate, channels=channels, dtype="int16", device=device)
    sd.wait()
    if rec.size == 0:
        return 0.0
    total = int((rec.astype("int64") ** 2).sum())
    return math.sqrt(total / rec.size)


class MicCapture:
    """Async source of raw PCM frames from the microphone.

    Usage::

        async with MicCapture() as mic:
            async for frame in mic.frames():
                ...   # frame: bytes of int16 PCM, frame_ms long
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        probe: Optional[Callable[[Any, int, int, int], float]] = None,
    ):
        s = settings or get_settings()
        self.sample_rate: int = int(s.audio.sample_rate)
        self.channels: int = int(s.audio.channels)
        self.frame_ms: int = int(s.audio.frame_ms)
        self.device = s.audio.get("device")
        self.device_fallback: List[Any] = list(s.audio.get("device_fallback", []) or [])
        self.probe_ms: int = int(s.audio.get("device_probe_ms", _DEFAULT_PROBE_MS))
        self.probe_rms_threshold: float = float(
            s.audio.get("device_probe_rms_threshold", _DEFAULT_PROBE_RMS_THRESHOLD)
        )
        self.frame_samples: int = self.sample_rate * self.frame_ms // 1000

        self._probe = probe or _probe_rms
        self.device_probed: Optional[Any] = None  # device actually chosen after probing

        # Sized for several seconds of headroom: a consumer that's briefly
        # busy (e.g. a slow whisper request) must not lose audio.
        queue_seconds = 8
        maxsize = max(32, queue_seconds * 1000 // self.frame_ms)
        self._queue: "asyncio.Queue[bytes]" = asyncio.Queue(maxsize=maxsize)
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._stream = None  # sounddevice.RawInputStream
        self.dropped_frames: int = 0

    def _resolve_device(self) -> Any:
        """Pick which device to actually open, probing candidates in order.

        With no ``device_fallback`` configured, this is a no-op returning
        ``self.device`` unchanged -- zero behavior change, and no probe call
        at all, for every caller that hasn't opted into this.
        """
        candidates = [self.device] + [d for d in self.device_fallback if d != self.device]
        if len(candidates) <= 1:
            return self.device

        first_error: Optional[Exception] = None
        for candidate in candidates:
            try:
                rms = self._probe(candidate, self.sample_rate, self.channels, self.probe_ms)
            except Exception as exc:  # noqa: BLE001 - a bad candidate must not crash startup
                if first_error is None:
                    first_error = exc
                continue
            if rms >= self.probe_rms_threshold:
                return candidate
        # Nothing passed the probe -- fall back to the primary device rather
        # than raising; a silent mic is a degraded session, not a crash.
        return self.device

    def _callback(self, indata, frames, time_info, status) -> None:
        # Runs on the PortAudio thread. Never block here; hand off to the loop.
        if self._loop is None:
            return
        data = bytes(indata)
        try:
            self._loop.call_soon_threadsafe(self._put, data)
        except RuntimeError:
            # Loop is closing; drop the frame.
            pass

    def _put(self, data: bytes) -> None:
        # Runs on the event loop. If the consumer has fallen behind past our
        # buffer, drop the oldest frame rather than raising QueueFull —
        # fresher audio matters more than a complete backlog for live speech.
        try:
            self._queue.put_nowait(data)
        except asyncio.QueueFull:
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            self.dropped_frames += 1
            try:
                self._queue.put_nowait(data)
            except asyncio.QueueFull:
                pass  # lost a race with another producer; not worth retrying

    def start(self) -> None:
        import sounddevice as sd  # lazy: requires PortAudio

        self.device_probed = self._resolve_device()
        self._loop = asyncio.get_running_loop()
        self._stream = sd.RawInputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="int16",
            blocksize=self.frame_samples,
            device=self.device_probed,
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
