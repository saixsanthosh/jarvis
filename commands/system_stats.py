"""
commands/system_stats.py — Live system information via psutil.

Covers CPU, RAM, disk, battery, network, top processes.
All functions return spoken-friendly strings.
"""

from __future__ import annotations

from utils.logger import setup_logger

logger = setup_logger(__name__)


def _psutil():
    try:
        import psutil
        return psutil
    except ImportError:
        raise RuntimeError("psutil not installed. Run: pip install psutil")


def get_cpu() -> str:
    ps = _psutil()
    percent = ps.cpu_percent(interval=0.5)
    freq    = ps.cpu_freq()
    cores   = ps.cpu_count(logical=False)
    threads = ps.cpu_count(logical=True)

    parts = [f"CPU usage is {percent:.0f}%"]
    if cores:
        parts.append(f"{cores} physical cores, {threads} threads")
    if freq:
        parts.append(f"running at {freq.current:.0f} MHz")
    return ", ".join(parts) + "."


def get_memory() -> str:
    ps  = _psutil()
    ram = ps.virtual_memory()
    used_gb  = ram.used  / 1_073_741_824
    total_gb = ram.total / 1_073_741_824
    return (
        f"RAM: {used_gb:.1f} GB used out of {total_gb:.1f} GB "
        f"({ram.percent:.0f}% utilised)."
    )


def get_disk(path: str = "/") -> str:
    ps = _psutil()
    try:
        disk = ps.disk_usage(path)
        free_gb  = disk.free  / 1_073_741_824
        total_gb = disk.total / 1_073_741_824
        return (
            f"Disk at '{path}': {free_gb:.1f} GB free out of "
            f"{total_gb:.1f} GB ({disk.percent:.0f}% used)."
        )
    except Exception as exc:
        return f"Couldn't read disk info: {exc}"


def get_battery() -> str:
    ps = _psutil()
    bat = ps.sensors_battery()
    if bat is None:
        return "No battery detected — running on AC power."
    status = "charging" if bat.power_plugged else "on battery"
    secs_left = bat.secsleft
    if secs_left > 0 and not bat.power_plugged:
        h, m = divmod(secs_left // 60, 60)
        time_str = f", about {h}h {m}m remaining" if h else f", about {m}m remaining"
    else:
        time_str = ""
    return f"Battery at {bat.percent:.0f}%, {status}{time_str}."


def get_top_processes(n: int = 5) -> str:
    ps = _psutil()
    procs = []
    for proc in ps.process_iter(["name", "cpu_percent", "memory_percent"]):
        try:
            procs.append(proc.info)
        except (ps.NoSuchProcess, ps.AccessDenied):
            pass

    top = sorted(procs, key=lambda p: p.get("cpu_percent", 0), reverse=True)[:n]
    if not top:
        return "Couldn't retrieve process list."

    lines = [f"Top {len(top)} processes by CPU:"]
    for p in top:
        lines.append(
            f"  {p['name']}: CPU {p['cpu_percent']:.1f}%, "
            f"RAM {p['memory_percent']:.1f}%"
        )
    return "\n".join(lines)


def get_network() -> str:
    ps = _psutil()
    net = ps.net_io_counters()
    sent_mb = net.bytes_sent / 1_048_576
    recv_mb = net.bytes_recv / 1_048_576
    return f"Network: sent {sent_mb:.1f} MB, received {recv_mb:.1f} MB this session."


def get_full_summary() -> str:
    """Spoken system health summary."""
    parts = []
    try:
        parts.append(get_cpu())
    except Exception:
        pass
    try:
        parts.append(get_memory())
    except Exception:
        pass
    try:
        parts.append(get_battery())
    except Exception:
        pass
    return " ".join(parts) if parts else "System info unavailable."
