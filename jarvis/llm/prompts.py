"""System prompt assembly (ARCHITECTURE.md §3).

Two frozen layers live on disk as ``.md`` files and are combined into one
plain-text system prompt:

    Layer A (``layer_a.md``)  — identity core, IDENTICAL across every model
                                 tier, forever. Do not edit casually: once
                                 this text has been served in production, any
                                 byte change invalidates the prompt cache for
                                 every session using it (see
                                 shared/prompt-caching.md — prefix match).
                                 Caching itself is Anthropic-specific and is
                                 applied by AnthropicProvider, not here — this
                                 module only returns plain text so any
                                 provider can use it.
    Layer B (``layer_b_<tier>.md``) — small per-tier behavior addendum,
                                 named after the settings.yaml tier key (e.g.
                                 "t1_simple", "t1_standard"). Safe to evolve
                                 as capabilities (tools, routing) come online.

Layer A also carries the mid-task escalation contract (ARCHITECTURE.md §2):
a model replies with the literal ``<ESCALATE>`` token (plus a one-sentence
reason) when a task is beyond it. It lives in Layer A, not per-tier Layer B,
because the instruction is identical for every tier -- ARCHITECTURE.md's own
wording is "every tier's system prompt includes" the same sentence, so one
copy here avoids four Layer-B files drifting out of sync. See
jarvis/core/orchestrator.py's handle_turn for the retry logic that catches it.

Layer C (dynamic context — datetime, memory digest, recall) is intentionally
*not* handled here: it changes every turn and belongs in the conversation
messages, not the system prompt, so editing it never invalidates the Layer
A+B cache. See jarvis/core/session.py.
"""
from __future__ import annotations

from pathlib import Path

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def _read(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text(encoding="utf-8").strip()


def load_layer_a() -> str:
    """The frozen identity core, shared by every tier."""
    return _read("layer_a.md")


def load_layer_b(tier: str) -> str:
    """The per-tier addendum, e.g. ``load_layer_b("t1_standard")``."""
    return _read(f"layer_b_{tier}.md")


def build_system_prompt(tier: str) -> str:
    """Layer A + Layer B, combined into the plain-text system prompt.

    Provider-agnostic on purpose: AnthropicProvider wraps this in a cached
    content block; OpenRouterProvider sends it as a plain system-role
    message. Neither Anthropic-specific formatting nor caching belongs here.
    """
    return load_layer_a() + "\n\n" + load_layer_b(tier)
