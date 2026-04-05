"""
commands/clipboard_cmd.py — Read or set the system clipboard.

Uses the stdlib `tkinter` on Linux/Windows, and `pbpaste/pbcopy` on macOS.
Falls back to `pyperclip` if installed.
"""

from __future__ import annotations

import platform
import subprocess

from utils.logger import setup_logger

logger = setup_logger(__name__)

_SYSTEM = platform.system()
_MAX_READ_CHARS = 400  # cap spoken length


def _read_clipboard() -> str:
    # macOS
    if _SYSTEM == "Darwin":
        result = subprocess.run(["pbpaste"], capture_output=True, text=True)
        return result.stdout

    # Linux — try xclip, then xsel, then tkinter
    if _SYSTEM == "Linux":
        for cmd in [["xclip", "-selection", "clipboard", "-o"],
                    ["xsel", "--clipboard", "--output"]]:
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
                if result.returncode == 0:
                    return result.stdout
            except FileNotFoundError:
                continue

    # Windows
    if _SYSTEM == "Windows":
        try:
            import win32clipboard  # type: ignore
            win32clipboard.OpenClipboard()
            data = win32clipboard.GetClipboardData()
            win32clipboard.CloseClipboard()
            return data
        except ImportError:
            pass

    # Universal fallback: pyperclip
    try:
        import pyperclip  # type: ignore
        return pyperclip.paste()
    except ImportError:
        pass

    # Last resort: tkinter
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        text = root.clipboard_get()
        root.destroy()
        return text
    except Exception:
        pass

    return ""


def read_clipboard() -> str:
    """Read clipboard and return a spoken-style summary."""
    text = _read_clipboard().strip()

    if not text:
        return "The clipboard is empty."

    if len(text) <= _MAX_READ_CHARS:
        logger.info("Clipboard read: %d chars", len(text))
        return f"Your clipboard says: {text}"

    preview = text[:_MAX_READ_CHARS]
    remaining = len(text) - _MAX_READ_CHARS
    return (
        f"The clipboard has {len(text)} characters. Here's the start: "
        f"{preview}... and {remaining} more characters."
    )


def clipboard_word_count() -> str:
    text = _read_clipboard().strip()
    if not text:
        return "The clipboard is empty."
    words = len(text.split())
    chars = len(text)
    return f"Clipboard contains {words} words and {chars} characters."
