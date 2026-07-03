"""Multi-provider LLM layer. See ARCHITECTURE.md §8.

Provider choice per tier lives in config/settings.yaml (``models.<tier>``)
and is read by jarvis/llm/factory.py — swapping Anthropic for OpenRouter (or
vice versa) on a given tier is a config edit, never a code change.
"""
from __future__ import annotations

from .client import LLMClient
from .factory import build_provider
from .prompts import build_system_prompt
from .types import ChatMessage, TurnResult

__all__ = [
    "LLMClient",
    "TurnResult",
    "ChatMessage",
    "build_system_prompt",
    "build_provider",
]
