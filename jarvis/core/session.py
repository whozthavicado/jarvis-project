"""Session state: conversation history + Layer C context (ARCHITECTURE.md §3).

Layer C (datetime today; memory digest and recall arrive with M5) is folded
into the text of the first user turn of a session, never into the system
prompt — see jarvis/llm/prompts.py for why that split matters. History is
provider-agnostic ``ChatMessage`` (plain role + text) so it can be handed to
any Provider unchanged; provider-specific wire formatting happens inside
each Provider, not here.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from jarvis.llm.prompts import build_system_prompt
from jarvis.llm.types import ChatMessage


def build_context_block(now: Optional[datetime] = None) -> str:
    """Pure function: render the dynamic ``<context>`` block for Layer C.

    Kept separate from Session for easy unit testing with a fixed timestamp.
    Memory digest and FTS recall lines will be appended here once M5 (memory)
    lands; until then this is deliberately just the clock.
    """
    ts = (now or datetime.now().astimezone()).strftime("%A %Y-%m-%d %H:%M %Z")
    return f"<context>\ndatetime: {ts}\n</context>"


def build_user_turn(text: str, include_context: bool) -> ChatMessage:
    """Build one user message, optionally prefixed with the context block."""
    if include_context:
        text = build_context_block() + "\n\n" + text
    return ChatMessage(role="user", text=text)


def build_assistant_turn(text: str) -> ChatMessage:
    return ChatMessage(role="assistant", text=text)


class Session:
    """One conversation's accumulated state.

    Usage::

        session = Session(tier="t1_standard")
        session.add_user_turn("what's the weather")
        result = await llm.stream_reply(session.system_prompt, session.messages, on_text)
        session.add_assistant_turn(result.text)
    """

    def __init__(self, tier: str = "t1_standard"):
        self.tier = tier
        self.system_prompt = build_system_prompt(tier)
        self.history: List[ChatMessage] = []
        self._context_injected = False

    def add_user_turn(self, text: str) -> None:
        turn = build_user_turn(text, include_context=not self._context_injected)
        self._context_injected = True
        self.history.append(turn)

    def add_assistant_turn(self, text: str) -> None:
        self.history.append(build_assistant_turn(text))

    @property
    def messages(self) -> List[ChatMessage]:
        return self.history
