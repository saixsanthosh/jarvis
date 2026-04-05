"""
commands/file_finder.py — Find and open files by voice.
"Find my resume" / "Open the budget spreadsheet" / "Find files named report"
"""
from __future__ import annotations
import os
import platform
import subprocess
from pathlib import Path
from utils.logger import setup_logger

logger = setup_logger(__name__)

_SYSTEM = platform.system()
_HOME = Path.home()

_SEARCH_DIRS = [
    _HOME / "Desktop",
    _HOME / "Documents",
    _HOME / "Downloads",
    _HOME / "Pictures",
    _HOME / "Videos",
    _HOME / "Music",
    _HOME,
]

_COMMON_EXTENSIONS = {
    "document": [".docx", ".doc", ".pdf", ".txt", ".odt", ".rtf"],
    "spreadsheet": [".xlsx", ".xls", ".csv", ".ods"],
    "presentation": [".pptx", ".ppt", ".odp"],
    "image": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp"],
    "video": [".mp4", ".avi", ".mkv", ".mov", ".wmv"],
    "code": [".py", ".js", ".html", ".css", ".java", ".cpp", ".c", ".ts"],
}


def find_files(query: str, max_results: int = 5) -> str:
    query_lower = query.lower().strip()
    results = []
    
    for search_dir in _SEARCH_DIRS:
        if not search_dir.exists():
            continue
        try:
            for root, dirs, files in os.walk(search_dir):
                # Skip hidden directories
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                depth = root.replace(str(search_dir), '').count(os.sep)
                if depth > 3:
                    dirs.clear()
                    continue
                    
                for fname in files:
                    if query_lower in fname.lower():
                        full = os.path.join(root, fname)
                        results.append(full)
                        if len(results) >= max_results:
                            break
                if len(results) >= max_results:
                    break
        except PermissionError:
            continue
        if len(results) >= max_results:
            break

    if not results:
        return f"I couldn't find any files matching '{query}'."

    if len(results) == 1:
        return f"Found it: {results[0]}. Want me to open it?"

    lines = [f"Found {len(results)} files matching '{query}':"]
    for i, r in enumerate(results, 1):
        name = os.path.basename(r)
        folder = os.path.dirname(r).replace(str(_HOME), "~")
        lines.append(f"{i}. {name} in {folder}")
    return " ".join(lines)


def open_file(path: str) -> str:
    path = os.path.expanduser(path.strip())
    if not os.path.exists(path):
        return f"File not found: {path}"
    try:
        if _SYSTEM == "Windows":
            os.startfile(path)
        elif _SYSTEM == "Darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
        return f"Opening {os.path.basename(path)}."
    except Exception as exc:
        return f"Couldn't open the file: {exc}"


def list_recent_downloads(count: int = 5) -> str:
    dl = _HOME / "Downloads"
    if not dl.exists():
        return "Downloads folder not found."
    
    files = sorted(dl.iterdir(), key=lambda f: f.stat().st_mtime if f.is_file() else 0, reverse=True)
    files = [f for f in files if f.is_file()][:count]
    
    if not files:
        return "No files in Downloads."
    
    lines = [f"Your {len(files)} most recent downloads:"]
    for f in files:
        lines.append(f"{f.name}")
    return " ".join(lines)
