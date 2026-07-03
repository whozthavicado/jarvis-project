"""Shared memory value types (ARCHITECTURE.md §4, M5 contract)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Snippet:
    """One FTS recall hit, ready to drop into the Layer C context block."""

    text: str
    source: str  # "turn" | "summary"
    ref_id: int
