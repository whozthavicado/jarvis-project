"""Orchestrator tests — handle_turn's success/failure/refusal paths and the
error -> spoken-fallback classification. No real LLM or audio involved.
"""
import asyncio

import httpx
import pytest
import anthropic

from jarvis.audio.types import Transcript
from jarvis.core.budget import BudgetGuard
from jarvis.core.offline import ConnectivityMonitor
from jarvis.core.orchestrator import _fallback_text_for, handle_turn
from jarvis.core.session import Session
from jarvis.llm.providers import OpenRouterError
from jarvis.llm.types import ChatMessage, TurnResult
from jarvis.routing.router import Router


def _req() -> httpx.Request:
    return httpx.Request("POST", "https://api.anthropic.com/v1/messages")


def _resp(status: int) -> httpx.Response:
    return httpx.Response(status_code=status, request=_req())


class _StubLLM:
    """Stands in for LLMClient — either returns a fixed TurnResult or raises."""

    def __init__(self, result: TurnResult = None, error: Exception = None):
        self._result = result
        self._error = error
        self.calls = []
        self.tier = "t1_standard"

    async def stream_reply(self, system_prompt, messages, on_text):
        self.calls.append((system_prompt, messages))
        if self._error is not None:
            raise self._error
        if self._result.text:  # a real stream emits no deltas for empty content
            on_text(self._result.text)
        return self._result


def _ok_result(text="Hello there.") -> TurnResult:
    return TurnResult(text=text, model="claude-sonnet-5", stop_reason="end_turn")


@pytest.mark.asyncio
async def test_successful_turn_updates_session_and_streams_text():
    session = Session(tier="t1_standard")
    llm = _StubLLM(result=_ok_result("Hi, how can I help?"))
    seen = []

    result = await handle_turn(session, llm, Transcript(text="hello"), seen.append)

    assert result.text == "Hi, how can I help?"
    assert seen == ["Hi, how can I help?"]
    # user turn + assistant turn both landed in history
    assert len(session.history) == 2
    assert session.history[0].role == "user"
    assert session.history[1] == ChatMessage(role="assistant", text="Hi, how can I help?")


@pytest.mark.asyncio
async def test_failed_turn_speaks_fallback_and_leaves_no_assistant_turn():
    session = Session(tier="t1_standard")
    llm = _StubLLM(error=anthropic.APIConnectionError(request=_req()))
    seen = []

    result = await handle_turn(session, llm, Transcript(text="hello"), seen.append)

    assert result is None
    assert len(seen) == 1 and "reach the cloud" in seen[0]
    # user turn is preserved (so context isn't lost), no assistant reply added
    assert len(session.history) == 1
    assert session.history[0].role == "user"


@pytest.mark.asyncio
async def test_refusal_speaks_a_generic_decline_but_result_is_returned():
    session = Session(tier="t1_standard")
    llm = _StubLLM(result=TurnResult(text="", model="claude-sonnet-5", stop_reason="refusal"))
    seen = []

    result = await handle_turn(session, llm, Transcript(text="hello"), seen.append)

    assert result is not None and result.refused
    assert seen == ["I'd rather not answer that."]
    # refusal shouldn't be recorded as if the model had actually said something
    assert len(session.history) == 1


@pytest.mark.parametrize(
    "exc,expected_snippet",
    [
        (anthropic.AuthenticationError("bad key", response=_resp(401), body=None), "credentials"),
        (anthropic.PermissionDeniedError("nope", response=_resp(403), body=None), "not authorized"),
        (anthropic.RateLimitError("slow down", response=_resp(429), body=None), "rate limited"),
        (anthropic.APIConnectionError(request=_req()), "reach the cloud"),
        (anthropic.APIStatusError("boom", response=_resp(500), body=None), "server side"),
        (OpenRouterError("free model unavailable"), "free model backend"),
        (ValueError("unexpected bug"), "try that again"),
    ],
)
def test_fallback_text_classifies_common_failures(exc, expected_snippet):
    assert expected_snippet in _fallback_text_for(exc)


@pytest.mark.asyncio
async def test_t0_grammar_match_bypasses_llm_and_session(monkeypatch):
    """A T0 command (RULE 0) never touches the LLM or session history."""
    session = Session(tier="t1_standard")
    llm = _StubLLM(result=_ok_result())  # would fail this test if called
    seen = []

    async def fake_what_time(args):
        return "It's four o'clock PM."

    from dataclasses import replace

    from jarvis.tools import registry

    fake_tool = replace(registry._REGISTRY["what_time"], handler=fake_what_time)
    monkeypatch.setitem(registry._REGISTRY, "what_time", fake_tool)

    result = await handle_turn(session, llm, Transcript(text="what time is it"), seen.append)

    assert result.model == "t0"
    assert result.stop_reason == "t0_command"
    assert seen == ["It's four o'clock PM."]
    assert llm.calls == []
    assert session.history == []


@pytest.mark.asyncio
async def test_non_t0_transcript_falls_through_to_llm():
    session = Session(tier="t1_standard")
    llm = _StubLLM(result=_ok_result("It looks sunny."))
    seen = []

    result = await handle_turn(session, llm, Transcript(text="what's the weather like"), seen.append)

    assert result.text == "It looks sunny."
    assert len(llm.calls) == 1
    assert len(session.history) == 2


class _StubRouter:
    """Router double: fixed tier, records which LLMClient was resolved."""

    def __init__(self, tier: str, llm: _StubLLM):
        self.tier = tier
        self._llm = llm
        self.resolved_texts = []

    async def resolve(self, text: str) -> str:
        self.resolved_texts.append(text)
        return self.tier

    def llm_for(self, tier: str) -> _StubLLM:
        assert tier == self.tier
        return self._llm

    @staticmethod
    def system_prompt_for(tier: str) -> str:
        return f"system-prompt-for-{tier}"


@pytest.mark.asyncio
async def test_router_decides_the_tier_and_system_prompt_per_turn():
    session = Session(tier="t1_standard")  # session's own tier is now unused for the call
    routed_llm = _StubLLM(result=_ok_result("Routed reply."))
    router = _StubRouter(tier="t2_medium", llm=routed_llm)
    unused_llm = _StubLLM(result=_ok_result("should not be used"))
    seen = []

    result = await handle_turn(
        session,
        unused_llm,
        Transcript(text="please design a plan for the migration"),
        seen.append,
        router=router,
    )

    assert result.text == "Routed reply."
    assert unused_llm.calls == []
    assert len(routed_llm.calls) == 1
    system_prompt, _messages = routed_llm.calls[0]
    assert system_prompt == "system-prompt-for-t2_medium"
    assert router.resolved_texts == ["please design a plan for the migration"]


@pytest.mark.asyncio
async def test_router_is_isinstance_compatible_with_real_router():
    # Guards against the stub's interface drifting from the real Router.
    real = Router()
    assert hasattr(real, "resolve") and hasattr(real, "llm_for") and hasattr(
        real, "system_prompt_for"
    )


class _MultiTierStubRouter:
    """Router double serving a different stub LLM per tier -- for budget
    tests that need the orchestrator to actually reroute mid-turn."""

    def __init__(self, resolved_tier: str, llms: dict):
        self._resolved_tier = resolved_tier
        self._llms = llms

    async def resolve(self, text: str) -> str:
        return self._resolved_tier

    def llm_for(self, tier: str):
        return self._llms[tier]

    @staticmethod
    def system_prompt_for(tier: str) -> str:
        return f"system-prompt-for-{tier}"


@pytest.mark.asyncio
async def test_budget_none_means_no_behavior_change():
    session = Session(tier="t1_standard")
    llm = _StubLLM(result=_ok_result("hi"))
    seen = []

    result = await handle_turn(session, llm, Transcript(text="hello"), seen.append, budget=None)

    assert result.text == "hi"
    assert seen == ["hi"]  # no budget notice prefixed


@pytest.mark.asyncio
async def test_soft_cap_prefixes_a_notice_but_still_uses_resolved_tier():
    session = Session(tier="t1_standard")
    t2_llm = _StubLLM(result=_ok_result("Complex reply."))
    router = _MultiTierStubRouter(resolved_tier="t2_medium", llms={"t2_medium": t2_llm})
    budget = BudgetGuard(soft_daily_usd=0.0, hard_daily_usd=1000.0)  # already over soft cap
    seen = []

    result = await handle_turn(
        session, t2_llm, Transcript(text="plan this out"), seen.append, router=router, budget=budget
    )

    assert result.text == "Complex reply."
    assert seen[0].startswith("Heads up")
    assert seen[1:] == ["Complex reply."]
    assert len(t2_llm.calls) == 1


@pytest.mark.asyncio
async def test_soft_cap_does_not_affect_t1_tiers():
    session = Session(tier="t1_standard")
    t1_llm = _StubLLM(result=_ok_result("Simple reply."))
    router = _MultiTierStubRouter(resolved_tier="t1_standard", llms={"t1_standard": t1_llm})
    budget = BudgetGuard(soft_daily_usd=0.0, hard_daily_usd=1000.0)
    seen = []

    await handle_turn(
        session, t1_llm, Transcript(text="hi"), seen.append, router=router, budget=budget
    )

    assert seen == ["Simple reply."]  # no soft-cap notice for a T1 tier


@pytest.mark.asyncio
async def test_hard_cap_forces_tier_down_to_t1_simple_with_router():
    session = Session(tier="t1_standard")
    t2_llm = _StubLLM(result=_ok_result("expensive reply"))
    t1_simple_llm = _StubLLM(result=_ok_result("cheap reply"))
    router = _MultiTierStubRouter(
        resolved_tier="t2_medium", llms={"t2_medium": t2_llm, "t1_simple": t1_simple_llm}
    )
    budget = BudgetGuard(soft_daily_usd=0.0, hard_daily_usd=0.0)  # already over hard cap
    seen = []

    result = await handle_turn(
        session, t2_llm, Transcript(text="plan this out"), seen.append, router=router, budget=budget
    )

    assert result.text == "cheap reply"
    assert seen[0].startswith("Running in reduced mode")
    assert t2_llm.calls == []  # never touched -- rerouted before the call
    assert len(t1_simple_llm.calls) == 1


@pytest.mark.asyncio
async def test_budget_records_spend_after_a_successful_turn():
    session = Session(tier="t1_standard")
    llm = _StubLLM(result=_ok_result("hi"))
    budget = BudgetGuard(soft_daily_usd=3.0, hard_daily_usd=6.0)

    await handle_turn(session, llm, Transcript(text="hello"), lambda _: None, budget=budget)

    assert budget.spent_usd >= 0.0  # _ok_result carries no usage, but record() must not raise


@pytest.mark.asyncio
async def test_soft_cap_decline_downgrades_tier_to_t1_simple():
    session = Session(tier="t1_standard")
    t2_llm = _StubLLM(result=_ok_result("expensive reply"))
    t1_simple_llm = _StubLLM(result=_ok_result("cheap reply"))
    router = _MultiTierStubRouter(
        resolved_tier="t2_medium", llms={"t2_medium": t2_llm, "t1_simple": t1_simple_llm}
    )
    budget = BudgetGuard(soft_daily_usd=0.0, hard_daily_usd=1000.0)
    seen = []

    result = await handle_turn(
        session,
        t2_llm,
        Transcript(text="plan this out"),
        seen.append,
        router=router,
        budget=budget,
        budget_confirm=lambda tier: False,
    )

    assert result.text == "cheap reply"
    assert seen[0].startswith("Declined")
    assert t2_llm.calls == []
    assert len(t1_simple_llm.calls) == 1


@pytest.mark.asyncio
async def test_soft_cap_decline_without_router_leaves_tier_unchanged():
    session = Session(tier="t1_standard")
    llm = _StubLLM(result=_ok_result("still using this tier"))
    llm.tier = "t2_medium"
    budget = BudgetGuard(soft_daily_usd=0.0, hard_daily_usd=1000.0)
    seen = []

    result = await handle_turn(
        session,
        llm,
        Transcript(text="plan this out"),
        seen.append,
        budget=budget,
        budget_confirm=lambda tier: False,
    )

    assert result.text == "still using this tier"
    assert seen[0].startswith("Declined")
    assert len(llm.calls) == 1  # no router to reroute to -- same tier still used


@pytest.mark.asyncio
async def test_budget_confirm_supports_async_callables():
    session = Session(tier="t1_standard")
    t2_llm = _StubLLM(result=_ok_result("expensive reply"))
    t1_simple_llm = _StubLLM(result=_ok_result("cheap reply"))
    router = _MultiTierStubRouter(
        resolved_tier="t2_medium", llms={"t2_medium": t2_llm, "t1_simple": t1_simple_llm}
    )
    budget = BudgetGuard(soft_daily_usd=0.0, hard_daily_usd=1000.0)

    async def decline(tier: str) -> bool:
        return False

    result = await handle_turn(
        session,
        t2_llm,
        Transcript(text="plan this out"),
        lambda _: None,
        router=router,
        budget=budget,
        budget_confirm=decline,
    )

    assert result.text == "cheap reply"
    assert len(t1_simple_llm.calls) == 1


class _SlowStubLLM:
    """Like _StubLLM, but sleeps before emitting the first token."""

    def __init__(self, result: TurnResult, delay_s: float):
        self._result = result
        self._delay_s = delay_s
        self.calls = []
        self.tier = "t1_standard"

    async def stream_reply(self, system_prompt, messages, on_text):
        self.calls.append((system_prompt, messages))
        await asyncio.sleep(self._delay_s)
        on_text(self._result.text)
        return self._result


@pytest.mark.asyncio
async def test_slow_first_token_speaks_filler_before_reply(monkeypatch):
    import jarvis.core.orchestrator as orchestrator_mod

    monkeypatch.setattr(orchestrator_mod, "_FILLER_DELAY_S", 0.01)
    session = Session(tier="t1_standard")
    llm = _SlowStubLLM(_ok_result("the real reply"), delay_s=0.05)
    seen = []
    spoken = []

    result = await handle_turn(
        session, llm, Transcript(text="hello"), seen.append, speak_filler=spoken.append
    )

    assert result.text == "the real reply"
    assert spoken == ["On it."]
    assert seen == ["the real reply"]
    # filler never lands in session history
    assert all("On it." not in m.text for m in session.history)


@pytest.mark.asyncio
async def test_fast_first_token_never_speaks_filler(monkeypatch):
    import jarvis.core.orchestrator as orchestrator_mod

    monkeypatch.setattr(orchestrator_mod, "_FILLER_DELAY_S", 1.5)
    session = Session(tier="t1_standard")
    llm = _StubLLM(result=_ok_result("fast reply"))
    seen = []
    spoken = []

    result = await handle_turn(
        session, llm, Transcript(text="hello"), seen.append, speak_filler=spoken.append
    )

    assert result.text == "fast reply"
    assert spoken == []


@pytest.mark.asyncio
async def test_no_speak_filler_param_is_backward_compatible():
    session = Session(tier="t1_standard")
    llm = _StubLLM(result=_ok_result("hi"))
    seen = []

    result = await handle_turn(session, llm, Transcript(text="hello"), seen.append)

    assert result.text == "hi"
    assert seen == ["hi"]


@pytest.mark.asyncio
async def test_t0_never_starts_a_filler_task(monkeypatch):
    import jarvis.core.orchestrator as orchestrator_mod
    from dataclasses import replace

    from jarvis.tools import registry

    monkeypatch.setattr(orchestrator_mod, "_FILLER_DELAY_S", 0.01)
    session = Session(tier="t1_standard")
    llm = _StubLLM(result=_ok_result())
    spoken = []

    async def fake_what_time(args):
        return "It's four o'clock PM."

    fake_tool = replace(registry._REGISTRY["what_time"], handler=fake_what_time)
    monkeypatch.setitem(registry._REGISTRY, "what_time", fake_tool)

    await handle_turn(
        session,
        llm,
        Transcript(text="what time is it"),
        lambda _: None,
        speak_filler=spoken.append,
    )

    await asyncio.sleep(0.05)  # give a filler task a chance to fire if one were wrongly started
    assert spoken == []


@pytest.mark.asyncio
async def test_offline_never_starts_a_filler_task(monkeypatch):
    import jarvis.core.orchestrator as orchestrator_mod

    monkeypatch.setattr(orchestrator_mod, "_FILLER_DELAY_S", 0.01)
    session = Session(tier="t1_standard")
    llm = _StubLLM(result=_ok_result())

    async def always_offline():
        return False

    offline = ConnectivityMonitor(probe=always_offline)
    spoken = []

    await handle_turn(
        session,
        llm,
        Transcript(text="hello"),
        lambda _: None,
        offline=offline,
        speak_filler=spoken.append,
    )

    await asyncio.sleep(0.05)
    assert spoken == []
