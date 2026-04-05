"""
audio/wake_detector.py — Listen passively for activation signals.

Supported triggers
──────────────────
1. Wake word via openWakeWord  ("hey_jarvis" built-in model).
2. Double-clap fallback         (always active, no model needed).

Design notes
────────────
• openWakeWord is loaded lazily and gracefully degrades if missing.
• The detector consumes a chunk-generator from AudioListener and blocks
  until a trigger fires, then returns which kind fired.
• No audio is buffered beyond what's needed for the sliding OWW window.
"""

from __future__ import annotations

import time
from collections import deque
from typing import Generator, Literal

import numpy as np

from config import (
    OWW_MODEL_NAME, OWW_THRESHOLD,
    CLAP_ENERGY_THRESHOLD, CLAP_MIN_GAP, CLAP_MAX_GAP,
    SAMPLE_RATE, CHUNK_SIZE,
)
from utils.logger import setup_logger

logger = setup_logger(__name__)

WakeTrigger = Literal["wake_word", "clap", "unknown"]


class WakeDetector:
    """Passive wake-event detector that blocks until triggered."""

    def __init__(self) -> None:
        self._oww = None
        self._oww_ok = False
        self._init_oww()

    # ── openWakeWord ──────────────────────────────────────────────────────────

    def _init_oww(self) -> None:
        try:
            from openwakeword.model import Model  # type: ignore
            import openwakeword  # type: ignore

            # Download pre-trained models on first run
            openwakeword.utils.download_models()

            self._oww = Model(
                wakeword_models=[OWW_MODEL_NAME],
                inference_framework="onnx",
            )
            self._oww_ok = True
            logger.info("openWakeWord loaded — model: %s", OWW_MODEL_NAME)
        except ImportError:
            logger.warning(
                "openWakeWord not installed. "
                "Run: pip install openwakeword   (wake-word disabled, clap only)"
            )
        except Exception as exc:
            logger.warning("openWakeWord init failed (%s) — clap-only mode.", exc)

    def _oww_score(self, chunk: np.ndarray) -> float:
        """Return the highest wake-word confidence score for this chunk."""
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

    # ── Public API ────────────────────────────────────────────────────────────

    def listen_for_wake(
        self,
        chunk_stream: Generator[np.ndarray, None, None],
    ) -> WakeTrigger:
        """
        Block until a wake event fires.

        Consumes chunks from *chunk_stream* (yielded by AudioListener.stream_chunks).
        Returns the trigger kind as a string.
        """
        clap_times: deque[float] = deque(maxlen=2)

        hint = "say 'Hey Jarvis'" if self._oww_ok else "double-clap"
        logger.info("👂 Waiting for wake signal (%s)…", hint)

        for chunk in chunk_stream:
            # ── Wake word ──────────────────────────────────────────────────
            score = self._oww_score(chunk)
            if score >= OWW_THRESHOLD:
                logger.info("Wake word detected (confidence=%.2f)", score)
                return "wake_word"

            # ── Double clap ────────────────────────────────────────────────
            if self._is_clap(chunk):
                now = time.monotonic()
                clap_times.append(now)

                if len(clap_times) == 2:
                    gap = clap_times[1] - clap_times[0]
                    if CLAP_MIN_GAP <= gap <= CLAP_MAX_GAP:
                        logger.info("Double-clap detected (gap=%.2fs)", gap)
                        return "clap"
                    # Gap too long — treat second clap as the new first
                    if gap > CLAP_MAX_GAP:
                        clap_times.popleft()

        return "unknown"  # stream exhausted (shouldn't normally happen)
