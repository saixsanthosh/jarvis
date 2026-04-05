"""
commands/dev_tools.py — Developer tools: git, docker, server monitoring.
"""
from __future__ import annotations
import subprocess
import os
from pathlib import Path
from utils.logger import setup_logger

logger = setup_logger(__name__)

# ── Git ───────────────────────────────────────────────────────────────────────

def _git(args: list[str], cwd: str = None) -> str:
    cwd = cwd or os.getcwd()
    try:
        r = subprocess.run(["git"] + args, capture_output=True, text=True, cwd=cwd, timeout=15)
        output = r.stdout.strip() or r.stderr.strip()
        return output[:500] if output else "Done."
    except FileNotFoundError:
        return "Git is not installed."
    except Exception as exc:
        return f"Git error: {exc}"

def git_status() -> str:
    out = _git(["status", "--short"])
    if not out or out == "Done.":
        return "Git working tree is clean. No changes."
    lines = out.split("\n")
    return f"Git status: {len(lines)} changed files. {out[:300]}"

def git_commit(message: str) -> str:
    _git(["add", "-A"])
    out = _git(["commit", "-m", message])
    if "nothing to commit" in out.lower():
        return "Nothing to commit — working tree is clean."
    return f"Committed with message: {message}."

def git_push() -> str:
    out = _git(["push"])
    if "error" in out.lower() or "fatal" in out.lower():
        return f"Push failed: {out[:200]}"
    return "Pushed to remote successfully."

def git_pull() -> str:
    out = _git(["pull"])
    return f"Pull result: {out[:200]}"

def git_log(count: int = 5) -> str:
    out = _git(["log", f"--oneline", f"-{count}"])
    return f"Last {count} commits: {out}"

def git_branch() -> str:
    out = _git(["branch", "--show-current"])
    return f"Current branch: {out}"

# ── Docker ────────────────────────────────────────────────────────────────────

def _docker(args: list[str]) -> str:
    try:
        r = subprocess.run(["docker"] + args, capture_output=True, text=True, timeout=15)
        output = r.stdout.strip() or r.stderr.strip()
        return output[:500] if output else "Done."
    except FileNotFoundError:
        return "Docker is not installed."
    except Exception as exc:
        return f"Docker error: {exc}"

def docker_list() -> str:
    out = _docker(["ps", "--format", "table {{.Names}}\t{{.Status}}\t{{.Ports}}"])
    if not out or "NAMES" not in out:
        return "No running containers."
    return f"Running containers: {out}"

def docker_list_all() -> str:
    out = _docker(["ps", "-a", "--format", "table {{.Names}}\t{{.Status}}"])
    return f"All containers: {out}"

def docker_start(name: str) -> str:
    out = _docker(["start", name.strip()])
    return f"Started container {name}." if "Error" not in out else out

def docker_stop(name: str) -> str:
    out = _docker(["stop", name.strip()])
    return f"Stopped container {name}." if "Error" not in out else out

def docker_restart(name: str) -> str:
    out = _docker(["restart", name.strip()])
    return f"Restarted container {name}." if "Error" not in out else out

def docker_logs(name: str, lines: int = 10) -> str:
    out = _docker(["logs", "--tail", str(lines), name.strip()])
    return f"Last {lines} lines from {name}: {out[:400]}"

# ── Server Monitor ────────────────────────────────────────────────────────────

def ping_host(host: str) -> str:
    import platform
    flag = "-n" if platform.system() == "Windows" else "-c"
    try:
        r = subprocess.run(["ping", flag, "3", host], capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            # Extract avg time
            output = r.stdout
            return f"{host} is reachable. {output.split(chr(10))[-2].strip()}" if output else f"{host} is up."
        return f"{host} is unreachable."
    except Exception as exc:
        return f"Ping error: {exc}"

def check_website(url: str) -> str:
    import requests
    if not url.startswith("http"):
        url = "https://" + url
    try:
        r = requests.get(url, timeout=10, allow_redirects=True)
        return f"{url} is up. Status: {r.status_code}. Response time: {r.elapsed.total_seconds():.2f}s."
    except requests.exceptions.Timeout:
        return f"{url} timed out."
    except requests.exceptions.ConnectionError:
        return f"{url} is down or unreachable."
    except Exception as exc:
        return f"Error checking {url}: {exc}"

def get_my_ip() -> str:
    try:
        import requests
        r = requests.get("https://api.ipify.org?format=json", timeout=5)
        ip = r.json().get("ip", "unknown")
        return f"Your public IP address is {ip}."
    except Exception:
        return "Couldn't determine your public IP."
