from datetime import datetime, timezone

from jarvis.core.session import Session, build_context_block


def test_context_block_is_pure_and_deterministic():
    fixed = datetime(2026, 7, 2, 19, 45, tzinfo=timezone.utc)
    block = build_context_block(fixed)
    assert block.startswith("<context>")
    assert block.endswith("</context>")
    assert "2026-07-02 19:45" in block


def test_first_user_turn_includes_context_subsequent_turns_do_not():
    session = Session(tier="sonnet")

    session.add_user_turn("hello")
    first = session.history[0]
    assert first["role"] == "user"
    assert len(first["content"]) == 2  # context block + the utterance
    assert first["content"][0]["text"].startswith("<context>")
    assert first["content"][1]["text"] == "hello"

    session.add_assistant_turn("hi there")
    session.add_user_turn("what's next")
    second = session.history[2]
    assert len(second["content"]) == 1  # no context block this time
    assert second["content"][0]["text"] == "what's next"


def test_messages_property_reflects_full_history_in_order():
    session = Session(tier="sonnet")
    session.add_user_turn("a")
    session.add_assistant_turn("b")
    session.add_user_turn("c")

    roles = [m["role"] for m in session.messages]
    assert roles == ["user", "assistant", "user"]


def test_system_blocks_built_once_at_construction():
    session = Session(tier="sonnet")
    assert len(session.system_blocks) == 1
    assert "Jarvis" in session.system_blocks[0]["text"]
