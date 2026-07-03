"""File tool handler tests — search_files mocks the mdfind subprocess;
read_file/write_file exercise a real tmp_path so behavior is genuine."""
import asyncio

import pytest

from jarvis.tools import files


class _FakeProc:
    def __init__(self, returncode=0, stdout=b"", stderr=b""):
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr

    async def communicate(self):
        return self._stdout, self._stderr


async def test_search_files_returns_capped_results(monkeypatch):
    paths = "\n".join(f"/tmp/file{i}.txt" for i in range(20))

    async def fake_exec(*args, **kwargs):
        assert args[0] == "mdfind"
        return _FakeProc(stdout=paths.encode())

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    result = await files.search_files({"query": "file", "limit": 3})
    assert len(result.splitlines()) == 3


async def test_search_files_no_matches(monkeypatch):
    async def fake_exec(*args, **kwargs):
        return _FakeProc(stdout=b"")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    result = await files.search_files({"query": "nope"})
    assert "No files found" in result


async def test_read_file_roundtrip(tmp_path):
    p = tmp_path / "note.txt"
    p.write_text("hello world")
    result = await files.read_file({"path": str(p)})
    assert result == "hello world"


async def test_read_file_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        await files.read_file({"path": str(tmp_path / "missing.txt")})


async def test_read_file_truncates_large_content(tmp_path):
    p = tmp_path / "big.txt"
    p.write_text("x" * 30_000)
    result = await files.read_file({"path": str(p)})
    assert "truncated" in result
    assert len(result) < 30_000


async def test_write_file_creates_and_overwrites(tmp_path):
    p = tmp_path / "out.txt"
    result = await files.write_file({"path": str(p), "content": "first"})
    assert p.read_text() == "first"
    assert "Wrote" in result

    await files.write_file({"path": str(p), "content": "second"})
    assert p.read_text() == "second"
