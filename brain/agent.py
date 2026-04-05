"""
brain/agent.py — AI Agent executor.

When no regex command matches, the LLM decides what action to take.
It can run shell commands, Python code, open apps, search the web,
manage files, and more — all by voice.

The agent works by:
1. Sending the user's request + a list of available tools to the LLM
2. LLM responds with a structured action (JSON)
3. Agent parses and executes the action
4. Returns the result as spoken text

Safety: dangerous actions require spoken confirmation via SecurityGuard.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import re
from typing import Optional

import requests

from config import OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT
from utils.logger import setup_logger

logger = setup_logger(__name__)

_SYSTEM = platform.system()

_AGENT_SYSTEM_PROMPT = """You are Jarvis, an AI assistant that can execute actions on the user's computer.
You are running on {os_name}.

When the user asks you to DO something (not just answer a question), respond with a JSON action block.
When the user asks a QUESTION or wants conversation, just respond normally with text.

Available actions (respond with exactly this JSON format):

1. Run a shell command:
{{"action": "shell", "command": "the command to run", "explain": "what this does"}}

2. Run Python code:
{{"action": "python", "code": "python code here", "explain": "what this does"}}

3. Open a URL in browser:
{{"action": "url", "url": "https://...", "explain": "opening X"}}

4. Open a file:
{{"action": "open_file", "path": "file path", "explain": "opening X"}}

5. Search the web:
{{"action": "search", "query": "search terms", "explain": "searching for X"}}

6. Type text (dictation):
{{"action": "type", "text": "text to type", "explain": "typing X"}}

7. No action needed (just answer):
Respond with normal text, no JSON.

Rules:
- ONLY output the JSON block if an action is needed. No extra text around it.
- For questions, general chat, jokes, etc — just respond normally.
- Be careful with destructive commands (rm, del, format). Warn the user.
- Use the correct OS commands ({os_name}).
- Keep explanations short (spoken aloud).
- For Python code, use print() to output results.
- NEVER run commands that could damage the system without clear intent from user.
"""

# Patterns to detect JSON action blocks in LLM response
_JSON_PATTERN = re.compile(r'\{[^{}]*"action"\s*:\s*"[^"]+?"[^{}]*\}', re.DOTALL)


class Agent:
    """Executes arbitrary actions decided by the LLM."""

    def __init__(self, speak_fn=None, confirm_fn=None):
        self._speak = speak_fn
        self._confirm = confirm_fn  # (text) -> bool, for dangerous actions

    def execute(self, user_text: str, context: str = "") -> Optional[str]:
        """
        Ask the LLM what to do, then execute the action.
        Returns a spoken response string, or None if no action was taken.
        """
        system = _AGENT_SYSTEM_PROMPT.format(os_name=_SYSTEM)
        if context:
            system += f"\n\nContext about the user:\n{context}"

        try:
            resp = requests.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": user_text,
                    "system": system,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "num_predict": 300,
                    },
                },
                timeout=OLLAMA_TIMEOUT,
            )
            resp.raise_for_status()
            reply = resp.json().get("response", "").strip()
        except Exception as exc:
            logger.error("Agent LLM error: %s", exc)
            return None

        # Try to extract a JSON action
        action = self._parse_action(reply)
        if action is None:
            # No action — LLM gave a normal text response
            return None

        # Execute the action
        return self._run_action(action)

    def _parse_action(self, text: str) -> Optional[dict]:
        """Extract a JSON action block from the LLM response."""
        match = _JSON_PATTERN.search(text)
        if not match:
            return None
        try:
            data = json.loads(match.group())
            if "action" in data:
                return data
        except json.JSONDecodeError:
            pass
        return None

    def _run_action(self, action: dict) -> str:
        """Execute a parsed action and return spoken result."""
        act = action.get("action", "")
        explain = action.get("explain", "")

        logger.info("Agent action: %s — %s", act, explain)

        if act == "shell":
            return self._run_shell(action.get("command", ""), explain)
        elif act == "python":
            return self._run_python(action.get("code", ""), explain)
        elif act == "url":
            return self._run_url(action.get("url", ""), explain)
        elif act == "open_file":
            return self._run_open_file(action.get("path", ""), explain)
        elif act == "search":
            return self._run_search(action.get("query", ""), explain)
        elif act == "type":
            return self._run_type(action.get("text", ""), explain)
        else:
            return f"I'm not sure how to do that action: {act}"

    # ── Action executors ─────────────────────────────────────────────────────

    def _run_shell(self, command: str, explain: str) -> str:
        if not command:
            return "No command to run."

        # Safety check for dangerous commands
        dangerous = ["rm -rf", "format", "del /f", "mkfs", ":(){", "dd if=",
                      "shutdown", "reboot", "> /dev/sda"]
        if any(d in command.lower() for d in dangerous):
            if self._confirm:
                if not self._confirm(f"This is a dangerous command: {command}. Should I proceed?"):
                    return "Command cancelled for safety."
            else:
                return f"Blocked dangerous command: {command}. Enable confirmation to proceed."

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=os.path.expanduser("~"),
            )
            output = result.stdout.strip() or result.stderr.strip()
            if result.returncode == 0:
                if output:
                    # Truncate long outputs for speech
                    if len(output) > 500:
                        output = output[:500] + "... and more."
                    return f"{explain}. Result: {output}" if explain else output
                return explain or "Done."
            else:
                return f"Command failed: {output[:200]}" if output else "Command failed."
        except subprocess.TimeoutExpired:
            return "Command timed out after 30 seconds."
        except Exception as exc:
            return f"Error running command: {exc}"

    def _run_python(self, code: str, explain: str) -> str:
        if not code:
            return "No code to run."

        try:
            # Capture print output
            import io
            import contextlib

            output = io.StringIO()
            local_vars = {}
            with contextlib.redirect_stdout(output):
                exec(code, {"__builtins__": __builtins__}, local_vars)

            result = output.getvalue().strip()
            if result:
                if len(result) > 500:
                    result = result[:500] + "... and more."
                return f"{explain}. {result}" if explain else result
            return explain or "Code executed successfully."
        except Exception as exc:
            return f"Python error: {exc}"

    def _run_url(self, url: str, explain: str) -> str:
        if not url:
            return "No URL provided."
        import webbrowser
        webbrowser.open(url)
        return explain or f"Opened {url}."

    def _run_open_file(self, path: str, explain: str) -> str:
        path = os.path.expanduser(path)
        if not os.path.exists(path):
            return f"File not found: {path}"
        try:
            if _SYSTEM == "Windows":
                os.startfile(path)
            elif _SYSTEM == "Darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
            return explain or f"Opened {os.path.basename(path)}."
        except Exception as exc:
            return f"Couldn't open file: {exc}"

    def _run_search(self, query: str, explain: str) -> str:
        if not query:
            return "Nothing to search for."
        import webbrowser
        from urllib.parse import quote_plus
        url = f"https://www.google.com/search?q={quote_plus(query)}"
        webbrowser.open(url)
        return explain or f"Searching for {query}."

    def _run_type(self, text: str, explain: str) -> str:
        if not text:
            return "Nothing to type."
        try:
            from pynput.keyboard import Controller  # type: ignore
            kb = Controller()
            kb.type(text)
            return explain or "Typed it out."
        except ImportError:
            return "Typing requires pynput. Install with: pip install pynput"
        except Exception as exc:
            return f"Typing error: {exc}"
