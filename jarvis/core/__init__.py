"""M3-minimal composition root: session state + the listen/reply/speak loop."""
from __future__ import annotations

from .orchestrator import converse, handle_turn
from .session import Session, build_context_block

__all__ = ["converse", "handle_turn", "Session", "build_context_block"]
