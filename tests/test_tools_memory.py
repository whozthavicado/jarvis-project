"""remember/recall tool handler tests, against a real tmp_path-backed store."""
import pytest

from jarvis.memory.store import MemoryStore
from jarvis.tools import memory_tools


@pytest.fixture
def store(tmp_path, monkeypatch):
    s = MemoryStore(tmp_path / "memory.sqlite3")
    monkeypatch.setattr(memory_tools, "get_store", lambda: s)
    yield s
    s.close()


@pytest.mark.asyncio
async def test_remember_core_fact_persists_and_regenerates_digest(store, tmp_path, monkeypatch):
    digest_path = tmp_path / "MEMORY.md"
    from jarvis.memory.digest import regenerate_core_digest

    monkeypatch.setattr(
        memory_tools, "regenerate_digest", lambda s: regenerate_core_digest(s, digest_path)
    )

    result = await memory_tools.remember({"kind": "core", "text": "prefers dark mode"})

    assert "Remembered" in result
    assert digest_path.read_text(encoding="utf-8").strip() == "- prefers dark mode"


@pytest.mark.asyncio
async def test_remember_non_core_fact_does_not_touch_digest(store, monkeypatch):
    called = []
    monkeypatch.setattr(memory_tools, "regenerate_digest", lambda s: called.append(s))

    await memory_tools.remember({"kind": "episodic", "text": "asked about pizza"})

    assert called == []


@pytest.mark.asyncio
async def test_remember_dedupes_repeated_fact(store, monkeypatch):
    monkeypatch.setattr(memory_tools, "regenerate_digest", lambda s: None)

    first = await memory_tools.remember({"kind": "core", "text": "likes jazz"})
    second = await memory_tools.remember({"kind": "core", "text": "likes jazz"})

    assert "Remembered" in first
    assert "Already remembered" in second


@pytest.mark.asyncio
async def test_recall_finds_logged_turns(store):
    session_id = store.start_session()
    store.log_turn(session_id, role="user", text="my dog's name is Waffles")

    result = await memory_tools.recall({"query": "what is my dog's name"})
    assert "Waffles" in result


@pytest.mark.asyncio
async def test_recall_reports_no_match_plainly(store):
    result = await memory_tools.recall({"query": "completely unrelated nonsense topic"})
    assert "No memory matches" in result
