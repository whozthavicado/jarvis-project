"""Daily spend tracking + soft/hard budget caps (ARCHITECTURE.md §5.5, M3-full).

Cost is derived from each ``TurnResult``'s usage fields against the sticker
per-MTok prices in ARCHITECTURE.md §2 (cache reads/writes get their own
multiplier rather than a separate flat rate, mirroring how Anthropic
actually bills caching). A model not in the price table -- OpenRouter's free
tier, or a model swapped in later -- costs $0, which is correct for
`t1_simple`'s current backend and a safe default otherwise.

``BudgetGuard`` only tracks spend and answers yes/no questions; the
orchestrator decides what to actually do with those answers (force a tier
down, prefix a spoken notice) -- see jarvis/core/orchestrator.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, Optional, Tuple

from jarvis.config import Settings, get_settings
from jarvis.llm.types import TurnResult

# (input $/MTok, output $/MTok) -- ARCHITECTURE.md §2's sticker prices.
_PRICES_PER_MTOK: Dict[str, Tuple[float, float]] = {
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-sonnet-5": (3.0, 15.0),
    "claude-opus-4-8": (5.0, 25.0),
    "claude-fable-5": (10.0, 50.0),
}
_CACHE_READ_MULTIPLIER = 0.1  # ~90% discount on cache hits
_CACHE_WRITE_MULTIPLIER = 1.25  # ~25% premium to write the cache

_CONFIRM_TIERS = ("t2_medium", "t3_complex")  # "T2+" per ARCHITECTURE.md §5.5


def _cost_usd(result: TurnResult) -> float:
    prices = _PRICES_PER_MTOK.get(result.model)
    if prices is None:
        return 0.0
    input_price, output_price = prices
    cost = (
        result.input_tokens * input_price
        + result.output_tokens * output_price
        + result.cache_read_tokens * input_price * _CACHE_READ_MULTIPLIER
        + result.cache_creation_tokens * input_price * _CACHE_WRITE_MULTIPLIER
    ) / 1_000_000
    return cost


@dataclass
class BudgetGuard:
    """Tracks today's spend and answers whether a tier is allowed to run.

    Not thread-safe by design -- the orchestrator loop is a single asyncio
    task, so a plain float counter is enough. Resets automatically at
    midnight (checked lazily, not via a scheduled timer).
    """

    soft_daily_usd: float
    hard_daily_usd: float
    _spent_usd: float = field(default=0.0, init=False)
    _day: date = field(default_factory=date.today, init=False)

    def _roll_over_if_new_day(self) -> None:
        today = date.today()
        if today != self._day:
            self._day = today
            self._spent_usd = 0.0

    def record(self, result: TurnResult) -> None:
        self._roll_over_if_new_day()
        self._spent_usd += _cost_usd(result)

    @property
    def spent_usd(self) -> float:
        self._roll_over_if_new_day()
        return self._spent_usd

    def hard_cap_hit(self) -> bool:
        """"Everything routes to [the cheapest tier] until midnight" (§5.5)."""
        return self.spent_usd >= self.hard_daily_usd

    def needs_confirmation(self, tier: str) -> bool:
        """"T2+ requests require spoken confirmation" once the soft cap is hit."""
        return tier in _CONFIRM_TIERS and self.spent_usd >= self.soft_daily_usd


_guard: Optional[BudgetGuard] = None


def get_budget_guard(settings: Optional[Settings] = None) -> BudgetGuard:
    """Process-wide BudgetGuard singleton, backed by settings -> budget.*."""
    global _guard
    if _guard is None:
        s = settings or get_settings()
        cfg = s.get("budget", {})
        _guard = BudgetGuard(
            soft_daily_usd=float(cfg.get("soft_daily_usd", 3.0)),
            hard_daily_usd=float(cfg.get("hard_daily_usd", 6.0)),
        )
    return _guard
