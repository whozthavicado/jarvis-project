"""File tools (ARCHITECTURE.md §6, M4): search_files, read_file, write_file.

search_files shells out to Spotify's index (``mdfind``) rather than walking
the filesystem -- instant on macOS, no directory traversal needed. read_file
is capped so a huge file can't blow the LLM's context or the spoken reply;
write_file is marked destructive since it can silently overwrite user data.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict

from jarvis.tools.registry import register
from jarvis.tools.types import ToolDef

_READ_CHAR_LIMIT = 20_000
_DEFAULT_SEARCH_LIMIT = 10


async def search_files(args: Dict[str, Any]) -> str:
    query = args["query"]
    limit = int(args.get("limit", _DEFAULT_SEARCH_LIMIT))
    proc = await asyncio.create_subprocess_exec(
        "mdfind", query,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(stderr.decode(errors="replace").strip() or "mdfind failed")
    paths = [p for p in stdout.decode(errors="replace").splitlines() if p][:limit]
    if not paths:
        return f"No files found matching '{query}'."
    return "\n".join(paths)


async def read_file(args: Dict[str, Any]) -> str:
    path = Path(args["path"]).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"No such file: {path}")
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) > _READ_CHAR_LIMIT:
        text = text[:_READ_CHAR_LIMIT] + f"\n... [truncated, {len(text)} chars total]"
    return text


async def write_file(args: Dict[str, Any]) -> str:
    path = Path(args["path"]).expanduser()
    content = args["content"]
    path.write_text(content, encoding="utf-8")
    return f"Wrote {len(content)} characters to {path}."


def _register_all() -> None:
    register(
        ToolDef(
            name="search_files",
            description="Search local files by name/content via Spotlight (mdfind).",
            parameters={
                "query": {"type": "string"},
                "limit": {"type": "integer"},
            },
            handler=search_files,
            timeout_s=15.0,
        )
    )
    register(
        ToolDef(
            name="read_file",
            description="Read a text file's contents (truncated if very large).",
            parameters={"path": {"type": "string"}},
            handler=read_file,
        )
    )
    register(
        ToolDef(
            name="write_file",
            description="Write text to a file, overwriting it if it exists.",
            parameters={
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            handler=write_file,
            is_destructive=True,
        )
    )


_register_all()
