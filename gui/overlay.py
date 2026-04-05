"""
gui/overlay.py — Always-on-top floating status overlay using tkinter.

Displays a real-time waveform bar and the current Jarvis state
(sleeping / listening / thinking / speaking) in a small transparent window.

Design goals
────────────
• Minimal footprint — 260 × 80 px, semi-transparent, no window decorations
• Runs in its own thread so it never blocks the audio pipeline
• Thread-safe state updates via a shared JarvisState object
• Degrades gracefully: if tkinter display is unavailable (headless), logs a
  warning and returns immediately without crashing the main process
"""

from __future__ import annotations

import threading
import time
from typing import Optional

from utils.logger import setup_logger

logger = setup_logger(__name__)


class JarvisState:
    """Thread-safe Jarvis status that the GUI reads every repaint cycle."""

    _STATES = {"sleeping", "listening", "thinking", "speaking", "active"}

    def __init__(self) -> None:
        self._state = "sleeping"
        self._lock  = threading.Lock()
        self._waveform: list[float] = [0.0] * 20

    def set(self, state: str) -> None:
        if state not in self._STATES:
            return
        with self._lock:
            self._state = state

    def get(self) -> str:
        with self._lock:
            return self._state

    def update_waveform(self, samples: list[float]) -> None:
        with self._lock:
            self._waveform = list(samples[-20:]) if samples else [0.0] * 20

    def get_waveform(self) -> list[float]:
        with self._lock:
            return list(self._waveform)


# State → (label_text, bar_colour)
_STATE_STYLE: dict[str, tuple[str, str]] = {
    "sleeping":  ("Sleeping…",  "#555560"),
    "listening": ("Listening",  "#3ddc97"),
    "thinking":  ("Thinking…",  "#f0a500"),
    "speaking":  ("Speaking",   "#5b8af5"),
    "active":    ("Active",     "#3ddc97"),
}


class WaveformOverlay:
    """Floating tkinter overlay — call run() in a daemon thread."""

    WIDTH  = 260
    HEIGHT = 80
    BARS   = 20

    def __init__(self, state: JarvisState) -> None:
        self._state = state
        self._tk_ok = False

    def run(self) -> None:
        """Entry point — start the tkinter main loop. Blocks until window closes."""
        try:
            import tkinter as tk
        except ImportError:
            logger.warning("tkinter not available — overlay disabled.")
            return

        try:
            root = tk.Tk()
        except Exception as exc:
            logger.warning("Cannot open display for overlay: %s", exc)
            return

        self._tk_ok = True
        root.title("Jarvis")
        root.geometry(f"{self.WIDTH}x{self.HEIGHT}+40+40")
        root.resizable(False, False)
        root.overrideredirect(True)      # no window decorations
        root.wm_attributes("-topmost", True)

        # Semi-transparency (supported on most platforms)
        try:
            root.wm_attributes("-alpha", 0.88)
        except Exception:
            pass

        self._position_overlay(root)

        # Canvas
        canvas = tk.Canvas(
            root,
            width=self.WIDTH,
            height=self.HEIGHT,
            bg="#1c1c24",
            highlightthickness=0,
        )
        canvas.pack()

        # State label
        label_var = tk.StringVar(value="Sleeping…")
        label = tk.Label(
            canvas,
            textvariable=label_var,
            bg="#1c1c24",
            fg="#ffffff",
            font=("Helvetica", 11, "bold"),
        )
        label_win = canvas.create_window(
            self.WIDTH // 2, 18, window=label, anchor="center"
        )

        # Waveform bars (rectangles updated each frame)
        bar_w   = (self.WIDTH - 24) // self.BARS
        bar_gap = 2
        bar_ids = []
        for i in range(self.BARS):
            x0 = 12 + i * (bar_w + bar_gap)
            bar_id = canvas.create_rectangle(
                x0, 60, x0 + bar_w, 62, fill="#555560", outline=""
            )
            bar_ids.append(bar_id)

        # Drag to reposition
        drag = {"x": 0, "y": 0}

        def on_press(e):
            drag["x"] = e.x
            drag["y"] = e.y

        def on_drag(e):
            dx = e.x - drag["x"]
            dy = e.y - drag["y"]
            x  = root.winfo_x() + dx
            y  = root.winfo_y() + dy
            root.geometry(f"+{x}+{y}")

        canvas.bind("<ButtonPress-1>",   on_press)
        canvas.bind("<B1-Motion>",       on_drag)

        def _update():
            state       = self._state.get()
            label_text, bar_colour = _STATE_STYLE.get(state, ("…", "#555560"))
            label_var.set(label_text)

            waveform = self._state.get_waveform()
            max_amp  = max(waveform) if waveform else 1.0
            if max_amp == 0:
                max_amp = 1.0

            for i, bar_id in enumerate(bar_ids):
                amp   = waveform[i] if i < len(waveform) else 0.0
                norm  = amp / max_amp          # 0..1
                bar_h = max(3, int(norm * 28))  # 3..28 px
                y0    = 62 - bar_h
                x0    = 12 + i * (bar_w + bar_gap)
                canvas.coords(bar_id, x0, y0, x0 + bar_w, 62)
                canvas.itemconfig(bar_id, fill=bar_colour)

            root.after(80, _update)  # ~12 fps

        _update()
        logger.info("Overlay started.")
        root.mainloop()

    def _position_overlay(self, root) -> None:
        from config import OVERLAY_POSITION
        root.update_idletasks()
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        margin = 20
        positions = {
            "bottom-right": (sw - self.WIDTH - margin, sh - self.HEIGHT - 60),
            "bottom-left":  (margin, sh - self.HEIGHT - 60),
            "top-right":    (sw - self.WIDTH - margin, margin + 30),
            "top-left":     (margin, margin + 30),
        }
        x, y = positions.get(OVERLAY_POSITION, positions["bottom-right"])
        root.geometry(f"{self.WIDTH}x{self.HEIGHT}+{x}+{y}")
