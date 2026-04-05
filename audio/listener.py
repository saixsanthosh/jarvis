"""
audio/listener.py — Raw microphone I/O.

Responsibilities
────────────────
• Open / close PyAudio streams cleanly.
• Provide a raw chunk generator (used by wake detector).
• Record speech until silence is detected (used after wake).
"""

from __future__ import annotations

import time
import numpy as np
import pyaudio

from config import (
    SAMPLE_RATE, CHANNELS, CHUNK_SIZE,
    SILENCE_THRESHOLD, SILENCE_DURATION, MAX_RECORD_SECONDS,
)
from utils.logger import setup_logger

logger = setup_logger(__name__)


class AudioListener:
    """Thin wrapper around PyAudio for microphone input."""

    # PyAudio format matches int16 → numpy int16 → divide by 32768 for float
    _PA_FORMAT = pyaudio.paInt16

    def __init__(self) -> None:
        self._pa = pyaudio.PyAudio()
        logger.info("AudioListener ready (sr=%d, chunk=%d)", SAMPLE_RATE, CHUNK_SIZE)

    # ── helpers ──────────────────────────────────────────────────────────────

    def _open_stream(self) -> pyaudio.Stream:
        return self._pa.open(
            format=self._PA_FORMAT,
            channels=CHANNELS,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE,
        )

    @staticmethod
    def _to_int16(raw: bytes) -> np.ndarray:
        return np.frombuffer(raw, dtype=np.int16)

    # ── public API ────────────────────────────────────────────────────────────

    def stream_chunks(self):
        """
        Generator: yields np.int16 chunks indefinitely from the microphone.
        The caller is responsible for breaking out of the loop.
        """
        stream = self._open_stream()
        logger.debug("Chunk stream opened.")
        try:
            while True:
                raw = stream.read(CHUNK_SIZE, exception_on_overflow=False)
                yield self._to_int16(raw)
        finally:
            stream.stop_stream()
            stream.close()
            logger.debug("Chunk stream closed.")

    def record_until_silence(self) -> np.ndarray:
        """
        Record from the microphone until the user stops speaking.

        Strategy: keep recording as long as audio energy is above SILENCE_THRESHOLD.
        Stop when we've seen SILENCE_DURATION consecutive seconds of silence
        *and* have recorded at least that much audio total.

        Returns a single np.int16 array of the full utterance.
        """
        logger.info("🎙  Recording — speak now…")
        stream = self._open_stream()

        frames: list[bytes] = []
        silence_chunks = 0
        max_chunks = int(SAMPLE_RATE / CHUNK_SIZE * MAX_RECORD_SECONDS)
        silence_limit = int(SAMPLE_RATE / CHUNK_SIZE * SILENCE_DURATION)

        try:
            for _ in range(max_chunks):
                raw = stream.read(CHUNK_SIZE, exception_on_overflow=False)
                frames.append(raw)

                energy = int(np.abs(self._to_int16(raw)).mean())
                if energy < SILENCE_THRESHOLD:
                    silence_chunks += 1
                else:
                    silence_chunks = 0

                # Need at least silence_limit chunks of speech before stopping
                if silence_chunks >= silence_limit and len(frames) > silence_limit:
                    break
        finally:
            stream.stop_stream()
            stream.close()

        audio = np.frombuffer(b"".join(frames), dtype=np.int16)
        duration = len(audio) / SAMPLE_RATE
        logger.info("Recording done (%.1fs)", duration)
        return audio

    def cleanup(self) -> None:
        """Release PyAudio resources — call on shutdown."""
        try:
            self._pa.terminate()
            logger.info("AudioListener cleaned up.")
        except Exception as exc:
            logger.warning("Cleanup error: %s", exc)
