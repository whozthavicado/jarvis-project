"""M1 composition: mic -> VAD -> whisper, exposed as ``transcripts()``.

This is the public contract other modules depend on (ARCHITECTURE.md §6)::

    async for t in transcripts():
        if t.usable:
            ...
"""
from __future__ import annotations

from typing import AsyncIterator, Optional

from jarvis.config import Settings, get_settings
from jarvis.audio.capture import MicCapture
from jarvis.audio.transcriber import WhisperClient
from jarvis.audio.types import Transcript
from jarvis.audio.vad import segment_stream
from jarvis.audio.watchdog import WhisperWatchdog


async def transcripts(
    settings: Optional[Settings] = None,
    include_rejected: bool = False,
) -> AsyncIterator[Transcript]:
    """Yield transcripts from live microphone input until cancelled.

    A :class:`WhisperWatchdog` runs alongside the client (ARCHITECTURE.md
    §5.4): if the whisper server stops answering health checks mid-session,
    it gets restarted in the background rather than every ``transcribe``
    call failing until someone notices.

    Args:
        settings: override settings (defaults to the global config).
        include_rejected: if True, also yield guard-rejected transcripts
            (useful for debugging); default only yields usable ones.
    """
    s = settings or get_settings()
    watchdog = WhisperWatchdog(s)
    async with MicCapture(s) as mic, WhisperClient(s) as whisper, watchdog:
        async for segment in segment_stream(mic.frames(), s):
            t = await whisper.transcribe(segment)
            if t.usable or include_rejected:
                yield t
