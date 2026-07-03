"""System prompt assembly (ARCHITECTURE.md §3).

Two frozen layers live on disk as ``.md`` files and are combined into one
cacheable system block:

    Layer A (``layer_a.md``)  — identity core, IDENTICAL across every model
                                 tier, forever. Do not edit casually: once
                                 this text has been served in production, any
                                 byte change invalidates the prompt cache for
                                 every session using it (see
                                 shared/prompt-caching.md — prefix match).
    Layer B (``layer_b_<tier>.md``) — small per-model behavior addendum. Safe
                                 to evolve as capabilities (tools, routing)
                                 come online in later milestones.

Layer C (dynamic context — datetime, memory digest, recall) is intentionally
*not* handled here: it changes every turn and belongs in ``messages``, not
``system``, so editing it never invalidates the Layer A+B cache. See
``jarvis/core/session.py``.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def _read(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text(encoding="utf-8").strip()


def load_layer_a() -> str:
    """The frozen identity core, shared by every tier."""
    return _read("layer_a.md")


def load_layer_b(tier: str) -> str:
    """The per-tier addendum, e.g. ``load_layer_b("sonnet")``."""
    return _read(f"layer_b_{tier}.md")


def build_system_blocks(tier: str) -> List[Dict]:
    """Build the ``system`` parameter: one cached block of Layer A + Layer B.

    A single block (not two) so there is exactly one cache breakpoint on the
    combined, stable prefix — see shared/prompt-caching.md placement patterns.
    """
    text = load_layer_a() + "\n\n" + load_layer_b(tier)
    return [
        {
            "type": "text",
            "text": text,
            "cache_control": {"type": "ephemeral"},
        }
    ]
