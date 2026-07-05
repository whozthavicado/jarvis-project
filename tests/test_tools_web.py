"""Web tool tests — httpx calls are faked, nothing here touches the network."""
import httpx
import pytest

from jarvis.tools import web


class _FakeResponse:
    def __init__(self, json_data=None, text="", status_code=200):
        self._json = json_data or {}
        self.text = text
        self.status_code = status_code

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("GET", "https://example.test")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("boom", request=request, response=response)


class _FakeClient:
    """Stands in for httpx.AsyncClient as an async context manager."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, params=None):
        self.calls.append((url, params))
        return self._responses.pop(0)


def _patch_client(monkeypatch, responses):
    fake = _FakeClient(responses)
    monkeypatch.setattr(web.httpx, "AsyncClient", lambda *a, **kw: fake)
    return fake


async def test_get_weather_happy_path(monkeypatch):
    geocode = _FakeResponse(json_data={"results": [{"latitude": 1.0, "longitude": 2.0, "name": "Testville"}]})
    forecast = _FakeResponse(json_data={"current": {"temperature_2m": 72.0, "wind_speed_10m": 5.0}})
    fake = _patch_client(monkeypatch, [geocode, forecast])

    result = await web.get_weather({"location": "testville"})

    assert result == "Testville: 72.0°F, wind 5.0 mph."
    assert len(fake.calls) == 2


async def test_get_weather_no_location_found(monkeypatch):
    geocode = _FakeResponse(json_data={"results": []})
    fake = _patch_client(monkeypatch, [geocode])

    result = await web.get_weather({"location": "nowhereville"})

    assert "Couldn't find a location" in result
    assert len(fake.calls) == 1  # forecast never called


async def test_fetch_url_returns_text(monkeypatch):
    resp = _FakeResponse(text="hello world")
    _patch_client(monkeypatch, [resp])

    result = await web.fetch_url({"url": "https://example.test"})

    assert result == "hello world"


async def test_fetch_url_truncates_over_limit(monkeypatch):
    long_text = "x" * (web._FETCH_CHAR_LIMIT + 500)
    resp = _FakeResponse(text=long_text)
    _patch_client(monkeypatch, [resp])

    result = await web.fetch_url({"url": "https://example.test"})

    assert result.startswith("x" * 100)
    assert "[truncated," in result
    assert len(result) < len(long_text)


async def test_fetch_url_http_error_propagates_to_registry(monkeypatch):
    resp = _FakeResponse(status_code=500)
    _patch_client(monkeypatch, [resp])

    from jarvis.tools.registry import execute
    from jarvis.tools.types import ToolCall

    result = await execute(ToolCall(name="fetch_url", args={"url": "https://example.test"}))

    assert result.is_error


async def test_get_weather_http_error_propagates_to_registry(monkeypatch):
    resp = _FakeResponse(status_code=500)
    _patch_client(monkeypatch, [resp])

    from jarvis.tools.registry import execute
    from jarvis.tools.types import ToolCall

    result = await execute(ToolCall(name="get_weather", args={"location": "testville"}))

    assert result.is_error
