"""Shell tool (ARCHITECTURE.md §5.3/§6, M4): run_command, allowlisted.

Commands are parsed with ``shlex.split`` (never ``shell=True`` -- same
subprocess invariant as jarvis/tools/macos.py) and the first token (the
binary name) is checked against ``tools.shell.allowlist`` in settings.yaml
before anything is spawned. Anything not on the list is rejected with a
plain error string, not an exception -- registry.execute()'s existing
exception handling never needs to special-case this tool.

Unlike macos.py's ``_run`` (which raises RuntimeError on a nonzero exit),
a nonzero exit here is returned as plain text, not raised. Shell commands
routinely have "expected" nonzero exits (e.g. ``grep`` finding no match);
forcing every one of those into an ``is_error=True`` tool_result would make
ordinary allowlisted usage look like a tool failure to the model. Do not
"fix" this to match macos.py's raise-on-nonzero idiom -- it's deliberate.

``is_destructive`` is deliberately left at its default (False): the
allowlist is this tool's entire security boundary, not a confirm-gate.
Marking it destructive would force a confirmation prompt in front of
harmless, already-allowlisted read-only commands like ``ls``/``git status``.
If a specific command needs gating, curate the allowlist instead of
flipping this flag.
"""
from __future__ import annotations

import asyncio
import shlex
from typing import Any, Dict, Optional

from jarvis.config import Settings, get_settings
from jarvis.tools.registry import register
from jarvis.tools.types import ToolDef

_TIMEOUT_S = 60.0  # ARCHITECTURE.md §5.3: 60s for shell vs. the 10s default


def _allowlist(settings: Optional[Settings] = None) -> set:
    s = settings or get_settings()
    return {str(b) for b in s.get("tools", {}).get("shell", {}).get("allowlist", [])}


async def run_command(args: Dict[str, Any], settings: Optional[Settings] = None) -> str:
    command = args["command"]
    try:
        parts = shlex.split(command)
    except ValueError as exc:  # unbalanced quotes etc.
        return f"Could not parse command: {exc}"
    if not parts:
        return "Empty command."

    binary = parts[0]
    if binary not in _allowlist(settings):
        return f"'{binary}' is not on the allowed command list; refusing to run it."

    proc = await asyncio.create_subprocess_exec(
        *parts,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        text = (stderr or stdout).decode(errors="replace").strip()
        return text or f"{binary} exited {proc.returncode}"
    return stdout.decode(errors="replace").strip() or "(no output)"


def _register_all() -> None:
    register(
        ToolDef(
            name="run_command",
            description="Run an allowlisted shell command and return its output.",
            parameters={"command": {"type": "string", "description": "Full command line to run"}},
            handler=run_command,
            timeout_s=_TIMEOUT_S,
        )
    )


_register_all()
