from jarvis.llm.prompts import build_system_blocks, load_layer_a, load_layer_b


def test_layer_a_is_shared_identity_core():
    text = load_layer_a()
    assert "Jarvis" in text
    assert "VOICE OUTPUT RULES" in text


def test_layer_b_sonnet_exists_and_is_distinct_from_layer_a():
    text = load_layer_b("sonnet")
    assert text  # non-empty
    assert text != load_layer_a()


def test_system_blocks_combine_both_layers_as_one_cached_block():
    blocks = build_system_blocks("sonnet")
    assert len(blocks) == 1
    block = blocks[0]
    assert block["type"] == "text"
    assert block["cache_control"] == {"type": "ephemeral"}
    assert "Jarvis" in block["text"]  # Layer A present
    assert load_layer_b("sonnet") in block["text"]  # Layer B present, verbatim
