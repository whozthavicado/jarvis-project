"""M1 — audio input: mic capture, voice-activity segmentation, transcription.

Public contract (see ARCHITECTURE.md §6):

    async for t in transcripts():   # t: Transcript
        ...
"""
from __future__ import annotations

from .pipeline import transcripts
from .types import Transcript

__all__ = ["transcripts", "Transcript"]
