"""macOS tool handler tests — subprocess calls are mocked, nothing here
actually touches the machine's volume/apps/screen."""
import asyncio

import pytest

from jarvis.tools import macos


class _FakeProc:
    def __init__(self, returncode=0, stdout=b"", stderr=b""):
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr

    async def communicate(self):
        return self._stdout, self._stderr


def _patch_exec(monkeypatch, calls, returncode=0, stdout=b""):
    async def fake_exec(*args, **kwargs):
        calls.append(args)
        return _FakeProc(returncode=returncode, stdout=stdout)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)


async def test_open_app_calls_open_dash_a(monkeypatch):
    calls = []
    _patch_exec(monkeypatch, calls)
    result = await macos.open_app({"app": "Safari"})
    assert calls == [("open", "-a", "Safari")]
    assert "Opened Safari" in result


async def test_close_app_uses_osascript_quit(monkeypatch):
    calls = []
    _patch_exec(monkeypatch, calls)
    result = await macos.close_app({"app": "Spotify"})
    assert calls[0][0] == "osascript"
    assert 'quit application "Spotify"' in calls[0][2] or 'to quit' in calls[0][2]
    assert "Closed Spotify" in result


async def test_volume_mute_and_directional(monkeypatch):
    calls = []
    _patch_exec(monkeypatch, calls)
    await macos.volume({"direction": "mute"})
    await macos.volume({"direction": "up"})
    assert "muted" in calls[0][2]
    assert "+ (10)" in calls[1][2] or "10" in calls[1][2]


async def test_lock_screen_sends_keystroke(monkeypatch):
    calls = []
    _patch_exec(monkeypatch, calls)
    result = await macos.lock_screen({})
    assert "keystroke" in calls[0][2]
    assert "Locking" in result


async def test_what_time_is_speakable_and_local_only(monkeypatch):
    calls = []
    _patch_exec(monkeypatch, calls)  # should not be invoked
    result = await macos.what_time({})
    assert calls == []
    assert result.startswith("It's")


async def test_failed_subprocess_raises_runtime_error(monkeypatch):
    async def fake_exec(*args, **kwargs):
        return _FakeProc(returncode=1, stderr=b"boom")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    with pytest.raises(RuntimeError, match="boom"):
        await macos.open_app({"app": "Nonexistent"})


async def test_set_timer_schedules_without_blocking(monkeypatch):
    calls = []
    _patch_exec(monkeypatch, calls)
    result = await macos.set_timer({"minutes": 5})
    assert "Timer set for 5 minutes" in result
    # the ring task itself sleeps 5*60s -- must not have run synchronously
    assert calls == []
