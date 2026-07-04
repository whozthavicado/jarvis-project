"""Whisper watchdog tests — health-flap restarts, the cap window, and the
disabled mode, all driven through check_once() so no real time passes."""
import asyncio
from typing import List

import pytest

from jarvis.config import Settings
from jarvis.audio.watchdog import WhisperWatchdog


def _watchdog(monkeypatch=None, healthy=True, **overrides) -> WhisperWatchdog:
    cfg = {"interval_s": 30, "max_restarts": 3, "cooldown_s": 300}
    cfg.update(overrides)
    settings = Settings({"whisper": {"watchdog": cfg}})

    async def health() -> bool:
        return healthy

    return WhisperWatchdog(settings, health=health)


class _SpawnRecorder:
    def __init__(self, fail: bool = False):
        self.calls: List[List[str]] = []
        self.fail = fail

    async def __call__(self, cmd: List[str]) -> None:
        self.calls.append(cmd)
        if self.fail:
            raise OSError("spawn failed")


async def test_healthy_server_is_left_alone():
    wd = _watchdog(healthy=True)
    spawn = _SpawnRecorder()
    wd._spawn = spawn
    assert await wd.check_once() is True
    assert spawn.calls == []


async def test_unhealthy_server_triggers_restart_with_repo_relative_cmd():
    wd = _watchdog(healthy=False)
    spawn = _SpawnRecorder()
    wd._spawn = spawn
    assert await wd.check_once() is False
    assert len(spawn.calls) == 1
    cmd = spawn.calls[0]
    assert cmd[0].endswith("scripts/start_whisper_server.sh")
    assert cmd[0].startswith("/"), "relative restart_cmd must resolve to an absolute path"


async def test_restart_cap_within_cooldown_window():
    wd = _watchdog(healthy=False, max_restarts=3, cooldown_s=300)
    spawn = _SpawnRecorder()
    wd._spawn = spawn
    now = [1000.0]
    wd._clock = lambda: now[0]

    for _ in range(5):
        await wd.check_once()
        now[0] += 1.0

    assert len(spawn.calls) == 3, "no more than max_restarts spawns per window"


async def test_restarts_resume_after_cooldown_expires():
    wd = _watchdog(healthy=False, max_restarts=1, cooldown_s=300)
    spawn = _SpawnRecorder()
    wd._spawn = spawn
    now = [1000.0]
    wd._clock = lambda: now[0]

    await wd.check_once()
    await wd.check_once()  # capped
    assert len(spawn.calls) == 1

    now[0] += 301.0  # window expired
    await wd.check_once()
    assert len(spawn.calls) == 2


async def test_null_restart_cmd_disables_auto_restart():
    wd = _watchdog(healthy=False, restart_cmd=None)
    spawn = _SpawnRecorder()
    wd._spawn = spawn
    assert await wd.check_once() is False
    assert spawn.calls == []


async def test_spawn_failure_does_not_raise():
    wd = _watchdog(healthy=False)
    wd._spawn = _SpawnRecorder(fail=True)
    assert await wd.check_once() is False  # OSError swallowed and logged


async def test_watchdog_loop_survives_a_health_exception():
    """The background task must not die if a check blows up."""
    boom = [True]

    async def health() -> bool:
        if boom[0]:
            boom[0] = False
            raise RuntimeError("health probe exploded")
        return True

    settings = Settings({"whisper": {"watchdog": {"interval_s": 0.01}}})
    wd = WhisperWatchdog(settings, health=health)
    async with wd:
        await asyncio.sleep(0.05)
        assert wd._task is not None and not wd._task.done()
    assert wd._task is None
