"""
brain/summarizer.py — Compress long conversation history into a short summary.

When the rolling message buffer hits SUMMARIZE_AFTER_N_MESSAGES the
Summarizer asks the LLM to distill the conversation into 2-3 sentences,
stores that in long-term memory, and resets the short-term buffer to just
the summary as a single "system" note.

This prevents context-window bloat while preserving continuity.
"""

from __future__ import annotations

import requests

from config import OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT
from utils.logger import setup_logger

logger = setup_logger(__name__)

_SUMMARIZE_PROMPT = (
    "Summarise the following conversation in 2-3 sentences. "
    "Focus only on facts, decisions, and user preferences that are worth remembering. "
    "Be extremely concise. Do not use first-person. "
    "Reply with only the summary, nothing else.\n\n"
    "Conversation:\n{conversation}"
)


class Summarizer:
    """Uses the local LLM to compress conversation history on demand."""

    @staticmethod
    def _format_conversation(messages: list[dict]) -> str:
        lines = []
        for m in messages:
            role = "User" if m["role"] == "user" else "Jarvis"
            lines.append(f"{role}: {m['content']}")
        return "\n".join(lines)

    def summarize(self, messages: list[dict]) -> str:
        """
        Ask the LLM to summarise *messages*.
        Returns a short summary string, or an empty string on failure.
        """
        if not messages:
            return ""

        conversation_text = self._format_conversation(messages)
        prompt = _SUMMARIZE_PROMPT.format(conversation=conversation_text)

        try:
            resp = requests.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "num_predict": 120,
                    },
                },
                timeout=OLLAMA_TIMEOUT,
            )
            resp.raise_for_status()
            summary = resp.json().get("response", "").strip()
            logger.info("Conversation summarised (%d chars)", len(summary))
            return summary
        except Exception as exc:
            logger.error("Summarisation failed: %s", exc)
            return ""

    def should_summarize(self, message_count: int) -> bool:
        from config import SUMMARIZE_AFTER_N_MESSAGES
        return message_count >= SUMMARIZE_AFTER_N_MESSAGES
