import pytest

from jarvis.config import Settings, get_settings
from jarvis.llm.factory import build_provider
from jarvis.llm.providers import AnthropicProvider, NvidiaProvider, OpenRouterProvider


def test_builds_anthropic_provider_for_anthropic_tier():
    provider = build_provider(get_settings(), "t1_standard")
    assert isinstance(provider, AnthropicProvider)
    assert provider.model == "claude-sonnet-5"
    assert provider.effort == "medium"
    assert provider.max_tokens == 8000


def test_builds_openrouter_provider_for_openrouter_tier():
    provider = build_provider(get_settings(), "t1_simple")
    assert isinstance(provider, OpenRouterProvider)
    assert provider.model == "google/gemma-4-31b-it:free"
    assert provider.max_tokens == 1024


def test_builds_nvidia_provider_for_nvidia_tier():
    provider = build_provider(get_settings(), "t1_simple_nvidia")
    assert isinstance(provider, NvidiaProvider)
    assert provider.model == "meta/llama-3.1-8b-instruct"
    assert provider.max_tokens == 1024


def test_unknown_tier_raises():
    with pytest.raises(ValueError, match="bogus"):
        build_provider(get_settings(), "bogus")


def test_unknown_provider_name_raises():
    s = Settings({"models": {"weird": {"provider": "not-a-real-provider", "model": "x"}}})
    with pytest.raises(ValueError, match="not-a-real-provider"):
        build_provider(s, "weird")


def test_max_tokens_and_effort_fall_back_to_defaults_when_unset():
    s = Settings({"models": {"bare": {"provider": "anthropic", "model": "claude-opus-4-8"}}})
    provider = build_provider(s, "bare")
    assert provider.max_tokens == 8000  # default
    assert provider.effort == "medium"  # default
