"""macOS device-control tools (ARCHITECTURE.md §6, M4).

Every handler shells out via ``asyncio.create_subprocess_exec`` (never
``shell=True`` -- args are passed as a list so user text can't break out
into arbitrary shell commands) to ``open`` or ``osascript``. These are the
handlers T0 grammar commands dispatch to with no LLM/API call involved; the
same registry entries will later be reachable from the LLM tool-use loop too.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict

from jarvis.tools.registry import register
from jarvis.tools.types import ToolDef

_BRIGHTNESS_KEY_CODE = {"up": "144", "down": "145"}


async def _run(*args: str) -> str:
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError((stderr or stdout).decode(errors="replace").strip() or f"{args[0]} failed")
    return stdout.decode(errors="replace").strip()


async def _osascript(script: str) -> str:
    return await _run("osascript", "-e", script)


async def open_app(args: Dict[str, Any]) -> str:
    app = args["app"]
    await _run("open", "-a", app)
    return f"Opened {app}."


async def close_app(args: Dict[str, Any]) -> str:
    app = args["app"]
    await _osascript(f'tell application "{app}" to quit')
    return f"Closed {app}."


async def volume(args: Dict[str, Any]) -> str:
    direction = args["direction"]
    if direction == "mute":
        await _osascript("set volume with output muted")
        return "Muted."
    if direction == "unmute":
        await _osascript("set volume without output muted")
        return "Unmuted."
    delta = 10 if direction == "up" else -10
    await _osascript(
        f"set volume output volume ((output volume of (get volume settings)) + ({delta}))"
    )
    return f"Volume {'up' if direction == 'up' else 'down'}."


async def media_control(args: Dict[str, Any]) -> str:
    action = args["action"]
    await _osascript(f'tell application "Music" to {action}')
    return f"{action.capitalize()}ing music." if action == "play" else "Paused music."


async def lock_screen(args: Dict[str, Any]) -> str:
    await _osascript(
        'tell application "System Events" to keystroke "q" using {control down, command down}'
    )
    return "Locking the screen."


async def brightness(args: Dict[str, Any]) -> str:
    direction = args["direction"]
    key_code = _BRIGHTNESS_KEY_CODE[direction]
    await _osascript(f'tell application "System Events" to key code {key_code}')
    return f"Brightness {direction}."


async def notify(args: Dict[str, Any]) -> str:
    title = args.get("title", "Jarvis")
    message = args["message"]
    safe_title = title.replace('"', '\\"')
    safe_message = message.replace('"', '\\"')
    await _osascript(f'display notification "{safe_message}" with title "{safe_title}"')
    return "Notified."


def _speakable_time(now: "datetime | None" = None) -> str:
    t = now or datetime.now()
    hour = t.hour % 12 or 12
    minute = t.minute
    period = "AM" if t.hour < 12 else "PM"
    if minute == 0:
        return f"{hour} o'clock {period}"
    return f"{hour}:{minute:02d} {period}"


async def what_time(args: Dict[str, Any]) -> str:
    return f"It's {_speakable_time()}."


async def set_timer(args: Dict[str, Any]) -> str:
    minutes = int(args["minutes"])

    async def _ring() -> None:
        await asyncio.sleep(minutes * 60)
        try:
            await _run("say", f"Your {minutes}-minute timer is up.")
        except Exception:  # noqa: BLE001 - best-effort notification, never crash the loop
            pass

    asyncio.ensure_future(_ring())
    unit = "minute" if minutes == 1 else "minutes"
    return f"Timer set for {minutes} {unit}."


def _register_all() -> None:
    register(
        ToolDef(
            name="open_app",
            description="Open a macOS application by name.",
            parameters={"app": {"type": "string", "description": "Application name"}},
            handler=open_app,
        )
    )
    register(
        ToolDef(
            name="close_app",
            description="Quit a running macOS application by name.",
            parameters={"app": {"type": "string", "description": "Application name"}},
            handler=close_app,
        )
    )
    register(
        ToolDef(
            name="volume",
            description="Adjust or mute/unmute system output volume.",
            parameters={
                "direction": {"type": "string", "enum": ["up", "down", "mute", "unmute"]}
            },
            handler=volume,
        )
    )
    register(
        ToolDef(
            name="media_control",
            description="Play or pause music.",
            parameters={"action": {"type": "string", "enum": ["play", "pause"]}},
            handler=media_control,
        )
    )
    register(
        ToolDef(
            name="lock_screen",
            description="Lock the screen.",
            parameters={},
            handler=lock_screen,
        )
    )
    register(
        ToolDef(
            name="brightness",
            description="Adjust screen brightness.",
            parameters={"direction": {"type": "string", "enum": ["up", "down"]}},
            handler=brightness,
        )
    )
    register(
        ToolDef(
            name="notify",
            description="Show a macOS notification.",
            parameters={
                "title": {"type": "string"},
                "message": {"type": "string"},
            },
            handler=notify,
        )
    )
    register(
        ToolDef(
            name="what_time",
            description="Get the current time in speakable form.",
            parameters={},
            handler=what_time,
        )
    )
    register(
        ToolDef(
            name="set_timer",
            description="Set a countdown timer for N minutes.",
            parameters={"minutes": {"type": "integer"}},
            handler=set_timer,
        )
    )


_register_all()
