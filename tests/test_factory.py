import pytest

from jarvis.config import Settings, get_settings
from jarvis.llm.factory import build_provider, resolve_models
from jarvis.llm.providers import AnthropicProvider, NvidiaProvider, OpenRouterProvider


@pytest.fixture(autouse=True)
def _no_tier_mode_env(monkeypatch):
    """Tests control the mode via Settings; a stray TIER_MODE env var
    (e.g. from the developer's shell) must not leak in."""
    monkeypatch.delenv("TIER_MODE", raising=False)


# --- free mode (the default) -------------------------------------------------

def test_default_mode_builds_openrouter_for_t1_standard():
    provider = build_provider(get_settings(), "t1_standard")
    assert isinstance(provider, OpenRouterProvider)
    assert provider.model == "nvidia/nemotron-3-nano-30b-a3b:free"


def test_default_mode_builds_nvidia_for_t1_simple():
    # t1_simple is NVIDIA-primary (not OpenRouter, unlike every other tier)
    # since 2026-07-04: OpenRouter's google/gemma-4-31b-it:free was found
    # live to be persistently rate-limited. See settings.yaml's comment.
    provider = build_provider(get_settings(), "t1_simple")
    assert isinstance(provider, NvidiaProvider)
    assert provider.model == "nvidia/nvidia-nemotron-nano-9b-v2"
    assert provider.max_tokens == 1024


def test_default_mode_builds_openrouter_for_t1_simple_openrouter_fallback():
    provider = build_provider(get_settings(), "t1_simple_openrouter")
    assert isinstance(provider, OpenRouterProvider)
    assert provider.model == "google/gemma-4-31b-it:free"
    assert provider.max_tokens == 1024


def test_default_mode_builds_nvidia_for_nvidia_twin_tiers():
    provider = build_provider(get_settings(), "t1_standard_nvidia")
    assert isinstance(provider, NvidiaProvider)
    assert provider.model == "nvidia/llama-3.3-nemotron-super-49b-v1"


def test_free_mode_never_builds_an_anthropic_provider():
    # The "Z.E.R.O Free" safety net: walk every tier in the active (free)
    # table and prove none of them can produce a paid Anthropic call.
    s = get_settings()
    for tier in resolve_models(s):
        provider = build_provider(s, tier)
        assert not isinstance(provider, AnthropicProvider), (
            f"free-mode tier {tier!r} built an AnthropicProvider"
        )


# --- anthropic mode (dormant upgrade path) -----------------------------------

def _anthropic_mode_settings() -> Settings:
    import yaml
    from pathlib import Path

    raw = yaml.safe_load(
        (Path(__file__).resolve().parent.parent / "config" / "settings.yaml").read_text()
    )
    raw["tier_mode"] = "anthropic"
    return Settings(raw)


def test_anthropic_mode_builds_sonnet_for_t1_standard():
    provider = build_provider(_anthropic_mode_settings(), "t1_standard")
    assert isinstance(provider, AnthropicProvider)
    assert provider.model == "claude-sonnet-5"
    assert provider.effort == "medium"
    assert provider.max_tokens == 8000
    assert provider.thinking == "adaptive"  # default when unset


def test_anthropic_mode_omits_thinking_for_fable():
    provider = build_provider(_anthropic_mode_settings(), "t3_complex")
    assert isinstance(provider, AnthropicProvider)
    assert provider.model == "claude-fable-5"
    assert provider.thinking == "none"


def test_tier_mode_env_var_flips_the_mode(monkeypatch):
    monkeypatch.setenv("TIER_MODE", "anthropic")
    provider = build_provider(get_settings(), "t1_standard")
    assert isinstance(provider, AnthropicProvider)
    assert provider.model == "claude-sonnet-5"


# --- resolution edge cases ----------------------------------------------------

def test_flat_models_map_still_works_for_any_mode():
    s = Settings({"models": {"bare": {"provider": "anthropic", "model": "claude-opus-4-8"}}})
    provider = build_provider(s, "bare")
    assert provider.max_tokens == 8000  # default
    assert provider.effort == "medium"  # default


def test_unknown_tier_raises():
    with pytest.raises(ValueError, match="bogus"):
        build_provider(get_settings(), "bogus")


def test_unknown_provider_name_raises():
    s = Settings({"models": {"weird": {"provider": "not-a-real-provider", "model": "x"}}})
    with pytest.raises(ValueError, match="not-a-real-provider"):
        build_provider(s, "weird")


def test_unknown_tier_mode_raises_with_available_modes(monkeypatch):
    monkeypatch.setenv("TIER_MODE", "bogus-mode")
    with pytest.raises(ValueError, match="bogus-mode"):
        build_provider(get_settings(), "t1_standard")
