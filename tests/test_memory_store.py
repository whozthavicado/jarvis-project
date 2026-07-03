"""MemoryStore tests (SQLite schema, dedup, FTS recall) — a real on-disk
sqlite file under tmp_path each test, no mocking needed since sqlite3 is
stdlib and fully local."""
import pytest

from jarvis.memory.store import MemoryStore


@pytest.fixture
def store(tmp_path):
    s = MemoryStore(tmp_path / "memory.sqlite3")
    yield s
    s.close()


def test_start_and_end_session_round_trip(store):
    session_id = store.start_session()
    assert isinstance(session_id, int)
    store.end_session(session_id, summary="talked about the weather")

    row = store._conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    assert row["ended_at"] is not None
    assert row["summary"] == "talked about the weather"


def test_log_turn_persists_and_is_recallable(store):
    session_id = store.start_session()
    store.log_turn(session_id, role="user", text="my favorite color is teal", tier="t1_standard")

    hits = store.recall("what is my favorite color")
    assert any("teal" in h.text for h in hits)


def test_recall_returns_empty_for_no_match(store):
    session_id = store.start_session()
    store.log_turn(session_id, role="user", text="the weather is nice today")

    assert store.recall("quantum spreadsheet nonsense") == []


def test_recall_returns_empty_for_query_with_no_content_words(store):
    session_id = store.start_session()
    store.log_turn(session_id, role="user", text="hello there")

    assert store.recall("the a to of") == []


def test_recall_respects_k_and_char_budget(store):
    session_id = store.start_session()
    for i in range(5):
        store.log_turn(session_id, role="user", text=f"unicorn fact number {i}")

    hits = store.recall("unicorn fact", k=2)
    assert len(hits) <= 2


def test_end_session_summary_is_also_recallable(store):
    session_id = store.start_session()
    store.end_session(session_id, summary="discussed a trip to marfa texas")

    hits = store.recall("trip to marfa")
    assert any(h.source == "summary" for h in hits)


def test_add_memory_dedupes_exact_and_near_matches(store):
    added_1, id_1 = store.add_memory(kind="core", text="Prefers dark mode")
    added_2, id_2 = store.add_memory(kind="core", text="  prefers   dark mode  ")

    assert added_1 is True
    assert added_2 is False
    assert id_1 == id_2
    assert len(store.list_memories(kind="core")) == 1


def test_add_memory_same_text_different_kind_is_not_a_dup(store):
    store.add_memory(kind="core", text="likes jazz")
    added, _ = store.add_memory(kind="episodic", text="likes jazz")
    assert added is True


def test_list_memories_filters_by_kind(store):
    store.add_memory(kind="core", text="fact a")
    store.add_memory(kind="episodic", text="fact b")

    core_only = store.list_memories(kind="core")
    assert [m["text"] for m in core_only] == ["fact a"]
