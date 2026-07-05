"""Shell tool tests — subprocess calls are mocked, nothing here actually
runs a real command."""
import asyncio

import pytest

from jarvis.config import Settings
from jarvis.tools import shell


class _FakeProc:
    def __init__(self, returncode=0, stdout=b"", stderr=b""):
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr

    async def communicate(self):
        return self._stdout, self._stderr


def _patch_exec(monkeypatch, calls, returncode=0, stdout=b"", stderr=b""):
    async def fake_exec(*args, **kwargs):
        calls.append(args)
        return _FakeProc(returncode=returncode, stdout=stdout, stderr=stderr)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)


def _settings_with_allowlist(*binaries) -> Settings:
    return Settings({"tools": {"shell": {"allowlist": list(binaries)}}})


async def test_allowed_command_runs_and_returns_output(monkeypatch):
    calls = []
    _patch_exec(monkeypatch, calls, stdout=b"hello.txt\n")
    settings = _settings_with_allowlist("ls")

    result = await shell.run_command({"command": "ls -la"}, settings=settings)

    assert calls == [("ls", "-la")]
    assert result == "hello.txt"


async def test_disallowed_binary_is_rejected_without_spawning(monkeypatch):
    calls = []
    _patch_exec(monkeypatch, calls)
    settings = _settings_with_allowlist("ls")

    result = await shell.run_command({"command": "rm -rf /"}, settings=settings)

    assert calls == []
    assert "not on the allowed command list" in result


async def test_nonzero_exit_returns_text_not_exception(monkeypatch):
    calls = []
    _patch_exec(monkeypatch, calls, returncode=1, stderr=b"no matches found")
    settings = _settings_with_allowlist("grep")

    result = await shell.run_command({"command": "grep foo bar.txt"}, settings=settings)

    assert result == "no matches found"


async def test_unparseable_command_is_handled(monkeypatch):
    calls = []
    _patch_exec(monkeypatch, calls)
    settings = _settings_with_allowlist("echo")

    result = await shell.run_command({"command": 'echo "unbalanced'}, settings=settings)

    assert calls == []
    assert "Could not parse command" in result


async def test_empty_command_is_handled(monkeypatch):
    calls = []
    _patch_exec(monkeypatch, calls)
    settings = _settings_with_allowlist("echo")

    result = await shell.run_command({"command": "   "}, settings=settings)

    assert calls == []
    assert result == "Empty command."


async def test_run_command_registered_with_60s_timeout():
    from jarvis.tools.registry import _REGISTRY

    assert _REGISTRY["run_command"].timeout_s == 60.0
    assert _REGISTRY["run_command"].is_destructive is False
