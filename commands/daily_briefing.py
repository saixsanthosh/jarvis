"""
commands/daily_briefing.py — "Good morning Jarvis" personalized briefing.
Combines weather, time, notes, timers, and system status.
"""
from __future__ import annotations
from datetime import datetime
from utils.logger import setup_logger

logger = setup_logger(__name__)


def get_briefing() -> str:
    parts = []
    now = datetime.now()
    greeting = "Good morning" if now.hour < 12 else "Good afternoon" if now.hour < 17 else "Good evening"
    parts.append(f"{greeting}! It's {now.strftime('%A, %B %d')} at {now.strftime('%I:%M %p')}.")

    # Weather
    try:
        from commands.weather import get_current_weather
        w = get_current_weather()
        if "couldn't" not in w.lower():
            parts.append(w)
    except Exception:
        pass

    # Pending notes
    try:
        from commands.notes_cmd import count_notes
        n = count_notes()
        if "0 note" not in n:
            parts.append(f"You have some notes pending. {n}")
    except Exception:
        pass

    # Battery
    try:
        from commands.system_stats import get_battery
        b = get_battery()
        if "No battery" not in b:
            parts.append(b)
    except Exception:
        pass

    parts.append("What would you like to do?")
    return " ".join(parts)
