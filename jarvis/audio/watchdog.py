"""Whisper-server watchdog (ARCHITECTURE.md §5.4).

Health-checks the whisper.cpp server on a fixed interval through
:meth:`WhisperClient.health` and, when it stops answering, restarts it by
spawning a configurable command (``whisper.watchdog.restart_cmd`` in
settings.yaml — by default ``scripts/start_whisper_server.sh``). Restarts are
capped per cooldown window so a server that dies instantly (missing model,
broken binary) is retried a few times and then left alone instead of being
respawned forever; health checks keep running either way, so once the window
expires a still-dead server gets another round of attempts.

Runs as a background asyncio task with the same context-manager lifecycle as
Speaker/MicCapture; ``transcripts()`` starts one alongside the WhisperClient
it guards. With ``restart_cmd: null`` it degrades to health-check-plus-log.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from pathlib import Path
from typing import Awaitable, Callable, List, Optional

from jarvis.config import Settings, get_settings
from jarvis.audio.transcriber import WhisperClient

log = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_RESTART_CMD = ["scripts/start_whisper_server.sh"]


def _resolve_cmd(cmd: List[str]) -> List[str]:
    """Resolve a relative argv[0] against the repo root (same convention as
    memory.db_path — settings paths are repo-relative unless absolute)."""
    head = Path(cmd[0])
    if not head.is_absolute():
        head = _REPO_ROOT / head
    return [str(head), *cmd[1:]]


class WhisperWatchdog:
    """Health-check the whisper server every ``interval_s``; restart on failure."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        client: Optional[WhisperClient] = None,
        health: Optional[Callable[[], Awaitable[bool]]] = None,
    ):
        s = settings or get_settings()
        cfg = s.whisper.get("watchdog", Settings({}))
        self.interval_s = float(cfg.get("interval_s", 30))
        cmd = cfg.get("restart_cmd", _DEFAULT_RESTART_CMD)
        self.restart_cmd = _resolve_cmd([str(c) for c in cmd]) if cmd else None
        self.max_restarts = int(cfg.get("max_restarts", 3))
        self.cooldown_s = float(cfg.get("cooldown_s", 300))

        self._health = health or (client or WhisperClient(s)).health
        self._restart_times: List[float] = []
        self._clock = time.monotonic
        self._task: Optional[asyncio.Task] = None

    # -- lifecycle (same shape as Speaker) --------------------------------
    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.ensure_future(self._run())

    async def aclose(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def __aenter__(self) -> "WhisperWatchdog":
        self.start()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.aclose()

    # -- core --------------------------------------------------------------
    async def check_once(self) -> bool:
        """One health probe; kick off a restart if the server is down.

        Returns True when healthy. Split out from the loop so tests can
        drive it directly without real time passing.
        """
        if await self._health():
            return True
        await self._maybe_restart()
        return False

    async def _maybe_restart(self) -> None:
        if self.restart_cmd is None:
            log.warning("whisper server unhealthy; auto-restart disabled (restart_cmd: null)")
            return
        now = self._clock()
        self._restart_times = [t for t in self._restart_times if now - t < self.cooldown_s]
        if len(self._restart_times) >= self.max_restarts:
            log.error(
                "whisper server unhealthy; restart cap reached (%d in the last %.0fs) — backing off",
                self.max_restarts,
                self.cooldown_s,
            )
            return
        self._restart_times.append(now)
        log.warning("whisper server unhealthy; restarting via %s", self.restart_cmd)
        try:
            await self._spawn(self.restart_cmd)
        except OSError:
            log.exception("whisper server restart command failed to spawn")

    @staticmethod
    async def _spawn(cmd: List[str]) -> None:
        # Fire-and-forget: the next health check is the success signal, not
        # the process handle (start_whisper_server.sh execs the server and
        # never exits while healthy).
        await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(self.interval_s)
            try:
                await self.check_once()
            except Exception:  # noqa: BLE001 - the watchdog must not die
                log.exception("whisper watchdog check failed")
