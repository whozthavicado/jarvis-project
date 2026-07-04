"""Tier -> Provider instance. The one place provider choice is decided.

Everything else in the codebase (Session, LLMClient's callers) talks to the
Provider interface; switching a tier between Anthropic/OpenRouter/NVIDIA is a
``config/settings.yaml`` edit, not a code change (that's the whole point of
this module existing).

Tier modes ("Z.E.R.O Free"): ``settings.models`` can be namespaced by mode —
``models.free.<tier>`` / ``models.anthropic.<tier>`` — with
:func:`jarvis.config.get_tier_mode` (env var ``TIER_MODE``, then
``tier_mode:`` in settings, default "free") picking which table is live.
Flipping the app between $0 production (OpenRouter + NVIDIA NIM) and paid
Claude models is therefore one env var, zero code. A *flat* ``models.<tier>``
map (no mode namespaces) still works — it applies to every mode, which keeps
small test fixtures terse and stays compatible with pre-mode configs.
"""
from __future__ import annotations

from typing import Mapping

from jarvis.config import Settings, get_tier_mode
from jarvis.llm.providers import AnthropicProvider, NvidiaProvider, OpenRouterProvider, Provider

_BUILDERS = {
    "anthropic": lambda cfg: AnthropicProvider(
        model=str(cfg.model),
        max_tokens=int(cfg.get("max_tokens", 8000)),
        effort=str(cfg.get("effort", "medium")),
        thinking=str(cfg.get("thinking", "adaptive")),
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


def _is_tier_config(value: object) -> bool:
    """A mapping with a ``provider`` key is one tier's config; a mapping of
    those is a mode namespace."""
    return isinstance(value, Mapping) and "provider" in value


def resolve_models(settings: Settings) -> Mapping:
    """The tier -> config table for the active tier mode.

    Namespaced shape (``models.<mode>.<tier>``) picks the active mode's
    table; flat shape (``models.<tier>``) is returned as-is for every mode.
    """
    models = settings.models
    mode = get_tier_mode(settings)

    entry = models.get(mode)
    if isinstance(entry, Mapping) and not _is_tier_config(entry):
        return entry

    if any(_is_tier_config(v) for v in models.values()):
        return models  # flat map: no mode namespaces, applies to every mode

    raise ValueError(
        f"settings.models has no table for tier_mode {mode!r} "
        f"(available modes: {sorted(models)})"
    )


def build_provider(settings: Settings, tier: str) -> Provider:
    """Build the Provider configured for *tier* in the active mode's table."""
    models = resolve_models(settings)
    try:
        cfg = models[tier]
    except KeyError as exc:
        raise ValueError(
            f"No models entry for tier {tier!r} in tier_mode "
            f"{get_tier_mode(settings)!r}"
        ) from exc

    provider_name = str(cfg.provider)
    builder = _BUILDERS.get(provider_name)
    if builder is None:
        raise ValueError(
            f"Unknown provider {provider_name!r} configured for tier {tier!r} "
            f"(known providers: {sorted(_BUILDERS)})"
        )
    return builder(cfg)
