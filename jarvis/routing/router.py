"""Per-turn tier routing (ARCHITECTURE.md §2) — the M2 module.

Ties Stage 1 heuristics and the Stage 2 Haiku classifier together, and caches
one LLMClient per tier so a routed conversation doesn't rebuild a Provider on
every turn. RULE 0 (T0 command grammar) is checked separately by the
orchestrator before a transcript ever reaches ``resolve`` — this module only
ever returns one of the four conversation tiers.

Classifier failure (no credentials, network error, etc.) falls back to
"t1_standard" rather than raising — a routing failure degrading to a
reasonable default is much better than crashing the turn, consistent with
the rest of the codebase's fail-soft posture (see orchestrator.py).
"""
from __future__ import annotations

from typing import Optional

from jarvis.config import Settings, get_settings
from jarvis.llm.client import LLMClient
from jarvis.llm.prompts import build_system_prompt
from jarvis.routing import classifier, heuristics

_CLASSIFIER_FALLBACK_TIER = "t1_standard"


class Router:
    def __init__(self, settings: Optional[Settings] = None):
        self._settings = settings or get_settings()
        self._clients: dict[str, LLMClient] = {}

    async def resolve(self, text: str) -> str:
        """Decide which tier should handle *text*. Never raises."""
        tier = heuristics.classify(text)
        if tier is not None:
            return tier
        try:
            return await classifier.classify(text, self._settings)
        except Exception:  # noqa: BLE001 - a routing failure must not crash the turn
            return _CLASSIFIER_FALLBACK_TIER

    def llm_for(self, tier: str) -> LLMClient:
        """Return the (cached) LLMClient for *tier*, building it on first use."""
        if tier not in self._clients:
            self._clients[tier] = LLMClient(self._settings, tier=tier)
        return self._clients[tier]

    @staticmethod
    def system_prompt_for(tier: str) -> str:
        return build_system_prompt(tier)
