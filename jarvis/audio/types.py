"""Shared audio value types."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Transcript:
    """A finalized transcription of one speech segment.

    Attributes:
        text: Cleaned transcript text (may be empty if rejected).
        confidence: Best-effort 0..1 confidence; ``None`` if unavailable.
        duration_ms: Length of the source audio segment.
        rejected: True if a guard (too short, hallucination, empty) dropped it.
        reason: Human-readable rejection reason when ``rejected`` is True.
        low_energy: True if the source segment's VAD-derived RMS energy was
            below LOW_ENERGY_RMS_THRESHOLD (ARCHITECTURE.md §5.4) -- this is
            what gated whether the hallucination guard applied.
    """

    text: str
    confidence: "float | None" = None
    duration_ms: int = 0
    rejected: bool = False
    reason: str = ""
    low_energy: bool = False

    @property
    def usable(self) -> bool:
        return bool(self.text) and not self.rejected
