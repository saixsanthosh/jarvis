"""
commands/system_control.py — OS-level actions.

All functions return a short human-readable string that Jarvis speaks back.

Adding a new app
────────────────
Insert an entry in APP_MAP:
    "myapp": {
        "Linux":   ["myapp-binary"],
        "Darwin":  ["open", "-a", "MyApp"],
        "Windows": ["myapp"],
    }

Each value is either:
  • A list of strings forming a single command, e.g. ["open", "-a", "Spotify"]
  • A list of alternative binary names to try, e.g. ["google-chrome", "chromium"]
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import webbrowser
from urllib.parse import quote_plus

from utils.logger import setup_logger

logger = setup_logger(__name__)

_SYSTEM = platform.system()   # "Linux" | "Darwin" | "Windows"

# ── App catalogue ─────────────────────────────────────────────────────────────
# Values: list of candidate binaries (Linux alternatives) OR exact arg list.
APP_MAP: dict[str, dict[str, list]] = {
    "spotify": {
        "Linux":   ["spotify", "flatpak run com.spotify.Client"],
        "Darwin":  ["open", "-a", "Spotify"],
        "Windows": ["spotify"],
    },
    "chrome": {
        "Linux":   ["google-chrome", "chromium-browser", "chromium"],
        "Darwin":  ["open", "-a", "Google Chrome"],
        "Windows": ["chrome"],
    },
    "firefox": {
        "Linux":   ["firefox"],
        "Darwin":  ["open", "-a", "Firefox"],
        "Windows": ["firefox"],
    },
    "vscode": {
        "Linux":   ["code"],
        "Darwin":  ["code"],
        "Windows": ["code"],
    },
    "cursor": {
        "Linux":   ["cursor"],
        "Darwin":  ["cursor"],
        "Windows": ["cursor"],
    },
    "terminal": {
        "Linux":   ["gnome-terminal", "kitty", "alacritty", "xterm", "konsole"],
        "Darwin":  ["open", "-a", "Terminal"],
        "Windows": ["wt", "cmd"],
    },
    "files": {
        "Linux":   ["nautilus", "dolphin", "thunar", "nemo"],
        "Darwin":  ["open", "."],
        "Windows": ["explorer"],
    },
    "calculator": {
        "Linux":   ["gnome-calculator", "kcalc", "galculator"],
        "Darwin":  ["open", "-a", "Calculator"],
        "Windows": ["calc"],
    },
    "discord": {
        "Linux":   ["discord"],
        "Darwin":  ["open", "-a", "Discord"],
        "Windows": ["discord"],
    },
    "slack": {
        "Linux":   ["slack"],
        "Darwin":  ["open", "-a", "Slack"],
        "Windows": ["slack"],
    },
    "obsidian": {
        "Linux":   ["obsidian"],
        "Darwin":  ["open", "-a", "Obsidian"],
        "Windows": ["obsidian"],
    },
    "telegram": {
        "Linux":   ["telegram-desktop", "Telegram"],
        "Darwin":  ["open", "-a", "Telegram"],
        "Windows": ["telegram"],
    },
}

# Friendly aliases → canonical key
_ALIASES: dict[str, str] = {
    "vs code": "vscode",
    "visual studio code": "vscode",
    "visual studio": "vscode",
    "google chrome": "chrome",
    "file manager": "files",
    "file explorer": "files",
    "finder": "files",
    "notepad": "vscode",
    "code editor": "vscode",
}

# Process names for pkill / taskkill
_PROC_NAMES: dict[str, list[str]] = {
    "spotify":    ["spotify"],
    "chrome":     ["chrome", "google-chrome", "chromium"],
    "firefox":    ["firefox"],
    "vscode":     ["code"],
    "cursor":     ["cursor"],
    "discord":    ["discord"],
    "slack":      ["slack"],
    "obsidian":   ["obsidian"],
    "telegram":   ["telegram-desktop", "Telegram"],
}


# ── helpers ───────────────────────────────────────────────────────────────────

def _resolve_key(name: str) -> str:
    name = name.lower().strip()
    return _ALIASES.get(name, name)


def _launch(cmd: list[str]) -> bool:
    """Try to launch a command detached from the Python process."""
    try:
        subprocess.Popen(cmd, start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except FileNotFoundError:
        return False
    except Exception as exc:
        logger.error("Launch failed %s: %s", cmd, exc)
        return False


# ── Public functions ──────────────────────────────────────────────────────────

def open_app(app_name: str) -> str:
    key = _resolve_key(app_name)
    entry = APP_MAP.get(key)

    if entry is None:
        return (
            f"I don't have '{app_name}' in my app list. "
            "You can add it to commands/system_control.py."
        )

    candidates = entry.get(_SYSTEM, [])
    if not candidates:
        return f"Opening {app_name} is not supported on {_SYSTEM} yet."

    # If the first element looks like a flag (e.g. "open", "-a") → single command
    if candidates[0].startswith("-") or len(candidates) > 1 and candidates[1].startswith("-"):
        if _launch(candidates):
            logger.info("Opened %s: %s", app_name, candidates)
            return f"Opening {app_name}."
        return f"Failed to open {app_name}."

    # Otherwise candidates is a list of alternative binary names to try
    for binary_str in candidates:
        binary = binary_str.split()[0]
        if shutil.which(binary):
            cmd = binary_str.split()
            if _launch(cmd):
                logger.info("Opened %s via %s", app_name, binary)
                return f"Opening {app_name}."

    return (
        f"I couldn't find {app_name} installed. "
        "Make sure it's on your PATH."
    )


def close_app(app_name: str) -> str:
    key = _resolve_key(app_name)
    targets = _PROC_NAMES.get(key, [key])
    killed_any = False

    for target in targets:
        try:
            if _SYSTEM == "Windows":
                r = subprocess.run(
                    ["taskkill", "/f", "/im", f"{target}.exe"],
                    capture_output=True,
                )
            else:
                r = subprocess.run(["pkill", "-f", target], capture_output=True)

            if r.returncode == 0:
                killed_any = True
                logger.info("Killed process: %s", target)
        except Exception as exc:
            logger.error("Error killing %s: %s", target, exc)

    if killed_any:
        return f"Closed {app_name}."
    return f"Couldn't find {app_name} running."


def search_youtube(query: str) -> str:
    url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
    webbrowser.open(url)
    logger.info("YouTube search: %s", query)
    return f"Searching YouTube for {query}."


def search_google(query: str) -> str:
    url = f"https://www.google.com/search?q={quote_plus(query)}"
    webbrowser.open(url)
    logger.info("Google search: %s", query)
    return f"Searching Google for {query}."


def open_url(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    webbrowser.open(url)
    return f"Opening {url}."


def set_volume(level: int) -> str:
    level = max(0, min(100, level))
    try:
        if _SYSTEM == "Linux":
            subprocess.run(
                ["amixer", "-q", "sset", "Master", f"{level}%"],
                check=True,
            )
        elif _SYSTEM == "Darwin":
            subprocess.run(
                ["osascript", "-e", f"set volume output volume {level}"],
                check=True,
            )
        elif _SYSTEM == "Windows":
            # Requires nircmd: https://www.nirsoft.net/utils/nircmd.html
            subprocess.run(
                ["nircmd", "setsysvolume", str(int(level * 655.35))],
                check=True,
            )
        return f"Volume set to {level} percent."
    except Exception as exc:
        logger.error("Volume error: %s", exc)
        return f"Couldn't change the volume: {exc}"
