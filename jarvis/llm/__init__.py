"""M3 (minimal) — streaming Claude client. See ARCHITECTURE.md §8 step 2."""
from __future__ import annotations

from .client import LLMClient
from .prompts import build_system_blocks
from .types import TurnResult

__all__ = ["LLMClient", "TurnResult", "build_system_blocks"]
