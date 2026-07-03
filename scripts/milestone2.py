"""Milestone 2 demo: a real streaming conversation with Sonnet 5.

Unlike Milestone 1 (which echoed the transcript back), this asks Claude and
speaks the streamed reply, with conversation history carried across turns.

Run modes:

    python -m scripts.milestone2              # live: mic -> Sonnet 5 -> say
    python -m scripts.milestone2 --text        # type instead of speaking
    python -m scripts.milestone2 --check       # verify API credentials work

Prereqs:
    * ANTHROPIC_API_KEY set, or `ant auth login` run once (see the claude-api
      skill's Authentication section — no key needed if a profile is active).
    * Everything Milestone 1 needed: a running whisper.cpp server, PortAudio.
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from jarvis.audio.types import Transcript
from jarvis.config import get_settings
from jarvis.core import Session, converse, handle_turn
from jarvis.llm import LLMClient
from jarvis.speech import Speaker


def _print_turn(t: Transcript, result) -> None:
    print(f"  you: {t.text}")
    if result is not None and result.text:
        print(f"  jarvis: {result.text}")
        usage = (
            f"    [{result.model} | in={result.input_tokens} out={result.output_tokens}"
            f" cache_read={result.cache_read_tokens} cache_write={result.cache_creation_tokens}]"
        )
        print(usage)


async def run_live() -> None:
    print("Jarvis M2: listening. Speak, then pause. Ctrl-C to stop.\n")
    await converse(on_turn=_print_turn)


async def run_text() -> None:
    print("Jarvis M2 (text mode). Type a message, Ctrl-C or empty line to stop.\n")
    settings = get_settings()
    session = Session(tier="sonnet")
    llm = LLMClient(settings)
    async with Speaker(settings) as speaker:
        while True:
            try:
                line = input("you: ").strip()
            except EOFError:
                break
            if not line:
                break
            t = Transcript(text=line)
            printed = []
            result = await handle_turn(session, llm, t, lambda chunk: printed.append(chunk))
            reply = "".join(printed)
            print(f"jarvis: {reply}")
            speaker.feed(reply)
            await speaker.flush()
            if result is None:
                print("  (that turn failed — see the fallback line above)")


async def run_check() -> None:
    """Confirm the Anthropic client can actually authenticate and reply."""
    settings = get_settings()
    llm = LLMClient(settings)
    chunks = []
    try:
        result = await llm.stream_reply(
            system_blocks=[{"type": "text", "text": "Reply with exactly: ok"}],
            messages=[{"role": "user", "content": "ping"}],
            on_text=chunks.append,
        )
    except Exception as exc:  # noqa: BLE001 - this IS the diagnostic
        print(f"FAILED: {type(exc).__name__}: {exc}")
        sys.exit(1)
    print(f"OK — model={result.model} stop_reason={result.stop_reason}")
    print(f"reply: {result.text!r}")
    sys.exit(0)


def main() -> None:
    parser = argparse.ArgumentParser(description="Jarvis Milestone 2 demo")
    parser.add_argument("--text", action="store_true", help="type instead of speaking")
    parser.add_argument(
        "--check", action="store_true", help="verify API credentials with one call"
    )
    args = parser.parse_args()

    try:
        if args.check:
            asyncio.run(run_check())
        elif args.text:
            asyncio.run(run_text())
        else:
            asyncio.run(run_live())
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
