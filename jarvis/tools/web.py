"""Web tools (ARCHITECTURE.md §6, M4): weather (Open-Meteo, no API key) and a
generic HTTP fetch. Both read-only (is_destructive=False) -- they only ever
GET external data, never mutate anything.

HTTP idiom: a fresh httpx.AsyncClient per call. Unlike WhisperClient, these
tools have no lifecycle to manage across calls, so a one-shot client per
invocation is the simplest fit (mirrors WhisperClient.health()'s own
throwaway-client fallback branch, the closest existing precedent).

Weather uses Open-Meteo (open-meteo.com) specifically because it needs no
API key -- consistent with this project's free-tier-first ethos (see the
Z.E.R.O Free tier-mode work).
"""
from __future__ import annotations

from typing import Any, Dict

import httpx

from jarvis.tools.registry import register
from jarvis.tools.types import ToolDef

_GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
_WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
_FETCH_CHAR_LIMIT = 20_000  # mirrors files.py's read_file cap
_WEATHER_TIMEOUT_S = 10.0
_FETCH_TIMEOUT_S = 15.0


async def get_weather(args: Dict[str, Any]) -> str:
    place = args["location"]
    async with httpx.AsyncClient(timeout=_WEATHER_TIMEOUT_S) as client:
        geo = await client.get(_GEOCODE_URL, params={"name": place, "count": 1})
        geo.raise_for_status()
        results = geo.json().get("results") or []
        if not results:
            return f"Couldn't find a location called '{place}'."
        lat = results[0]["latitude"]
        lon = results[0]["longitude"]
        resolved_name = results[0].get("name", place)

        resp = await client.get(
            _WEATHER_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,weather_code,wind_speed_10m",
                "temperature_unit": "fahrenheit",
            },
        )
        resp.raise_for_status()
        current = resp.json().get("current", {})

    temp = current.get("temperature_2m")
    wind = current.get("wind_speed_10m")
    return f"{resolved_name}: {temp}°F, wind {wind} mph."


async def fetch_url(args: Dict[str, Any]) -> str:
    url = args["url"]
    async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT_S, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        text = resp.text
    if len(text) > _FETCH_CHAR_LIMIT:
        text = text[:_FETCH_CHAR_LIMIT] + f"\n... [truncated, {len(text)} chars total]"
    return text


def _register_all() -> None:
    register(
        ToolDef(
            name="get_weather",
            description="Get current weather for a place name (via Open-Meteo, no API key).",
            parameters={"location": {"type": "string", "description": "City/place name"}},
            handler=get_weather,
        )
    )
    register(
        ToolDef(
            name="fetch_url",
            description="Fetch a URL's raw text/HTML content (truncated if very large).",
            parameters={"url": {"type": "string"}},
            handler=fetch_url,
            timeout_s=_FETCH_TIMEOUT_S,
        )
    )


_register_all()
