"""
commands/timers.py — In-process timer and reminder engine.

Each timer runs as a daemon thread that sleeps for the requested duration
then calls the speak_fn callback to deliver the spoken reminder.

Usage
─────
    mgr = TimerManager(speak_fn=speaker.speak)
    mgr.set_timer(seconds=300, label="pasta")  # "Remind me in 5 minutes — pasta"
    mgr.list_timers()                          # "You have 1 active timer…"
    mgr.cancel_all()
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Callable

from utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class _Timer:
    id: int
    label: str
    duration: float          # seconds
    fire_at: float           # monotonic timestamp
    thread: threading.Thread = field(repr=False)
    cancelled: bool = False


class TimerManager:
    """Manages multiple concurrent timers with spoken alerts."""

    def __init__(self, speak_fn: Callable[[str], None]) -> None:
        self._speak = speak_fn
        self._timers: dict[int, _Timer] = {}
        self._lock = threading.Lock()
        self._next_id = 1

    # ── Public API ────────────────────────────────────────────────────────────

    def set_timer(self, seconds: float, label: str = "timer") -> str:
        """Schedule a spoken reminder in *seconds* seconds."""
        if seconds <= 0:
            return "That doesn't sound like a valid duration."

        timer_id = self._next_id
        self._next_id += 1
        fire_at = time.monotonic() + seconds

        t = threading.Thread(
            target=self._fire,
            args=(timer_id, label, seconds),
            name=f"timer-{timer_id}",
            daemon=True,
        )
        timer = _Timer(
            id=timer_id,
            label=label,
            duration=seconds,
            fire_at=fire_at,
            thread=t,
        )
        with self._lock:
            self._timers[timer_id] = timer
        t.start()

        human = _seconds_to_human(seconds)
        logger.info("Timer #%d set: '%s' in %s", timer_id, label, human)
        return f"Timer set. I'll remind you about '{label}' in {human}."

    def list_timers(self) -> str:
        with self._lock:
            active = [t for t in self._timers.values() if not t.cancelled]

        if not active:
            return "You have no active timers."

        lines = [f"You have {len(active)} active timer(s):"]
        now = time.monotonic()
        for t in active:
            remaining = max(0.0, t.fire_at - now)
            lines.append(f"  Timer #{t.id} '{t.label}' — {_seconds_to_human(remaining)} remaining")
        return "\n".join(lines)

    def cancel_timer(self, timer_id: int) -> str:
        with self._lock:
            t = self._timers.get(timer_id)
        if t is None:
            return f"No timer #{timer_id} found."
        t.cancelled = True
        logger.info("Timer #%d cancelled.", timer_id)
        return f"Timer #{timer_id} '{t.label}' cancelled."

    def cancel_all(self) -> str:
        with self._lock:
            for t in self._timers.values():
                t.cancelled = True
            count = len(self._timers)
            self._timers.clear()
        return f"Cancelled {count} timer(s)." if count else "No timers to cancel."

    # ── Internal ──────────────────────────────────────────────────────────────

    def _fire(self, timer_id: int, label: str, seconds: float) -> None:
        """Sleep until the timer fires, then speak the reminder."""
        time.sleep(seconds)
        with self._lock:
            t = self._timers.get(timer_id)
            if t is None or t.cancelled:
                return
            del self._timers[timer_id]

        logger.info("Timer #%d fired: '%s'", timer_id, label)
        self._speak(f"Timer alert! {label} — your {_seconds_to_human(seconds)} timer is up.")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _seconds_to_human(seconds: float) -> str:
    """Convert seconds to a natural English duration string."""
    s = int(seconds)
    if s < 60:
        return f"{s} second{'s' if s != 1 else ''}"
    m, s = divmod(s, 60)
    if s == 0:
        return f"{m} minute{'s' if m != 1 else ''}"
    return f"{m} minute{'s' if m != 1 else ''} and {s} second{'s' if s != 1 else ''}"


def parse_duration(text: str) -> float | None:
    """
    Parse a natural-language duration into seconds.
    Examples:
        "5 minutes"          → 300.0
        "2 hours 30 minutes" → 9000.0
        "90 seconds"         → 90.0
    Returns None if no duration found.
    """
    import re
    total = 0.0
    patterns = [
        (r"(\d+(?:\.\d+)?)\s*hour", 3600),
        (r"(\d+(?:\.\d+)?)\s*(?:minute|min)", 60),
        (r"(\d+(?:\.\d+)?)\s*second", 1),
    ]
    found = False
    for pat, mult in patterns:
        m = re.search(pat, text, re.I)
        if m:
            total += float(m.group(1)) * mult
            found = True
    return total if found else None
