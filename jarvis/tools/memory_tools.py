"""remember/recall tools (ARCHITECTURE.md §4 write path, §6 M4/M5 contract).

``remember`` is how the model *proposes* a durable fact; the orchestrator
(via MemoryStore) is what actually persists it -- "Claude proposes; the
orchestrator persists, memory is never model-managed state" (ARCHITECTURE.md
§4). Deduping against existing memories and regenerating memory/MEMORY.md
for kind="core" facts both happen here, in the handler that runs the write,
not left to the model to police itself.

``recall`` lets the model pull additional context mid-turn if the automatic
FTS injection in Layer C (jarvis/core/session.py) didn't surface what it
needed -- same MemoryStore, same recall() call, just triggered explicitly.
"""
from __future__ import annotations

from typing import Any, Dict

from jarvis.memory import get_store, regenerate_digest
from jarvis.tools.registry import register
from jarvis.tools.types import ToolDef

_CORE_KIND = "core"


async def remember(args: Dict[str, Any]) -> str:
    kind = args["kind"]
    text = args["text"]
    store = get_store()
    added, _memory_id = store.add_memory(kind=kind, text=text)
    if kind == _CORE_KIND:
        regenerate_digest(store)
    if not added:
        return f"Already remembered: {text}"
    return f"Remembered ({kind}): {text}"


async def recall(args: Dict[str, Any]) -> str:
    query = args["query"]
    limit = int(args.get("limit", 3))
    store = get_store()
    snippets = store.recall(query, k=limit)
    if not snippets:
        return f"No memory matches for '{query}'."
    return "\n".join(f"- {snippet.text}" for snippet in snippets)


def _register_all() -> None:
    register(
        ToolDef(
            name="remember",
            description=(
                "Persist a durable fact about the user or a recurring task. "
                "kind='core' facts always stay in context; other kinds are "
                "recalled only when relevant to a later request."
            ),
            parameters={
                "kind": {"type": "string"},
                "text": {"type": "string"},
            },
            handler=remember,
        )
    )
    register(
        ToolDef(
            name="recall",
            description="Search past conversation turns and session summaries for relevant context.",
            parameters={
                "query": {"type": "string"},
                "limit": {"type": "integer"},
            },
            handler=recall,
        )
    )


_register_all()
