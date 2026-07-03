"""Tool capability surface (ARCHITECTURE.md §6, M4).

Importing this package registers every built-in tool (macos.py, files.py)
via their module-level ``_register_all()`` side effect, so callers just do
``from jarvis.tools import execute, get_tools`` without needing to know
which module defines which tool.
"""
from __future__ import annotations

from jarvis.tools import files as _files  # noqa: F401 - registration side effect
from jarvis.tools import macos as _macos  # noqa: F401 - registration side effect
from jarvis.tools.registry import execute, get_tools, register
from jarvis.tools.types import ToolCall, ToolDef, ToolResult

__all__ = [
    "execute",
    "get_tools",
    "register",
    "ToolCall",
    "ToolDef",
    "ToolResult",
]
