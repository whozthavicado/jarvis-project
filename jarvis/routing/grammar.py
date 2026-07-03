"""T0 local command grammar (ARCHITECTURE.md §2, RULE 0).

Declarative and code-free by design: ``config/grammar.yaml`` lists regex
patterns per command, this module only normalizes the transcript and matches
it -- no API call, no LLM, sub-millisecond. A match becomes a ``ToolCall``
the orchestrator hands straight to ``jarvis.tools.execute``.
"""
from __future__ import annotations

import functools
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from jarvis.tools.types import ToolCall

_DEFAULT_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "grammar.yaml"

_INT_ARGS = {"minutes", "n"}


@dataclass(frozen=True)
class GrammarCommand:
    id: str
    tool: str
    patterns: List["re.Pattern[str]"]
    args: Dict[str, Any]


def load_grammar(path: "str | Path | None" = None) -> List[GrammarCommand]:
    p = Path(path) if path is not None else _DEFAULT_PATH
    with p.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    commands = []
    for entry in data.get("commands", []):
        patterns = [re.compile(pat, re.IGNORECASE) for pat in entry["patterns"]]
        commands.append(
            GrammarCommand(
                id=entry["id"],
                tool=entry["tool"],
                patterns=patterns,
                args=dict(entry.get("args", {})),
            )
        )
    return commands


@functools.lru_cache(maxsize=1)
def _default_commands() -> List[GrammarCommand]:
    return load_grammar()


def _normalize(text: str) -> str:
    return text.strip().rstrip(".!").strip().lower()


def match(text: str, commands: "List[GrammarCommand] | None" = None) -> Optional[ToolCall]:
    """Match *text* against T0 grammar. Returns a ToolCall, or None if no
    command matched (the caller should fall through to the LLM path)."""
    cmds = commands if commands is not None else _default_commands()
    normalized = _normalize(text)
    if not normalized:
        return None

    for cmd in cmds:
        for pattern in cmd.patterns:
            m = pattern.match(normalized)
            if m is None:
                continue
            call_args: Dict[str, Any] = dict(cmd.args)
            for key, value in m.groupdict().items():
                if value is None:
                    continue
                call_args[key] = int(value) if key in _INT_ARGS else value
            return ToolCall(name=cmd.tool, args=call_args)
    return None
