"""Live backend for the Z.E.R.O dashboard.

See docs/superpowers/specs/2026-07-04-zero-live-backend-integration-design.md.

One process runs two things concurrently in the same asyncio event loop,
sharing one Session/LLMClient/Router: the existing voice loop
(:func:`jarvis.core.orchestrator.converse`, unchanged -- mic -> whisper ->
LLM -> speak) and a WebSocket server that lets the dashboard send typed text
through the *same* :func:`jarvis.core.orchestrator.handle_turn` pipeline.
Because both input channels write to the same shared Session/MemoryStore,
the dashboard's activity feed reflects everything Z.E.R.O does, whether
triggered by voice or by typing in the dashboard.

Run with ``python -m jarvis.server``.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import websockets
from websockets.asyncio.server import ServerConnection

from jarvis.audio.types import Transcript
from jarvis.config import Settings, get_settings
from jarvis.core.broadcast import Broadcaster
from jarvis.core.budget import get_budget_guard
from jarvis.core.offline import get_connectivity_monitor
from jarvis.core.orchestrator import converse, handle_turn
from jarvis.core.session import Session
from jarvis.llm import LLMClient
from jarvis.memory import get_store
from jarvis.routing import Router

__all__ = ["Broadcaster", "handle_client", "run_server", "main"]

logger = logging.getLogger(__name__)

_HISTORY_LIMIT = 20
_DEFAULT_HOST = "localhost"
_DEFAULT_PORT = 8765


def _recent_history(session: Session, limit: int = _HISTORY_LIMIT) -> List[Dict[str, str]]:
    """Last *limit* turns from the in-memory session history, dashboard-shaped.

    Reads ``session.history`` directly rather than adding a new MemoryStore
    query method -- the server is a single long-running process for this
    pass, so a freshly-connected dashboard tab sees the current session's
    real history, which is enough to avoid an empty-looking activity feed.
    """
    recent = session.history[-limit:]
    return [{"role": m.role, "text": m.text} for m in recent]


async def handle_client(
    websocket: "ServerConnection",
    session: Session,
    llm: LLMClient,
    broadcaster: Broadcaster,
    router: Optional[Router] = None,
) -> None:
    """Per-connection coroutine: forward broadcasts, handle chat/history requests.

    A malformed message, an unrecognized message type, or this client's own
    disconnect never crashes the shared session or another client's
    connection -- only this connection's own tasks stop.
    """
    queue = broadcaster.subscribe()

    async def _forward() -> None:
        while True:
            event = await queue.get()
            await websocket.send(json.dumps(event))

    forward_task = asyncio.ensure_future(_forward())
    try:
        async for raw in websocket:
            try:
                message: Any = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                logger.warning("dropped malformed WS message: %r", raw)
                continue

            msg_type = message.get("type") if isinstance(message, dict) else None
            if msg_type == "chat":
                text = str(message.get("text", "")).strip()
                if not text:
                    continue
                transcript = Transcript(text=text)
                result = await handle_turn(
                    session,
                    llm,
                    transcript,
                    lambda _chunk: None,  # dashboard chat has no incremental-streaming UI yet
                    router=router,
                    budget=get_budget_guard(),
                    offline=get_connectivity_monitor(),
                    broadcaster=broadcaster,
                )
                reply_text = result.text if result is not None else "Something went wrong there. Let's try that again."
                await websocket.send(json.dumps({"type": "reply", "text": reply_text}))
            elif msg_type == "history":
                await websocket.send(
                    json.dumps({"type": "history", "entries": _recent_history(session)})
                )
            elif msg_type == "remember":
                text = str(message.get("text", "")).strip()
                if not text:
                    continue
                kind = str(message.get("kind") or "note")
                store = get_store()
                added, _memory_id = store.add_memory(kind=kind, text=text)
                if added:
                    broadcaster.publish(
                        {
                            "type": "activity",
                            "actor": "User",
                            "description": f"Saved note: {text}",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                    )
                await websocket.send(
                    json.dumps({"type": "remember_ack", "added": added, "text": text})
                )
            else:
                logger.warning("dropped unrecognized WS message type: %r", msg_type)
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        broadcaster.unsubscribe(queue)
        forward_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, websockets.exceptions.ConnectionClosed):
            await forward_task


async def run_server(
    session: Session,
    llm: LLMClient,
    broadcaster: Broadcaster,
    router: Optional[Router] = None,
    host: str = _DEFAULT_HOST,
    port: int = _DEFAULT_PORT,
) -> None:
    """Serve the dashboard WebSocket endpoint until cancelled."""

    async def _handler(websocket: "ServerConnection") -> None:
        await handle_client(websocket, session, llm, broadcaster, router=router)

    async with websockets.serve(_handler, host, port):
        await asyncio.Future()  # run until the enclosing task is cancelled


async def main(settings: Optional[Settings] = None) -> None:
    s = settings or get_settings()
    session = Session(tier="t1_standard", store=get_store(s))
    llm = LLMClient(s, tier="t1_standard")
    router = Router(s)
    broadcaster = Broadcaster()

    print(f"Z.E.R.O server: dashboard on ws://{_DEFAULT_HOST}:{_DEFAULT_PORT}, voice loop live. Ctrl-C to stop.")

    await asyncio.gather(
        converse(s, session=session, llm=llm, router=router, broadcaster=broadcaster),
        run_server(session, llm, broadcaster, router=router),
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
