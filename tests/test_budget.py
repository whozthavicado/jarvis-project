"""jarvis.core.budget: cost estimation, soft/hard caps, daily rollover."""
from datetime import date, timedelta

import pytest

from jarvis.config import Settings
from jarvis.core.budget import BudgetGuard, get_budget_guard
from jarvis.llm.types import TurnResult


def _result(model="claude-sonnet-5", input_tokens=0, output_tokens=0, cache_read=0, cache_creation=0):
    return TurnResult(
        text="x",
        model=model,
        stop_reason="end_turn",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read,
        cache_creation_tokens=cache_creation,
    )


def test_record_computes_cost_from_sticker_prices():
    guard = BudgetGuard(soft_daily_usd=3.0, hard_daily_usd=6.0)
    # 1M input + 1M output tokens on Sonnet ($3 + $15 per MTok) = $18
    guard.record(_result(model="claude-sonnet-5", input_tokens=1_000_000, output_tokens=1_000_000))
    assert guard.spent_usd == pytest.approx(18.0)


def test_cache_read_and_creation_use_multipliers():
    guard = BudgetGuard(soft_daily_usd=3.0, hard_daily_usd=6.0)
    # Sonnet input price $3/MTok: 1M cache-read tokens -> 0.1x, 1M cache-creation -> 1.25x
    guard.record(_result(model="claude-sonnet-5", cache_read=1_000_000, cache_creation=1_000_000))
    assert guard.spent_usd == pytest.approx(3 * 0.1 + 3 * 1.25)


def test_unknown_model_costs_nothing():
    guard = BudgetGuard(soft_daily_usd=3.0, hard_daily_usd=6.0)
    guard.record(_result(model="google/gemma-4-31b-it:free", input_tokens=1_000_000, output_tokens=1_000_000))
    assert guard.spent_usd == 0.0


def test_hard_cap_hit_once_spend_reaches_hard_daily_usd():
    guard = BudgetGuard(soft_daily_usd=3.0, hard_daily_usd=6.0)
    assert not guard.hard_cap_hit()
    guard.record(_result(input_tokens=2_000_000))  # $6 at Sonnet's $3/MTok input price
    assert guard.hard_cap_hit()


def test_needs_confirmation_only_for_t2_plus_after_soft_cap():
    guard = BudgetGuard(soft_daily_usd=1.0, hard_daily_usd=6.0)
    guard.record(_result(input_tokens=400_000))  # $1.2, over the $1 soft cap

    assert guard.needs_confirmation("t2_medium")
    assert guard.needs_confirmation("t3_complex")
    assert not guard.needs_confirmation("t1_standard")
    assert not guard.needs_confirmation("t1_simple")


def test_needs_confirmation_false_before_soft_cap():
    guard = BudgetGuard(soft_daily_usd=100.0, hard_daily_usd=200.0)
    guard.record(_result(input_tokens=1000))
    assert not guard.needs_confirmation("t2_medium")


def test_spend_rolls_over_on_a_new_day():
    guard = BudgetGuard(soft_daily_usd=3.0, hard_daily_usd=6.0)
    guard.record(_result(input_tokens=2_000_000))
    assert guard.hard_cap_hit()

    guard._day = date.today() - timedelta(days=1)  # simulate yesterday's counter
    assert guard.spent_usd == 0.0
    assert not guard.hard_cap_hit()


def test_get_budget_guard_is_a_process_wide_singleton(monkeypatch):
    import jarvis.core.budget as budget

    monkeypatch.setattr(budget, "_guard", None)
    s = Settings({"budget": {"soft_daily_usd": 1.0, "hard_daily_usd": 2.0}})

    first = get_budget_guard(s)
    second = get_budget_guard(Settings({"budget": {"soft_daily_usd": 99.0, "hard_daily_usd": 99.0}}))

    assert first is second
    assert first.soft_daily_usd == 1.0  # second call's settings are ignored once cached
    monkeypatch.setattr(budget, "_guard", None)
