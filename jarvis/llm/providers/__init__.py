"""Provider implementations, each exposing the same ``stream_reply`` shape
(see ``Provider`` in ``base.py``). ``jarvis/llm/factory.py`` picks one per
tier from ``config/settings.yaml`` — that's the only place provider choice
should be decided; the rest of the codebase talks to the Provider interface,
not to a specific vendor's SDK.
"""
from __future__ import annotations

from .anthropic_provider import AnthropicProvider
from .base import Provider
from .openrouter_provider import OpenRouterError, OpenRouterProvider

__all__ = ["Provider", "AnthropicProvider", "OpenRouterProvider", "OpenRouterError"]
