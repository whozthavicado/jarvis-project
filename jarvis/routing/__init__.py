"""Routing package (ARCHITECTURE.md §2). Only T0 grammar matching (M4) is
built so far; the Stage 1 heuristics (RULES 1-5) and the Haiku classifier
land with the M2 milestone."""
from __future__ import annotations

from jarvis.routing.grammar import load_grammar, match

__all__ = ["load_grammar", "match"]
