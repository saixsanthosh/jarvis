"""
commands/screenshot_cmd.py — Screenshot capture + OCR text extraction.
"Take a screenshot" / "What's on my screen"
Requires: pip install pillow pytesseract (and tesseract-ocr system package)
"""
from __future__ import annotations
import os
import tempfile
from datetime import datetime
from pathlib import Path
from utils.logger import setup_logger

logger = setup_logger(__name__)

_SCREENSHOTS_DIR = Path.home() / "Pictures" / "Jarvis_Screenshots"


def take_screenshot(read_text: bool = False) -> str:
    try:
        from PIL import ImageGrab  # type: ignore
    except ImportError:
        return "Screenshot requires Pillow. Run: pip install pillow"

    try:
        img = ImageGrab.grab()
    except Exception as exc:
        return f"Couldn't capture screen: {exc}"

    _SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = _SCREENSHOTS_DIR / f"screenshot_{ts}.png"
    img.save(str(path))
    logger.info("Screenshot saved: %s", path)

    if read_text:
        text = _ocr_image(img)
        if text:
            preview = text[:400]
            return f"Screenshot saved. Here's what I can read: {preview}"
        return "Screenshot saved, but I couldn't read any text from it."

    return f"Screenshot saved to {path}."


def read_screen() -> str:
    return take_screenshot(read_text=True)


def _ocr_image(img) -> str:
    try:
        import pytesseract  # type: ignore
        text = pytesseract.image_to_string(img).strip()
        return text
    except ImportError:
        logger.warning("pytesseract not installed. Run: pip install pytesseract")
        logger.warning("Also install tesseract-ocr: sudo apt install tesseract-ocr (Linux)")
        return ""
    except Exception as exc:
        logger.error("OCR error: %s", exc)
        return ""
