"""Sentence-buffered text-to-speech.

Perceived latency in a voice assistant is *time to first spoken sentence*, not
time to full response. :class:`Speaker` accepts streamed text chunks, cuts them
into complete sentences as soon as boundaries appear, and speaks them
sequentially through macOS ``say`` while more text is still arriving.

``split_sentences`` is pure so it can be unit-tested; the async plumbing around
it is thin.
"""
from __future__ import annotations

import asyncio
import re
from typing import List, Optional, Tuple

from jarvis.config import Settings, get_settings

# A sentence ends at ., !, ?, … (optionally quoted/bracketed) followed by
# whitespace, or at a hard newline.
_BOUNDARY = re.compile(r'(.+?(?:[.!?…]+["\')\]]?\s+|\n+))', re.DOTALL)


def split_sentences(buffer: str) -> Tuple[List[str], str]:
    """Split *buffer* into complete sentences and a trailing remainder.

    Only emits sentences whose terminal punctuation is followed by whitespace
    (so a sentence still being streamed is held back as the remainder).

    Returns:
        (sentences, remainder) where each sentence is stripped and non-empty.
    """
    sentences: List[str] = []
    pos = 0
    for m in _BOUNDARY.finditer(buffer):
        chunk = m.group(1).strip()
        if chunk:
            sentences.append(chunk)
        pos = m.end()
    return sentences, buffer[pos:]


class Speaker:
    """Speak streamed text through macOS ``say``, one sentence at a time."""

    def __init__(self, settings: Optional[Settings] = None):
        s = settings or get_settings()
        self.voice = s.tts.get("voice")
        self.rate = int(s.tts.rate)
        self._buffer = ""
        self._queue: "asyncio.Queue[Optional[str]]" = asyncio.Queue()
        self._worker: Optional[asyncio.Task] = None
        self._current: Optional[asyncio.subprocess.Process] = None
        self._say_cmd = "say"  # overridable in tests
        self._osascript_cmd = "osascript"  # overridable in tests

    # -- lifecycle -------------------------------------------------------
    def start(self) -> None:
        if self._worker is None:
            self._worker = asyncio.ensure_future(self._run())

    async def aclose(self) -> None:
        await self.flush()
        await self._queue.put(None)  # sentinel
        if self._worker is not None:
            await self._worker
            self._worker = None

    async def __aenter__(self) -> "Speaker":
        self.start()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.aclose()

    # -- public API (ARCHITECTURE.md §6) --------------------------------
    def feed(self, text_chunk: str) -> None:
        """Add streamed text; enqueue any newly-complete sentences."""
        self.start()
        self._buffer += text_chunk
        sentences, self._buffer = split_sentences(self._buffer)
        for sentence in sentences:
            self._queue.put_nowait(sentence)

    async def flush(self) -> None:
        """Speak any buffered remainder (call at end of a response)."""
        remainder = self._buffer.strip()
        self._buffer = ""
        if remainder:
            self.start()
            self._queue.put_nowait(remainder)
        # Wait for the queue to drain.
        await self._queue.join()

    async def interrupt(self) -> None:
        """Stop current speech and discard anything queued (barge-in)."""
        self._buffer = ""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except asyncio.QueueEmpty:
                break
        if self._current is not None and self._current.returncode is None:
            self._current.terminate()

    # -- worker ----------------------------------------------------------
    async def _run(self) -> None:
        while True:
            item = await self._queue.get()
            if item is None:  # shutdown sentinel
                self._queue.task_done()
                break
            try:
                await self._speak(item)
            finally:
                self._queue.task_done()

    async def _speak(self, text: str) -> None:
        args = [self._say_cmd, "-r", str(self.rate)]
        if self.voice:
            args += ["-v", str(self.voice)]
        args.append(text)
        failed = False
        try:
            self._current = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            try:
                await self._current.wait()
                # A positive exit code is a real `say` failure; a negative one
                # means we terminated it ourselves (barge-in via interrupt()).
                failed = (self._current.returncode or 0) > 0
            finally:
                self._current = None
        except OSError:
            failed = True
        if failed:
            await self._notify(text)

    async def _notify(self, text: str) -> None:
        """§5.4: `say` failure falls back to an on-screen notification."""
        safe = text.replace('"', "'")
        script = f'display notification "{safe}" with title "Z.E.R.O"'
        try:
            proc = await asyncio.create_subprocess_exec(
                self._osascript_cmd,
                "-e",
                script,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
        except OSError:
            pass  # nothing left to surface it with; the text is still in history
