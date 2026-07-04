"""jarvis.llm.fallbacks: is_transient classification, chain walking, circuit breaker."""
import httpx
import pytest
import anthropic

from jarvis.config import Settings
from jarvis.llm.fallbacks import CircuitBreaker, fallback_chain, get_circuit_breaker, is_transient
from jarvis.llm.providers import OpenRouterError


def _req() -> httpx.Request:
    return httpx.Request("POST", "https://api.anthropic.com/v1/messages")


def _status_error(code: int) -> anthropic.APIStatusError:
    resp = httpx.Response(status_code=code, request=_req())
    return anthropic.APIStatusError("boom", response=resp, body=None)


def _httpx_status_error(code: int) -> httpx.HTTPStatusError:
    resp = httpx.Response(code, request=_req())
    return httpx.HTTPStatusError("boom", request=_req(), response=resp)


@pytest.mark.parametrize(
    "exc,expected",
    [
        (anthropic.RateLimitError("slow down", response=httpx.Response(429, request=_req()), body=None), True),
        (anthropic.APIConnectionError(request=_req()), True),
        (_status_error(500), True),
        (_status_error(529), True),
        (_status_error(400), False),
        (
            anthropic.AuthenticationError("bad key", response=httpx.Response(401, request=_req()), body=None),
            False,
        ),
        (
            anthropic.PermissionDeniedError("nope", response=httpx.Response(403, request=_req()), body=None),
            False,
        ),
        (OpenRouterError("free model unavailable"), True),
        (ValueError("some bug"), False),
        # Raw httpx errors -- what the OpenRouter/NVIDIA providers actually
        # raise. Free-tier 429s being transient is what makes the whole free
        # fallback ladder fire at all.
        (_httpx_status_error(429), True),
        (_httpx_status_error(500), True),
        (_httpx_status_error(503), True),
        (_httpx_status_error(401), False),
        (_httpx_status_error(404), False),
        (httpx.ConnectError("no route", request=_req()), True),
        (httpx.ReadTimeout("slow", request=_req()), True),
    ],
)
def test_is_transient_classification(exc, expected):
    assert is_transient(exc) is expected


def test_fallback_map_is_mode_namespaced(monkeypatch):
    from jarvis.config import Settings

    s = Settings(
        {
            "tier_mode": "free",
            "fallbacks": {
                "free": {"a": "a_nvidia"},
                "anthropic": {"a": "b"},
            },
        }
    )
    monkeypatch.delenv("TIER_MODE", raising=False)
    assert fallback_chain(s, "a") == ["a_nvidia"]

    monkeypatch.setenv("TIER_MODE", "anthropic")
    assert fallback_chain(s, "a") == ["b"]


def test_namespaced_fallbacks_with_missing_mode_mean_no_fallbacks(monkeypatch):
    from jarvis.config import Settings

    monkeypatch.setenv("TIER_MODE", "some-new-mode")
    s = Settings({"fallbacks": {"free": {"a": "b"}}})
    assert fallback_chain(s, "a") == []


def test_fallback_chain_walks_multiple_hops():
    s = Settings({"fallbacks": {"a": "b", "b": "c"}})
    assert fallback_chain(s, "a") == ["b", "c"]


def test_fallback_chain_stops_at_a_tier_with_no_entry():
    s = Settings({"fallbacks": {"a": "b"}})
    assert fallback_chain(s, "b") == []


def test_fallback_chain_stops_on_a_cycle():
    s = Settings({"fallbacks": {"a": "b", "b": "a"}})
    assert fallback_chain(s, "a") == ["b"]


def test_fallback_chain_respects_max_hops():
    s = Settings({"fallbacks": {"a": "b", "b": "c", "c": "d", "d": "e"}})
    assert fallback_chain(s, "a", max_hops=2) == ["b", "c"]


def test_circuit_breaker_is_closed_initially():
    breaker = CircuitBreaker()
    assert not breaker.is_open("t1_standard")


def test_circuit_breaker_trips_after_threshold_failures():
    breaker = CircuitBreaker(failure_threshold=3)
    for _ in range(2):
        breaker.record_failure("t2_medium")
    assert not breaker.is_open("t2_medium")

    breaker.record_failure("t2_medium")
    assert breaker.is_open("t2_medium")


def test_circuit_breaker_success_resets_failure_count():
    breaker = CircuitBreaker(failure_threshold=3)
    breaker.record_failure("t2_medium")
    breaker.record_failure("t2_medium")
    breaker.record_success("t2_medium")
    breaker.record_failure("t2_medium")

    assert not breaker.is_open("t2_medium")


def test_circuit_breaker_cooldown_expires(monkeypatch):
    breaker = CircuitBreaker(failure_threshold=1, cooldown_s=100.0)
    fake_time = [1000.0]
    monkeypatch.setattr("jarvis.llm.fallbacks.time.monotonic", lambda: fake_time[0])

    breaker.record_failure("t2_medium")
    assert breaker.is_open("t2_medium")

    fake_time[0] += 101.0
    assert not breaker.is_open("t2_medium")


def test_get_circuit_breaker_is_a_process_wide_singleton(monkeypatch):
    import jarvis.llm.fallbacks as fallbacks

    monkeypatch.setattr(fallbacks, "_breaker", None)
    first = get_circuit_breaker()
    second = get_circuit_breaker()
    assert first is second
    monkeypatch.setattr(fallbacks, "_breaker", None)
