"""
utils/logger.py — Centralised logging factory.
All modules call setup_logger(__name__) to get a consistently-formatted logger.
"""

import logging
import sys
from pathlib import Path

_LOG_DIR = Path(__file__).parent.parent / "logs"
_LOG_DIR.mkdir(exist_ok=True)

_FORMATTER = logging.Formatter(
    fmt="[%(asctime)s] %(levelname)-8s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)


def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Return a logger that writes to stdout and to logs/jarvis.log."""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if logger.handlers:
        return logger  # already configured — avoid duplicate handlers

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(_FORMATTER)
    logger.addHandler(console)

    # Rolling file handler (keeps the last 1 MB)
    try:
        from logging.handlers import RotatingFileHandler
        fh = RotatingFileHandler(
            _LOG_DIR / "jarvis.log",
            maxBytes=1_000_000,
            backupCount=2,
        )
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(_FORMATTER)
        logger.addHandler(fh)
    except Exception:
        pass  # File logging is best-effort

    logger.propagate = False
    return logger
