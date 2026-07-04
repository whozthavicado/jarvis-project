"""Router tests: Stage 1/2 combination, LLMClient caching, fail-soft fallback."""
import pytest

from jarvis.config import get_settings
from jarvis.llm.client import LLMClient
from jarvis.routing.router import Router


@pytest.mark.asyncio
async def test_heuristic_match_short_circuits_the_classifier(monkeypatch):
    router = Router(get_settings())

    async def _boom(*args, **kwargs):
        raise AssertionError("classifier should not be called when heuristics resolve it")

    monkeypatch.setattr("jarvis.routing.router.classifier.classify", _boom)

    tier = await router.resolve("what's the capital of France")
    assert tier == "t1_simple"


@pytest.mark.asyncio
async def test_ambiguous_text_falls_through_to_classifier(monkeypatch):
    router = Router(get_settings())
    seen = []

    async def _fake_classify(text, settings, llm=None):
        seen.append(text)
        assert llm is router.llm_for("router")  # shares the cached router-tier client
        return "t2_medium"

    monkeypatch.setattr("jarvis.routing.router.classifier.classify", _fake_classify)

    text = " ".join(["word"] * 40)  # ambiguous per heuristics
    tier = await router.resolve(text)
    assert tier == "t2_medium"
    assert seen == [text]


@pytest.mark.asyncio
async def test_classifier_failure_falls_back_to_t1_standard(monkeypatch):
    router = Router(get_settings())

    async def _boom(*args, **kwargs):
        raise RuntimeError("no credentials")

    monkeypatch.setattr("jarvis.routing.router.classifier.classify", _boom)

    text = " ".join(["word"] * 40)
    tier = await router.resolve(text)
    assert tier == "t1_standard"


def test_llm_for_caches_clients_per_tier():
    router = Router(get_settings())
    a = router.llm_for("t1_standard")
    b = router.llm_for("t1_standard")
    c = router.llm_for("t1_simple")

    assert a is b
    assert a is not c
    assert isinstance(a, LLMClient)


def test_system_prompt_for_differs_by_tier():
    standard = Router.system_prompt_for("t1_standard")
    simple = Router.system_prompt_for("t1_simple")
    assert standard != simple
    assert "Z.E.R.O" in standard
