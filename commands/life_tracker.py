"""
commands/life_tracker.py — Shopping list, expense tracker, habit tracker.
All stored in SQLite for persistence across sessions.
"""
from __future__ import annotations
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from config import DATA_DIR
from utils.logger import setup_logger

logger = setup_logger(__name__)

_DB_PATH = DATA_DIR / "life.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS shopping (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item TEXT NOT NULL,
    added REAL NOT NULL,
    done INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    amount REAL NOT NULL,
    category TEXT DEFAULT 'general',
    description TEXT,
    created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS habits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS habit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    habit_name TEXT NOT NULL,
    logged REAL NOT NULL
);
"""

def _conn():
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn

# ── Shopping List ─────────────────────────────────────────────────────────────

def add_to_shopping(item: str) -> str:
    db = _conn()
    db.execute("INSERT INTO shopping (item, added) VALUES (?, ?)", (item.strip(), time.time()))
    db.commit()
    count = db.execute("SELECT COUNT(*) FROM shopping WHERE done=0").fetchone()[0]
    db.close()
    return f"Added {item} to your shopping list. You have {count} item{'s' if count != 1 else ''} total."

def read_shopping_list() -> str:
    db = _conn()
    rows = db.execute("SELECT item FROM shopping WHERE done=0 ORDER BY added DESC").fetchall()
    db.close()
    if not rows:
        return "Your shopping list is empty."
    items = [r["item"] for r in rows]
    return f"Your shopping list has {len(items)} items: {', '.join(items)}."

def clear_shopping_list() -> str:
    db = _conn()
    count = db.execute("SELECT COUNT(*) FROM shopping WHERE done=0").fetchone()[0]
    db.execute("DELETE FROM shopping")
    db.commit()
    db.close()
    return f"Cleared {count} items from your shopping list."

def remove_from_shopping(item: str) -> str:
    db = _conn()
    cur = db.execute("DELETE FROM shopping WHERE LOWER(item) LIKE ? AND done=0", (f"%{item.lower()}%",))
    db.commit()
    db.close()
    if cur.rowcount > 0:
        return f"Removed {item} from your shopping list."
    return f"Couldn't find {item} on your list."

# ── Expense Tracker ───────────────────────────────────────────────────────────

def log_expense(amount: float, description: str = "", category: str = "general") -> str:
    db = _conn()
    db.execute("INSERT INTO expenses (amount, category, description, created) VALUES (?, ?, ?, ?)",
               (amount, category.lower(), description, time.time()))
    db.commit()
    # This week's total
    week_ago = time.time() - 7 * 86400
    total = db.execute("SELECT SUM(amount) FROM expenses WHERE created > ?", (week_ago,)).fetchone()[0] or 0
    db.close()
    msg = f"Logged {amount} for {description or category}." if description else f"Logged {amount} in {category}."
    msg += f" This week's total: {total:.0f}."
    return msg

def get_expenses(period: str = "week") -> str:
    db = _conn()
    if period == "today":
        start = datetime.now().replace(hour=0, minute=0, second=0).timestamp()
    elif period == "month":
        start = time.time() - 30 * 86400
    else:
        start = time.time() - 7 * 86400

    rows = db.execute("SELECT amount, category, description FROM expenses WHERE created > ? ORDER BY created DESC", (start,)).fetchall()
    total = sum(r["amount"] for r in rows)
    db.close()

    if not rows:
        return f"No expenses recorded this {period}."

    cats = {}
    for r in rows:
        c = r["category"]
        cats[c] = cats.get(c, 0) + r["amount"]

    breakdown = ", ".join(f"{c}: {v:.0f}" for c, v in cats.items())
    return f"This {period} you spent {total:.0f} total. Breakdown: {breakdown}."

def clear_expenses() -> str:
    db = _conn()
    db.execute("DELETE FROM expenses")
    db.commit()
    db.close()
    return "All expenses cleared."

# ── Habit Tracker ─────────────────────────────────────────────────────────────

def log_habit(name: str) -> str:
    db = _conn()
    name = name.lower().strip()
    # Create habit if not exists
    db.execute("INSERT OR IGNORE INTO habits (name, created) VALUES (?, ?)", (name, time.time()))
    db.execute("INSERT INTO habit_logs (habit_name, logged) VALUES (?, ?)", (name, time.time()))
    db.commit()

    # Calculate streak
    streak = _get_streak(db, name)
    total = db.execute("SELECT COUNT(*) FROM habit_logs WHERE habit_name=?", (name,)).fetchone()[0]
    db.close()

    msg = f"Logged {name}! Total: {total} times."
    if streak > 1:
        msg += f" You're on a {streak}-day streak!"
    return msg

def get_habits() -> str:
    db = _conn()
    habits = db.execute("SELECT name FROM habits ORDER BY name").fetchall()
    if not habits:
        db.close()
        return "No habits tracked yet. Say 'log workout' to start."

    lines = ["Your tracked habits:"]
    for h in habits:
        streak = _get_streak(db, h["name"])
        total = db.execute("SELECT COUNT(*) FROM habit_logs WHERE habit_name=?", (h["name"],)).fetchone()[0]
        streak_str = f", {streak}-day streak" if streak > 1 else ""
        lines.append(f"{h['name']}: {total} total{streak_str}")
    db.close()
    return " ".join(lines)

def _get_streak(db, name: str) -> int:
    rows = db.execute(
        "SELECT DISTINCT DATE(logged, 'unixepoch', 'localtime') as d FROM habit_logs WHERE habit_name=? ORDER BY d DESC",
        (name,)
    ).fetchall()
    if not rows:
        return 0
    streak = 1
    today = datetime.now().strftime("%Y-%m-%d")
    if rows[0]["d"] != today:
        return 0
    for i in range(1, len(rows)):
        prev = datetime.strptime(rows[i-1]["d"], "%Y-%m-%d")
        curr = datetime.strptime(rows[i]["d"], "%Y-%m-%d")
        if (prev - curr).days == 1:
            streak += 1
        else:
            break
    return streak
