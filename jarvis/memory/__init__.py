"""Persistent memory (ARCHITECTURE.md §4, M5): SQLite episodic log + FTS5
recall (store.py), the curated memory/MEMORY.md digest (digest.py), and
Haiku session summaries + compaction (summarizer.py).

``get_store``/``core_digest``/``regenerate_digest`` are the settings-aware
entry points everything else (Session, the remember/recall tools) should
use -- they resolve paths from ``config/settings.yaml`` -> ``memory``
so a path change is a config edit, not a code change, matching
jarvis/llm/factory.py's precedent for tier config.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from jarvis.config import Settings, get_settings
from jarvis.memory.digest import load_core_digest, regenerate_core_digest, render_core_digest
from jarvis.memory.store import MemoryStore
from jarvis.memory.summarizer import compact, summarize
from jarvis.memory.types import Snippet

__all__ = [
    "MemoryStore",
    "Snippet",
    "render_core_digest",
    "compact",
    "summarize",
    "get_store",
    "core_digest",
    "regenerate_digest",
    "db_path",
    "digest_path",
]

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_store: Optional[MemoryStore] = None


def _resolve_path(settings: Settings, key: str, default: str) -> Path:
    cfg = settings.get("memory", {})
    value = cfg.get(key, default)
    p = Path(value)
    return p if p.is_absolute() else _PROJECT_ROOT / p


def db_path(settings: Optional[Settings] = None) -> Path:
    return _resolve_path(settings or get_settings(), "db_path", "data/memory.sqlite3")


def digest_path(settings: Optional[Settings] = None) -> Path:
    return _resolve_path(settings or get_settings(), "digest_path", "memory/MEMORY.md")


def get_store(settings: Optional[Settings] = None) -> MemoryStore:
    """Process-wide MemoryStore singleton, backed by settings -> memory.db_path."""
    global _store
    if _store is None:
        _store = MemoryStore(db_path(settings))
    return _store


def core_digest(settings: Optional[Settings] = None) -> str:
    return load_core_digest(digest_path(settings))


def regenerate_digest(store: MemoryStore, settings: Optional[Settings] = None) -> str:
    return regenerate_core_digest(store, digest_path(settings))
