"""
jarvis_app.pyw — Windows Desktop Application (background service).

Run this file to start Jarvis as a background app:
  - Starts Ollama automatically
  - Runs in system tray (small icon near clock)
  - Auto-restarts on crash
  - Right-click tray icon for controls
  - Logs everything to data/jarvis_app.log

Double-click this file or run: pythonw jarvis_app.pyw
The .pyw extension means NO console window appears.
"""

from __future__ import annotations

import os
import sys
import time
import signal
import subprocess
import threading
import traceback
from pathlib import Path
from datetime import datetime

# Add project root to path
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ".")

from config import DATA_DIR
from utils.logger import setup_logger

logger = setup_logger("jarvis_app")

# ── App-level log file ────────────────────────────────────────────────────────
_APP_LOG = DATA_DIR / "jarvis_app.log"

def _log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}\n"
    try:
        with open(_APP_LOG, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass
    print(line.strip())


class JarvisDesktopApp:
    """
    Desktop application wrapper for Jarvis.
    Manages Ollama, crash recovery, and system tray.
    """

    MAX_RESTARTS = 5
    RESTART_DELAY = 3  # seconds between restarts
    OLLAMA_STARTUP_WAIT = 5  # seconds to wait for Ollama

    def __init__(self):
        self._running = True
        self._jarvis = None
        self._restart_count = 0
        self._ollama_process = None
        self._tray_icon = None

    # ── Ollama management ─────────────────────────────────────────────────────

    def _is_ollama_running(self) -> bool:
        """Check if Ollama server is already running."""
        try:
            import requests
            r = requests.get("http://localhost:11434/api/tags", timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    def _start_ollama(self) -> bool:
        """Start Ollama server if not running."""
        if self._is_ollama_running():
            _log("Ollama already running ✓")
            return True

        _log("Starting Ollama server...")
        try:
            # Try to find ollama
            import shutil
            ollama_path = shutil.which("ollama")
            if not ollama_path:
                # Common Windows install paths
                for p in [
                    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe"),
                    os.path.expandvars(r"%LOCALAPPDATA%\Ollama\ollama.exe"),
                    r"C:\Program Files\Ollama\ollama.exe",
                    r"C:\Program Files (x86)\Ollama\ollama.exe",
                ]:
                    if os.path.exists(p):
                        ollama_path = p
                        break

            if not ollama_path:
                _log("ERROR: Ollama not found. Install from https://ollama.com/download")
                return False

            self._ollama_process = subprocess.Popen(
                [ollama_path, "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            _log(f"Ollama started (PID: {self._ollama_process.pid})")

            # Wait for it to be ready
            for i in range(10):
                time.sleep(1)
                if self._is_ollama_running():
                    _log("Ollama ready ✓")
                    return True

            _log("WARNING: Ollama started but not responding yet")
            return True  # Still try to proceed

        except Exception as exc:
            _log(f"ERROR starting Ollama: {exc}")
            return False

    # ── System tray ───────────────────────────────────────────────────────────

    def _start_tray(self) -> None:
        """Start system tray icon in a separate thread."""
        try:
            import pystray
            from PIL import Image, ImageDraw
        except ImportError:
            _log("pystray/Pillow not installed — no tray icon")
            return

        def _make_icon(color="#3ddc97"):
            img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            draw.ellipse([8, 8, 56, 56], fill=color)
            # Draw "J" in center
            try:
                draw.text((22, 14), "J", fill="white")
            except Exception:
                pass
            return img

        def on_wake(icon, item):
            _log("Tray: Manual wake requested")

        def on_restart(icon, item):
            _log("Tray: Restart requested")
            self._restart_jarvis()

        def on_quit(icon, item):
            _log("Tray: Quit requested")
            self._running = False
            icon.stop()
            self._cleanup()
            os._exit(0)

        def on_open_log(icon, item):
            os.startfile(str(_APP_LOG)) if sys.platform == "win32" else None

        def on_open_folder(icon, item):
            folder = os.path.dirname(os.path.abspath(__file__))
            if sys.platform == "win32":
                os.startfile(folder)

        menu = pystray.Menu(
            pystray.MenuItem("Jarvis v2 — Running", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Restart Jarvis", on_restart),
            pystray.MenuItem("Open log file", on_open_log),
            pystray.MenuItem("Open project folder", on_open_folder),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", on_quit),
        )

        self._tray_icon = pystray.Icon(
            "jarvis",
            _make_icon(),
            "Jarvis v2 — Running",
            menu,
        )

        threading.Thread(target=self._tray_icon.run, daemon=True).start()
        _log("System tray icon started ✓")

    # ── Jarvis lifecycle ──────────────────────────────────────────────────────

    def _run_jarvis(self) -> None:
        """Run Jarvis main loop. This blocks until exit or crash."""
        from main import Jarvis
        self._jarvis = Jarvis()
        self._jarvis.run()

    def _restart_jarvis(self) -> None:
        """Force restart Jarvis."""
        _log("Restarting Jarvis...")
        self._restart_count = 0
        # The crash recovery loop in run() will restart it

    def _cleanup(self) -> None:
        """Clean shutdown."""
        _log("Cleaning up...")
        if self._ollama_process:
            try:
                self._ollama_process.terminate()
                _log("Ollama stopped")
            except Exception:
                pass

    # ── Main loop with crash recovery ─────────────────────────────────────────

    def run(self) -> None:
        """Main entry point — runs Jarvis with auto-restart on crash."""
        _log("="*50)
        _log("Jarvis Desktop App starting...")
        _log(f"Working dir: {os.getcwd()}")
        _log(f"Python: {sys.executable}")
        _log("="*50)

        # Start Ollama
        if not self._start_ollama():
            _log("WARNING: Continuing without Ollama — LLM features may not work")

        # Start system tray
        self._start_tray()

        # Main loop with crash recovery
        while self._running:
            try:
                _log(f"Starting Jarvis (attempt {self._restart_count + 1})...")
                self._run_jarvis()

                # If we get here, Jarvis exited normally
                if not self._running:
                    break
                _log("Jarvis exited normally")

            except KeyboardInterrupt:
                _log("Keyboard interrupt — shutting down")
                break

            except Exception as exc:
                self._restart_count += 1
                _log(f"CRASH #{self._restart_count}: {exc}")
                _log(traceback.format_exc())

                if self._restart_count >= self.MAX_RESTARTS:
                    _log(f"Too many crashes ({self.MAX_RESTARTS}). Giving up.")
                    break

                _log(f"Restarting in {self.RESTART_DELAY}s...")
                time.sleep(self.RESTART_DELAY)

        self._cleanup()
        _log("Jarvis Desktop App stopped.")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    JarvisDesktopApp().run()
