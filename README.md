# Z.E.R.O

Local-first personal voice assistant for an 8 GB MacBook. All heavy intelligence
runs through the Claude API; the machine only captures audio, transcribes, routes,
executes tools, and speaks. Full design in [ARCHITECTURE.md](ARCHITECTURE.md).

## Status

**Milestone 1 — hear & speak** (in place): microphone capture → voice-activity
segmentation → whisper.cpp transcription → macOS `say`. Fixed after live testing:
a mic-buffer overflow during transcription, and whisper's `[BLANK_AUDIO]`-style
silence markers leaking past the hallucination guard.

**Milestone 2 — real conversation** (in place): the echo is replaced with an
actual streaming reply, with conversation history carried across turns. The
layered system prompt (frozen identity core + per-tier addendum; dynamic
datetime context in the conversation, not the system prompt) is implemented
as designed in ARCHITECTURE.md §3.

**Multi-provider (in place):** `jarvis/llm` now supports more than one model
backend behind the same interface. After researching OpenRouter's free tier
(quality, rate limits, catalog stability — see the provider-strategy decision
from 2026-07-02), the **simple tier (`t1_simple`) routes to OpenRouter's free
Gemma 4 31B** ($0 marginal cost), while the **standard/medium tier
(`t1_standard`) stays on Sonnet 5** (paid) — free-model tool-calling
reliability is untested and the medium tier is cheap anyway. Complex-tier
work (Opus/Fable) stays paid Anthropic as originally planned; those tiers
aren't wired up yet regardless (later milestones). Switching a tier's
provider or model is a `config/settings.yaml` edit (`models.<tier>`), never a
code change — see `jarvis/llm/factory.py`. Because free-tier model catalogs
rotate with little notice (verified live: some entries expire within days),
`t1_simple` has an automatic same-turn fallback to `t1_standard` — but only
when nothing has been spoken yet, so a mid-stream failure never produces
garbled double-speech (see `jarvis/llm/client.py`).

Modules delivered: `jarvis/audio` (M1), `jarvis/speech` (M6), `jarvis/config`,
`jarvis/llm` (M3 minimal, multi-provider), `jarvis/core` (session + orchestrator
loop).

**Not yet live-tested against a real API** — no Anthropic *or* OpenRouter
credentials are configured in this dev environment. Everything is verified by
a test suite (69 tests) built from real wire formats: Anthropic's own SDK
types for the Anthropic provider, and `httpx.MockTransport` (httpx's own
supported no-network testing mechanism) for the OpenRouter provider's SSE
streaming. Run `--check --tier <tier>` yourself once you have credentials —
it talks to that tier's provider directly, bypassing the fallback, so a
failure always tells you about the tier you asked about.

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
python -m scripts.milestone1 --tts-only "Hello, I am Z.E.R.O."   # speech only
python -m scripts.milestone1               # live: speak, pause, hear it echoed
```

### Try Milestone 2

Needs credentials for whichever tier's provider you're using, in addition to
everything Milestone 1 needs:
- `t1_standard` (Sonnet 5, default): `ANTHROPIC_API_KEY` set, or an
  `ant auth login` profile active.
- `t1_simple` (OpenRouter free): `OPENROUTER_API_KEY` set — get one at
  [openrouter.ai/keys](https://openrouter.ai/keys).

```bash
python -m scripts.milestone2 --check                    # Sonnet 5: do credentials work?
python -m scripts.milestone2 --check --tier t1_simple    # OpenRouter free: do credentials work?
python -m scripts.milestone2 --text                      # type a conversation (no mic needed)
python -m scripts.milestone2 --tier t1_simple            # live, on the free tier
python -m scripts.milestone2                              # live, on Sonnet 5 (default)
```

## Tests

Hardware- and network-free (fake `say`, mocked HTTP, synthetic audio frames):

```bash
pytest
```

## Layout

```
config/settings.yaml     tiers (provider + model + fallback), audio/VAD/TTS params, budgets
jarvis/config.py         dotted-access settings loader
jarvis/audio/             M1: capture, vad, transcriber, pipeline (transcripts())
jarvis/speech/            M6: sentence-buffered TTS (Speaker)
jarvis/llm/client.py     tier-aware facade: picks a provider, streams, same-turn fallback
jarvis/llm/factory.py    tier -> Provider instance (the only place provider choice is decided)
jarvis/llm/providers/    AnthropicProvider, OpenRouterProvider -- same interface, swappable
jarvis/llm/prompts.py    layered system prompt (Layer A frozen + Layer B per-tier)
jarvis/core/              session (history + context) + the listen/reply/speak loop
scripts/milestone1.py    the hear->transcribe->speak demo
scripts/milestone2.py    the real-conversation demo (--check / --text / live / --tier)
scripts/start_whisper_server.sh
tests/                    mirrors jarvis/
```

Next: T0 local command grammar + first tools (M4), then routing across tiers
(M2). See ARCHITECTURE.md §8.
