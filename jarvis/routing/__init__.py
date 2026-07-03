"""Routing package (ARCHITECTURE.md §2).

RULE 0 (T0 command grammar, M4) is ``match``/``load_grammar`` below. Per-turn
tier routing across T1-T3 (M2: Stage 1 heuristics + Stage 2 Haiku classifier)
is :class:`jarvis.routing.router.Router`.
"""
from __future__ import annotations

from jarvis.routing.grammar import load_grammar, match
from jarvis.routing.router import Router

__all__ = ["load_grammar", "match", "Router"]
