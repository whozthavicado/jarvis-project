"""Tool registry tests: dispatch, unknown tools, destructive confirm-gate,
timeouts, and handler-exception -> error ToolResult translation."""
import asyncio

import pytest

from jarvis.tools import registry
from jarvis.tools.types import ToolCall, ToolDef


@pytest.fixture(autouse=True)
def _isolated_registry(monkeypatch):
    """Each test gets a clean registry so built-in tools don't leak in."""
    monkeypatch.setattr(registry, "_REGISTRY", {})


async def _ok(args):
    return f"ok:{args}"


async def _boom(args):
    raise ValueError("handler blew up")


async def _slow(args):
    await asyncio.sleep(10)
    return "too slow"


def _def(name, handler, **kwargs) -> ToolDef:
    return ToolDef(name=name, description="test", parameters={}, handler=handler, **kwargs)


async def test_execute_dispatches_to_registered_handler():
    registry.register(_def("echo", _ok))
    result = await registry.execute(ToolCall(name="echo", args={"a": 1}))
    assert not result.is_error
    assert result.content == "ok:{'a': 1}"


async def test_execute_unknown_tool_is_error():
    result = await registry.execute(ToolCall(name="nope"))
    assert result.is_error
    assert "Unknown tool" in result.content


async def test_execute_handler_exception_becomes_error_result():
    registry.register(_def("boom", _boom))
    result = await registry.execute(ToolCall(name="boom"))
    assert result.is_error
    assert "handler blew up" in result.content


async def test_execute_timeout_becomes_error_result():
    registry.register(_def("slow", _slow, timeout_s=0.01))
    result = await registry.execute(ToolCall(name="slow"))
    assert result.is_error
    assert "timed out" in result.content


async def test_destructive_tool_without_confirm_is_refused():
    registry.register(_def("danger", _ok, is_destructive=True))
    result = await registry.execute(ToolCall(name="danger"))
    assert result.is_error
    assert "confirmation" in result.content


async def test_destructive_tool_runs_when_confirm_returns_true():
    registry.register(_def("danger", _ok, is_destructive=True))
    result = await registry.execute(ToolCall(name="danger", args={}), confirm=lambda call: True)
    assert not result.is_error


async def test_destructive_tool_supports_async_confirm():
    registry.register(_def("danger", _ok, is_destructive=True))

    async def confirm(call):
        return True

    result = await registry.execute(ToolCall(name="danger", args={}), confirm=confirm)
    assert not result.is_error


def test_get_tools_returns_all_registered():
    registry.register(_def("a", _ok))
    registry.register(_def("b", _ok))
    names = {t.name for t in registry.get_tools()}
    assert names == {"a", "b"}
