"""Milestone 2 demo: a real streaming conversation, now multi-provider.

Unlike Milestone 1 (which echoed the transcript back), this asks Claude (or
another configured provider) and speaks the streamed reply, with
conversation history carried across turns.

There's no automatic routing between tiers yet (that's a later milestone),
so pick one for the whole session with --tier. See config/settings.yaml ->
models for what's configured; as of this milestone:

    t1_simple    OpenRouter free (Gemma 4 31B) -- casual/simple only
    t1_standard  Sonnet 5, paid Anthropic (default)

Run modes:

    python -m scripts.milestone2                       # live, Sonnet 5
    python -m scripts.milestone2 --tier t1_simple       # live, OpenRouter free
    python -m scripts.milestone2 --text                 # type instead of speaking
    python -m scripts.milestone2 --check                # verify credentials for --tier

Prereqs:
    * For t1_standard (and any Anthropic tier): ANTHROPIC_API_KEY set, or
      `ant auth login` run once.
    * For t1_simple: OPENROUTER_API_KEY set (https://openrouter.ai/keys).
    * Everything Milestone 1 needed: a running whisper.cpp server, PortAudio.
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from jarvis.audio.types import Transcript
from jarvis.config import get_settings
from jarvis.core import Session, converse, handle_turn
from jarvis.llm import LLMClient, build_provider
from jarvis.llm.types import ChatMessage
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


async def run_live(tier: str) -> None:
    print(f"Z.E.R.O M2: listening on tier={tier!r}. Speak, then pause. Ctrl-C to stop.\n")
    await converse(tier=tier, on_turn=_print_turn)


async def run_text(tier: str) -> None:
    print(f"Z.E.R.O M2 (text mode, tier={tier!r}). Type a message, Ctrl-C or empty line to stop.\n")
    settings = get_settings()
    session = Session(tier=tier)
    llm = LLMClient(settings, tier=tier)
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


async def run_check(tier: str) -> None:
    """Confirm the configured provider for *tier* can actually authenticate and reply.

    Talks to the tier's provider directly via build_provider(), bypassing
    LLMClient's same-turn fallback — otherwise a failure here could actually
    be reporting the *fallback* tier's error (e.g. checking t1_simple could
    silently report an Anthropic auth failure instead of an OpenRouter one),
    which defeats the point of a per-tier diagnostic.
    """
    settings = get_settings()
    provider = build_provider(settings, tier)
    chunks = []
    try:
        result = await provider.stream_reply(
            system_prompt="Reply with exactly: ok",
            messages=[ChatMessage(role="user", text="ping")],
            on_text=chunks.append,
        )
    except Exception as exc:  # noqa: BLE001 - this IS the diagnostic
        print(f"FAILED (tier={tier!r}): {type(exc).__name__}: {exc}")
        sys.exit(1)
    print(f"OK (tier={tier!r}) — model={result.model} stop_reason={result.stop_reason}")
    print(f"reply: {result.text!r}")
    sys.exit(0)


def main() -> None:
    parser = argparse.ArgumentParser(description="Z.E.R.O Milestone 2 demo")
    parser.add_argument("--text", action="store_true", help="type instead of speaking")
    parser.add_argument(
        "--check", action="store_true", help="verify the tier's provider credentials with one call"
    )
    parser.add_argument(
        "--tier",
        default="t1_standard",
        help="which configured tier to use (see config/settings.yaml -> models); "
        "e.g. t1_simple (OpenRouter free) or t1_standard (Sonnet 5, default)",
    )
    args = parser.parse_args()

    try:
        if args.check:
            asyncio.run(run_check(args.tier))
        elif args.text:
            asyncio.run(run_text(args.tier))
        else:
            asyncio.run(run_live(args.tier))
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
