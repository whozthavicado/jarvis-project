from jarvis.memory.digest import load_core_digest, regenerate_core_digest, render_core_digest


class _StubStore:
    def __init__(self, facts):
        self._facts = facts

    def list_memories(self, kind=None):
        return [{"text": f} for f in self._facts]


def test_load_core_digest_returns_empty_string_when_file_missing(tmp_path):
    assert load_core_digest(tmp_path / "nope.md") == ""


def test_render_core_digest_renders_bullets():
    text = render_core_digest(["likes jazz", "works on jarvis-project"])
    assert text == "- likes jazz\n- works on jarvis-project"


def test_render_core_digest_empty_for_no_facts():
    assert render_core_digest([]) == ""


def test_regenerate_core_digest_writes_file_and_returns_text(tmp_path):
    path = tmp_path / "memory" / "MEMORY.md"
    store = _StubStore(["prefers Spanish replies"])

    text = regenerate_core_digest(store, path)

    assert text == "- prefers Spanish replies"
    assert path.read_text(encoding="utf-8").strip() == text
    assert load_core_digest(path) == text


def test_regenerate_core_digest_overwrites_previous_content(tmp_path):
    path = tmp_path / "MEMORY.md"
    regenerate_core_digest(_StubStore(["fact a"]), path)
    regenerate_core_digest(_StubStore(["fact b"]), path)

    assert load_core_digest(path) == "- fact b"
