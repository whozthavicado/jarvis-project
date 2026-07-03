"""``memory/MEMORY.md`` management (ARCHITECTURE.md §4.1, M5).

The core digest is the only memory that is *always* in context (Layer C,
jarvis/core/session.py): curated durable facts, written only via the
``remember`` tool (kind="core") or a manual edit to the file. Everything
here is a pure read/render/write over that one file -- no SQLite, no
network -- so it's trivially testable and safe to call every turn.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional, Union

_DEFAULT_PATH = Path(__file__).resolve().parent.parent.parent / "memory" / "MEMORY.md"


def load_core_digest(path: Optional[Union[str, Path]] = None) -> str:
    """The digest file's contents, or "" if it doesn't exist yet (no core
    facts recorded so far -- nothing to inject, not an error)."""
    p = Path(path) if path is not None else _DEFAULT_PATH
    if not p.is_file():
        return ""
    return p.read_text(encoding="utf-8").strip()


def render_core_digest(facts: Iterable[str]) -> str:
    """Pure function: facts -> the digest file's text. Kept separate from
    ``regenerate_core_digest`` so rendering is testable without touching disk."""
    lines = [f"- {fact}" for fact in facts]
    return "\n".join(lines)


def regenerate_core_digest(store, path: Optional[Union[str, Path]] = None) -> str:
    """Rewrite the digest file from every kind="core" memory in *store*.

    Called whenever a "core" fact is remembered (ARCHITECTURE.md §4 write
    path: "Claude proposes; the orchestrator persists"). *store* is a
    :class:`jarvis.memory.store.MemoryStore` -- typed loosely here to avoid
    importing it just for the annotation.
    """
    facts = [m["text"] for m in store.list_memories(kind="core")]
    text = render_core_digest(facts)
    p = Path(path) if path is not None else _DEFAULT_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text((text + "\n") if text else "", encoding="utf-8")
    return text
