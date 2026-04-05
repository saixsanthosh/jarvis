"""
audio/transcriber.py — Speech-to-text via faster-whisper.

Why faster-whisper?
───────────────────
• CTranslate2 backend → 2-4× faster than openai-whisper on CPU.
• int8 quantisation cuts RAM usage significantly.
• VAD filter built-in — skips silent regions automatically.
"""

from __future__ import annotations

import numpy as np
from faster_whisper import WhisperModel  # type: ignore

from config import (
    WHISPER_MODEL, WHISPER_DEVICE,
    WHISPER_COMPUTE_TYPE, WHISPER_LANGUAGE,
)
from utils.logger import setup_logger

logger = setup_logger(__name__)

# Normalisation constant for int16 → float32
_INT16_MAX = 32_768.0


class Transcriber:
    """Converts raw int16 audio to text using faster-whisper."""

    def __init__(self) -> None:
        logger.info(
            "Loading Whisper '%s' on %s (%s)…",
            WHISPER_MODEL, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE,
        )
        self._model = WhisperModel(
            WHISPER_MODEL,
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE_TYPE,
        )
        logger.info("Whisper ready ✓")

    # ── Public API ────────────────────────────────────────────────────────────

    def transcribe(self, audio: np.ndarray) -> str:
        """
        Transcribe *audio* (np.int16, 16 kHz mono) to a text string.

        Returns an empty string if nothing was heard or on error.
        """
        if audio is None or len(audio) == 0:
            return ""

        # Whisper expects float32 in [-1, 1]
        audio_f32 = audio.astype(np.float32) / _INT16_MAX

        try:
            segments, info = self._model.transcribe(
                audio_f32,
                language=WHISPER_LANGUAGE,
                beam_size=5,
                best_of=5,
                condition_on_previous_text=False,
                # Built-in VAD removes silence segments
                vad_filter=True,
                vad_parameters={
                    "min_silence_duration_ms": 500,
                    "speech_pad_ms": 200,
                },
            )

            text = " ".join(seg.text for seg in segments).strip()

            if text:
                logger.info("STT → '%s'", text)
            else:
                logger.debug("STT returned empty (probably silence)")

            return text

        except Exception as exc:
            logger.error("Transcription failed: %s", exc, exc_info=True)
            return ""
