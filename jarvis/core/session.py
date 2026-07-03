"""Session state: conversation history + Layer C context (ARCHITECTURE.md §3).

Layer C (datetime, memory digest, FTS recall) is folded into the text of the
first user turn of a session, never into the system prompt — see
jarvis/llm/prompts.py for why that split matters. History is
provider-agnostic ``ChatMessage`` (plain role + text) so it can be handed to
any Provider unchanged; provider-specific wire formatting happens inside
each Provider, not here.

M5 wires in the rest of Layer C plus the episodic log: pass a
:class:`jarvis.memory.MemoryStore` as *store* and a Session will pull the
core digest + top FTS recall hits for the first turn's context block, log
every turn (as plain text, without the context block) to SQLite, compact
its own history once it grows past ~6K tokens, and write a Haiku session
summary via :meth:`close`. Without a store, none of that runs — a Session
behaves exactly as it did before M5 (single tier, no persistence), which is
what every pre-M5 test still exercises.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from jarvis.config import Settings
from jarvis.llm.prompts import build_system_prompt
from jarvis.llm.types import ChatMessage
from jarvis.memory import MemoryStore, compact as memory_compact, core_digest, summarize as memory_summarize


def build_context_block(
    now: Optional[datetime] = None,
    memory_digest: str = "",
    recall_snippets: Optional[List[str]] = None,
) -> str:
    """Pure function: render the dynamic ``<context>`` block for Layer C.

    Kept separate from Session for easy unit testing with a fixed timestamp.
    ``memory_digest``/``recall_snippets`` are omitted entirely when empty, so
    a memory-less caller gets the exact same block M5 predates.
    """
    ts = (now or datetime.now().astimezone()).strftime("%A %Y-%m-%d %H:%M %Z")
    lines = ["<context>", f"datetime: {ts}"]
    if memory_digest:
        lines.append("memory digest:")
        lines.append(memory_digest)
    if recall_snippets:
        lines.append("relevant recall (FTS matches for this query, may be empty):")
        lines.extend(f"- {snippet}" for snippet in recall_snippets)
    lines.append("</context>")
    return "\n".join(lines)


def build_user_turn(
    text: str,
    include_context: bool,
    memory_digest: str = "",
    recall_snippets: Optional[List[str]] = None,
) -> ChatMessage:
    """Build one user message, optionally prefixed with the context block."""
    if include_context:
        block = build_context_block(memory_digest=memory_digest, recall_snippets=recall_snippets)
        text = block + "\n\n" + text
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

    def __init__(self, tier: str = "t1_standard", store: Optional[MemoryStore] = None):
        self.tier = tier
        self.system_prompt = build_system_prompt(tier)
        self.history: List[ChatMessage] = []
        self._context_injected = False
        self.store = store
        self._session_id: Optional[int] = store.start_session() if store is not None else None

    def add_user_turn(self, text: str) -> None:
        include_context = not self._context_injected
        digest = ""
        recall_snippets: List[str] = []
        if include_context and self.store is not None:
            digest = core_digest()
            recall_snippets = [snippet.text for snippet in self.store.recall(text)]

        turn = build_user_turn(text, include_context, digest, recall_snippets)
        self._context_injected = True
        self.history.append(turn)
        if self.store is not None:
            self.store.log_turn(self._session_id, role="user", text=text, tier=self.tier)

    def add_assistant_turn(self, text: str) -> None:
        self.history.append(build_assistant_turn(text))
        if self.store is not None:
            self.store.log_turn(self._session_id, role="assistant", text=text, tier=self.tier)

    async def compact_if_needed(self, settings: Optional[Settings] = None) -> None:
        """Replace turns older than the last few with a Haiku summary once
        history has grown past the compaction threshold (ARCHITECTURE.md
        §4.2). A no-op for the short histories every non-M5 test builds."""
        self.history = await memory_compact(self.history, settings=settings)

    async def close(self, settings: Optional[Settings] = None) -> None:
        """Write a Haiku session summary and close out the SQLite session
        row. A no-op without a store. Summarization failure (no
        credentials, network error) is swallowed -- an unsummarized session
        row is fine, a crash on shutdown is not."""
        if self.store is None or self._session_id is None:
            return
        summary = None
        if self.history:
            try:
                summary = await memory_summarize(self.history, settings=settings)
            except Exception:  # noqa: BLE001 - see docstring
                summary = None
        self.store.end_session(self._session_id, summary=summary)

    @property
    def messages(self) -> List[ChatMessage]:
        return self.history
