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
    # Router + all four tiers wired up.
    assert s.models.t1_simple == "claude-haiku-4-5"
    assert s.models.t1_standard == "claude-sonnet-5"
    assert s.models.t2_medium == "claude-opus-4-8"
    assert s.models.t3_complex == "claude-fable-5"


def test_get_with_default():
    s = get_settings()
    assert s.audio.get("device", "sentinel") is None  # present but null
    assert s.audio.get("missing", "sentinel") == "sentinel"
