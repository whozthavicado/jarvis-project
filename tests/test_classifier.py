"""Stage 2 classifier tests — a stub LLMClient, no vendor SDK, no network.

Since the free-mode restructure the classifier is provider-agnostic: it
speaks to whatever backs the "router" tier through the LLMClient interface
and digs its JSON out of the reply defensively (prompt-enforced JSON, not
API-schema-enforced), so these tests exercise messy real-world reply shapes:
clean JSON, code fences, surrounding prose, and think tags.
"""
import json

import pytest

from jarvis.config import get_settings
from jarvis.llm.types import ChatMessage, TurnResult
from jarvis.routing.classifier import ROUTER_PROMPT, classify


class _StubLLM:
    """Stands in for LLMClient: returns a fixed reply text, records the call."""

    def __init__(self, reply_text: str):
        self._reply_text = reply_text
        self.calls = []

    async def stream_reply(self, system_prompt, messages, on_text):
        self.calls.append((system_prompt, messages))
        return TurnResult(text=self._reply_text, model="stub-router", stop_reason="stop")


def _reply(tier: str) -> str:
    return json.dumps({"tier": tier, "intent": "x", "tools_needed": []})


@pytest.mark.asyncio
async def test_classify_maps_label_to_tier_key():
    llm = _StubLLM(_reply("T2"))
    tier = await classify("some ambiguous transcript", get_settings(), llm=llm)
    assert tier == "t2_medium"


@pytest.mark.asyncio
async def test_classify_sends_router_prompt_and_user_text():
    llm = _StubLLM(_reply("T1"))
    await classify("hi there", get_settings(), llm=llm)

    system_prompt, messages = llm.calls[0]
    assert system_prompt == ROUTER_PROMPT
    assert messages == [ChatMessage(role="user", text="hi there")]


@pytest.mark.asyncio
async def test_all_four_labels_map_correctly():
    expected = {
        "T1": "t1_simple",
        "T1.5": "t1_standard",
        "T2": "t2_medium",
        "T3": "t3_complex",
    }
    for label, tier_key in expected.items():
        assert await classify("text", get_settings(), llm=_StubLLM(_reply(label))) == tier_key


@pytest.mark.asyncio
async def test_lowercase_label_is_tolerated():
    llm = _StubLLM(json.dumps({"tier": "t1.5", "intent": "x", "tools_needed": []}))
    assert await classify("text", get_settings(), llm=llm) == "t1_standard"


@pytest.mark.asyncio
async def test_json_wrapped_in_code_fence_and_prose_still_parses():
    reply = 'Sure! Here is the classification:\n```json\n{"tier": "T2", "intent": "coding", "tools_needed": []}\n```\nHope that helps.'
    assert await classify("text", get_settings(), llm=_StubLLM(reply)) == "t2_medium"


@pytest.mark.asyncio
async def test_think_tags_before_json_are_ignored():
    reply = '<think>The user wants code, that is T2 territory.</think>{"tier": "T2", "intent": "coding", "tools_needed": []}'
    assert await classify("text", get_settings(), llm=_StubLLM(reply)) == "t2_medium"


@pytest.mark.asyncio
async def test_unparseable_reply_raises_for_caller_fail_soft():
    with pytest.raises(ValueError):
        await classify("text", get_settings(), llm=_StubLLM("I think tier two is best!"))


@pytest.mark.asyncio
async def test_unknown_label_raises_for_caller_fail_soft():
    with pytest.raises(KeyError):
        await classify("text", get_settings(), llm=_StubLLM(_reply("T9")))
