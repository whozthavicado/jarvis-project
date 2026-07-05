#!/usr/bin/env bash
# Launch a persistent whisper.cpp server for Jarvis (M1).
#
# Loads the model once and serves HTTP on :8080 so transcription stays warm.
#
# Default model is the quantized tiny model (~30 MB on disk, ~13-20 MB
# resident) -- chosen for speed on CPU-only inference (see WHISPER_EXTRA_ARGS
# below): live-measured ~1.5s to transcribe a 3s clip on this machine, vs
# ~4.5s for the base model (2026-07-04, no GPU). Tiny is less accurate,
# especially on uncommon words/names -- set WHISPER_MODEL to the base model
# path below if you'd rather trade latency for accuracy.
#
# First-time setup:
#   git clone https://github.com/ggml-org/whisper.cpp
#   cd whisper.cpp && cmake -B build && cmake --build build -j --config Release
#   ./models/download-ggml-model.sh tiny-q5_1
#   # optionally also: ./models/download-ggml-model.sh base-q5_1  (more accurate, slower)
#
# Then point WHISPER_DIR at that checkout and run this script.

set -euo pipefail

WHISPER_DIR="${WHISPER_DIR:-$HOME/whisper.cpp}"
MODEL="${WHISPER_MODEL:-$WHISPER_DIR/models/ggml-tiny-q5_1.bin}"
HOST="${WHISPER_HOST:-127.0.0.1}"
PORT="${WHISPER_PORT:-8080}"
LANG="${WHISPER_LANG:-auto}"
# Extra flags passed through to the server binary, e.g. WHISPER_EXTRA_ARGS="--no-gpu"
# if Metal init hangs on your GPU (seen on some Intel Macs).
EXTRA_ARGS="${WHISPER_EXTRA_ARGS:-}"

# Server binary location differs across whisper.cpp versions.
BIN=""
for candidate in \
  "$WHISPER_DIR/build/bin/whisper-server" \
  "$WHISPER_DIR/build/bin/server" \
  "$WHISPER_DIR/server"; do
  if [[ -x "$candidate" ]]; then BIN="$candidate"; break; fi
done

if [[ -z "$BIN" ]]; then
  echo "ERROR: whisper server binary not found under $WHISPER_DIR." >&2
  echo "Build it first (see the header of this script)." >&2
  exit 1
fi
if [[ ! -f "$MODEL" ]]; then
  echo "ERROR: model not found: $MODEL" >&2
  echo "Download it: $WHISPER_DIR/models/download-ggml-model.sh tiny-q5_1" >&2
  exit 1
fi

echo "Starting whisper server: $BIN"
echo "  model=$MODEL  host=$HOST  port=$PORT  lang=$LANG  extra_args=$EXTRA_ARGS"
# shellcheck disable=SC2086
exec "$BIN" -m "$MODEL" --host "$HOST" --port "$PORT" -l "$LANG" $EXTRA_ARGS
