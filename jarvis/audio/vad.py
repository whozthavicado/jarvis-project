"""Voice-activity segmentation.

Turns a stream of fixed-size PCM frames into complete utterance segments, so
Whisper only runs on actual speech. Uses ``webrtcvad`` when available and falls
back to a simple RMS-energy gate otherwise (keeps the pipeline importable and
testable without the native extension).

The segmentation state machine (:class:`VadSegmenter`) is pure and synchronous
so it can be unit-tested by feeding synthetic frames; :func:`segment_stream`
wraps it for the async pipeline.
"""
from __future__ import annotations

import math
from collections import deque
from typing import AsyncIterator, Callable, Deque, List, Optional

from jarvis.config import Settings, get_settings


def _make_speech_detector(sample_rate: int, aggressiveness: int) -> Callable[[bytes], bool]:
    """Return a ``frame -> is_speech`` predicate.

    Prefers webrtcvad; falls back to an RMS-energy threshold if the native
    module is unavailable or rejects the frame size.
    """
    try:
        import webrtcvad  # native extension

        vad = webrtcvad.Vad(aggressiveness)

        def detect(frame: bytes) -> bool:
            try:
                return vad.is_speech(frame, sample_rate)
            except Exception:
                return _energy_speech(frame)

        return detect
    except Exception:
        return _energy_speech


def _energy_speech(frame: bytes, threshold: float = 500.0) -> bool:
    """RMS-energy fallback over int16 PCM (no numpy dependency)."""
    if not frame:
        return False
    n = len(frame) // 2
    if n == 0:
        return False
    total = 0
    for i in range(0, n * 2, 2):
        sample = int.from_bytes(frame[i : i + 2], "little", signed=True)
        total += sample * sample
    rms = math.sqrt(total / n)
    return rms >= threshold


class VadSegmenter:
    """Pure state machine: feed frames, get back completed segments.

    Call :meth:`push` for each frame. It returns a ``bytes`` segment when an
    utterance completes (trailing silence reached or max length hit), else
    ``None``. Segments shorter than ``min_segment_ms`` are dropped (returns
    ``None`` and resets).
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        is_speech: Optional[Callable[[bytes], bool]] = None,
    ):
        s = settings or get_settings()
        self.frame_ms = int(s.audio.frame_ms)
        self.start_frames = int(s.vad.start_frames)
        self.end_silence_frames = max(1, int(s.vad.end_silence_ms) // self.frame_ms)
        self.max_frames = max(1, int(s.vad.max_segment_ms) // self.frame_ms)
        self.min_frames = max(1, int(s.vad.min_segment_ms) // self.frame_ms)

        self._is_speech = is_speech or _make_speech_detector(
            int(s.audio.sample_rate), int(s.vad.aggressiveness)
        )

        # Pre-roll buffer: keep a little audio before the trigger so the first
        # phoneme is not clipped.
        self._preroll: Deque[bytes] = deque(maxlen=self.start_frames)
        self._voiced: List[bytes] = []
        self._triggered = False
        self._trailing_silence = 0
        self._recent_voiced = deque(maxlen=self.start_frames)

    def push(self, frame: bytes) -> Optional[bytes]:
        speech = self._is_speech(frame)

        if not self._triggered:
            self._preroll.append(frame)
            self._recent_voiced.append(speech)
            if sum(self._recent_voiced) >= self.start_frames:
                # Trigger: adopt the pre-roll as the segment's opening.
                self._triggered = True
                self._voiced = list(self._preroll)
                self._trailing_silence = 0
                self._preroll.clear()
                self._recent_voiced.clear()
            return None

        # Triggered: accumulate and watch for the end.
        self._voiced.append(frame)
        self._trailing_silence = 0 if speech else self._trailing_silence + 1

        ended = self._trailing_silence >= self.end_silence_frames
        too_long = len(self._voiced) >= self.max_frames
        if ended or too_long:
            return self._finish()
        return None

    def _finish(self) -> Optional[bytes]:
        segment = b"".join(self._voiced)
        length = len(self._voiced)
        self._reset()
        if length < self.min_frames:
            return None
        return segment

    def _reset(self) -> None:
        self._voiced = []
        self._triggered = False
        self._trailing_silence = 0
        self._preroll.clear()
        self._recent_voiced.clear()

    def flush(self) -> Optional[bytes]:
        """Force-close any in-progress segment (e.g. on shutdown)."""
        if self._triggered:
            return self._finish()
        return None


async def segment_stream(
    frames: AsyncIterator[bytes], settings: Optional[Settings] = None
) -> AsyncIterator[bytes]:
    """Async wrapper: consume a frame stream, yield utterance segments."""
    seg = VadSegmenter(settings)
    async for frame in frames:
        out = seg.push(frame)
        if out is not None:
            yield out
