"""
commands/notes_cmd.py — Voice-driven quick notes stored in SQLite.

"Take a note: buy groceries tomorrow"
"Read my notes"
"Read my last 3 notes"
"Delete all notes"

Notes are stored alongside long-term memory in the same data/ directory.
"""

from __future__ import annotations

import sqlite3
import time
from datetime import datetime
from pathlib import Path

from config import DATA_DIR
from utils.logger import setup_logger

logger = setup_logger(__name__)

_DB_PATH = DATA_DIR / "notes.db"
_MAX_READ = 10  # max notes to read aloud at once

_SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    content  TEXT NOT NULL,
    created  REAL NOT NULL
);
"""


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


def add_note(content: str) -> str:
    """Store a new voice note."""
    content = content.strip()
    if not content:
        return "I didn't catch what to note down."
    try:
        db = _conn()
        db.execute("INSERT INTO notes (content, created) VALUES (?, ?)",
                   (content, time.time()))
        db.commit()
        count = db.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
        db.close()
        logger.info("Note saved: '%s' (total: %d)", content[:50], count)
        return f"Got it — noted. You now have {count} note{'s' if count != 1 else ''}."
    except Exception as exc:
        logger.error("Note save error: %s", exc)
        return f"Couldn't save the note: {exc}"


def read_notes(limit: int = 5) -> str:
    """Read recent notes aloud."""
    try:
        db = _conn()
        rows = db.execute(
            "SELECT content, created FROM notes ORDER BY created DESC LIMIT ?",
            (min(limit, _MAX_READ),),
        ).fetchall()
        db.close()

        if not rows:
            return "You don't have any notes yet."

        lines = [f"Here are your {'last ' + str(len(rows)) + ' ' if len(rows) > 1 else ''}note{'s' if len(rows) != 1 else ''}:"]
        for r in rows:
            ts = datetime.fromtimestamp(r["created"]).strftime("%B %d at %I:%M %p")
            lines.append(f"  {ts}: {r['content']}")
        return " ".join(lines)
    except Exception as exc:
        logger.error("Note read error: %s", exc)
        return f"Couldn't read notes: {exc}"


def count_notes() -> str:
    """Return how many notes exist."""
    try:
        db = _conn()
        count = db.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
        db.close()
        return f"You have {count} note{'s' if count != 1 else ''}."
    except Exception as exc:
        return f"Couldn't count notes: {exc}"


def delete_all_notes() -> str:
    """Delete all notes."""
    try:
        db = _conn()
        count = db.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
        db.execute("DELETE FROM notes")
        db.commit()
        db.close()
        return f"Deleted {count} note{'s' if count != 1 else ''}. Starting fresh."
    except Exception as exc:
        return f"Couldn't delete notes: {exc}"
