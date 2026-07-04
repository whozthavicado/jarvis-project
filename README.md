# Z.E.R.O

Local-first personal voice assistant for an 8 GB MacBook. All heavy intelligence
runs through hosted model APIs; the machine only captures audio, transcribes,
routes, executes tools, and speaks. Full design in [ARCHITECTURE.md](ARCHITECTURE.md).

## Two modes

Z.E.R.O runs in one of two tier modes, switched by a single setting
(`TIER_MODE` env var, or `tier_mode:` in `config/settings.yaml`) — the
routing architecture, tools, memory, and voice pipeline are identical in
both; only which models answer changes.

| | **Free mode** (default) | **Pro mode** |
|---|---|---|
| `TIER_MODE` | `free` (or unset) | `anthropic` |
| Engines | OpenRouter free tier (primary) + NVIDIA NIM (fallback) | Claude models (Sonnet 5 / Opus 4.8 / Fable 5 / Haiku 4.5), plus OpenRouter free for the simple tier |
| Cost | **$0** — zero Anthropic calls, ever | Paid Anthropic API usage |
| Keys needed | `OPENROUTER_API_KEY` + `NVIDIA_API_KEY` | those two + `ANTHROPIC_API_KEY` |
| Caveats | Free catalogs rotate and rate-limit (~20 req/min, ~200 req/day per model) — that's why every tier has a second-catalog fallback | none beyond cost |

Copy `.env.example` to `.env`, fill in keys, and load it
(`set -a; source .env; set +a`). In free mode every tier falls back
OpenRouter → NVIDIA twin → smaller free tier, so worst case Z.E.R.O answers
with a smaller free model instead of not answering at all. Upgrading later
is exactly one change: `TIER_MODE=anthropic` plus an `ANTHROPIC_API_KEY` —
the Anthropic client code stays intact and dormant in free mode, never
deleted. (A Claude Pro subscription used to *develop* this project in Claude
Code is completely separate and is never called by the app.)

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

Needs credentials for whichever mode you're running (see **Two modes**
above), in addition to everything Milestone 1 needs.

```bash
# Free mode (default): verify each engine independently
python -m scripts.milestone2 --check                          # t1_standard via OpenRouter free
python -m scripts.milestone2 --check --tier t1_simple          # OpenRouter free (small model)
python -m scripts.milestone2 --check --tier t1_standard_nvidia # NVIDIA NIM fallback engine
python -m scripts.milestone2 --check --tier router             # the free classifier model

python -m scripts.milestone2 --text                            # type a conversation (no mic needed)
python -m scripts.milestone2                                    # live voice conversation

# Pro mode: same commands with the mode flipped
TIER_MODE=anthropic python -m scripts.milestone2 --check       # Sonnet 5: do credentials work?
```

## Tests

Hardware- and network-free (fake `say`, mocked HTTP, synthetic audio frames):

```bash
pytest
```

## Layout

```
config/settings.yaml     tier modes (free/anthropic model tables + fallback maps), audio/VAD/TTS params, budgets
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

Delivered since: T0 command grammar + tools (M4), per-turn tier routing
(M2), persistent memory (M5), the fallback ladder / circuit breaker /
budget guard (M3-full), and the free/anthropic tier-mode split. Next:
hardening (watchdogs, offline mode). See ARCHITECTURE.md §8.
