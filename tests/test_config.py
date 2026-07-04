import pytest

from jarvis.config import Settings, get_settings, get_tier_mode, load_settings


def test_loads_default_settings():
    s = get_settings()
    assert s.audio.sample_rate == 16000
    assert s.audio.frame_ms in (10, 20, 30)  # webrtcvad constraint


def test_dotted_and_mapping_access_agree():
    s = get_settings()
    assert s.audio.sample_rate == s["audio"]["sample_rate"]


def test_default_tier_mode_is_free(monkeypatch):
    monkeypatch.delenv("TIER_MODE", raising=False)
    assert get_tier_mode(get_settings()) == "free"


def test_tier_mode_env_var_overrides_settings(monkeypatch):
    monkeypatch.setenv("TIER_MODE", "anthropic")
    assert get_tier_mode(get_settings()) == "anthropic"


def test_tier_mode_settings_value_used_when_no_env(monkeypatch):
    monkeypatch.delenv("TIER_MODE", raising=False)
    assert get_tier_mode(Settings({"tier_mode": "anthropic"})) == "anthropic"
    assert get_tier_mode(Settings({})) == "free"  # default


def test_free_mode_model_table_never_names_anthropic():
    # The load-bearing guarantee of "Z.E.R.O Free": no tier in the free
    # table can ever resolve to a paid Anthropic call.
    s = get_settings()
    for tier, cfg in s.models.free.items():
        assert cfg.provider in ("openrouter", "nvidia"), (
            f"free-mode tier {tier!r} names provider {cfg.provider!r}"
        )


def test_anthropic_mode_table_preserved_as_upgrade_path():
    s = get_settings()
    assert s.models.anthropic.t1_standard.provider == "anthropic"
    assert s.models.anthropic.t1_standard.model == "claude-sonnet-5"
    assert s.models.anthropic.t2_medium.model == "claude-opus-4-8"
    assert s.models.anthropic.t3_complex.model == "claude-fable-5"
    assert s.models.anthropic.router.model == "claude-haiku-4-5"
    # Fable 400s on an explicit thinking config -- must be "none" here.
    assert s.models.anthropic.t3_complex.thinking == "none"


def test_free_fallback_map_pairs_every_openrouter_tier_with_its_nvidia_twin():
    s = get_settings()
    fb = s.fallbacks.free
    assert fb.t1_simple == "t1_simple_nvidia"
    assert fb.t1_standard == "t1_standard_nvidia"
    assert fb.t2_medium == "t2_medium_nvidia"
    assert fb.t3_complex == "t3_complex_nvidia"
    assert fb.router == "router_nvidia"


def test_every_fallback_target_has_a_model_entry_in_its_mode():
    # A chain hop naming a tier with no model entry would only blow up at
    # fallback time, mid-conversation -- catch it at config time instead.
    s = get_settings()
    for mode in ("free", "anthropic"):
        models = s.models[mode]
        for source, target in s.fallbacks[mode].items():
            assert source in models, f"{mode}: fallback source {source!r} has no model entry"
            assert target in models, f"{mode}: fallback target {target!r} has no model entry"


def test_anthropic_fallback_ladder_matches_architecture():
    s = get_settings()
    fb = s.fallbacks.anthropic
    assert fb.t3_complex == "t2_medium"
    assert fb.t2_medium == "t1_standard"
    assert fb.t1_simple == "t1_simple_nvidia"


def test_get_with_default():
    s = get_settings()
    assert s.audio.get("device", "sentinel") is None  # present but null
    assert s.audio.get("missing", "sentinel") == "sentinel"
