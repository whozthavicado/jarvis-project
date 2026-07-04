"""Settings loader.

Reads ``config/settings.yaml`` once and exposes it as nested, attribute-style
namespaces so callers can write ``settings.audio.sample_rate`` instead of
threading dicts around. Kept deliberately tiny — no schema framework.

Also home to :func:`get_tier_mode` — the one switch that decides whether the
app runs in "free" mode (OpenRouter + NVIDIA NIM, $0) or "anthropic" mode
(Claude models, paid). It lives here rather than in jarvis/llm because both
the model table (jarvis/llm/factory.py) and the fallback map
(jarvis/llm/fallbacks.py) need it without importing each other.
"""
from __future__ import annotations

import functools
import os
from pathlib import Path
from typing import Any, Mapping

import yaml

DEFAULT_TIER_MODE = "free"

_DEFAULT_PATH = Path(__file__).resolve().parent.parent / "config" / "settings.yaml"


class Settings(Mapping):
    """Read-only, dotted-access view over a nested mapping.

    Behaves as a Mapping (``settings["audio"]``) *and* supports attribute access
    (``settings.audio.sample_rate``). Nested dicts are wrapped lazily.
    """

    __slots__ = ("_data",)

    def __init__(self, data: Mapping[str, Any]):
        self._data = dict(data)

    def __getattr__(self, name: str) -> Any:
        try:
            return self._wrap(self._data[name])
        except KeyError as exc:  # pragma: no cover - defensive
            raise AttributeError(name) from exc

    def __getitem__(self, key: str) -> Any:
        return self._wrap(self._data[key])

    def __iter__(self):
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def get(self, key: str, default: Any = None) -> Any:
        return self._wrap(self._data[key]) if key in self._data else default

    @staticmethod
    def _wrap(value: Any) -> Any:
        return Settings(value) if isinstance(value, Mapping) else value

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"Settings({self._data!r})"


def load_settings(path: "str | Path | None" = None) -> Settings:
    """Load settings from *path* (defaults to ``config/settings.yaml``)."""
    p = Path(path) if path is not None else _DEFAULT_PATH
    with p.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return Settings(data)


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide cached settings (the common entry point)."""
    return load_settings()


def get_tier_mode(settings: Settings) -> str:
    """Which model table / fallback map the app runs on.

    Resolution order: ``TIER_MODE`` env var (so flipping modes never needs a
    file edit), then ``tier_mode:`` in settings.yaml, then "free". The value
    is a key into ``models.<mode>`` / ``fallbacks.<mode>`` — validation that
    the mode actually exists happens where those tables are read (factory /
    fallbacks), which can produce a far more useful error message.
    """
    return os.environ.get("TIER_MODE") or str(settings.get("tier_mode", DEFAULT_TIER_MODE))
