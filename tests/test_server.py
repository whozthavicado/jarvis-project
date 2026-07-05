"""jarvis/server.py tests — a fake WebSocket connection object and a
stubbed orchestrator.handle_turn, mirroring test_orchestrator.py's
stubbing style. No real network/audio involved.
"""
import asyncio
import json

import jarvis.server as server_mod
from jarvis.core.broadcast import Broadcaster
from jarvis.core.session import Session
from jarvis.llm.types import TurnResult


class _FakeWebSocket:
    """Async-iterable fake connection: push() queues incoming raw messages,
    close() ends the iteration (like a real disconnect)."""

    def __init__(self):
        self.sent = []
        self._queue: "asyncio.Queue[str]" = asyncio.Queue()
        self._closed = asyncio.Event()

    def __aiter__(self):
        return self

    async def __anext__(self):
        get_task = asyncio.ensure_future(self._queue.get())
        closed_task = asyncio.ensure_future(self._closed.wait())
        done, pending = await asyncio.wait(
            {get_task, closed_task}, return_when=asyncio.FIRST_COMPLETED
        )
        for p in pending:
            p.cancel()
        if get_task in done:
            return get_task.result()
        raise StopAsyncIteration

    async def send(self, data: str) -> None:
        self.sent.append(data)

    def push(self, raw: str) -> None:
        self._queue.put_nowait(raw)

    def close(self) -> None:
        self._closed.set()


def _ok_result(text="hi there") -> TurnResult:
    return TurnResult(text=text, model="fake-model", stop_reason="end_turn")


async def test_chat_message_gets_a_real_reply(monkeypatch):
    async def fake_handle_turn(*args, **kwargs):
        return _ok_result("hi there")

    monkeypatch.setattr(server_mod, "handle_turn", fake_handle_turn)

    ws = _FakeWebSocket()
    ws.push(json.dumps({"type": "chat", "text": "hello"}))
    ws.close()

    await server_mod.handle_client(ws, Session(tier="t1_standard"), object(), Broadcaster())

    assert json.loads(ws.sent[-1]) == {"type": "reply", "text": "hi there"}


async def test_empty_chat_text_is_ignored(monkeypatch):
    calls = []

    async def fake_handle_turn(*args, **kwargs):
        calls.append(1)
        return _ok_result()

    monkeypatch.setattr(server_mod, "handle_turn", fake_handle_turn)

    ws = _FakeWebSocket()
    ws.push(json.dumps({"type": "chat", "text": "   "}))
    ws.close()

    await server_mod.handle_client(ws, Session(tier="t1_standard"), object(), Broadcaster())

    assert calls == []
    assert ws.sent == []


async def test_failed_turn_sends_a_fallback_reply(monkeypatch):
    async def fake_handle_turn(*args, **kwargs):
        return None  # handle_turn returns None on a failed turn

    monkeypatch.setattr(server_mod, "handle_turn", fake_handle_turn)

    ws = _FakeWebSocket()
    ws.push(json.dumps({"type": "chat", "text": "hello"}))
    ws.close()

    await server_mod.handle_client(ws, Session(tier="t1_standard"), object(), Broadcaster())

    assert "try that again" in json.loads(ws.sent[-1])["text"]


async def test_history_request_returns_recent_turns():
    session = Session(tier="t1_standard")
    session.add_user_turn("hi")  # first turn gets Layer C's <context> block prepended
    session.add_assistant_turn("hello")
    session.add_user_turn("how are you")  # second+ turns are plain text

    ws = _FakeWebSocket()
    ws.push(json.dumps({"type": "history"}))
    ws.close()

    await server_mod.handle_client(ws, session, object(), Broadcaster())

    payload = json.loads(ws.sent[-1])
    assert payload["type"] == "history"
    assert payload["entries"][1:] == [
        {"role": "assistant", "text": "hello"},
        {"role": "user", "text": "how are you"},
    ]
    assert payload["entries"][0]["text"].endswith("hi")  # context-prefixed first turn


async def test_malformed_message_is_ignored_and_connection_continues(monkeypatch):
    async def fake_handle_turn(*args, **kwargs):
        return _ok_result("ok")

    monkeypatch.setattr(server_mod, "handle_turn", fake_handle_turn)

    ws = _FakeWebSocket()
    ws.push("not json{{{")
    ws.push(json.dumps({"type": "chat", "text": "hi"}))
    ws.close()

    await server_mod.handle_client(ws, Session(tier="t1_standard"), object(), Broadcaster())

    assert json.loads(ws.sent[-1]) == {"type": "reply", "text": "ok"}


async def test_unrecognized_message_type_is_ignored():
    ws = _FakeWebSocket()
    ws.push(json.dumps({"type": "unknown"}))
    ws.close()

    await server_mod.handle_client(ws, Session(tier="t1_standard"), object(), Broadcaster())

    assert ws.sent == []


async def test_disconnect_unsubscribes_from_the_broadcaster():
    ws = _FakeWebSocket()
    ws.close()
    broadcaster = Broadcaster()

    await server_mod.handle_client(ws, Session(tier="t1_standard"), object(), broadcaster)

    assert len(broadcaster._subscribers) == 0


async def test_broadcast_events_are_forwarded_to_the_connected_client():
    ws = _FakeWebSocket()
    broadcaster = Broadcaster()
    session = Session(tier="t1_standard")

    task = asyncio.ensure_future(server_mod.handle_client(ws, session, object(), broadcaster))
    await asyncio.sleep(0.05)  # let it subscribe
    broadcaster.publish({"type": "status", "state": "thinking"})
    await asyncio.sleep(0.05)
    ws.close()
    await asyncio.wait_for(task, timeout=1)

    assert json.loads(ws.sent[0]) == {"type": "status", "state": "thinking"}
