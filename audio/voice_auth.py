"""
audio/voice_auth.py — Speaker-identity verification via resemblyzer.

How it works
────────────
1. Enrollment  : record N seconds of the owner's voice → compute an embedding
                 (256-D vector) → save to disk as a .npy file.
2. Verification: after every wake event, record 3 s of speech → compute
                 embedding → compare cosine similarity to stored embedding.
                 If similarity ≥ VOICE_AUTH_THRESHOLD → accept.
                 Otherwise → reject (Jarvis stays silent).

resemblyzer uses a pre-trained GE2E speaker-encoder that maps any audio
sample to a fixed-length embedding space where speakers cluster together.
It is fully offline after the first download.

Graceful degradation
────────────────────
If resemblyzer is not installed, VoiceAuth always returns True (disabled).
VOICE_AUTH_ENABLED in config.py must also be True for this to activate.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

import numpy as np

from config import (
    SAMPLE_RATE,
    VOICE_AUTH_THRESHOLD,
    VOICE_ENROLLMENT_PATH,
    VOICE_ENROLLMENT_SECONDS,
)
from utils.logger import setup_logger

logger = setup_logger(__name__)


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    a = a / (np.linalg.norm(a) + 1e-8)
    b = b / (np.linalg.norm(b) + 1e-8)
    return float(np.dot(a, b))


class VoiceAuth:
    """Speaker identity gatekeeper."""

    def __init__(self) -> None:
        self._encoder = None
        self._owner_embedding: Optional[np.ndarray] = None
        self._available = False

        self._load_encoder()
        self._load_enrollment()

    # ── Setup ─────────────────────────────────────────────────────────────────

    def _load_encoder(self) -> None:
        try:
            from resemblyzer import VoiceEncoder  # type: ignore
            self._encoder = VoiceEncoder()
            self._available = True
            logger.info("resemblyzer VoiceEncoder loaded ✓")
        except ImportError:
            logger.warning(
                "resemblyzer not installed. Voice auth disabled.\n"
                "  pip install resemblyzer"
            )
        except Exception as exc:
            logger.warning("VoiceEncoder init failed: %s", exc)

    def _load_enrollment(self) -> None:
        if not self._available:
            return
        path = VOICE_ENROLLMENT_PATH
        if path.exists():
            self._owner_embedding = np.load(str(path))
            logger.info("Owner voice embedding loaded from %s", path)
        else:
            logger.warning(
                "No voice enrollment found. Run:  python -m audio.voice_auth enroll"
            )

    # ── Embedding ─────────────────────────────────────────────────────────────

    def _audio_to_embedding(self, audio: np.ndarray) -> Optional[np.ndarray]:
        if not self._available or self._encoder is None:
            return None
        try:
            from resemblyzer import preprocess_wav  # type: ignore
            audio_f32 = audio.astype(np.float32) / 32_768.0
            wav = preprocess_wav(audio_f32, source_sr=SAMPLE_RATE)
            return self._encoder.embed_utterance(wav)
        except Exception as exc:
            logger.error("Embedding failed: %s", exc)
            return None

    # ── Public API ────────────────────────────────────────────────────────────

    def is_ready(self) -> bool:
        return self._available and self._owner_embedding is not None

    def enroll(self, audio: np.ndarray) -> bool:
        """
        Store *audio* as the owner's voice profile.
        Returns True on success.
        """
        emb = self._audio_to_embedding(audio)
        if emb is None:
            logger.error("Enrollment failed — could not compute embedding.")
            return False

        VOICE_ENROLLMENT_PATH.parent.mkdir(parents=True, exist_ok=True)
        np.save(str(VOICE_ENROLLMENT_PATH), emb)
        self._owner_embedding = emb
        logger.info("Voice enrollment saved to %s", VOICE_ENROLLMENT_PATH)
        return True

    def verify(self, audio: np.ndarray) -> bool:
        """
        Compare *audio* to the enrolled voice.
        Returns True if the speaker matches (or if auth is not ready).
        """
        if not self.is_ready():
            # Fail open — if enrollment is missing, don't lock the user out
            return True

        emb = self._audio_to_embedding(audio)
        if emb is None:
            return True  # Fail open on embedding error

        score = _cosine_similarity(emb, self._owner_embedding)
        logger.info("Voice similarity: %.3f (threshold: %.2f)", score, VOICE_AUTH_THRESHOLD)

        if score >= VOICE_AUTH_THRESHOLD:
            return True
        else:
            logger.warning("Voice mismatch — access denied (score=%.3f)", score)
            return False


# ── CLI enrollment helper ─────────────────────────────────────────────────────

def _run_enrollment() -> None:
    """Interactive enrollment: record the owner's voice and save embedding."""
    import pyaudio

    print(f"\n[Voice Auth] Enrollment — speak for {VOICE_ENROLLMENT_SECONDS} seconds.")
    print("Press Enter when ready…")
    input()
    print("Recording now — speak naturally…")

    pa = pyaudio.PyAudio()
    from config import CHANNELS, CHUNK_SIZE

    stream = pa.open(
        format=pyaudio.paInt16,
        channels=CHANNELS,
        rate=SAMPLE_RATE,
        input=True,
        frames_per_buffer=CHUNK_SIZE,
    )
    frames = []
    total_chunks = int(SAMPLE_RATE / CHUNK_SIZE * VOICE_ENROLLMENT_SECONDS)
    for _ in range(total_chunks):
        data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
        frames.append(data)

    stream.stop_stream()
    stream.close()
    pa.terminate()

    audio = np.frombuffer(b"".join(frames), dtype=np.int16)
    auth = VoiceAuth()
    success = auth.enroll(audio)
    print("Enrollment successful ✓" if success else "Enrollment failed ✗")
    print("Set VOICE_AUTH_ENABLED = True in config.py to activate.")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "enroll":
        _run_enrollment()
    else:
        print("Usage:  python -m audio.voice_auth enroll")
