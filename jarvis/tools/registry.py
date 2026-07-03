"""Tool registry: name -> schema + handler + destructive flag (ARCHITECTURE.md §6).

Tools register themselves at import time (see jarvis/tools/__init__.py, which
imports the handler modules so this module never has to know their names).
``execute`` is the single entry point the orchestrator and (later) the LLM
tool-use loop both call: it enforces the confirm-gate for destructive tools
and a per-tool timeout, and never lets a handler exception escape.
"""
from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Dict, List, Union

from jarvis.tools.types import ToolCall, ToolDef, ToolResult

ConfirmFn = Callable[[ToolCall], Union[bool, Awaitable[bool]]]

_REGISTRY: Dict[str, ToolDef] = {}


def register(tool: ToolDef) -> None:
    _REGISTRY[tool.name] = tool


def get_tools(tier: "str | None" = None) -> List[ToolDef]:
    """All registered tools. No per-tier filtering exists yet -- every tier
    sees the same tool set until a later milestone needs otherwise."""
    return list(_REGISTRY.values())


async def _resolve_confirm(confirm: "ConfirmFn | None", call: ToolCall) -> bool:
    if confirm is None:
        return False
    outcome = confirm(call)
    if asyncio.iscoroutine(outcome):
        outcome = await outcome
    return bool(outcome)


async def execute(call: ToolCall, confirm: "ConfirmFn | None" = None) -> ToolResult:
    """Run *call* against the registry. Never raises."""
    tool = _REGISTRY.get(call.name)
    if tool is None:
        return ToolResult(content=f"Unknown tool: {call.name}", is_error=True)

    if tool.is_destructive and not await _resolve_confirm(confirm, call):
        return ToolResult(
            content=f"{call.name} is a destructive action and needs confirmation; not executed.",
            is_error=True,
        )

    try:
        text = await asyncio.wait_for(tool.handler(call.args), timeout=tool.timeout_s)
    except asyncio.TimeoutError:
        return ToolResult(content=f"{call.name} timed out", is_error=True)
    except Exception as exc:  # noqa: BLE001 - handler errors become tool_result errors
        return ToolResult(content=str(exc), is_error=True)

    return ToolResult(content=text)
