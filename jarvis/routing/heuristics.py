"""Stage 1 routing — free, <1 ms local heuristics (ARCHITECTURE.md §2, RULES 1-4).

RULE 0 (T0 command grammar) lives in :mod:`jarvis.routing.grammar` and is
checked separately, before a transcript ever reaches this module — by the
time ``classify`` runs, the orchestrator has already ruled out a direct
device command.

Rules are checked in order; the first match wins. ``classify`` returns the
matching tier's settings.yaml key, or ``None`` if nothing matched (RULE 5:
ambiguous, fall through to the Stage 2 Haiku classifier — see
jarvis/routing/classifier.py).
"""
from __future__ import annotations

from typing import Optional

_ESCALATION_PHRASES = (
    "think hard",
    "deep dive",
    "this is important",
    "use your best model",
)

_CODE_SIGNALS = (
    "```",
    "write code",
    "write a function",
    "debug",
    "stack trace",
    "traceback",
    "fix this bug",
    "refactor",
)

_PLANNING_VERBS = (
    "plan",
    "design",
    "compare and decide",
    "research",
)

_TOOL_WORK_SIGNALS = (
    "summarize",
    "summarise",
    "draft",
    "find and",
    "email",
    "calendar",
)

_WORD_COUNT_T2_THRESHOLD = 80
_WORD_COUNT_T1_MAX = 25


def classify(text: str) -> Optional[str]:
    """Return a settings.yaml tier key for *text*, or None if ambiguous."""
    lowered = text.lower()
    words = text.split()

    if any(phrase in lowered for phrase in _ESCALATION_PHRASES):
        return "t3_complex"

    if (
        any(signal in lowered for signal in _CODE_SIGNALS)
        or any(verb in lowered for verb in _PLANNING_VERBS)
        or len(words) > _WORD_COUNT_T2_THRESHOLD
    ):
        return "t2_medium"

    tool_signal_count = sum(1 for signal in _TOOL_WORK_SIGNALS if signal in lowered)
    if tool_signal_count >= 1:
        return "t1_standard"

    if len(words) <= _WORD_COUNT_T1_MAX:
        return "t1_simple"

    return None
