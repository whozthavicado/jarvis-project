"""jarvis.memory package wiring: settings-driven paths, store singleton."""
import jarvis.memory as memory
from jarvis.config import Settings
from jarvis.memory import digest_path, db_path, get_store


def test_db_path_defaults_relative_to_project_root():
    p = db_path(Settings({}))
    assert str(p).endswith("data/memory.sqlite3")
    assert p.is_absolute()


def test_digest_path_defaults_relative_to_project_root():
    p = digest_path(Settings({}))
    assert str(p).endswith("memory/MEMORY.md")
    assert p.is_absolute()


def test_paths_honor_settings_override(tmp_path):
    s = Settings({"memory": {"db_path": str(tmp_path / "x.sqlite3"), "digest_path": str(tmp_path / "M.md")}})
    assert db_path(s) == tmp_path / "x.sqlite3"
    assert digest_path(s) == tmp_path / "M.md"


def test_get_store_is_a_process_wide_singleton(monkeypatch, tmp_path):
    monkeypatch.setattr(memory, "_store", None)
    s = Settings({"memory": {"db_path": str(tmp_path / "singleton.sqlite3")}})

    first = get_store(s)
    second = get_store(Settings({"memory": {"db_path": str(tmp_path / "different.sqlite3")}}))

    assert first is second  # settings on the second call are ignored once cached
    monkeypatch.setattr(memory, "_store", None)  # leave global state clean for other tests
