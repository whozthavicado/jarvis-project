"""Tier -> Provider instance. The one place provider choice is decided.

Everything else in the codebase (Session, LLMClient's callers) talks to the
Provider interface; switching a tier between Anthropic/OpenRouter/NVIDIA is a
``config/settings.yaml`` edit, not a code change (that's the whole point of
this module existing).
"""
from __future__ import annotations

from jarvis.config import Settings
from jarvis.llm.providers import AnthropicProvider, NvidiaProvider, OpenRouterProvider, Provider

_BUILDERS = {
    "anthropic": lambda cfg: AnthropicProvider(
        model=str(cfg.model),
        max_tokens=int(cfg.get("max_tokens", 8000)),
        effort=str(cfg.get("effort", "medium")),
    ),
    "openrouter": lambda cfg: OpenRouterProvider(
        model=str(cfg.model),
        max_tokens=int(cfg.get("max_tokens", 1024)),
    ),
    "nvidia": lambda cfg: NvidiaProvider(
        model=str(cfg.model),
        max_tokens=int(cfg.get("max_tokens", 1024)),
    ),
}


def build_provider(settings: Settings, tier: str) -> Provider:
    """Build the Provider configured for *tier* in ``settings.models``."""
    try:
        cfg = settings.models[tier]
    except KeyError as exc:
        raise ValueError(f"No models.{tier!r} entry in settings") from exc

    provider_name = str(cfg.provider)
    builder = _BUILDERS.get(provider_name)
    if builder is None:
        raise ValueError(
            f"Unknown provider {provider_name!r} configured for tier {tier!r} "
            f"(known providers: {sorted(_BUILDERS)})"
        )
    return builder(cfg)
