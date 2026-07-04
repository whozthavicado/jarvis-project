# Z.E.R.O Live Backend Integration — Design Spec

Date: 2026-07-04

## Goal

Connect the existing Python voice/tool-execution backend (`jarvis/`) to the Z.E.R.O dashboard (`dashboard/`) so the dashboard's Assistant widget and Real-Time Activity panel show real, live data instead of static mocks — while keeping voice input native (no browser mic capture in this pass).

## Context

- The Python backend (`jarvis/`) already implements: mic capture → whisper.cpp transcription → LLM reply → macOS `say` TTS; a T0 command grammar that executes OS actions (open/close apps, volume, media, lock screen, brightness, timers, file search/read/write); multi-tier routing; persistent SQLite memory; a fallback/circuit-breaker/budget system. It has only ever run as one-shot CLI scripts (`scripts/milestone2.py` etc.) — never as a long-running service, and (until this session) never against live API credentials.
- Live credentials (`OPENROUTER_API_KEY`, `NVIDIA_API_KEY`) were verified working on 2026-07-04 against all 10 free-mode tier keys (see the build-status memory for detail; one transient timeout and one rate-limited primary tier were observed, both with working fallbacks).
- The dashboard (`dashboard/`) is a new Next.js app, 100% static mock data behind `useDashboardData()`, built in a prior session (see `docs/superpowers/specs/2026-07-04-zero-dashboard-design.md` and its plan).
- **Decision: keep audio native.** Voice capture continues to happen via the Mac's mic in the Python process (already built and working); the dashboard does not capture audio in the browser. This was chosen over browser-mic capture because it reuses fully-built infrastructure instead of building a new audio-streaming path from scratch — the fastest route to a working system.
- **Decision: scope of "live" for this pass** is the Assistant widget (real typed chat, real replies) and the Real-Time Activity panel (real turn history), plus a live status indicator. Every other panel (System Performance, Predictive Analysis, Resource Distribution, Active Modules, Key Projects, Executive Summary, Quote, Global Connectivity, Encryption/Security) stays on mock data — those are cosmetic/no real backend equivalent exists yet, and wiring them isn't necessary for "does Z.E.R.O actually listen, talk, and execute."
- **Decision: new server module location** is `jarvis/server.py`, inside the existing importable Python package (not a standalone `scripts/` runner), so it can import `orchestrator`/`Session`/`MemoryStore` directly like the rest of the package does.

## Architecture

One Python process runs two things concurrently in the same asyncio event loop, sharing one `Session` and one `MemoryStore` instance:

1. **The existing voice loop** (`converse()` in `jarvis/core/orchestrator.py`) — unchanged, still does mic → whisper → LLM → speak.
2. **A new WebSocket server** (`jarvis/server.py`) — lets the dashboard send typed text through the *same* `orchestrator.handle_turn()` pipeline used by voice input.

Because both input channels write to the same shared `Session`/`MemoryStore`, the dashboard's activity feed reflects everything Z.E.R.O does, whether triggered by voice or by typing in the dashboard.

## Components

### `jarvis/server.py` (new)

- **`Broadcaster`**: a minimal pub/sub class. `subscribe()` returns an `asyncio.Queue` that receives every published event; `publish(event: dict)` pushes to all subscribed queues (each currently-connected WebSocket client owns one queue). Events are plain dicts: `{"type": "status", "state": "idle"|"thinking"|"speaking"}` or `{"type": "activity", "actor": ..., "description": ..., "timestamp": ...}`.
- **`handle_client(websocket)`**: the per-connection coroutine registered with `websockets.serve()`. On connect, subscribes to the `Broadcaster` and starts a background task forwarding broadcast events to this client as JSON. Reads incoming messages in a loop:
  - `{"type": "chat", "text": "..."}` → builds a `Transcript(text=...)` and calls `orchestrator.handle_turn(session, llm, transcript, on_text, broadcaster=broadcaster)`; on completion, sends `{"type": "reply", "text": result.text}` back to the sender only (not broadcast to other clients — only the requester gets the direct reply object, though the resulting activity/status events *do* broadcast to everyone via the normal turn-completion hook).
  - `{"type": "history"}` → queries `MemoryStore` for the last ~20 turns and replies `{"type": "history", "entries": [...]}` so a freshly-opened dashboard tab isn't empty.
  - Any other/malformed message: logged and ignored — must not crash the connection or the shared session.
- **`run_server(host, port, session, llm, broadcaster)`**: thin wrapper around `websockets.serve(...)`, run as one of the tasks in the process's `asyncio.gather()`.

### `jarvis/core/orchestrator.py` (modified)

- `handle_turn()` gains one new optional parameter: `broadcaster: Broadcaster | None = None`, following the exact existing pattern already used for `router`/`budget`/`offline` (default `None` = zero behavior change for every existing caller and test). When provided:
  - Publishes `{"type": "status", "state": "thinking"}` when a turn begins.
  - Publishes `{"type": "status", "state": "speaking"}` right before TTS output begins (voice path only — the dashboard-chat path skips straight to `idle` after the reply, since there's no audio to speak back to a typed request).
  - Publishes `{"type": "status", "state": "idle"}` when the turn completes (success or fallback).
  - Publishes `{"type": "activity", ...}` once per completed turn, sourced from the same data already being written to `MemoryStore.log_turn()` — actor is `"User"` for a dashboard-typed turn, `"Z.E.R.O"` for the reply, consistent with the dashboard's existing `ActivityEntry.actor` union type.

### Entrypoint

`python -m jarvis.server` — a small `if __name__ == "__main__":` block in `jarvis/server.py` that builds one shared `Session`/`LLMClient`/`Broadcaster`, then `asyncio.gather(converse(...), run_server(...))`. Manual foreground run for this pass; process supervision (e.g. a `launchd` plist to keep it running persistently) is an explicitly deferred follow-up, not part of this plan.

### `dashboard/hooks/useZeroBackend.ts` (new)

- Opens a WebSocket to `NEXT_PUBLIC_ZERO_WS_URL` (default `ws://localhost:8765`).
- Exposes: `connectionState` (`"connecting"|"open"|"closed"`), `coreStatus` (`"idle"|"thinking"|"speaking"`, defaults to `"idle"`), `activityFeed: ActivityEntry[]` (starts empty, filled by the `history` response on connect and appended to live), `lastReply: string | null`, and `sendChat(text: string): void`.
- Auto-reconnects with exponential backoff (capped) on disconnect.
- On disconnect, `activityFeed` and other live fields fall back to values from the existing `useDashboardData()` mock hook, so the dashboard never renders an empty/broken-looking panel — this hook composes with, rather than replaces, the mock data hook.

### Component wiring (modified)

- **`AssistantWidget.tsx`**: input becomes a controlled `<input>` with local state; `onSubmit`/Enter-key calls `sendChat(text)` from `useZeroBackend()`; the widget displays `lastReply` below the input once one arrives (replacing or supplementing the static greeting).
- **`RealTimeActivity.tsx`**: swaps its data source from `useDashboardData().activityFeed` to `useZeroBackend().activityFeed` (with the fallback-to-mock behavior described above already handled inside the hook, so this component's own code barely changes — just which hook it reads from).
- **`CenterHeader.tsx`**: the existing pulsing "Intelligent Core Active" indicator's color/label reflects `useZeroBackend().coreStatus` (`thinking`/`speaking` gets a distinct visual treatment) instead of being permanently "active".

## Data Flow

1. User types in the Assistant widget → `useZeroBackend().sendChat(text)` → WS message `{"type":"chat","text":...}`.
2. `jarvis/server.py`'s `handle_client` builds a `Transcript`, calls `orchestrator.handle_turn(..., broadcaster=broadcaster)`.
3. `handle_turn` publishes `thinking` → runs the existing routing/LLM/tool-execution/memory pipeline unchanged → publishes the turn's `activity` entry → publishes `idle`.
4. The server sends `{"type":"reply","text":...}` back to the requesting client.
5. All connected dashboard clients (in practice, one) receive the `status`/`activity` broadcasts and update `coreStatus`/`activityFeed` live.
6. Independently, if the user talks to Z.E.R.O out loud, the voice loop's turns go through the identical `handle_turn(..., broadcaster=broadcaster)` call, so the same status/activity events fire and the dashboard reflects voice-triggered activity too, without the dashboard needing to know the difference.

## Error Handling

- `broadcaster=None` (server not running, or a caller that doesn't pass one) preserves `handle_turn`'s exact current behavior — no new failure mode is introduced for any existing test or caller.
- A WebSocket disconnect doesn't affect the shared `Session`/voice loop — they're independent of any particular client connection.
- Malformed/unrecognized client messages are logged and ignored, never raised in a way that kills the connection or the shared event loop.
- LLM failures still go through the existing fallback/circuit-breaker chain; the text sent back over the socket is the same fallback/apology text the voice path would have spoken, not a raw exception.
- Dashboard-side: on WS error/close, `useZeroBackend` transitions to `"closed"`, retries with backoff, and callers see the mock-data fallback rather than blank/broken UI.

## Testing

- Follows the existing repo pattern (pytest, fake LLM/transport clients): unit tests for `Broadcaster` (publish reaches all subscribers, a slow/absent subscriber doesn't block others) and for `handle_client`'s message handling (using a fake WebSocket connection object and a stubbed `orchestrator.handle_turn`, mirroring `tests/test_orchestrator.py`'s existing stubbing style).
- `handle_turn`'s new `broadcaster` param gets the same "None = no behavior change" test coverage pattern already used for `router`/`budget`/`offline` in `tests/test_orchestrator.py`.
- No test framework exists on the dashboard side (established in the prior dashboard-build session) — the hook and component wiring are verified by manually running the server and the dashboard dev server together and confirming a typed message gets a real reply and appears in the activity feed.

## Out of Scope (this pass)

- Browser-based microphone capture (native audio only, per the decision above).
- Wiring System Performance / Predictive Analysis / Resource Distribution / Active Modules / Key Projects / Executive Summary / Quote / Global Connectivity / Encryption-Security to any real data source — these stay mock.
- Process supervision / `launchd` service / auto-restart-on-crash for `jarvis/server.py` — it runs in the foreground for this pass.
- Authentication/authorization on the WebSocket endpoint (single local user, local machine, no external exposure).
- `.env` auto-loading via `python-dotenv` — for this pass, environment variables are exported manually into the shell before running (as already confirmed working during live credential verification); adding `python-dotenv` is a small, separate, easy follow-up if it becomes annoying, not required for the integration itself to work.
