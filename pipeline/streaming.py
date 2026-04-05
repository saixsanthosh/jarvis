"""
pipeline/streaming.py — Low-latency sentence-streaming TTS pipeline.

Architecture
────────────
                     ┌─────────────────────────────────────────┐
  LLMBrain.stream()  │  Token producer                         │
       yields token  │  Accumulates tokens into sentence buffer │
                     │  Flushes on sentence-ending punctuation  │
                     └──────────────┬──────────────────────────┘
                                    │ complete sentence
                                    ▼
                     ┌─────────────────────────────────────────┐
                     │  Queue (thread-safe)                     │
                     └──────────────┬──────────────────────────┘
                                    │
                                    ▼
                     ┌─────────────────────────────────────────┐
                     │  TTS worker thread                       │
                     │  Dequeues sentences, synthesises, plays  │
                     └─────────────────────────────────────────┘

Result: first sentence starts playing within ~0.5s of the first token,
while the rest of the reply is still being generated.
"""

from __future__ import annotations

import queue
import re
import threading
from typing import Callable

from config import STREAM_SENTENCE_ENDINGS, STREAM_MIN_SENTENCE_CHARS
from utils.logger import setup_logger

logger = setup_logger(__name__)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")

# Sentinel to signal the worker to stop waiting
_DONE = object()


class StreamingPipeline:
    """Pipes LLM token stream to TTS with sentence-level chunking."""

    def __init__(
        self,
        speak_fn: Callable[[str], None],
    ) -> None:
        self._speak = speak_fn
        self._q: queue.Queue = queue.Queue()
        self._worker = threading.Thread(
            target=self._tts_worker, name="tts-worker", daemon=True
        )
        self._worker.start()
        logger.info("Streaming pipeline ready (TTS worker running).")

    # ── Worker ────────────────────────────────────────────────────────────────

    def _tts_worker(self) -> None:
        """Background thread: drains the queue and calls speak()."""
        while True:
            item = self._q.get()
            if item is _DONE:
                self._q.task_done()
                continue          # Don't exit — keep the daemon alive
            try:
                self._speak(item)
            except Exception as exc:
                logger.error("TTS worker error: %s", exc)
            finally:
                self._q.task_done()

    # ── Public API ────────────────────────────────────────────────────────────

    def generate_and_speak(
        self,
        token_generator,
        on_token: Callable[[str], None] | None = None,
    ) -> str:
        """
        Consume *token_generator*, accumulate into sentences, feed TTS queue.

        Parameters
        ──────────
        token_generator : iterable of str tokens from LLMBrain.stream()
        on_token        : optional callback per raw token (for UI display)

        Returns the complete response as a single string.
        """
        full_tokens: list[str] = []
        sentence_buf: list[str] = []

        for token in token_generator:
            full_tokens.append(token)
            sentence_buf.append(token)

            if on_token:
                on_token(token)

            # Check if the buffer ends with sentence-ending punctuation
            buf_str = "".join(sentence_buf)
            if self._should_flush(buf_str):
                sentence = buf_str.strip()
                if sentence:
                    logger.debug("Queuing sentence (%d chars): %s…", len(sentence), sentence[:40])
                    self._q.put(sentence)
                sentence_buf = []

        # Flush any remaining partial sentence
        remainder = "".join(sentence_buf).strip()
        if remainder:
            self._q.put(remainder)

        # Wait for TTS to finish all queued sentences
        self._q.join()

        return "".join(full_tokens).strip()

    @staticmethod
    def _should_flush(buf: str) -> bool:
        """True if *buf* should be flushed to TTS now.

        Flushes when:
        - Buffer ends with sentence-ending punctuation (.!?;:) and is ≥ min chars
        - Buffer is very long (80+ chars) and ends with a comma (clause break)
        """
        stripped = buf.strip()
        if not stripped:
            return False

        length = len(stripped)

        # Sentence-ending punctuation
        if length >= STREAM_MIN_SENTENCE_CHARS and stripped[-1] in STREAM_SENTENCE_ENDINGS:
            return True

        # Long clause — flush at comma to avoid TTS backing up
        if length >= 80 and stripped[-1] == ",":
            return True

        return False

    def speak_immediate(self, text: str) -> None:
        """Bypass queue — speak *text* directly (for command responses)."""
        self._q.put(text)
        self._q.join()
