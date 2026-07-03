from jarvis.llm.prompts import build_system_prompt, load_layer_a, load_layer_b


def test_layer_a_is_shared_identity_core():
    text = load_layer_a()
    assert "Jarvis" in text
    assert "VOICE OUTPUT RULES" in text


def test_layer_b_exists_per_tier_and_is_distinct_from_layer_a():
    for tier in ("t1_simple", "t1_standard"):
        text = load_layer_b(tier)
        assert text  # non-empty
        assert text != load_layer_a()


def test_layer_b_differs_between_tiers():
    assert load_layer_b("t1_simple") != load_layer_b("t1_standard")


def test_system_prompt_combines_both_layers_as_plain_text():
    # Plain text on purpose — caching/formatting is a provider-specific
    # concern (AnthropicProvider), not something baked in here so any
    # provider can consume the same prompt.
    prompt = build_system_prompt("t1_standard")
    assert isinstance(prompt, str)
    assert "Jarvis" in prompt  # Layer A present
    assert load_layer_b("t1_standard") in prompt  # Layer B present, verbatim
