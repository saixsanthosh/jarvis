"""
audio/wake_detector.py — Listen passively for activation signals.

Supported triggers (ALL run simultaneously)
───────────────────────────────────────────
1. Custom wake phrases  — "wake up daddy's home", "yo jarvis", etc.
   Uses Whisper to transcribe short audio buffers and match phrases.
   Add any phrase you want in config.py → CUSTOM_WAKE_PHRASES.

2. Wake word via openWakeWord  ("hey_jarvis" built-in model).
   Fast neural model, low CPU. Falls back gracefully if not installed.

3. Double-clap fallback  (always active, no model needed).
   Two sharp claps within 0.15–1.0 seconds.

Architecture
────────────
The detector buffers audio chunks. Every WAKE_PHRASE_BUFFER_SECONDS it
checks if there was enough speech energy to warrant a Whisper transcription.
If yes, it transcribes and checks against CUSTOM_WAKE_PHRASES.
Meanwhile, every chunk is also checked by openWakeWord and clap detection.
"""

from __future__ import annotations

import time
from collections import deque
from typing import Generator, Literal, Optional, Callable

import numpy as np

from config import (
    OWW_MODEL_NAME, OWW_THRESHOLD,
    CLAP_ENERGY_THRESHOLD, CLAP_MIN_GAP, CLAP_MAX_GAP,
    SAMPLE_RATE, CHUNK_SIZE,
    CUSTOM_WAKE_PHRASES, WAKE_PHRASE_BUFFER_SECONDS, WAKE_PHRASE_MIN_ENERGY,
)
from utils.logger import setup_logger

logger = setup_logger(__name__)

WakeTrigger = Literal["wake_word", "clap", "custom_phrase", "unknown"]

# Normalisation constant for int16 → float32
_INT16_MAX = 32_768.0


class WakeDetector:
    """Passive wake-event detector that blocks until triggered."""

    def __init__(self, transcribe_fn: Optional[Callable] = None) -> None:
        self._oww = None
        self._oww_ok = False
        self._transcribe = transcribe_fn
        self._phrases = [p.lower().strip() for p in CUSTOM_WAKE_PHRASES if p.strip()]
        self._init_oww()

        if self._phrases:
            logger.info(
                "Custom wake phrases enabled: %s",
                ", ".join(f'"{p}"' for p in self._phrases[:5])
            )

    # ── openWakeWord ──────────────────────────────────────────────────────────

    def _init_oww(self) -> None:
        try:
            from openwakeword.model import Model  # type: ignore
            import openwakeword  # type: ignore

            openwakeword.utils.download_models()

            self._oww = Model(
                wakeword_models=[OWW_MODEL_NAME],
                inference_framework="onnx",
            )
            self._oww_ok = True
            logger.info("openWakeWord loaded — model: %s", OWW_MODEL_NAME)
        except ImportError:
            logger.warning(
                "openWakeWord not installed — using custom phrases + clap only."
            )
        except Exception as exc:
            logger.warning("openWakeWord init failed (%s) — phrase + clap mode.", exc)

    def _oww_score(self, chunk: np.ndarray) -> float:
        if not self._oww_ok or self._oww is None:
            return 0.0
        try:
            self._oww.predict(chunk)
            scores = self._oww.prediction_buffer
            return max(
                (preds[-1] for preds in scores.values() if preds),
                default=0.0,
            )
        except Exception as exc:
            logger.debug("OWW predict error: %s", exc)
            return 0.0

    # ── Clap detection ────────────────────────────────────────────────────────

    @staticmethod
    def _is_clap(chunk: np.ndarray) -> bool:
        peak = int(np.abs(chunk).max())
        return peak > CLAP_ENERGY_THRESHOLD

    # ── Custom phrase detection ───────────────────────────────────────────────

    def _check_phrases(self, audio_buffer: np.ndarray) -> Optional[str]:
        """Transcribe audio buffer and check for wake phrases."""
        if not self._transcribe or not self._phrases:
            return None

        # Check if there's enough speech energy
        energy = int(np.abs(audio_buffer).mean())
        if energy < WAKE_PHRASE_MIN_ENERGY:
            return None

        try:
            text = self._transcribe(audio_buffer).lower().strip()
            if not text or len(text) < 2:
                return None

            # Check each wake phrase
            for phrase in self._phrases:
                if phrase in text:
                    logger.info("Custom wake phrase matched: '%s' in '%s'", phrase, text)
                    return phrase

        except Exception as exc:
            logger.debug("Phrase check error: %s", exc)

        return None

    # ── Public API ────────────────────────────────────────────────────────────

    def listen_for_wake(
        self,
        chunk_stream: Generator[np.ndarray, None, None],
    ) -> WakeTrigger:
        """
        Block until a wake event fires.

        Consumes chunks from *chunk_stream* (yielded by AudioListener.stream_chunks).
        Runs three detection methods simultaneously:
          1. Custom phrase matching (Whisper-based)
          2. openWakeWord neural model
          3. Double-clap energy detection
        """
        clap_times: deque[float] = deque(maxlen=2)

        # Audio buffer for phrase detection
        phrase_buffer: list[np.ndarray] = []
        chunks_per_buffer = int(SAMPLE_RATE / CHUNK_SIZE * WAKE_PHRASE_BUFFER_SECONDS)
        chunk_count = 0
        has_speech = False

        # Build hint message
        hints = []
        if self._phrases:
            hints.append(f'say "{self._phrases[0]}"')
        elif self._oww_ok:
            hints.append("say 'Hey Jarvis'")
        hints.append("or double-clap")
        logger.info("👂 Waiting for wake signal (%s)…", " ".join(hints))

        for chunk in chunk_stream:
            chunk_count += 1

            # ── 1. openWakeWord ────────────────────────────────────────────
            score = self._oww_score(chunk)
            if score >= OWW_THRESHOLD:
                logger.info("Wake word detected (confidence=%.2f)", score)
                return "wake_word"

            # ── 2. Double clap ─────────────────────────────────────────────
            if self._is_clap(chunk):
                now = time.monotonic()
                clap_times.append(now)

                if len(clap_times) == 2:
                    gap = clap_times[1] - clap_times[0]
                    if CLAP_MIN_GAP <= gap <= CLAP_MAX_GAP:
                        logger.info("Double-clap detected (gap=%.2fs)", gap)
                        return "clap"
                    if gap > CLAP_MAX_GAP:
                        clap_times.popleft()

            # ── 3. Custom phrase detection ─────────────────────────────────
            if self._phrases and self._transcribe:
                phrase_buffer.append(chunk)

                # Track if any chunk has speech-level energy
                energy = int(np.abs(chunk).mean())
                if energy >= WAKE_PHRASE_MIN_ENERGY:
                    has_speech = True

                # Every N chunks, check the buffer
                if chunk_count >= chunks_per_buffer:
                    if has_speech and phrase_buffer:
                        audio = np.concatenate(phrase_buffer)
                        matched = self._check_phrases(audio)
                        if matched:
                            return "custom_phrase"

                    # Reset buffer
                    phrase_buffer = []
                    chunk_count = 0
                    has_speech = False

        return "unknown"
