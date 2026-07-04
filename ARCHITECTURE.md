# Z.E.R.O — Personal Voice Assistant Architecture

**Target hardware:** MacBook, 8 GB RAM total (~4–5 GB realistically free for us)
**Design principle:** everything heavy runs in the cloud; the local machine only does
audio capture, transcription, orchestration, tool execution, and TTS.

---

## 0. Key technology decisions (and why)

| Decision | Choice | Why |
|---|---|---|
| Orchestrator | **Python + asyncio** (not n8n, not LangGraph) | n8n runs a full Node server + editor UI (~500 MB–1 GB) — unaffordable on 8 GB. LangGraph adds abstraction we don't need for one linear pipeline with a router. Plain asyncio + the `anthropic` SDK is ~100 MB and fully debuggable. |
| STT | **whisper.cpp**, `base` model, quantized (q5_1), Metal | `base-q5_1` ≈ 60 MB on disk, ~200–300 MB peak RAM with Metal. `tiny` (~40 MB) as fallback if RAM pressure is observed. Run as a persistent `whisper-server` process (HTTP) so the model loads once. |
| VAD | **silero-vad** (ONNX, ~2 MB) or `webrtcvad` | Gate the mic so Whisper only runs on actual speech. Essential for battery + CPU. |
| TTS | **macOS `say`** (or `AVSpeechSynthesizer` via pyobjc later) | Native, zero extra RAM, streams instantly. |
| LLM access | **Anthropic Python SDK**, streaming, prompt caching | All intelligence via API. No local LLM — there is no RAM for one. |
| Storage | **SQLite** (stdlib) + plain Markdown files | No vector DB, no embedding model (would eat 500 MB+ RAM). SQLite FTS5 gives keyword recall for free. |

### RAM budget (steady state)

```
whisper-server (base-q5_1, Metal)   ~250–350 MB
Python orchestrator + SDK           ~100–150 MB
silero-vad + audio buffers          ~ 50 MB
SQLite + misc                       ~ 30 MB
------------------------------------------------
Total Z.E.R.O footprint              ~450–600 MB   ✅ well under budget
```

---

## 1. System architecture

```
┌────────────────────────────── LOCAL (macOS, ~600 MB) ──────────────────────────────┐
│                                                                                     │
│  ┌──────────┐   PCM    ┌─────────┐  speech   ┌──────────────────┐                   │
│  │  Mic     │────────▶│  VAD     │─────────▶│  whisper-server   │                   │
│  │  capture │  16 kHz  │ (silero) │  chunks   │  (base-q5_1)     │                   │
│  └──────────┘          └─────────┘           └────────┬─────────┘                   │
│                                                       │ transcript (text)          │
│                                                       ▼                            │
│  ┌───────────────────────────── ORCHESTRATOR (Python asyncio) ─────────────────┐    │
│  │                                                                             │    │
│  │   ┌────────────┐    ┌──────────────┐    ┌───────────────────────────────┐   │    │
│  │   │ Session /  │──▶│  ROUTER       │──▶│  LLM CLIENT                    │   │    │
│  │   │ context    │    │  T0 grammar   │    │  tier → model, streaming,     │───┼──▶ Anthropic API
│  │   │ builder    │    │  T1–T4 rules  │    │  caching, fallback ladder     │   │    │  (Haiku 4.5 /
│  │   └─────┬──────┘    │  + Haiku      │    └──────────────┬────────────────┘   │    │   Sonnet 5 /
│  │         │           │  classifier   │                   │ tool_use blocks   │    │   Opus 4.8 /
│  │         │           └──────┬───────┘                    ▼                   │    │   Fable 5)
│  │         │                  │ T0: skip LLM   ┌────────────────────────────┐  │    │
│  │         │                  └──────────────▶│  TOOL EXECUTOR              │  │    │
│  │         ▼                                  │  osascript / Shortcuts /    │──┼───▶ macOS + external APIs
│  │   ┌────────────┐                           │  mdfind / shell / HTTP      │  │    │
│  │   │ MEMORY     │◀── remember/recall tool ──│  (approval gate for        │  │    │
│  │   │ SQLite+FTS │                           │   destructive actions)      │  │    │
│  │   │ + MEMORY.md│                           └────────────────────────────┘  │    │
│  │   └────────────┘                                                           │    │
│  └──────────────────────────────────────┬──────────────────────────────────────┘    │
│                                         │ response text (sentence stream)          │
│                                         ▼                                          │
│                                  ┌────────────┐                                    │
│                                  │  TTS       │  macOS `say`                       │
│                                  │  (speaks   │  (sentence-by-sentence as          │
│                                  │  streamed) │   tokens stream in)                │
│                                  └────────────┘                                    │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

**Where each component lives:**

| Component | Process | Lifetime |
|---|---|---|
| whisper-server | separate process, launched at startup | persistent (model loaded once) |
| VAD + mic capture | orchestrator thread/task | persistent |
| Orchestrator, router, LLM client, tool executor, memory | one Python process | persistent |
| TTS | `say` subprocess per utterance | ephemeral |
| All Claude models | Anthropic cloud | per-request |

**Data flow for one turn:**
1. VAD detects speech end → audio chunk → whisper-server → transcript.
2. Session builder assembles context: identity prompt + memory digest + recent turns.
3. Router assigns a tier (T0–T4). T0 executes locally with **no API call**.
4. LLM client streams the request to the assigned model with the tool set.
5. Tool-use loop: execute tool calls locally, feed results back, repeat until `end_turn`.
6. Response text streams to TTS **sentence by sentence** (speak while still generating).
7. Turn is logged to SQLite; memory writes (if any) persisted.

---

## 2. Routing & intent classification

### Model tiers

| Tier | Handles | Model | Model ID | Price in/out per MTok |
|---|---|---|---|---|
| **T0** | Direct device commands — no LLM at all | *(none — local grammar)* | — | $0 |
| **T1 — simple** | One-fact answers, short rewrites, casual chat, classification, a *single* obvious tool call | Haiku 4.5 | `claude-haiku-4-5` | $1 / $5 |
| **T1.5 — standard** | Multi-step tool use, summarizing a document, drafting an email, most day-to-day agentic work | Sonnet 5 | `claude-sonnet-5` | $3 / $15 (intro $2 / $10 through 2026-08-31) |
| **T2 — medium** | Multi-step reasoning, coding, planning, research spanning many tool calls | Opus 4.8 | `claude-opus-4-8` | $5 / $25 |
| **T3 — complex** | Hardest long-horizon work; only on explicit request or confirmed escalation | Fable 5 | `claude-fable-5` | $10 / $50 |

> Fable 5 caveats (design-relevant): thinking is always on (omit the `thinking` param — an explicit config 400s), safety classifiers can return `stop_reason: "refusal"`, it requires 30-day data retention on the org, and single turns can run minutes. Always send it with the server-side `fallbacks` parameter targeting Opus 4.8 (see §5).

### Tier modes (added 2026-07-03)

The table above is the **anthropic** (paid) mode. Production default is
**free** mode: the same tier keys repointed at OpenRouter free-tier models
(primary) and NVIDIA NIM (a fallback twin per tier), $0, zero Anthropic
calls. One switch flips modes — the `TIER_MODE` env var or `tier_mode:` in
settings.yaml; the model tables and fallback maps live in
`config/settings.yaml` under `models.<mode>` / `fallbacks.<mode>`. Routing
logic (T0 grammar, RULES 1-5, the Stage-2 classifier, escalation) is
mode-agnostic. Two free-mode consequences: the Stage-2 classifier uses
prompt-enforced JSON plus defensive extraction instead of Anthropic's
schema-constrained `output_config` (see `jarvis/llm/parsing.py`), and open
reasoning models' inline `<think>` blocks are stream-filtered before TTS.

### Stage 1 — local heuristics (free, <1 ms)

Run these rules in order; first match wins:

```
RULE 0  (T0)  Transcript matches command grammar:
              "open <app>", "close <app>", "volume up/down/mute",
              "play/pause", "what time is it", "set a timer for N minutes",
              "lock screen", "brightness up/down"
              → execute directly via osascript/Shortcuts. NO API CALL.

RULE 1  (T3)  Explicit escalation phrases:
              "think hard", "deep dive", "this is important", "use your best model"
              → Fable 5

RULE 2  (T2)  Strong complexity signals (any 1):
              - contains code or asks to write/debug code
              - multi-step planning verbs: "plan", "design", "compare and decide",
                "research X and then Y"
              - transcript > 80 words
              → Opus 4.8

RULE 3  (T1.5) Tool-work signals:
              - needs ≥2 tool calls (file search + read, web fetch + summarize)
              - "summarize", "draft", "find and ...", "email", "calendar"
              → Sonnet 5

RULE 4  (T1)  Everything short and self-contained:
              - ≤25 words, question form, no tool verbs, chit-chat
              → Haiku 4.5

RULE 5  Ambiguous → Stage 2.
```

### Stage 2 — Haiku classifier (~$0.0005/call, ~300 ms)

Only when heuristics can't decide. One Haiku call with **structured output** so parsing can't fail:

```python
resp = client.messages.create(
    model="claude-haiku-4-5",
    max_tokens=200,
    system=ROUTER_PROMPT,          # short rubric describing the tiers
    messages=[{"role": "user", "content": transcript}],
    output_config={"format": {"type": "json_schema", "schema": {
        "type": "object",
        "properties": {
            "tier": {"type": "string", "enum": ["T1", "T1.5", "T2", "T3"]},
            "intent": {"type": "string"},
            "tools_needed": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["tier", "intent", "tools_needed"],
        "additionalProperties": False,
    }}},
)
```

### Escalation & de-escalation

- **Mid-task escalation:** every tier's system prompt includes: *"If this task is beyond what you can do well, reply only with the token `<ESCALATE>` and one sentence explaining why."* The orchestrator catches it and re-runs the turn one tier up (max one escalation per turn; T2→T3 requires the user to confirm because of cost).
- **Failure escalation:** if a T1/T1.5 answer errors twice in the tool loop, retry the whole turn at the next tier.
- **Never route to Fable silently.** T3 is entered only via RULE 1, classifier + user confirmation, or explicit user request. Z.E.R.O says "This one's hard — engaging full power, give me a couple of minutes" so latency is expected.

---

## 3. System prompt scheme

**Goal: one personality, four models, maximum cache hits.** The prompt is layered; layers A+B form the *frozen prefix* (cached), layer C is dynamic and lives in `messages` where it can't invalidate the cache.

```
render order (this order matters for caching):
[ tools (deterministic, sorted by name) ]
[ Layer A: identity core — identical text for all tiers ]
[ Layer B: tier addendum — per-model behavior tuning ]   ← cache_control here
--------------------------------------------------------  (cache breakpoint)
[ Layer C: memory digest + datetime — first user turn or system-role message ]
[ conversation history ]
```

### Layer A — identity core (~600 tokens, byte-frozen)

```
You are Z.E.R.O, a personal voice assistant running on <user>'s MacBook.

VOICE OUTPUT RULES (critical — your text is spoken aloud by TTS):
- Answer in 1–3 short sentences unless the user asked for detail.
- No markdown, no bullet lists, no code blocks in the spoken reply.
  If the output is code or a document, save it with a tool and say where it is.
- Numbers and units in speakable form ("three thirty PM", not "15:30").
- Lead with the answer; explanation only if asked.

PERSONALITY:
- Calm, dry, lightly witty. Competent butler, not a cheerleader.
- Address the user by name occasionally. Never say "As an AI".
- If something failed, say what failed and what you'll try instead.

TOOLS:
- Prefer tools over guessing. Never claim you did something without a
  successful tool result to point to.
- Destructive actions (delete, send, purchase, system settings) always
  go through their dedicated tool so the user gets a confirmation prompt.

MEMORY:
- You have persistent memory. When you learn a durable fact about the user
  (preference, name, recurring task), call the `remember` tool.
- A digest of stored memory appears in the first message of each session.
```

### Layer B — tier addenda (small, per model)

| Tier | Addendum (essence) | API params |
|---|---|---|
| Haiku 4.5 | "Answer directly and briefly. If the task needs multiple steps or planning, reply `<ESCALATE>`." | no `thinking`, `max_tokens=1000` |
| Sonnet 5 | "You handle everyday multi-step tasks. Execute tool chains end-to-end without narrating each step. Reply `<ESCALATE>` only if genuine deep reasoning is required." | `thinking={"type":"adaptive"}` (default anyway), `output_config={"effort":"medium"}`, `max_tokens=8000` |
| Opus 4.8 | "You handle complex reasoning and coding. Plan briefly, act, verify. For minor choices pick a reasonable option and note it rather than asking." | `thinking={"type":"adaptive"}`, `output_config={"effort":"high"}`, streaming, `max_tokens=16000` |
| Fable 5 | "Hardest tasks only. Full task spec is given up front; work autonomously. Before reporting progress, audit each claim against a tool result." | **omit `thinking` entirely**, `output_config={"effort":"high"}`, `fallbacks=[{"model":"claude-opus-4-8"}]` + beta `server-side-fallback-2026-06-01`, streaming mandatory |

### Layer C — dynamic context (never in the system prefix)

Injected as the **first user message** of the session (or refreshed via a
`<context>` block on later turns):

```
<context>
datetime: Tuesday 2026-07-02 18:55, timezone America/Mexico_City
user: Bernumeno
memory digest:
- Prefers replies in Spanish when he speaks Spanish.
- Works on "jarvis-project"; main machine is an 8GB MacBook.
- Dislikes long spoken answers.
relevant recall (FTS matches for this query, may be empty):
- [2026-06-28] asked to always use Firefox, not Safari.
</context>
```

**Why this layout works:** timestamps and memory change every turn; if they lived in the system prompt they would invalidate the entire cache on every request. Down in `messages` they cost nothing. Note the minimum cacheable prefix is model-dependent (2048–4096 tokens) — the identity+tools prefix should comfortably exceed that on Sonnet/Opus/Fable; Haiku calls are cheap enough that a cache miss there is acceptable.

**Consistent personality across models** comes from (a) the shared, byte-identical Layer A, (b) the shared memory digest, and (c) the voice-output rules being concrete enough that all four models converge on the same style. Expect small tonal differences; tune Layer B per model, never Layer A.

---

## 4. Persistent memory strategy

Three storage layers, all local, all cheap in tokens:

### 4.1 Core profile — `memory/MEMORY.md` (≤400 tokens, always injected)
Curated durable facts: name, language preference, recurring routines, hard rules ("never auto-send email"). Written only via the `remember` tool or manual edit. This is the only memory that is *always* in context.

### 4.2 Episodic log + summaries — SQLite
```sql
turns(id, session_id, ts, role, text, tier, tokens_in, tokens_out)
sessions(id, started_at, ended_at, summary TEXT)      -- summary written by Haiku
memories(id, ts, kind, text, source_session)          -- structured facts
turns_fts  -- FTS5 virtual table over turns.text + sessions.summary
```
- At session end (or every ~20 turns), a **Haiku call** (~$0.001) summarizes the session into ≤150 tokens and stores it.
- Within a session, when history exceeds ~6K tokens, the orchestrator compacts: replace turns older than the last 6 with a Haiku-generated summary block. (Fixed window + summary — predictable token cost, no server-side compaction complexity needed at this scale.)

### 4.3 Recall — SQLite FTS5 (no embeddings, no vector DB)
Before each LLM call, the orchestrator runs an FTS query built from the transcript's content words against past turns/summaries. Top 3 hits, ≤600 tokens total, injected into the `<context>` block **only if they match**. Zero RAM overhead — this is the 8 GB-friendly substitute for semantic search. (If recall quality disappoints later, an embeddings upgrade slots in behind the same `recall()` interface.)

### Token budget per turn (worst case)

| Slot | Budget |
|---|---|
| Tools + Layer A + Layer B (cached after first call) | ~2,500 tok — ~90% discount on cache hits |
| Memory digest (Layer C) | ≤400 |
| FTS recall | ≤600 |
| Conversation window (last ~6 turns + summary) | ≤3,000 |
| **Typical uncached input per turn** | **~1–4K tokens** |

### Write path
The model calls `remember(kind, text)`; the orchestrator dedupes against existing memories (exact/near match), writes to SQLite, and regenerates `MEMORY.md` if `kind == "core"`. Claude proposes; the orchestrator persists — memory is never model-managed state.

---

## 5. Error handling & fallback logic

### 5.1 Model fallback ladder

```
Fable 5  ──refusal──▶  server-side fallbacks param → Opus 4.8 (same request, automatic)
Fable 5  ──429/529──▶  retry as Opus 4.8 (client-side re-route)
Opus 4.8 ──429/529──▶  retry ×2 (SDK auto-backoff) → re-route to Sonnet 5, prefix reply with
                       "Running in reduced mode:"
Sonnet 5 ──429/529──▶  retry ×2 → Haiku 4.5 degraded mode
Haiku    ──fail────▶   speak: "I can't reach the cloud right now."
ANY      ──no network─▶ OFFLINE MODE: T0 grammar commands still work
                       (open apps, volume, timers); everything else gets
                       "I'm offline — I can still control the Mac."
```

Fable requests always carry the server-side fallback (one round trip, automatic repricing):

```python
resp = client.beta.messages.stream(
    model="claude-fable-5",
    max_tokens=32000,
    betas=["server-side-fallback-2026-06-01"],
    fallbacks=[{"model": "claude-opus-4-8"}],
    ...
)
```

### 5.2 Error taxonomy (typed SDK exceptions — never string-match)

| Exception / condition | Action |
|---|---|
| `RateLimitError` (429) | SDK auto-retries with backoff (`max_retries=2`); then drop one tier |
| `APIStatusError` ≥500 / 529 | same as above |
| `APIConnectionError` / `APITimeoutError` | 1 retry; then offline mode + spoken notice |
| 400 `invalid_request_error` | bug, not transient — log loudly, never retry, speak generic failure |
| `stop_reason == "refusal"` | **check before reading `content`** (Fable can return empty content); if server fallback also refused, tell the user plainly |
| `stop_reason == "max_tokens"` | retry once with doubled `max_tokens` (streamed) |
| `stop_reason == "pause_turn"` | re-send assistant content to continue (cap: 5 continuations) |

Circuit breaker per model: 3 consecutive failures → mark model down for 5 minutes, route around it, re-probe after.

### 5.3 Tool errors
Tool failures never crash the loop — return `{"type":"tool_result", "tool_use_id":..., "content": "<error>", "is_error": true}` so the model can adapt. Per-tool timeout (default 10 s; 60 s for shell). Two failures of the same tool in one turn → model is told to stop using it this turn. All `tool_result`s for parallel calls go back **in a single user message**.

### 5.4 Voice-UX resilience
- **Acknowledge fast:** if first token hasn't arrived in 1.5 s, speak a filler ("On it."). For T2/T3, always acknowledge up front.
- **Speak while streaming:** buffer streamed text, flush to `say` at sentence boundaries — perceived latency is time-to-first-sentence, not time-to-full-response.
- **Whisper hallucination guard:** discard transcripts that are empty, repeated punctuation, or the classic silence artifacts ("thank you.", "subtitles by...") when VAD energy was low.
- **Watchdogs:** whisper-server health-checked every 30 s, auto-restarted; `say` failure falls back to on-screen notification (`osascript display notification`).

### 5.5 Budget guard
Daily spend counter from `usage` fields (`input_tokens`, `output_tokens`, cache fields) per response. Soft cap (e.g. $3/day): T2+ requests require spoken confirmation. Hard cap: everything routes to Haiku until midnight, and Z.E.R.O says so.

---

## 6. Module structure — built for delegated implementation

Each module is a package with one public interface, its own tests, and **no imports from sibling internals** — so separate Claude Code sessions (Opus or Sonnet) can implement and maintain each one against the contracts below without stepping on each other.

```
jarvis-project/
├── ARCHITECTURE.md          ← this file
├── pyproject.toml
├── config/
│   ├── settings.yaml        # model IDs, tier params, budgets, audio device
│   └── grammar.yaml         # T0 command grammar (declarative, no code)
├── jarvis/
│   ├── audio/               # M1 — mic capture, VAD, whisper client
│   │   ├── capture.py
│   │   ├── vad.py
│   │   └── transcriber.py   # talks to whisper-server over HTTP
│   ├── routing/             # M2 — tiering
│   │   ├── heuristics.py    # rules 0–5 (pure functions, trivially testable)
│   │   └── classifier.py    # Haiku structured-output fallback
│   ├── llm/                 # M3 — everything Anthropic
│   │   ├── client.py        # streaming, caching, retries, circuit breaker
│   │   ├── fallbacks.py     # ladder from §5.1
│   │   └── prompts/         # layer_a.md, layer_b_{haiku,sonnet,opus,fable}.md, router.md
│   ├── tools/               # M4 — capability surface
│   │   ├── registry.py      # name → schema + handler + is_destructive flag
│   │   ├── macos.py         # open_app, system_control, notify (osascript/Shortcuts)
│   │   ├── files.py         # search_files (mdfind), read_file, write_file
│   │   ├── shell.py         # run_command (allowlisted, confirm-gated)
│   │   ├── web.py           # external APIs: weather, HTTP fetch
│   │   └── memory_tools.py  # remember, recall
│   ├── memory/              # M5 — persistence
│   │   ├── store.py         # SQLite schema + FTS
│   │   ├── digest.py        # MEMORY.md management
│   │   └── summarizer.py    # Haiku session summaries + compaction
│   ├── speech/              # M6 — TTS
│   │   └── tts.py           # sentence-buffered `say` streaming
│   └── core/                # M7 — the only module that imports the others
│       ├── orchestrator.py  # main loop: listen → route → call → tools → speak
│       ├── session.py       # context assembly (layers A/B/C), history window
│       └── budget.py        # spend tracking, caps
└── tests/                   # mirrors jarvis/ 1:1; every module mockable
```

### Module contracts (the load-bearing part)

```python
# M1 audio — async generator of final transcripts
async def transcripts() -> AsyncIterator[Transcript]          # Transcript(text, confidence, ts)

# M2 routing — pure function + optional async fallback
def route(t: Transcript, ctx: SessionContext) -> RouteDecision # RouteDecision(tier, intent, tools_hint) | None
async def classify(t: Transcript) -> RouteDecision             # Haiku fallback

# M3 llm — one entry point; owns streaming, caching, retries, ladder
async def run_turn(tier: Tier, context: BuiltContext,
                   tools: list[ToolDef],
                   on_text: Callable[[str], None],             # streamed text → TTS
                   execute: Callable[[ToolCall], Awaitable[ToolResult]],
                   ) -> TurnResult                             # TurnResult(text, usage, tier_used, escalated)

# M4 tools
registry.get_tools(tier: Tier) -> list[ToolDef]                # schema dicts for the API
await registry.execute(call: ToolCall) -> ToolResult           # enforces confirm-gate + timeout

# M5 memory
store.log_turn(...); store.recall(query: str, k=3) -> list[Snippet]
digest.core_digest() -> str                                    # ≤400 tokens
summarizer.compact(history) -> History                         # windowing + summary

# M6 speech
speaker.feed(text_chunk: str); speaker.flush(); speaker.interrupt()

# M7 core — composition only; contains no business logic of its own
```

**Delegation guide:** M1, M4, M5, M6 are independent and can each be built by a separate Sonnet session against these signatures. M2 and M3 are small but subtle (routing rules, caching/fallback correctness) — Opus territory. M7 is assembled last, when the others' tests pass. `config/settings.yaml` is the single source for model IDs and tier parameters so a model swap never touches code.

---

## 7. Cost model (sanity check)

Assume 60 interactions/day: 40 × T0 (free), 12 × T1 Haiku, 5 × T1.5 Sonnet, 2.5 × T2 Opus, 0.5 × T3 Fable. With caching (~2.5K-token prefix at ~0.1× on hits) and ~3K uncached input / ~300 spoken-output tokens typical:

| Tier | est. cost/turn | daily |
|---|---|---|
| T1 Haiku | ~$0.005 | $0.06 |
| T1.5 Sonnet | ~$0.02 | $0.10 |
| T2 Opus (tool loops) | ~$0.10 | $0.25 |
| T3 Fable (long turns) | ~$0.75 | $0.38 |
| Router classifier calls | ~$0.0005 | ~$0.01 |
| **Total** | | **≈ $0.80/day, ~$25/month** |

The two levers that keep this true: T0 grammar handling ~2/3 of turns for free, and a frozen cached prefix (never interpolate timestamps into the system prompt).

---

## 8. Build order

1. **M6 + M1** — speak and hear (whisper-server + VAD + `say`). Testable standalone.
2. **M3 minimal** — single-model (Sonnet) streaming chat, sentence-streamed to TTS. *First end-to-end voice conversation here.*
3. **M4** — T0 grammar + first tools (open_app, search_files, timers).
4. **M2** — routing tiers + Haiku classifier + escalation token.
5. **M5** — SQLite log, MEMORY.md, `remember`/`recall`, compaction.
6. **M3 full** — caching, fallback ladder, circuit breaker, budget guard, Fable path.
7. Hardening: watchdogs, offline mode, hallucination guard, spend caps.
