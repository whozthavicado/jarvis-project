from datetime import datetime, timezone

import pytest

from jarvis.core.session import Session, build_context_block
from jarvis.memory.store import MemoryStore


def test_context_block_is_pure_and_deterministic():
    fixed = datetime(2026, 7, 2, 19, 45, tzinfo=timezone.utc)
    block = build_context_block(fixed)
    assert block.startswith("<context>")
    assert block.endswith("</context>")
    assert "2026-07-02 19:45" in block


def test_first_user_turn_includes_context_subsequent_turns_do_not():
    session = Session(tier="t1_standard")

    session.add_user_turn("hello")
    first = session.history[0]
    assert first.role == "user"
    assert first.text.startswith("<context>")
    assert first.text.endswith("hello")

    session.add_assistant_turn("hi there")
    session.add_user_turn("what's next")
    second = session.history[2]
    assert second.role == "user"
    assert second.text == "what's next"  # no context block this time


def test_messages_property_reflects_full_history_in_order():
    session = Session(tier="t1_standard")
    session.add_user_turn("a")
    session.add_assistant_turn("b")
    session.add_user_turn("c")

    roles = [m.role for m in session.messages]
    assert roles == ["user", "assistant", "user"]


def test_system_prompt_built_once_at_construction():
    session = Session(tier="t1_standard")
    assert isinstance(session.system_prompt, str)
    assert "Jarvis" in session.system_prompt


def test_different_tiers_get_different_layer_b_addenda():
    standard = Session(tier="t1_standard")
    simple = Session(tier="t1_simple")
    assert standard.system_prompt != simple.system_prompt
    # Layer A (identity core) is still shared verbatim across tiers.
    assert "VOICE OUTPUT RULES" in standard.system_prompt
    assert "VOICE OUTPUT RULES" in simple.system_prompt


def test_build_context_block_includes_digest_and_recall_only_when_given():
    bare = build_context_block(memory_digest="", recall_snippets=[])
    assert "memory digest" not in bare
    assert "relevant recall" not in bare

    full = build_context_block(memory_digest="- likes jazz", recall_snippets=["asked about pizza"])
    assert "memory digest:\n- likes jazz" in full
    assert "relevant recall" in full
    assert "- asked about pizza" in full


@pytest.fixture
def store(tmp_path):
    s = MemoryStore(tmp_path / "memory.sqlite3")
    yield s
    s.close()


def test_session_with_store_logs_turns_and_opens_a_session_row(store):
    session = Session(tier="t1_standard", store=store)
    session.add_user_turn("hello")
    session.add_assistant_turn("hi there")

    rows = store._conn.execute("SELECT role, text FROM turns ORDER BY id").fetchall()
    assert [(r["role"], r["text"]) for r in rows] == [("user", "hello"), ("assistant", "hi there")]
    # logged turn text is the raw text, not the context-wrapped version
    assert rows[0]["text"] == "hello"


def test_session_with_store_injects_digest_and_recall_on_first_turn(store, monkeypatch, tmp_path):
    digest_path = tmp_path / "MEMORY.md"
    digest_path.write_text("- likes jazz\n", encoding="utf-8")
    monkeypatch.setattr("jarvis.core.session.core_digest", lambda: "- likes jazz")

    other_session_id = store.start_session()
    store.log_turn(other_session_id, role="user", text="my dog's name is Waffles")

    session = Session(tier="t1_standard", store=store)
    session.add_user_turn("what's my dog's name")

    first = session.history[0]
    assert "memory digest:\n- likes jazz" in first.text
    assert "Waffles" in first.text


@pytest.mark.asyncio
async def test_session_close_writes_summary_via_store(store, monkeypatch):
    async def fake_summarize(history, settings=None):
        return "a short summary"

    monkeypatch.setattr("jarvis.core.session.memory_summarize", fake_summarize)

    session = Session(tier="t1_standard", store=store)
    session.add_user_turn("hello")
    session.add_assistant_turn("hi")
    await session.close()

    row = store._conn.execute(
        "SELECT ended_at, summary FROM sessions WHERE id = ?", (session._session_id,)
    ).fetchone()
    assert row["ended_at"] is not None
    assert row["summary"] == "a short summary"


@pytest.mark.asyncio
async def test_session_close_without_store_is_a_noop():
    session = Session(tier="t1_standard")
    await session.close()  # must not raise
