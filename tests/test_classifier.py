"""Stage 2 Haiku classifier tests — a fake Anthropic client, no network."""
import json
from types import SimpleNamespace

import pytest

from jarvis.config import get_settings
from jarvis.routing.classifier import classify


class _FakeTextBlock:
    def __init__(self, text: str):
        self.type = "text"
        self.text = text


class _FakeMessages:
    def __init__(self, payload: dict):
        self._payload = payload
        self.last_call_kwargs = None

    async def create(self, **kwargs):
        self.last_call_kwargs = kwargs
        return SimpleNamespace(content=[_FakeTextBlock(json.dumps(self._payload))])


class _FakeClient:
    def __init__(self, payload: dict):
        self.messages = _FakeMessages(payload)


@pytest.mark.asyncio
async def test_classify_maps_label_to_tier_key():
    fake = _FakeClient({"tier": "T2", "intent": "coding", "tools_needed": []})
    tier = await classify("some ambiguous transcript", get_settings(), client=fake)
    assert tier == "t2_medium"


@pytest.mark.asyncio
async def test_classify_uses_router_model_and_json_schema_output():
    fake = _FakeClient({"tier": "T1", "intent": "chit_chat", "tools_needed": []})
    await classify("hi there", get_settings(), client=fake)

    kwargs = fake.messages.last_call_kwargs
    assert kwargs["model"] == "claude-haiku-4-5"
    assert kwargs["output_config"]["format"]["type"] == "json_schema"
    assert kwargs["messages"] == [{"role": "user", "content": "hi there"}]


@pytest.mark.asyncio
async def test_all_four_labels_map_correctly():
    expected = {
        "T1": "t1_simple",
        "T1.5": "t1_standard",
        "T2": "t2_medium",
        "T3": "t3_complex",
    }
    for label, tier_key in expected.items():
        fake = _FakeClient({"tier": label, "intent": "x", "tools_needed": []})
        assert await classify("text", get_settings(), client=fake) == tier_key
