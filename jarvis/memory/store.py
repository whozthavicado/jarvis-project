"""SQLite episodic log + FTS5 recall (ARCHITECTURE.md §4.2/§4.3, M5).

Three tables plus one search index, all in a single local SQLite file (no
new dependency -- ``sqlite3`` is stdlib):

    sessions   -- one row per conversation, closed out with a Haiku summary
    turns      -- every user/assistant turn, tagged with the tier that
                  answered it
    memories   -- structured facts written via the ``remember`` tool
                  (ARCHITECTURE.md §4.1/§4's write path)
    turns_fts  -- a standalone FTS5 table (not content-linked to turns/
                  sessions, to sidestep external-content trigger upkeep for
                  two source tables) fed manually by log_turn/end_session,
                  covering both turn text and session summaries as the
                  design calls for

``recall`` is deliberately forgiving: FTS5's query syntax breaks on stray
punctuation in a spoken transcript, so the query is rebuilt as an OR of
quoted content words rather than passed through raw.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from jarvis.memory.types import Snippet

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    summary TEXT
);

CREATE TABLE IF NOT EXISTS turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    ts TEXT NOT NULL,
    role TEXT NOT NULL,
    text TEXT NOT NULL,
    tier TEXT,
    tokens_in INTEGER NOT NULL DEFAULT 0,
    tokens_out INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    kind TEXT NOT NULL,
    text TEXT NOT NULL,
    source_session INTEGER
);

CREATE VIRTUAL TABLE IF NOT EXISTS turns_fts USING fts5(
    text, kind UNINDEXED, ref_id UNINDEXED
);
"""

_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "to", "of", "and", "or",
    "in", "on", "at", "for", "it", "its", "what", "whats", "do", "does",
    "did", "can", "you", "i", "my", "me", "that", "this", "with", "be",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_fts_query(text: str) -> Optional[str]:
    """A forgiving FTS5 MATCH expression from *text*'s content words.

    Punctuation/apostrophes in a spoken transcript can otherwise trip FTS5's
    own query grammar, so every token is quoted (treated as a literal, not
    parsed as syntax) and OR'd together rather than passed through raw.
    """
    words = re.findall(r"[A-Za-z0-9']+", text.lower())
    tokens = [w for w in words if w not in _STOPWORDS and len(w) > 1]
    if not tokens:
        return None
    return " OR ".join(f'"{t}"' for t in tokens)


class MemoryStore:
    def __init__(self, db_path: Union[str, Path]):
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def start_session(self) -> int:
        cur = self._conn.execute("INSERT INTO sessions (started_at) VALUES (?)", (_now(),))
        self._conn.commit()
        return cur.lastrowid

    def end_session(self, session_id: int, summary: Optional[str] = None) -> None:
        self._conn.execute(
            "UPDATE sessions SET ended_at = ?, summary = COALESCE(?, summary) WHERE id = ?",
            (_now(), summary, session_id),
        )
        self._conn.commit()
        if summary:
            self._index_fts(summary, kind="summary", ref_id=session_id)

    def log_turn(
        self,
        session_id: int,
        role: str,
        text: str,
        tier: Optional[str] = None,
        tokens_in: int = 0,
        tokens_out: int = 0,
    ) -> int:
        cur = self._conn.execute(
            "INSERT INTO turns (session_id, ts, role, text, tier, tokens_in, tokens_out) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (session_id, _now(), role, text, tier, tokens_in, tokens_out),
        )
        self._conn.commit()
        turn_id = cur.lastrowid
        self._index_fts(text, kind="turn", ref_id=turn_id)
        return turn_id

    def _index_fts(self, text: str, kind: str, ref_id: int) -> None:
        self._conn.execute(
            "INSERT INTO turns_fts (text, kind, ref_id) VALUES (?, ?, ?)", (text, kind, ref_id)
        )
        self._conn.commit()

    def add_memory(self, kind: str, text: str, source_session: Optional[int] = None) -> Tuple[bool, int]:
        """Insert a fact unless an identical one (same kind, normalized text)
        already exists. Returns (added, memory_id) -- dedup lives here so no
        caller can forget it (ARCHITECTURE.md §4 write path)."""
        normalized = " ".join(text.split()).strip().lower()
        existing = self._conn.execute(
            "SELECT id FROM memories WHERE kind = ? AND lower(trim(text)) = ?",
            (kind, normalized),
        ).fetchone()
        if existing is not None:
            return False, existing["id"]
        cur = self._conn.execute(
            "INSERT INTO memories (ts, kind, text, source_session) VALUES (?, ?, ?, ?)",
            (_now(), kind, text.strip(), source_session),
        )
        self._conn.commit()
        return True, cur.lastrowid

    def list_memories(self, kind: Optional[str] = None) -> List[Dict]:
        if kind is None:
            rows = self._conn.execute("SELECT * FROM memories ORDER BY id").fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM memories WHERE kind = ? ORDER BY id", (kind,)
            ).fetchall()
        return [dict(r) for r in rows]

    def recall(self, query: str, k: int = 3, max_chars: int = 2400) -> List[Snippet]:
        """Top-*k* FTS hits over turns+summaries, capped at *max_chars* total
        (ARCHITECTURE.md §4.3: "Top 3 hits, ≤600 tokens total"). Empty list
        if the query has no usable content words, or nothing matches."""
        match = _build_fts_query(query)
        if match is None:
            return []
        rows = self._conn.execute(
            "SELECT text, kind, ref_id FROM turns_fts WHERE turns_fts MATCH ? "
            "ORDER BY rank LIMIT ?",
            (match, k),
        ).fetchall()

        snippets: List[Snippet] = []
        budget = max_chars
        for row in rows:
            if budget <= 0:
                break
            text = row["text"]
            if len(text) > budget:
                text = text[:budget] + "..."
            snippets.append(Snippet(text=text, source=row["kind"], ref_id=row["ref_id"]))
            budget -= len(text)
        return snippets

    def close(self) -> None:
        self._conn.close()
