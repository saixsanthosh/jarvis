"""
commands/router.py — Intent-based command routing (v2 — COMPLETE).
50+ voice commands. First match wins. Returns (matched, response).
"""
from __future__ import annotations
import re
from typing import Callable
from commands.system_control import (
    open_app, close_app, search_youtube, search_google, open_url, set_volume,
)
from utils.logger import setup_logger

logger = setup_logger(__name__)

_timer_manager = None
def set_timer_manager(mgr) -> None:
    global _timer_manager
    _timer_manager = mgr

_Handler = Callable[[re.Match], str]

_RAW_PATTERNS: list[tuple[str, _Handler]] = [

    # ── Daily briefing ───────────────────────────────────────────────────
    (r"(?:good\s+)?(?:morning|afternoon|evening)(?:\s+jarvis)?$",
                                                      lambda m: _briefing()),
    (r"(?:daily|morning)\s+(?:briefing|summary|update)",
                                                      lambda m: _briefing()),

    # ── Home automation ──────────────────────────────────────────────────
    (r"turn on\s+(?:the\s+)?(.+?)(?:\s+light|\s+fan|\s+lamp)?$",
                                                      lambda m: _ha_on(m.group(1))),
    (r"turn off\s+(?:the\s+)?(.+?)(?:\s+light|\s+fan|\s+lamp)?$",
                                                      lambda m: _ha_off(m.group(1))),
    (r"(?:set\s+)?(?:the\s+)?(?:thermostat|temperature|ac)\s+(?:to\s+)?(\d+)",
                                                      lambda m: _ha_temp(int(m.group(1)))),

    # ── Spotify ──────────────────────────────────────────────────────────
    (r"(?:pause|stop)\s+(?:spotify|music|song|track)",  lambda m: _sp_pause()),
    (r"(?:play|resume)\s+(?:spotify|music)$",           lambda m: _sp_pause()),
    (r"play\s+(.+?)\s+on\s+spotify",                    lambda m: _sp_play(m.group(1))),
    (r"(?:next|skip)\s*(?:song|track)?$",               lambda m: _sp_next()),
    (r"(?:previous|prev|back)\s*(?:song|track)?$",      lambda m: _sp_prev()),
    (r"what(?:'s| is)\s+(?:playing|this song|current song)",
                                                        lambda m: _sp_now()),

    # ── YouTube ──────────────────────────────────────────────────────────
    (r"search\s+youtube\s+for\s+(.+)",                lambda m: search_youtube(m.group(1))),
    (r"play\s+(.+?)\s+on\s+youtube",                  lambda m: search_youtube(m.group(1))),
    (r"\byoutube\b\s+(.+)",                           lambda m: search_youtube(m.group(1))),

    # ── Web search / URL ─────────────────────────────────────────────────
    (r"search\s+(?:google\s+)?for\s+(.+)",            lambda m: search_google(m.group(1))),
    (r"google\s+(.+)",                                lambda m: search_google(m.group(1))),
    (r"(?:go to|open|visit)\s+(https?://\S+)",        lambda m: open_url(m.group(1))),
    (r"(?:go to|open|visit)\s+([\w.-]+\.\w{2,})",    lambda m: open_url(m.group(1))),

    # ── App control ──────────────────────────────────────────────────────
    (r"\b(?:open|launch|start|run)\s+(.+)",           lambda m: open_app(m.group(1).strip())),
    (r"\b(?:close|quit|kill|exit)\s+(.+)",            lambda m: close_app(m.group(1).strip())),

    # ── Volume ───────────────────────────────────────────────────────────
    (r"(?:set\s+)?volume\s+(?:to\s+)?(\d+)",          lambda m: set_volume(int(m.group(1)))),
    (r"(?:mute|unmute)",                              lambda m: set_volume(0)),

    # ── Weather ──────────────────────────────────────────────────────────
    (r"weather\s+(?:for\s+)?today",                   lambda m: _weather_today()),
    (r"weather\s+(?:for\s+)?tomorrow",                lambda m: _weather_tomorrow()),
    (r"(?:what(?:'s| is) the\s+)?weather",            lambda m: _weather_current()),
    (r"(?:will it|is it going to)\s+rain",            lambda m: _weather_today()),
    (r"(?:how(?:'s| is) it|temperature)\s+outside",   lambda m: _weather_current()),

    # ── Timers ───────────────────────────────────────────────────────────
    (r"remind me (?:in|after)\s+(.+?)\s+(?:to\s+)(.+)",
                                                      lambda m: _set_timer_label(m)),
    (r"(?:set\s+a?\s*)?timer\s+(?:for\s+)?(.+)",     lambda m: _set_timer_raw(m.group(1))),
    (r"(?:list|show)\s+(?:my\s+)?timers?",            lambda m: _list_timers()),
    (r"cancel\s+(?:all\s+)?timers?",                  lambda m: _cancel_timers()),

    # ── Date & time ──────────────────────────────────────────────────────
    (r"what(?:'s| is)\s+(?:the\s+)?(?:date|today(?:'s date)?)",
                                                      lambda m: _date()),
    (r"what(?:'s| is)\s+(?:the\s+)?(?:time|current time)",
                                                      lambda m: _time()),
    (r"what day (?:is it|is today)",                  lambda m: _date()),

    # ── News ─────────────────────────────────────────────────────────────
    (r"(?:what(?:'s| is)|give me|read)\s+(?:the\s+)?(?:latest\s+)?news",
                                                      lambda m: _news()),
    (r"(?:tech|technology)\s+news",                   lambda m: _tech_news()),
    (r"(?:world|global|international)\s+news",        lambda m: _world_news()),
    (r"news\s+(?:about|on|for)\s+(.+)",               lambda m: _news()),

    # ── System stats ─────────────────────────────────────────────────────
    (r"(?:how(?:'s| is)|what(?:'s| is))\s+(?:the\s+)?(?:cpu|processor)",
                                                      lambda m: _cpu()),
    (r"(?:how(?:'s| is)|what(?:'s| is))\s+(?:the\s+)?(?:ram|memory)",
                                                      lambda m: _ram()),
    (r"(?:how(?:'s| is)|what(?:'s| is))\s+(?:the\s+)?battery",
                                                      lambda m: _battery()),
    (r"(?:show|give)\s+(?:me\s+)?(?:system\s+)?(?:stats?|status|info)",
                                                      lambda m: _sysinfo()),
    (r"(?:how much\s+)?(?:disk|storage)\s+space",     lambda m: _disk()),
    (r"(?:top|running)\s+processes",                  lambda m: _top_procs()),
    (r"(?:network|internet)\s+(?:stats?|usage|info)", lambda m: _network()),
    (r"(?:what(?:'s| is)\s+)?my\s+(?:ip|IP)\s*(?:address)?",
                                                      lambda m: _my_ip()),

    # ── Notes ────────────────────────────────────────────────────────────
    (r"(?:take|make|add|save)\s+(?:a\s+)?note(?:\s*[:]\s*|\s+)(.+)",
                                                      lambda m: _add_note(m.group(1))),
    (r"(?:read|show|list)\s+(?:my\s+)?(?:last\s+(\d+)\s+)?notes?",
                                                      lambda m: _read_notes(m)),
    (r"(?:how many|count)\s+notes?",                  lambda m: _count_notes()),
    (r"(?:delete|clear|erase)\s+(?:all\s+)?notes?",   lambda m: _delete_notes()),

    # ── Shopping list ────────────────────────────────────────────────────
    (r"add\s+(.+?)\s+to\s+(?:my\s+)?(?:shopping|grocery)\s*list",
                                                      lambda m: _shop_add(m.group(1))),
    (r"(?:read|show|what(?:'s| is) on)\s+(?:my\s+)?(?:shopping|grocery)\s*list",
                                                      lambda m: _shop_read()),
    (r"(?:clear|empty|delete)\s+(?:my\s+)?(?:shopping|grocery)\s*list",
                                                      lambda m: _shop_clear()),
    (r"remove\s+(.+?)\s+from\s+(?:my\s+)?(?:shopping|grocery)\s*list",
                                                      lambda m: _shop_remove(m.group(1))),

    # ── Expenses ─────────────────────────────────────────────────────────
    (r"(?:spent|spend|log expense|expense)\s+(\d+(?:\.\d+)?)\s*(?:on|for)?\s*(.*)",
                                                      lambda m: _expense_log(m)),
    (r"(?:how much|what)\s+(?:did I|have I)\s+(?:spent?|expenses?)\s*(?:this\s+)?(\w*)",
                                                      lambda m: _expense_get(m.group(1) or "week")),
    (r"(?:show|get|read)\s+(?:my\s+)?expenses?\s*(?:this\s+)?(\w*)",
                                                      lambda m: _expense_get(m.group(1) or "week")),

    # ── Habits ───────────────────────────────────────────────────────────
    (r"(?:log|done|did|completed?)\s+(?:my\s+)?(.+?)(?:\s+today)?$",
                                                      lambda m: _habit_log(m.group(1))),
    (r"(?:show|how(?:'s| is)|what(?:'s| is))\s+(?:my\s+)?(?:habits?|streaks?)",
                                                      lambda m: _habits()),

    # ── Screenshot + OCR ─────────────────────────────────────────────────
    (r"(?:take|capture)\s+(?:a\s+)?screenshot",       lambda m: _screenshot()),
    (r"what(?:'s| is)\s+on\s+(?:my\s+)?screen",      lambda m: _read_screen()),
    (r"(?:read|ocr)\s+(?:my\s+)?screen",              lambda m: _read_screen()),

    # ── Dictation / typing ───────────────────────────────────────────────
    (r"type\s+(?:this\s*[:]\s*|out\s+)?(.+)",         lambda m: _type_text(m.group(1))),
    (r"press\s+(?:the\s+)?(.+?)(?:\s+key)?$",         lambda m: _press_key(m.group(1))),
    (r"(?:keyboard\s+)?shortcut\s+(.+)",              lambda m: _shortcut(m.group(1))),

    # ── File finder ──────────────────────────────────────────────────────
    (r"find\s+(?:my\s+|a\s+)?(?:file\s+)?(?:named?\s+|called?\s+)?(.+)",
                                                      lambda m: _find_file(m.group(1))),
    (r"(?:recent|latest)\s+downloads?",               lambda m: _recent_downloads()),

    # ── Git ──────────────────────────────────────────────────────────────
    (r"git\s+status",                                 lambda m: _git_status()),
    (r"git\s+commit\s+(?:with\s+)?(?:message\s+)?(.+)",
                                                      lambda m: _git_commit(m.group(1))),
    (r"git\s+push",                                   lambda m: _git_push()),
    (r"git\s+pull",                                   lambda m: _git_pull()),
    (r"git\s+log",                                    lambda m: _git_log()),
    (r"git\s+branch",                                 lambda m: _git_branch()),

    # ── Docker ───────────────────────────────────────────────────────────
    (r"(?:docker|container)s?\s+(?:list|running|ps)",  lambda m: _docker_list()),
    (r"(?:start|restart|stop)\s+(?:docker\s+)?container\s+(.+)",
                                                      lambda m: _docker_action(m)),

    # ── Server / website check ───────────────────────────────────────────
    (r"(?:ping|check)\s+(?:the\s+)?(?:server\s+)?(.+)",
                                                      lambda m: _check_site(m.group(1))),
    (r"(?:is\s+)?(?:my\s+)?(?:website|site|server)\s+(?:up|running|alive)",
                                                      lambda m: _check_site("localhost")),

    # ── WhatsApp ─────────────────────────────────────────────────────────
    (r"(?:send|text)\s+(?:a\s+)?(?:whatsapp|message)\s+(?:to\s+)?(\w+)\s+(?:saying|that|message)\s+(.+)",
                                                      lambda m: _whatsapp(m.group(1), m.group(2))),

    # ── Calculator ───────────────────────────────────────────────────────
    (r"(?:calculate|what(?:'s| is))\s+([\d+\-*/().^ ]+)$",
                                                      lambda m: _calc(m.group(1))),

    # ── Run code / command ───────────────────────────────────────────────
    (r"run\s+(?:python\s+)?(?:code\s+)?(.+)",         lambda m: _run_python(m.group(1))),
    (r"(?:run|execute)\s+command\s+(.+)",             lambda m: _run_shell(m.group(1))),

    # ── Clipboard ────────────────────────────────────────────────────────
    (r"(?:read|what(?:'s| is in)|show)\s+(?:my\s+)?clipboard",
                                                      lambda m: _clipboard()),

    # ── Memory ───────────────────────────────────────────────────────────
    (r"(?:what do you\s+)?(?:remember|know)\s+about\s+me",
                                                      lambda m: _recall_facts()),
    (r"(?:forget|clear|delete)\s+(?:everything|all)\s*(?:you know|memory|memories)?",
                                                      lambda m: _clear_memory()),

    # ── Help ─────────────────────────────────────────────────────────────
    (r"(?:what can you do|help|commands?|features?)",  lambda m: _help()),
]

_COMPILED: list[tuple[re.Pattern, _Handler]] = [
    (re.compile(p, re.IGNORECASE | re.DOTALL), h)
    for p, h in _RAW_PATTERNS
]


# ═══════════════════════════════════════════════════════════════════════════════
# Handler wrappers
# ═══════════════════════════════════════════════════════════════════════════════

def _briefing():
    from commands.daily_briefing import get_briefing; return get_briefing()

# Weather
def _weather_current():
    from commands.weather import get_current_weather; return get_current_weather()
def _weather_today():
    from commands.weather import get_weather_today; return get_weather_today()
def _weather_tomorrow():
    from commands.weather import get_weather_tomorrow; return get_weather_tomorrow()

# Timers
def _set_timer_raw(raw):
    if not _timer_manager: return "Timer system not initialised."
    from commands.timers import parse_duration
    s = parse_duration(raw)
    if not s: return f"Didn't catch a duration in '{raw}'."
    return _timer_manager.set_timer(s, raw.strip())
def _set_timer_label(m):
    if not _timer_manager: return "Timer system not initialised."
    from commands.timers import parse_duration
    s = parse_duration(m.group(1))
    if not s: return f"Couldn't parse duration from '{m.group(1)}'."
    label = m.group(2) if m.lastindex >= 2 else "reminder"
    return _timer_manager.set_timer(s, label.strip())
def _list_timers():
    return _timer_manager.list_timers() if _timer_manager else "No timer system."
def _cancel_timers():
    return _timer_manager.cancel_all() if _timer_manager else "No timer system."

# Date/time
def _date():
    from datetime import datetime; return datetime.now().strftime("Today is %A, %B %d, %Y.")
def _time():
    from datetime import datetime; return datetime.now().strftime("It's currently %I:%M %p.")

# News
def _news():
    from commands.news_cmd import get_news; return get_news()
def _tech_news():
    from commands.news_cmd import get_tech_news; return get_tech_news()
def _world_news():
    from commands.news_cmd import get_world_news; return get_world_news()

# System stats
def _cpu():
    from commands.system_stats import get_cpu; return get_cpu()
def _ram():
    from commands.system_stats import get_memory; return get_memory()
def _battery():
    from commands.system_stats import get_battery; return get_battery()
def _sysinfo():
    from commands.system_stats import get_full_summary; return get_full_summary()
def _disk():
    from commands.system_stats import get_disk; return get_disk()
def _top_procs():
    from commands.system_stats import get_top_processes; return get_top_processes()
def _network():
    from commands.system_stats import get_network; return get_network()
def _my_ip():
    from commands.dev_tools import get_my_ip; return get_my_ip()

# Spotify
def _sp_pause():
    from commands.spotify_ctrl import play_pause; return play_pause()
def _sp_play(q):
    from commands.spotify_ctrl import play_song; return play_song(q)
def _sp_next():
    from commands.spotify_ctrl import skip_next; return skip_next()
def _sp_prev():
    from commands.spotify_ctrl import skip_prev; return skip_prev()
def _sp_now():
    from commands.spotify_ctrl import now_playing; return now_playing()

# Home automation
def _ha_on(d):
    from commands.home_auto import turn_on; return turn_on(d)
def _ha_off(d):
    from commands.home_auto import turn_off; return turn_off(d)
def _ha_temp(t):
    from commands.home_auto import set_temperature; return set_temperature(t)

# Notes
def _add_note(c):
    from commands.notes_cmd import add_note; return add_note(c)
def _read_notes(m):
    from commands.notes_cmd import read_notes; return read_notes(int(m.group(1)) if m.group(1) else 5)
def _count_notes():
    from commands.notes_cmd import count_notes; return count_notes()
def _delete_notes():
    from commands.notes_cmd import delete_all_notes; return delete_all_notes()

# Shopping
def _shop_add(item):
    from commands.life_tracker import add_to_shopping; return add_to_shopping(item)
def _shop_read():
    from commands.life_tracker import read_shopping_list; return read_shopping_list()
def _shop_clear():
    from commands.life_tracker import clear_shopping_list; return clear_shopping_list()
def _shop_remove(item):
    from commands.life_tracker import remove_from_shopping; return remove_from_shopping(item)

# Expenses
def _expense_log(m):
    from commands.life_tracker import log_expense
    amt = float(m.group(1))
    desc = m.group(2).strip() if m.group(2) else ""
    return log_expense(amt, desc)
def _expense_get(period):
    from commands.life_tracker import get_expenses; return get_expenses(period or "week")

# Habits
def _habit_log(name):
    from commands.life_tracker import log_habit; return log_habit(name)
def _habits():
    from commands.life_tracker import get_habits; return get_habits()

# Screenshot
def _screenshot():
    from commands.screenshot_cmd import take_screenshot; return take_screenshot()
def _read_screen():
    from commands.screenshot_cmd import read_screen; return read_screen()

# Dictation
def _type_text(t):
    from commands.dictation_cmd import type_text; return type_text(t)
def _press_key(k):
    from commands.dictation_cmd import press_key; return press_key(k)
def _shortcut(s):
    from commands.dictation_cmd import keyboard_shortcut; return keyboard_shortcut(s)

# Files
def _find_file(q):
    from commands.file_finder import find_files; return find_files(q)
def _recent_downloads():
    from commands.file_finder import list_recent_downloads; return list_recent_downloads()

# Git
def _git_status():
    from commands.dev_tools import git_status; return git_status()
def _git_commit(msg):
    from commands.dev_tools import git_commit; return git_commit(msg)
def _git_push():
    from commands.dev_tools import git_push; return git_push()
def _git_pull():
    from commands.dev_tools import git_pull; return git_pull()
def _git_log():
    from commands.dev_tools import git_log; return git_log()
def _git_branch():
    from commands.dev_tools import git_branch; return git_branch()

# Docker
def _docker_list():
    from commands.dev_tools import docker_list; return docker_list()
def _docker_action(m):
    from commands.dev_tools import docker_start, docker_stop, docker_restart
    text = m.group(0).lower()
    name = m.group(1).strip()
    if "restart" in text: return docker_restart(name)
    if "stop" in text: return docker_stop(name)
    return docker_start(name)

# Server
def _check_site(host):
    from commands.dev_tools import check_website; return check_website(host.strip())

# WhatsApp
def _whatsapp(contact, msg):
    from commands.messaging import send_whatsapp; return send_whatsapp(contact, msg)

# Calculator
def _calc(expr):
    from commands.code_runner import calculate; return calculate(expr)

# Code runner
def _run_python(code):
    from commands.code_runner import run_python; return run_python(code)
def _run_shell(cmd):
    from commands.code_runner import run_shell; return run_shell(cmd)

# Clipboard
def _clipboard():
    from commands.clipboard_cmd import read_clipboard; return read_clipboard()

# Memory
def _recall_facts():
    try:
        from brain.long_memory import LongMemory
        facts = LongMemory().get_all_facts()
        if not facts: return "I don't have any stored facts about you yet."
        lines = ["Here's what I remember:"]
        for f in facts: lines.append(f"  {f['key']}: {f['value']}")
        return " ".join(lines)
    except Exception as exc: return f"Memory error: {exc}"
def _clear_memory():
    try:
        from brain.long_memory import LongMemory; LongMemory().clear_all()
        return "All memory cleared. Starting fresh."
    except Exception as exc: return f"Error: {exc}"

# Help
def _help():
    return (
        "I can do almost anything! Here's a quick rundown: "
        "Open or close any app. Search YouTube or Google. "
        "Check weather, CPU, RAM, battery, disk, network. "
        "Set timers and reminders. Take and read voice notes. "
        "Shopping list, expense tracking, habit tracking. "
        "Control Spotify playback. Read your clipboard. "
        "Take screenshots and read your screen. "
        "Type text and press keyboard shortcuts for you. "
        "Find files on your computer. "
        "Run git commands, manage Docker containers. "
        "Check if websites are up. Read the news. "
        "Do math calculations. Send WhatsApp messages. "
        "Control smart home devices. Get a morning briefing. "
        "And anything else — just ask and I'll figure it out."
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Router entry point
# ═══════════════════════════════════════════════════════════════════════════════

def route_command(text: str) -> tuple[bool, str]:
    for pattern, handler in _COMPILED:
        m = pattern.search(text)
        if m:
            try:
                response = handler(m)
                logger.info("Matched [%s]", pattern.pattern[:50])
                return True, response
            except Exception as exc:
                logger.error("Handler error: %s", exc)
                return True, f"Ran into a problem: {exc}"
    return False, ""
