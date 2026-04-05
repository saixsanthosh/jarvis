"""
commands/code_runner.py — Run Python code or shell commands by voice.
"Run Python print hello world" / "Run command dir"
"""
from __future__ import annotations
import subprocess
import io
import contextlib
import platform
from utils.logger import setup_logger

logger = setup_logger(__name__)


def run_python(code: str) -> str:
    if not code.strip():
        return "No code to run."
    try:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exec(code, {"__builtins__": __builtins__}, {})
        result = output.getvalue().strip()
        if result:
            return f"Result: {result[:500]}" if len(result) > 500 else f"Result: {result}"
        return "Code ran successfully with no output."
    except Exception as exc:
        return f"Python error: {exc}"


def run_shell(command: str) -> str:
    if not command.strip():
        return "No command to run."
    
    # Block dangerous commands
    dangerous = ["rm -rf /", "format c:", "del /f /s /q c:", "mkfs", ":(){"]
    if any(d in command.lower() for d in dangerous):
        return "That command looks dangerous. I've blocked it for safety."

    try:
        r = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=30, cwd=str(__import__("pathlib").Path.home()),
        )
        output = r.stdout.strip() or r.stderr.strip()
        if output:
            return f"Result: {output[:500]}" if len(output) > 500 else f"Result: {output}"
        return "Command completed."
    except subprocess.TimeoutExpired:
        return "Command timed out."
    except Exception as exc:
        return f"Error: {exc}"


def calculate(expression: str) -> str:
    """Safely evaluate a math expression."""
    import re
    # Only allow safe math characters
    clean = re.sub(r'[^0-9+\-*/().%^ ]', '', expression)
    if not clean:
        return "I couldn't parse that math expression."
    try:
        clean = clean.replace('^', '**')
        result = eval(clean, {"__builtins__": {}}, {})
        return f"The answer is {result}."
    except Exception:
        return f"Couldn't calculate: {expression}"
