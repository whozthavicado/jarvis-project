"""Milestone 1 demo: prove the hear -> transcribe -> speak loop.

There is no LLM in this milestone. Z.E.R.O listens, transcribes what you said,
prints it, and echoes it back through TTS. This exercises M1 (audio) + M6
(speech) end to end.

Run modes:

    python -m scripts.milestone1              # live: mic -> whisper -> say
    python -m scripts.milestone1 --tts-only   # speak a line (no mic/whisper)
    python -m scripts.milestone1 --check       # health-check whisper server

Prereqs for live mode:
    * A running whisper.cpp server (see scripts/start_whisper_server.sh).
    * PortAudio + the `sounddevice` package (pip install -e .).
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from jarvis.audio import transcripts
from jarvis.audio.transcriber import WhisperClient
from jarvis.config import get_settings
from jarvis.speech import Speaker


async def run_live() -> None:
    settings = get_settings()
    print("Z.E.R.O M1: listening. Speak, then pause. Ctrl-C to stop.\n")
    async with Speaker(settings) as speaker:
        async for t in transcripts(settings):
            print(f"  heard ({t.duration_ms} ms): {t.text!r}")
            speaker.feed(f"You said: {t.text}. ")
            await speaker.flush()


async def run_tts_only(text: str) -> None:
    async with Speaker() as speaker:
        speaker.feed(text)
        await speaker.flush()


async def run_check() -> None:
    settings = get_settings()
    async with WhisperClient(settings) as w:
        ok = await w.health()
    url = settings.whisper.server_url
    print(f"whisper server {url}: {'OK' if ok else 'UNREACHABLE'}")
    sys.exit(0 if ok else 1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Z.E.R.O Milestone 1 demo")
    parser.add_argument("--tts-only", metavar="TEXT", help="speak TEXT and exit")
    parser.add_argument(
        "--check", action="store_true", help="health-check the whisper server"
    )
    args = parser.parse_args()

    try:
        if args.check:
            asyncio.run(run_check())
        elif args.tts_only is not None:
            asyncio.run(run_tts_only(args.tts_only))
        else:
            asyncio.run(run_live())
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
