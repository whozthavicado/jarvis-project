# Jarvis

Local-first personal voice assistant for an 8 GB MacBook. All heavy intelligence
runs through the Claude API; the machine only captures audio, transcribes, routes,
executes tools, and speaks. Full design in [ARCHITECTURE.md](ARCHITECTURE.md).

## Status

**Milestone 1 — hear & speak** (in place): microphone capture → voice-activity
segmentation → whisper.cpp transcription → macOS `say`. No LLM yet; the demo
echoes back what you said, proving the audio loop end to end.

Modules delivered: `jarvis/audio` (M1), `jarvis/speech` (M6), `jarvis/config`.

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
scripts/milestone1.py    the hear->transcribe->speak demo
scripts/start_whisper_server.sh
tests/                   mirrors jarvis/
```

Next: Milestone 2 wires a single Claude model (Sonnet 5) into a streaming voice
conversation. See ARCHITECTURE.md §8.
