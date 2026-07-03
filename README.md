# Jarvis

Local-first personal voice assistant for an 8 GB MacBook. All heavy intelligence
runs through the Claude API; the machine only captures audio, transcribes, routes,
executes tools, and speaks. Full design in [ARCHITECTURE.md](ARCHITECTURE.md).

## Status

**Milestone 1 — hear & speak** (in place): microphone capture → voice-activity
segmentation → whisper.cpp transcription → macOS `say`. Fixed after live testing:
a mic-buffer overflow during transcription, and whisper's `[BLANK_AUDIO]`-style
silence markers leaking past the hallucination guard.

**Milestone 2 — real conversation** (in place): the echo is replaced with an
actual streaming reply from Sonnet 5, with conversation history carried across
turns. Single model only — no routing, tools, or memory yet (those are later
milestones per ARCHITECTURE.md §8). The layered system prompt (frozen identity
core + per-tier addendum, cached; dynamic datetime context in `messages`) is
implemented as designed in ARCHITECTURE.md §3.

Modules delivered: `jarvis/audio` (M1), `jarvis/speech` (M6), `jarvis/config`,
`jarvis/llm` (M3 minimal), `jarvis/core` (session + orchestrator loop).

**Not yet live-tested against the real API** — no Anthropic credentials are
configured in this dev environment. Everything below `--check` is verified by
a mocked test suite (49 tests, built from the real SDK's own event/message
types); run `--check` yourself once you have credentials to confirm the live
path.

## Setup

Use a virtualenv on Python 3.9+ (3.11+ recommended):

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

`sounddevice` needs PortAudio (`brew install portaudio`). The audio and speech
libraries import lazily, so tests and non-mic code run without it.

### Run the whisper server (once, stays resident)

```bash
# One-time build + model download — see scripts/start_whisper_server.sh header.
WHISPER_DIR=~/whisper.cpp ./scripts/start_whisper_server.sh
```

### Try Milestone 1

```bash
python -m scripts.milestone1 --check       # is the whisper server up?
python -m scripts.milestone1 --tts-only "Hello, I am Jarvis."   # speech only
python -m scripts.milestone1               # live: speak, pause, hear it echoed
```

### Try Milestone 2

Needs `ANTHROPIC_API_KEY` set (or an `ant auth login` profile active) in
addition to everything Milestone 1 needs:

```bash
python -m scripts.milestone2 --check       # one call: do credentials work?
python -m scripts.milestone2 --text        # type a conversation (no mic needed)
python -m scripts.milestone2               # live: speak, hear Sonnet 5 reply
```

## Tests

Hardware- and network-free (fake `say`, mocked HTTP, synthetic audio frames):

```bash
pytest
```

## Layout

```
config/settings.yaml     model IDs, tiers, audio/VAD/TTS params, budgets
jarvis/config.py         dotted-access settings loader
jarvis/audio/            M1: capture, vad, transcriber, pipeline (transcripts())
jarvis/speech/           M6: sentence-buffered TTS (Speaker)
jarvis/llm/              M3 minimal: streaming client, layered system prompts
jarvis/core/             session (history + context) + the listen/reply/speak loop
scripts/milestone1.py    the hear->transcribe->speak demo
scripts/milestone2.py    the real-conversation demo (--check / --text / live)
scripts/start_whisper_server.sh
tests/                   mirrors jarvis/
```

Next: T0 local command grammar + first tools (M4), then routing across tiers
(M2). See ARCHITECTURE.md §8.
