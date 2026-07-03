from jarvis.config import get_settings, load_settings


def test_loads_default_settings():
    s = get_settings()
    assert s.audio.sample_rate == 16000
    assert s.audio.frame_ms in (10, 20, 30)  # webrtcvad constraint


def test_dotted_and_mapping_access_agree():
    s = get_settings()
    assert s.audio.sample_rate == s["audio"]["sample_rate"]


def test_model_ids_present():
    s = get_settings()
    # Each tier now names a provider + model (see jarvis/llm/factory.py).
    assert s.models.t1_simple.provider == "openrouter"
    assert s.models.t1_simple.model == "google/gemma-4-31b-it:free"
    assert s.models.t1_standard.provider == "anthropic"
    assert s.models.t1_standard.model == "claude-sonnet-5"
    assert s.models.t2_medium.model == "claude-opus-4-8"
    assert s.models.t3_complex.model == "claude-fable-5"
    assert s.models.router.model == "claude-haiku-4-5"


def test_t1_simple_falls_back_through_nvidia_to_t1_standard():
    s = get_settings()
    assert s.fallbacks.t1_simple == "t1_simple_nvidia"
    assert s.fallbacks.t1_simple_nvidia == "t1_standard"


def test_get_with_default():
    s = get_settings()
    assert s.audio.get("device", "sentinel") is None  # present but null
    assert s.audio.get("missing", "sentinel") == "sentinel"
