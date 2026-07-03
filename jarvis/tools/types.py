"""Shared tool value types (ARCHITECTURE.md §6, M4 contract).

Provider-agnostic like jarvis/llm/types.py: a ``ToolCall`` is just a name and
args dict, whether it came from an LLM tool_use block or a T0 grammar match.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict


@dataclass(frozen=True)
class ToolCall:
    name: str
    args: Dict[str, Any] = field(default_factory=dict)
    id: str = ""


@dataclass(frozen=True)
class ToolResult:
    content: str
    is_error: bool = False


Handler = Callable[[Dict[str, Any]], Awaitable[str]]


@dataclass(frozen=True)
class ToolDef:
    """One registered tool: its API schema plus a local async handler.

    Attributes:
        name: Unique tool name, also the key the router/grammar dispatches on.
        description: Shown to the model in the tool schema.
        parameters: JSON-schema ``properties`` dict for the tool call (the
            API-facing schema; T0 grammar calls bypass this and build args
            directly from regex captures).
        handler: async function(args) -> result text. Raises on failure;
            the registry turns exceptions into an error ToolResult.
        is_destructive: if True, execute() refuses to run without a truthy
            confirm callback (ARCHITECTURE.md §1: "Destructive actions ...
            always go through their dedicated tool so the user gets a
            confirmation prompt").
        timeout_s: per-call timeout before the registry cancels the handler.
    """

    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Handler
    is_destructive: bool = False
    timeout_s: float = 10.0

    def schema(self) -> Dict[str, Any]:
        """API-facing tool schema dict (Anthropic tool_use format)."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": self.parameters,
                "required": list(self.parameters.keys()),
            },
        }
