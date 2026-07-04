"""jarvis.llm.parsing: think-tag stripping/filtering and defensive JSON extraction.

The streaming filter is load-bearing for voice output: a leaked <think> span
would be spoken aloud by TTS, so the chunk-boundary edge cases here are the
whole point, not paranoia.
"""
import pytest

from jarvis.llm.parsing import ThinkTagStreamFilter, extract_json_object, strip_think


# --- strip_think ---------------------------------------------------------------

def test_strip_think_removes_closed_spans():
    assert strip_think("a<think>reasoning</think>b") == "ab"


def test_strip_think_removes_unclosed_trailing_span():
    assert strip_think("answer <think>cut off mid-thou") == "answer "


def test_strip_think_passthrough_when_no_tags():
    assert strip_think("plain text") == "plain text"


def test_strip_think_multiple_spans():
    assert strip_think("<think>a</think>x<think>b</think>y") == "xy"


# --- extract_json_object --------------------------------------------------------

def test_extracts_clean_json():
    assert extract_json_object('{"tier": "T1"}') == {"tier": "T1"}


def test_extracts_json_from_code_fence():
    text = 'Here you go:\n```json\n{"tier": "T2", "tools_needed": []}\n```\nDone!'
    assert extract_json_object(text) == {"tier": "T2", "tools_needed": []}


def test_extracts_json_after_think_block():
    text = '<think>{"tier": "T3"} is tempting but no...</think>{"tier": "T1"}'
    # The object inside the think block must NOT win -- it's discarded first.
    assert extract_json_object(text) == {"tier": "T1"}


def test_extracts_nested_json():
    text = 'prefix {"a": {"b": [1, 2]}} suffix'
    assert extract_json_object(text) == {"a": {"b": [1, 2]}}


def test_skips_non_dict_json_and_broken_braces():
    text = "set {1, 2} is not json but this is: {\"ok\": true}"
    assert extract_json_object(text) == {"ok": True}


def test_raises_when_no_json_object_present():
    with pytest.raises(ValueError, match="No JSON object"):
        extract_json_object("I would put this in tier two.")


# --- ThinkTagStreamFilter -------------------------------------------------------

def _run_filter(chunks):
    out = []
    f = ThinkTagStreamFilter(out.append)
    for c in chunks:
        f.feed(c)
    f.flush()
    return "".join(out)


def test_filter_passthrough_without_tags():
    assert _run_filter(["Hello, ", "world."]) == "Hello, world."


def test_filter_suppresses_think_span_in_one_chunk():
    assert _run_filter(["a<think>hidden</think>b"]) == "ab"


def test_filter_suppresses_span_across_many_chunks():
    chunks = ["Sure! <thi", "nk>step 1... step 2...", " step 3</th", "ink>The answer is 4."]
    assert _run_filter(chunks) == "Sure! The answer is 4."


def test_filter_open_tag_split_one_char_per_chunk():
    chunks = list("x<think>secret</think>y")
    assert _run_filter(chunks) == "xy"


def test_filter_drops_unclosed_think_at_stream_end():
    assert _run_filter(["visible ", "<think>never closed..."]) == "visible "


def test_filter_emits_partial_tag_lookalike_on_flush():
    # A reply genuinely ending in "<thin" (not a tag) must not be swallowed.
    assert _run_filter(["a < b and a <thin"]) == "a < b and a <thin"


def test_filter_handles_less_than_signs_in_math():
    assert _run_filter(["x <", " y <= z"]) == "x < y <= z"


def test_filter_multiple_spans_across_chunks():
    chunks = ["<think>a</think>one<t", "hink>b</think>", "two"]
    assert _run_filter(chunks) == "onetwo"


def test_filter_emits_incrementally_not_only_at_flush():
    out = []
    f = ThinkTagStreamFilter(out.append)
    f.feed("Hello, world. ")
    # Everything except a potential tag prefix must already be out -- TTS
    # latency depends on this (speak-while-streaming, ARCHITECTURE.md §5.4).
    assert "".join(out).startswith("Hello, world.")
