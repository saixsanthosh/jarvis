"""
brain/memory.py — Short-term conversation context.

Keeps a rolling window of the last N user+assistant message pairs.
This is fed directly into the Ollama /api/chat endpoint as the
`messages` list, giving the LLM conversational continuity.
"""

from __future__ import annotations

from collections import deque
from typing import TypedDict

from config import MAX_CONTEXT_MESSAGES
from utils.logger import setup_logger

logger = setup_logger(__name__)


class Message(TypedDict):
    role: str    # "user" | "assistant"
    content: str


class ConversationMemory:
    """Rolling-window message buffer for multi-turn conversation."""

    def __init__(self) -> None:
        # maxlen keeps memory bounded automatically
        self._buf: deque[Message] = deque(maxlen=MAX_CONTEXT_MESSAGES)

    # ── write ─────────────────────────────────────────────────────────────────

    def add_user(self, text: str) -> None:
        self._buf.append({"role": "user", "content": text})

    def add_assistant(self, text: str) -> None:
        self._buf.append({"role": "assistant", "content": text})

    # ── read ──────────────────────────────────────────────────────────────────

    def get_history(self) -> list[Message]:
        """Return message list suitable for the Ollama chat API."""
        return list(self._buf)

    def clear(self) -> None:
        self._buf.clear()
        logger.info("Conversation memory cleared.")

    # ── dunder ────────────────────────────────────────────────────────────────

    def __len__(self) -> int:
        return len(self._buf)

    def __repr__(self) -> str:
        return f"<ConversationMemory messages={len(self)}>"
