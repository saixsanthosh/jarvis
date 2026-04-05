"""
brain/llm.py — Interface to a locally-running Ollama instance.

Design
──────
• Checks at startup that Ollama is reachable and the configured model exists.
• think()  → full blocking response (used for TTS pipeline).
• stream() → generator of token strings (useful for CLI debug / future UI).
• Injects the system prompt on every call so context is always correct.
"""

from __future__ import annotations

import json
from typing import Generator

import requests

from config import (
    OLLAMA_BASE_URL, OLLAMA_MODEL,
    OLLAMA_TIMEOUT, OLLAMA_MAX_TOKENS,
    SYSTEM_PROMPT,
)
from brain.memory import Message
from utils.logger import setup_logger

logger = setup_logger(__name__)

_CHAT_URL = f"{OLLAMA_BASE_URL}/api/chat"
_TAGS_URL = f"{OLLAMA_BASE_URL}/api/tags"

_FALLBACK_REPLY = (
    "I'm having a bit of trouble thinking right now. "
    "Please check that Ollama is running and try again."
)


class LLMBrain:
    """Sends conversation history to Ollama and returns a reply."""

    def __init__(self) -> None:
        self._verify_ollama()

    # ── Startup check ────────────────────────────────────────────────────────

    def _verify_ollama(self) -> None:
        try:
            resp = requests.get(_TAGS_URL, timeout=5)
            resp.raise_for_status()
            available = [m["name"] for m in resp.json().get("models", [])]
            logger.info("Ollama reachable. Models: %s", available)

            if not any(OLLAMA_MODEL in name for name in available):
                logger.warning(
                    "Model '%s' not found locally. Pull it with:\n"
                    "  ollama pull %s",
                    OLLAMA_MODEL, OLLAMA_MODEL,
                )
        except requests.exceptions.ConnectionError:
            logger.error(
                "Cannot reach Ollama at %s. Start it with:  ollama serve",
                OLLAMA_BASE_URL,
            )
        except Exception as exc:
            logger.error("Ollama check error: %s", exc)

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _build_payload(
        self,
        messages: list[Message],
        stream: bool,
        system_prompt: str | None = None,
    ) -> dict:
        return {
            "model": OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt or SYSTEM_PROMPT},
                *messages,
            ],
            "stream": stream,
            "options": {
                "temperature": 0.7,
                "num_predict": OLLAMA_MAX_TOKENS,
                "stop": ["\n\n\n"],   # prevent rambling
            },
        }

    # ── Public API ────────────────────────────────────────────────────────────

    def think(self, messages: list[Message], system_prompt: str | None = None) -> str:
        """
        Send *messages* to Ollama and return the complete reply as a string.
        Blocks until the model finishes.
        """
        payload = self._build_payload(messages, stream=False, system_prompt=system_prompt)
        try:
            resp = requests.post(_CHAT_URL, json=payload, timeout=OLLAMA_TIMEOUT)
            resp.raise_for_status()
            reply = resp.json()["message"]["content"].strip()
            logger.debug("LLM reply: %s", reply[:120])
            return reply
        except requests.exceptions.Timeout:
            logger.error("Ollama timed out after %ds", OLLAMA_TIMEOUT)
            return _FALLBACK_REPLY
        except Exception as exc:
            logger.error("LLM error: %s", exc, exc_info=True)
            return _FALLBACK_REPLY

    def stream(self, messages: list[Message], system_prompt: str | None = None) -> Generator[str, None, None]:
        """
        Stream token-by-token replies from Ollama.
        Yields string fragments as they arrive.
        Useful for future streaming TTS or a real-time UI.
        """
        payload = self._build_payload(messages, stream=True, system_prompt=system_prompt)
        try:
            with requests.post(
                _CHAT_URL,
                json=payload,
                stream=True,
                timeout=OLLAMA_TIMEOUT,
            ) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if line:
                        data = json.loads(line)
                        if data.get("done"):
                            break
                        token = data.get("message", {}).get("content", "")
                        if token:
                            yield token
        except Exception as exc:
            logger.error("Stream error: %s", exc)
            yield _FALLBACK_REPLY
