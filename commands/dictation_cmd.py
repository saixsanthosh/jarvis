"""
commands/dictation_cmd.py — Type what you say into any app.
"Start dictation" / "Type this: hello world"
Requires: pip install pynput
"""
from __future__ import annotations
import time
from utils.logger import setup_logger

logger = setup_logger(__name__)

_dictation_active = False


def type_text(text: str) -> str:
    try:
        from pynput.keyboard import Controller  # type: ignore
        kb = Controller()
        time.sleep(0.5)  # brief delay to let user switch to target window
        kb.type(text)
        logger.info("Typed %d chars", len(text))
        return f"Typed it out: {text[:50]}"
    except ImportError:
        return "Dictation requires pynput. Run: pip install pynput"
    except Exception as exc:
        return f"Typing error: {exc}"


def type_and_enter(text: str) -> str:
    try:
        from pynput.keyboard import Controller, Key  # type: ignore
        kb = Controller()
        time.sleep(0.5)
        kb.type(text)
        kb.press(Key.enter)
        kb.release(Key.enter)
        return f"Typed and pressed enter."
    except ImportError:
        return "Requires pynput. Run: pip install pynput"
    except Exception as exc:
        return f"Typing error: {exc}"


def press_key(key_name: str) -> str:
    try:
        from pynput.keyboard import Controller, Key  # type: ignore
        kb = Controller()
        key_map = {
            "enter": Key.enter, "tab": Key.tab, "escape": Key.esc,
            "space": Key.space, "backspace": Key.backspace,
            "delete": Key.delete, "up": Key.up, "down": Key.down,
            "left": Key.left, "right": Key.right,
            "home": Key.home, "end": Key.end,
            "page up": Key.page_up, "page down": Key.page_down,
            "f1": Key.f1, "f2": Key.f2, "f5": Key.f5, "f11": Key.f11,
        }
        key = key_map.get(key_name.lower())
        if key:
            kb.press(key)
            kb.release(key)
            return f"Pressed {key_name}."
        return f"Unknown key: {key_name}"
    except ImportError:
        return "Requires pynput. Run: pip install pynput"
    except Exception as exc:
        return f"Key press error: {exc}"


def keyboard_shortcut(shortcut: str) -> str:
    try:
        from pynput.keyboard import Controller, Key  # type: ignore
        kb = Controller()
        
        mod_map = {"ctrl": Key.ctrl_l, "alt": Key.alt_l, "shift": Key.shift_l,
                    "win": Key.cmd, "super": Key.cmd, "cmd": Key.cmd}
        
        parts = [p.strip().lower() for p in shortcut.split("+")]
        mods = [mod_map[p] for p in parts[:-1] if p in mod_map]
        final_key = parts[-1] if parts else ""
        
        for m in mods:
            kb.press(m)
        if final_key:
            kb.press(final_key)
            kb.release(final_key)
        for m in reversed(mods):
            kb.release(m)
        
        return f"Pressed {shortcut}."
    except ImportError:
        return "Requires pynput. Run: pip install pynput"
    except Exception as exc:
        return f"Shortcut error: {exc}"
