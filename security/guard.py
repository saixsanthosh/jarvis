"""
security/guard.py — Security layer between voice input and execution.

Two layers of protection
────────────────────────
1. Dangerous-verb detection   — if the command contains a guarded verb
   (delete, format, kill, wipe …) Jarvis asks "Are you sure? Say yes to confirm."
   The user has CONFIRMATION_TIMEOUT seconds to speak "yes".

2. Voice-auth gate (optional) — if VOICE_AUTH_ENABLED=True and resemblyzer
   is installed, Jarvis verifies the speaker's identity before every active
   conversation session.

The guard is NOT a security perimeter against a determined attacker —
it is a safety net against accidental misfire ("delete Chrome" when you
meant "open Chrome") and against someone shouting commands while you're
away from the mic.
"""

from __future__ import annotations

import time
from typing import Callable, Optional

from config import (
    GUARDED_VERBS,
    CONFIRMATION_TIMEOUT,
    CONFIRMATION_PHRASE,
    DENIAL_PHRASE,
)
from utils.logger import setup_logger

logger = setup_logger(__name__)


class SecurityGuard:
    """
    Pre-execution safety filter.

    Parameters
    ──────────
    speak_fn    : callable that synthesises and plays a string
    listen_fn   : callable that records until silence and returns np.ndarray
    transcribe_fn : callable that transcribes np.ndarray → str
    """

    def __init__(
        self,
        speak_fn: Callable[[str], None],
        listen_fn: Optional[Callable] = None,
        transcribe_fn: Optional[Callable] = None,
    ) -> None:
        self._speak      = speak_fn
        self._listen     = listen_fn
        self._transcribe = transcribe_fn
        self._confirmation_available = listen_fn is not None and transcribe_fn is not None

    # ── Public API ────────────────────────────────────────────────────────────

    def check(self, command_text: str) -> tuple[bool, str]:
        """
        Inspect *command_text* and decide whether to proceed.

        Returns
        ───────
        (True,  "")             — safe to execute
        (True,  "")             — dangerous but user confirmed
        (False, reason_str)     — blocked (denied or timed out)
        """
        if self._is_guarded(command_text):
            return self._request_confirmation(command_text)
        return True, ""

    # ── Internal ──────────────────────────────────────────────────────────────

    def _is_guarded(self, text: str) -> bool:
        t = text.lower()
        return any(verb in t for verb in GUARDED_VERBS)

    def _request_confirmation(self, command_text: str) -> tuple[bool, str]:
        logger.warning("Guarded command detected: '%s'", command_text)

        if not self._confirmation_available:
            # No confirmation mechanism — block the command
            msg = (
                "That sounds like a potentially dangerous command. "
                "Confirmation listening is not configured, so I've blocked it."
            )
            logger.info("Blocked (no listen/transcribe fn): %s", command_text)
            return False, msg

        self._speak(
            "That command sounds destructive. "
            f"Say '{CONFIRMATION_PHRASE}' to confirm, or '{DENIAL_PHRASE}' to cancel."
        )

        deadline = time.monotonic() + CONFIRMATION_TIMEOUT
        while time.monotonic() < deadline:
            try:
                audio = self._listen()
                text  = self._transcribe(audio).lower().strip()
                logger.debug("Confirmation heard: '%s'", text)

                if CONFIRMATION_PHRASE in text:
                    logger.info("Command confirmed by voice: %s", command_text)
                    return True, ""

                if DENIAL_PHRASE in text or any(p in text for p in ["cancel", "abort", "stop"]):
                    return False, "Got it, cancelled."

            except Exception as exc:
                logger.error("Confirmation listen error: %s", exc)
                break

        return False, "Confirmation timed out — command cancelled for safety."
