"""
gui/tray.py — System tray icon with right-click context menu.

Shows Jarvis status (sleeping / listening / thinking / speaking) and
provides quick actions without needing the terminal window.

Requires: pip install pystray Pillow

If pystray is not installed the function returns immediately
without crashing the main process.
"""

from __future__ import annotations

import threading
from typing import Callable, Optional

from gui.overlay import JarvisState
from utils.logger import setup_logger

logger = setup_logger(__name__)

# Icon dimensions (small enough for any tray)
_ICON_SIZE = 64


def _make_icon_image(state: str):
    """Draw a coloured circle icon using Pillow."""
    try:
        from PIL import Image, ImageDraw  # type: ignore
    except ImportError:
        return None

    colours = {
        "sleeping":  "#555560",
        "listening": "#3ddc97",
        "thinking":  "#f0a500",
        "speaking":  "#5b8af5",
        "active":    "#3ddc97",
    }
    bg    = colours.get(state, "#555560")
    img   = Image.new("RGBA", (_ICON_SIZE, _ICON_SIZE), (0, 0, 0, 0))
    draw  = ImageDraw.Draw(img)
    pad   = 8
    draw.ellipse([pad, pad, _ICON_SIZE - pad, _ICON_SIZE - pad], fill=bg)
    return img


class TrayIcon:
    """
    System tray integration.

    Parameters
    ──────────
    state      : shared JarvisState object
    exit_fn    : called when user clicks "Quit" from the tray menu
    """

    def __init__(
        self,
        state: JarvisState,
        exit_fn: Optional[Callable] = None,
    ) -> None:
        self._state   = state
        self._exit_fn = exit_fn
        self._icon    = None

    def run(self) -> None:
        """Block in the tray icon loop. Run in a daemon thread."""
        try:
            import pystray  # type: ignore
        except ImportError:
            logger.warning(
                "pystray not installed — system tray disabled.\n"
                "  pip install pystray Pillow"
            )
            return

        try:
            icon_img = _make_icon_image("sleeping")
            if icon_img is None:
                logger.warning("Pillow not installed — tray icon will be blank.")
                from PIL import Image  # type: ignore
                icon_img = Image.new("RGB", (_ICON_SIZE, _ICON_SIZE), "gray")

            menu = pystray.Menu(
                pystray.MenuItem("Jarvis Status", None, enabled=False),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Wake now",     lambda *_: self._wake()),
                pystray.MenuItem("Sleep",        lambda *_: self._sleep()),
                pystray.MenuItem("Clear memory", lambda *_: self._clear_memory()),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Quit Jarvis",  lambda *_: self._quit()),
            )

            self._icon = pystray.Icon(
                "jarvis",
                icon_img,
                "Jarvis — Sleeping",
                menu,
            )

            # Poll state every 0.5 s and update the icon
            def _state_poller():
                last = ""
                while self._icon and self._icon.visible:
                    current = self._state.get()
                    if current != last:
                        last = current
                        try:
                            new_img = _make_icon_image(current)
                            if new_img:
                                self._icon.icon  = new_img
                                self._icon.title = f"Jarvis — {current.capitalize()}"
                        except Exception:
                            pass
                    import time
                    time.sleep(0.5)

            threading.Thread(target=_state_poller, daemon=True).start()
            logger.info("System tray icon started.")
            self._icon.run()

        except Exception as exc:
            logger.error("Tray icon error: %s", exc)

    # ── Menu actions ──────────────────────────────────────────────────────────

    def _wake(self) -> None:
        self._state.set("active")
        logger.info("Tray: manual wake triggered")

    def _sleep(self) -> None:
        self._state.set("sleeping")
        logger.info("Tray: sleep triggered")

    def _clear_memory(self) -> None:
        try:
            from brain.long_memory import LongMemory
            LongMemory().clear_all()
            logger.info("Tray: memory cleared")
        except Exception as exc:
            logger.error("Memory clear error: %s", exc)

    def _quit(self) -> None:
        logger.info("Tray: quit requested")
        if self._icon:
            self._icon.stop()
        if self._exit_fn:
            self._exit_fn()
        import os, signal
        os.kill(os.getpid(), signal.SIGINT)
