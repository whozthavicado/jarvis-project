"""Session state: conversation history + Layer C context (ARCHITECTURE.md §3).

Layer C (datetime today; memory digest and recall arrive with M5) is injected
into the first user turn of a session as a leading text block, never into the
cached system prompt — see jarvis/llm/prompts.py for why that split matters.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from jarvis.llm.prompts import build_system_blocks


def build_context_block(now: Optional[datetime] = None) -> str:
    """Pure function: render the dynamic ``<context>`` block for Layer C.

    Kept separate from Session for easy unit testing with a fixed timestamp.
    Memory digest and FTS recall lines will be appended here once M5 (memory)
    lands; until then this is deliberately just the clock.
    """
    ts = (now or datetime.now().astimezone()).strftime("%A %Y-%m-%d %H:%M %Z")
    return f"<context>\ndatetime: {ts}\n</context>"


def build_user_turn(text: str, include_context: bool) -> dict:
    """Build one user message, optionally prefixed with the context block."""
    content: List[dict] = []
    if include_context:
        content.append({"type": "text", "text": build_context_block()})
    content.append({"type": "text", "text": text})
    return {"role": "user", "content": content}


def build_assistant_turn(text: str) -> dict:
    return {"role": "assistant", "content": text}


class Session:
    """One conversation's accumulated state.

    Usage::

        session = Session(tier="sonnet")
        session.add_user_turn("what's the weather")
        result = await llm.stream_reply(session.system_blocks, session.messages, on_text)
        session.add_assistant_turn(result.text)
    """

    def __init__(self, tier: str = "sonnet"):
        self.tier = tier
        self.system_blocks = build_system_blocks(tier)
        self.history: List[dict] = []
        self._context_injected = False

    def add_user_turn(self, text: str) -> None:
        turn = build_user_turn(text, include_context=not self._context_injected)
        self._context_injected = True
        self.history.append(turn)

    def add_assistant_turn(self, text: str) -> None:
        self.history.append(build_assistant_turn(text))

    @property
    def messages(self) -> List[dict]:
        return self.history
