"""Offline-mode tests — ConnectivityMonitor caching/feedback and the
orchestrator's §5.1 last-rung behavior (T0 still works, LLM turns get the
spoken offline notice, transport failures mark us offline)."""
from types import SimpleNamespace

import httpx
import pytest

from jarvis.audio.types import Transcript
from jarvis.config import Settings
from jarvis.core import orchestrator
from jarvis.core.offline import ConnectivityMonitor
from jarvis.core.orchestrator import _OFFLINE_NOTICE, handle_turn
from jarvis.core.session import Session
from jarvis.llm.types import TurnResult

_SETTINGS = Settings({"offline": {"cache_ttl_s": 30}})


def _monitor(verdicts) -> "tuple[ConnectivityMonitor, list]":
    """Monitor whose probe pops scripted verdicts and records each call."""
    calls = []

    async def probe() -> bool:
        calls.append(True)
        return verdicts.pop(0)

    return ConnectivityMonitor(_SETTINGS, probe=probe), calls


class _StubLLM:
    """Minimal LLMClient stand-in; optionally raises instead of answering."""

    def __init__(self, exc: Exception = None):
        self.exc = exc
        self.calls = 0
        self.tier = "t1_standard"

    async def stream_reply(self, system_prompt, messages, on_text) -> TurnResult:
        self.calls += 1
        if self.exc is not None:
            raise self.exc
        on_text("A fine reply.")
        return TurnResult(text="A fine reply.", model="stub", stop_reason="end_turn")


# -- ConnectivityMonitor ----------------------------------------------------

async def test_verdict_is_cached_within_ttl():
    mon, calls = _monitor([True, False])
    assert await mon.is_online() is True
    assert await mon.is_online() is True  # cached, second verdict not consumed
    assert len(calls) == 1


async def test_reprobes_after_ttl_expires():
    mon, calls = _monitor([True, False])
    now = [1000.0]
    mon._clock = lambda: now[0]
    assert await mon.is_online() is True
    now[0] += 31.0
    assert await mon.is_online() is False
    assert len(calls) == 2


async def test_mark_offline_skips_the_probe():
    mon, calls = _monitor([True])
    mon.mark_offline()
    assert await mon.is_online() is False
    assert calls == []  # verdict came from the observation, not a probe


async def test_recovery_after_mark_offline_ttl():
    mon, calls = _monitor([True])
    now = [1000.0]
    mon._clock = lambda: now[0]
    mon.mark_offline()
    now[0] += 31.0
    assert await mon.is_online() is True
    assert len(calls) == 1


# -- orchestrator integration ------------------------------------------------

def _transcript(text: str) -> Transcript:
    return Transcript(text=text, duration_ms=800)


async def test_offline_turn_speaks_notice_and_never_touches_llm_or_history():
    mon, _ = _monitor([False])
    session = Session(tier="t1_standard")
    llm = _StubLLM()
    spoken = []

    result = await handle_turn(
        session, llm, _transcript("what's the weather in Lisbon"), spoken.append,
        offline=mon,
    )

    assert result is not None and result.model == "offline"
    assert result.stop_reason == "offline"
    assert spoken == [_OFFLINE_NOTICE]
    assert llm.calls == 0
    assert session.messages == []  # offline turns leave no history, like T0


async def test_t0_command_still_runs_while_offline(monkeypatch):
    mon, calls = _monitor([False])
    session = Session(tier="t1_standard")
    llm = _StubLLM()
    spoken = []

    monkeypatch.setattr(orchestrator, "match_t0", lambda text: object())

    async def fake_execute(call, confirm=None):
        return SimpleNamespace(content="It's 3 PM.")

    monkeypatch.setattr(orchestrator, "execute_tool", fake_execute)

    result = await handle_turn(
        session, llm, _transcript("what time is it"), spoken.append, offline=mon,
    )

    assert result is not None and result.model == "t0"
    assert spoken == ["It's 3 PM."]
    assert calls == []  # T0 short-circuits before connectivity is even asked


async def test_transport_error_marks_offline_for_the_next_turn():
    mon, calls = _monitor([True])
    session = Session(tier="t1_standard")
    failing = _StubLLM(exc=httpx.ConnectError("no route to host"))
    spoken = []

    result = await handle_turn(
        session, failing, _transcript("tell me a story"), spoken.append, offline=mon,
    )
    assert result is None  # normal failed-turn contract: apology spoken
    assert len(calls) == 1

    # Next turn: no new probe, straight to the offline notice, LLM untouched.
    llm = _StubLLM()
    spoken2 = []
    result2 = await handle_turn(
        session, llm, _transcript("still there?"), spoken2.append, offline=mon,
    )
    assert result2 is not None and result2.model == "offline"
    assert spoken2 == [_OFFLINE_NOTICE]
    assert llm.calls == 0
    assert len(calls) == 1  # mark_offline() supplied the verdict, not a probe


async def test_non_transport_error_does_not_mark_offline():
    mon, calls = _monitor([True, True])
    session = Session(tier="t1_standard")
    failing = _StubLLM(exc=RuntimeError("bug, not the network"))
    spoken = []

    await handle_turn(
        session, failing, _transcript("tell me a story"), spoken.append, offline=mon,
    )

    assert await mon.is_online() is True  # still online per the cached probe
    assert len(calls) == 1


async def test_no_monitor_means_unchanged_behavior():
    session = Session(tier="t1_standard")
    llm = _StubLLM()
    spoken = []

    result = await handle_turn(session, llm, _transcript("hello there"), spoken.append)

    assert result is not None and result.text == "A fine reply."
    assert llm.calls == 1
