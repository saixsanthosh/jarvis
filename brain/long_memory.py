"""
brain/long_memory.py — Persistent long-term memory backed by SQLite.

Stores two kinds of data
────────────────────────
1. Facts   — explicit key/value pairs extracted from conversation
             ("my name is Alex", "I use Python", "prefer dark mode")
2. Sessions — plain-text summaries of past conversations, auto-generated

On every LLM call the most relevant facts are prepended to the system prompt
so Jarvis remembers things across restarts.

Fact extraction happens via lightweight heuristics (no extra LLM call):
- "my name is X"  →  fact("name", X)
- "I work at X"   →  fact("employer", X)
- "I prefer X"    →  fact("preference:X", "yes")
- etc.

The schema is intentionally simple — one table for facts, one for sessions.
"""

from __future__ import annotations

import re
import sqlite3
import time
from pathlib import Path
from typing import Optional

from config import LTM_DB_PATH, LTM_MAX_FACTS, LTM_RECALL_COUNT
from utils.logger import setup_logger

logger = setup_logger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS facts (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    key       TEXT NOT NULL,
    value     TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    created   REAL NOT NULL,
    accessed  REAL NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_facts_key ON facts(key);

CREATE TABLE IF NOT EXISTS sessions (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    summary  TEXT NOT NULL,
    created  REAL NOT NULL
);
"""

# Heuristic extraction patterns: (key_template, group_index, regex)
_EXTRACT_PATTERNS: list[tuple[str, int, re.Pattern]] = [
    ("name",           1, re.compile(r"my name is ([A-Z][a-z]+)", re.I)),
    ("location",       1, re.compile(r"i(?:'m| am) (?:in|from|based in) ([A-Za-z ,]+?)(?:\.|,|$)", re.I)),
    ("job",            1, re.compile(r"i (?:work as|am) (?:a |an )?([a-z ]+?)(?:\.|,|$)", re.I)),
    ("employer",       1, re.compile(r"i work (?:at|for) ([A-Za-z0-9 ]+?)(?:\.|,|$)", re.I)),
    ("language",       1, re.compile(r"i (?:use|prefer|code in) ([Pp]ython|[Rr]ust|[Gg]o|[Tt]ype[Ss]cript|[Jj]ava[Ss]cript|[Cc]\+\+|[Cc]#)", re.I)),
    ("os",             1, re.compile(r"i(?:'m| am) (?:using|on) (ubuntu|debian|arch|mac(?:os)?|windows)", re.I)),
]


class LongMemory:
    """Persistent fact store + session history."""

    def __init__(self, db_path: Path = LTM_DB_PATH) -> None:
        self._path = db_path
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
        count = self._conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        logger.info("LongMemory ready — %d facts stored at %s", count, db_path)

    # ── Read ──────────────────────────────────────────────────────────────────

    def get_all_facts(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT key, value FROM facts ORDER BY accessed DESC LIMIT ?",
            (LTM_RECALL_COUNT,),
        ).fetchall()
        return [{"key": r["key"], "value": r["value"]} for r in rows]

    def get_context_prefix(self) -> str:
        """Build a compact context string to prepend to each LLM system prompt."""
        facts = self.get_all_facts()
        if not facts:
            return ""
        lines = ["Known facts about the user:"]
        for f in facts:
            lines.append(f"  - {f['key']}: {f['value']}")
        return "\n".join(lines)

    def search(self, query: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT key, value FROM facts WHERE key LIKE ? OR value LIKE ? LIMIT 5",
            (f"%{query}%", f"%{query}%"),
        ).fetchall()
        return [{"key": r["key"], "value": r["value"]} for r in rows]

    # ── Write ─────────────────────────────────────────────────────────────────

    def store_fact(self, key: str, value: str, confidence: float = 1.0) -> None:
        now = time.time()
        self._conn.execute(
            """INSERT INTO facts (key, value, confidence, created, accessed)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET
                   value=excluded.value,
                   confidence=excluded.confidence,
                   accessed=excluded.accessed""",
            (key.lower().strip(), value.strip(), confidence, now, now),
        )
        self._conn.commit()
        # Enforce max size
        self._conn.execute(
            "DELETE FROM facts WHERE id NOT IN "
            "(SELECT id FROM facts ORDER BY accessed DESC LIMIT ?)",
            (LTM_MAX_FACTS,),
        )
        self._conn.commit()
        logger.debug("Stored fact: %s = %s", key, value)

    def store_session_summary(self, summary: str) -> None:
        self._conn.execute(
            "INSERT INTO sessions (summary, created) VALUES (?, ?)",
            (summary, time.time()),
        )
        self._conn.commit()
        logger.info("Session summary stored (%d chars)", len(summary))

    def touch_fact(self, key: str) -> None:
        """Update the 'accessed' timestamp to boost recency score."""
        self._conn.execute(
            "UPDATE facts SET accessed=? WHERE key=?",
            (time.time(), key.lower()),
        )
        self._conn.commit()

    # ── Extraction ────────────────────────────────────────────────────────────

    def maybe_extract_and_store(self, user_text: str) -> list[str]:
        """
        Heuristically scan *user_text* for facts worth remembering.
        Returns list of stored keys (empty if nothing found).
        """
        stored = []
        for key, group, pattern in _EXTRACT_PATTERNS:
            m = pattern.search(user_text)
            if m:
                value = m.group(group).strip().rstrip(".,;")
                self.store_fact(key, value, confidence=0.9)
                stored.append(key)
        return stored

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def forget(self, key: str) -> bool:
        cur = self._conn.execute("DELETE FROM facts WHERE key=?", (key.lower(),))
        self._conn.commit()
        return cur.rowcount > 0

    def clear_all(self) -> None:
        self._conn.execute("DELETE FROM facts")
        self._conn.execute("DELETE FROM sessions")
        self._conn.commit()
        logger.info("All long-term memory cleared.")

    def close(self) -> None:
        self._conn.close()
