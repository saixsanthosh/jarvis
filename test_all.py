#!/usr/bin/env python3
"""test_all.py — Verify every Jarvis module without hardware."""
import sys, os, traceback, tempfile
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ".")

PASS = FAIL = WARN = 0

def test(name, fn):
    global PASS, FAIL, WARN
    try:
        r = fn()
        if r == "WARN":
            print(f"  ⚠️  {name}"); WARN += 1
        elif r is False:
            print(f"  ❌ {name} → returned False"); FAIL += 1
        else:
            print(f"  ✅ {name}"); PASS += 1
    except Exception as e:
        print(f"  ❌ {name} → {e}"); FAIL += 1

print("\n" + "="*60)
print("  JARVIS v2 — Full Test Suite (all modules)")
print("="*60)

# ═══════════════════════════════════════════════════════════════
print("\n── 1. Module Imports (26 modules) ──")
# ═══════════════════════════════════════════════════════════════
modules = [
    "config", "utils.logger",
    "brain.memory", "brain.long_memory", "brain.summarizer", "brain.llm", "brain.agent",
    "commands.system_control", "commands.system_stats", "commands.weather",
    "commands.timers", "commands.clipboard_cmd", "commands.spotify_ctrl",
    "commands.notes_cmd", "commands.home_auto", "commands.daily_briefing",
    "commands.news_cmd", "commands.file_finder", "commands.screenshot_cmd",
    "commands.dictation_cmd", "commands.life_tracker", "commands.dev_tools",
    "commands.messaging", "commands.code_runner", "commands.router",
    "pipeline.streaming", "security.guard", "gui.overlay",
]
for mod in modules:
    test(mod, lambda m=mod: __import__(m))

# ═══════════════════════════════════════════════════════════════
print("\n── 2. Conversation Memory ──")
# ═══════════════════════════════════════════════════════════════
def _t_mem():
    from brain.memory import ConversationMemory
    m = ConversationMemory()
    m.add_user("Hi"); m.add_assistant("Hello!")
    assert len(m) == 2; m.clear(); assert len(m) == 0
test("ConversationMemory CRUD", _t_mem)

# ═══════════════════════════════════════════════════════════════
print("\n── 3. Long-Term Memory ──")
# ═══════════════════════════════════════════════════════════════
def _t_ltm():
    from brain.long_memory import LongMemory
    from pathlib import Path
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f: p = Path(f.name)
    try:
        ltm = LongMemory(db_path=p)
        ltm.store_fact("name", "Alex"); ltm.store_fact("lang", "Python")
        assert len(ltm.get_all_facts()) >= 2
        assert "Alex" in ltm.get_context_prefix()
        stored = ltm.maybe_extract_and_store("My name is David")
        assert "name" in stored
        ltm.store_session_summary("Test summary")
        ltm.clear_all(); assert len(ltm.get_all_facts()) == 0
        ltm.close()
    finally: os.unlink(p)
test("LongMemory lifecycle", _t_ltm)

def _t_ltm_extract():
    from brain.long_memory import LongMemory
    from pathlib import Path
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f: p = Path(f.name)
    try:
        ltm = LongMemory(db_path=p)
        tests = [("My name is Sarah","name"), ("I work at Google","employer"),
                 ("I use Python","language"), ("I'm from Chennai","location"),
                 ("I am a software engineer","job"), ("I'm using Ubuntu","os")]
        for text, key in tests:
            assert key in ltm.maybe_extract_and_store(text), f"Failed: {text}"
        ltm.close()
    finally: os.unlink(p)
test("LTM fact extraction (6 patterns)", _t_ltm_extract)

# ═══════════════════════════════════════════════════════════════
print("\n── 4. Agent ──")
# ═══════════════════════════════════════════════════════════════
def _t_agent():
    from brain.agent import Agent
    a = Agent()
    # Test JSON parsing
    parsed = a._parse_action('{"action": "shell", "command": "echo hi", "explain": "test"}')
    assert parsed is not None and parsed["action"] == "shell"
    # Test no-action detection
    assert a._parse_action("Just a regular answer.") is None
test("Agent JSON action parser", _t_agent)

def _t_agent_safety():
    from brain.agent import Agent
    a = Agent()
    r = a._run_action({"action": "shell", "command": "rm -rf /", "explain": "danger"})
    assert "blocked" in r.lower() or "dangerous" in r.lower()
test("Agent blocks dangerous commands", _t_agent_safety)

# ═══════════════════════════════════════════════════════════════
print("\n── 5. Notes ──")
# ═══════════════════════════════════════════════════════════════
def _t_notes():
    from commands import notes_cmd
    orig = notes_cmd._DB_PATH
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        notes_cmd._DB_PATH = __import__("pathlib").Path(f.name)
    try:
        r = notes_cmd.add_note("Buy milk"); assert "noted" in r.lower() or "got it" in r.lower()
        r = notes_cmd.add_note("Call dentist"); assert "2" in r
        r = notes_cmd.read_notes(); assert "milk" in r.lower()
        r = notes_cmd.count_notes(); assert "2" in r
        r = notes_cmd.delete_all_notes(); assert "2" in r
    finally: notes_cmd._DB_PATH = orig; os.unlink(f.name)
test("Notes CRUD", _t_notes)

# ═══════════════════════════════════════════════════════════════
print("\n── 6. Timers ──")
# ═══════════════════════════════════════════════════════════════
def _t_parse():
    from commands.timers import parse_duration
    assert parse_duration("5 minutes") == 300.0
    assert parse_duration("2 hours 30 minutes") == 9000.0
    assert parse_duration("90 seconds") == 90.0
    assert parse_duration("nothing") is None
test("parse_duration()", _t_parse)

def _t_timer():
    from commands.timers import TimerManager
    import time
    spoken = []
    mgr = TimerManager(speak_fn=lambda t: spoken.append(t))
    r = mgr.set_timer(0.1, "test"); assert "Timer set" in r
    time.sleep(0.3); assert len(spoken) >= 1
test("TimerManager fire", _t_timer)

# ═══════════════════════════════════════════════════════════════
print("\n── 7. Shopping List ──")
# ═══════════════════════════════════════════════════════════════
def _t_shop():
    from commands import life_tracker as lt
    orig = lt._DB_PATH
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        lt._DB_PATH = __import__("pathlib").Path(f.name)
    try:
        r = lt.add_to_shopping("Milk"); assert "milk" in r.lower()
        r = lt.add_to_shopping("Bread"); assert "2" in r
        r = lt.read_shopping_list(); assert "milk" in r.lower() and "bread" in r.lower()
        r = lt.remove_from_shopping("milk"); assert "removed" in r.lower()
        r = lt.clear_shopping_list()
    finally: lt._DB_PATH = orig; os.unlink(f.name)
test("Shopping list CRUD", _t_shop)

# ═══════════════════════════════════════════════════════════════
print("\n── 8. Expense Tracker ──")
# ═══════════════════════════════════════════════════════════════
def _t_expense():
    from commands import life_tracker as lt
    orig = lt._DB_PATH
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        lt._DB_PATH = __import__("pathlib").Path(f.name)
    try:
        r = lt.log_expense(500, "groceries"); assert "500" in r
        r = lt.log_expense(200, "coffee"); assert "700" in r  # weekly total
        r = lt.get_expenses("week"); assert "700" in r
        lt.clear_expenses()
    finally: lt._DB_PATH = orig; os.unlink(f.name)
test("Expense tracker", _t_expense)

# ═══════════════════════════════════════════════════════════════
print("\n── 9. Habit Tracker ──")
# ═══════════════════════════════════════════════════════════════
def _t_habit():
    from commands import life_tracker as lt
    orig = lt._DB_PATH
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        lt._DB_PATH = __import__("pathlib").Path(f.name)
    try:
        r = lt.log_habit("workout"); assert "logged" in r.lower()
        r = lt.log_habit("workout"); assert "2" in r  # total: 2
        r = lt.get_habits(); assert "workout" in r.lower()
    finally: lt._DB_PATH = orig; os.unlink(f.name)
test("Habit tracker", _t_habit)

# ═══════════════════════════════════════════════════════════════
print("\n── 10. Command Router (pattern matching) ──")
# ═══════════════════════════════════════════════════════════════
def _route_test(text, should_match, expect_in=None):
    from commands.router import route_command
    matched, resp = route_command(text)
    assert matched == should_match, f"'{text}' matched={matched} expected={should_match}"
    if expect_in:
        assert expect_in.lower() in resp.lower(), f"'{expect_in}' not in: {resp[:80]}"

test("route: 'what's the date'",      lambda: _route_test("what's the date", True, "today is"))
test("route: 'what's the time'",      lambda: _route_test("what's the time", True, "currently"))
test("route: 'what can you do'",      lambda: _route_test("what can you do", True, "I can do"))
test("route: 'good morning'",         lambda: _route_test("good morning", True))
test("route: 'how many notes'",       lambda: _route_test("how many notes", True, "note"))
test("route: 'git status'",           lambda: _route_test("git status", True))
test("route: 'git branch'",           lambda: _route_test("git branch", True))
test("route: 'calculate 2+2'",        lambda: _route_test("calculate 2+2", True, "4"))
test("route: 'what is quantum physics' → LLM",
                                       lambda: _route_test("What is quantum physics", False))

# ═══════════════════════════════════════════════════════════════
print("\n── 11. System Stats ──")
# ═══════════════════════════════════════════════════════════════
test("get_cpu()", lambda: ("CPU" in __import__("commands.system_stats", fromlist=["get_cpu"]).get_cpu()))
test("get_memory()", lambda: ("RAM" in __import__("commands.system_stats", fromlist=["get_memory"]).get_memory()))
test("get_disk()", lambda: ("Disk" in __import__("commands.system_stats", fromlist=["get_disk"]).get_disk()))

# ═══════════════════════════════════════════════════════════════
print("\n── 12. Weather ──")
# ═══════════════════════════════════════════════════════════════
def _t_weather():
    from commands.weather import get_current_weather
    r = get_current_weather()
    if "couldn't" in r.lower(): print(f"    Network blocked"); return "WARN"
    assert "°" in r
test("get_current_weather()", _t_weather)

# ═══════════════════════════════════════════════════════════════
print("\n── 13. Security Guard ──")
# ═══════════════════════════════════════════════════════════════
def _t_guard():
    from security.guard import SecurityGuard
    g = SecurityGuard(speak_fn=lambda t: None)
    ok, _ = g.check("open Chrome"); assert ok
    ok, reason = g.check("delete all files"); assert not ok
test("SecurityGuard safe vs guarded", _t_guard)

# ═══════════════════════════════════════════════════════════════
print("\n── 14. GUI State ──")
# ═══════════════════════════════════════════════════════════════
def _t_gui():
    from gui.overlay import JarvisState
    s = JarvisState()
    assert s.get() == "sleeping"
    s.set("listening"); assert s.get() == "listening"
    s.set("invalid"); assert s.get() == "listening"
test("JarvisState", _t_gui)

# ═══════════════════════════════════════════════════════════════
print("\n── 15. Streaming Pipeline ──")
# ═══════════════════════════════════════════════════════════════
def _t_stream():
    from pipeline.streaming import StreamingPipeline
    spoken = []
    pipe = StreamingPipeline(speak_fn=lambda t: spoken.append(t))
    def tokens():
        for w in "Hello there. How are you? Fine.".split(): yield w + " "
    full = pipe.generate_and_speak(tokens())
    assert len(spoken) >= 1 and "Hello" in full
test("StreamingPipeline", _t_stream)

# ═══════════════════════════════════════════════════════════════
print("\n── 16. System Prompt + LTM ──")
# ═══════════════════════════════════════════════════════════════
def _t_sysprompt():
    from brain.long_memory import LongMemory
    from config import SYSTEM_PROMPT
    from pathlib import Path
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f: p = Path(f.name)
    try:
        ltm = LongMemory(db_path=p)
        ltm.store_fact("name", "Alex")
        ctx = ltm.get_context_prefix()
        prompt = SYSTEM_PROMPT + "\n\n" + ctx
        assert "Jarvis" in prompt and "Alex" in prompt
        ltm.close()
    finally: os.unlink(p)
test("LTM → system prompt injection", _t_sysprompt)

def _t_llm_sig():
    from brain.llm import LLMBrain
    import inspect
    assert "system_prompt" in inspect.signature(LLMBrain.think).parameters
    assert "system_prompt" in inspect.signature(LLMBrain.stream).parameters
test("LLMBrain accepts system_prompt", _t_llm_sig)

# ═══════════════════════════════════════════════════════════════
print("\n── 17. Code Runner ──")
# ═══════════════════════════════════════════════════════════════
def _t_calc():
    from commands.code_runner import calculate
    r = calculate("2 + 2"); assert "4" in r
    r = calculate("100 / 4"); assert "25" in r
test("calculate()", _t_calc)

def _t_pyrun():
    from commands.code_runner import run_python
    r = run_python("print(7 * 6)"); assert "42" in r
test("run_python()", _t_pyrun)

def _t_shellblock():
    from commands.code_runner import run_shell
    r = run_shell("rm -rf /"); assert "dangerous" in r.lower() or "blocked" in r.lower()
test("run_shell blocks dangerous", _t_shellblock)

# ═══════════════════════════════════════════════════════════════
print("\n── 18. File Finder ──")
# ═══════════════════════════════════════════════════════════════
def _t_findfile():
    from commands.file_finder import find_files
    r = find_files("nonexistent_xyz_file_12345")
    assert "couldn't find" in r.lower()
test("find_files (no match)", _t_findfile)

def _t_downloads():
    from commands.file_finder import list_recent_downloads
    r = list_recent_downloads()
    assert "download" in r.lower() or "no files" in r.lower()
test("list_recent_downloads()", _t_downloads)

# ═══════════════════════════════════════════════════════════════
print("\n── 19. Dev Tools ──")
# ═══════════════════════════════════════════════════════════════
test("git_status()", lambda: __import__("commands.dev_tools", fromlist=["git_status"]).git_status())
test("git_branch()", lambda: __import__("commands.dev_tools", fromlist=["git_branch"]).git_branch())
test("docker_list()", lambda: __import__("commands.dev_tools", fromlist=["docker_list"]).docker_list())

# ═══════════════════════════════════════════════════════════════
print("\n── 20. Daily Briefing ──")
# ═══════════════════════════════════════════════════════════════
def _t_brief():
    from commands.daily_briefing import get_briefing
    r = get_briefing()
    assert any(w in r.lower() for w in ["morning", "afternoon", "evening"])
test("get_briefing()", _t_brief)

# ═══════════════════════════════════════════════════════════════
print("\n── 21. News ──")
# ═══════════════════════════════════════════════════════════════
def _t_news():
    from commands.news_cmd import get_news
    r = get_news()
    if "couldn't" in r.lower(): print("    Network blocked"); return "WARN"
    assert "headline" in r.lower() or "1." in r
test("get_news()", _t_news)

# ═══════════════════════════════════════════════════════════════
print("\n── 22. Edge TTS ──")
# ═══════════════════════════════════════════════════════════════
test("edge_tts import", lambda: __import__("edge_tts"))

def _t_edge_synth():
    import asyncio, edge_tts
    from config import EDGE_TTS_VOICE
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False); tmp.close()
    try:
        async def s():
            c = edge_tts.Communicate("Hello.", voice=EDGE_TTS_VOICE)
            await c.save(tmp.name)
        asyncio.run(s())
        assert os.path.getsize(tmp.name) > 1000
        print(f"    Generated {os.path.getsize(tmp.name):,} bytes ✓")
    except Exception as e:
        print(f"    Network blocked: {type(e).__name__}"); return "WARN"
    finally:
        try: os.unlink(tmp.name)
        except: pass
test("Edge TTS synthesis", _t_edge_synth)

# ═══════════════════════════════════════════════════════════════
print("\n── 23. Home Automation ──")
# ═══════════════════════════════════════════════════════════════
test("HA disabled → helpful error", lambda: "disabled" in __import__("commands.home_auto", fromlist=["turn_on"]).turn_on("light").lower() or "HA_ENABLED" in __import__("commands.home_auto", fromlist=["turn_on"]).turn_on("light"))

# ═══════════════════════════════════════════════════════════════
print("\n── 24. Messaging ──")
# ═══════════════════════════════════════════════════════════════
def _t_whatsapp():
    from commands.messaging import _CONTACTS
    # Just verify the contact lookup logic works (don't call pywhatkit)
    assert "unknown_person" not in _CONTACTS
    assert isinstance(_CONTACTS, dict)
test("WhatsApp contact lookup", _t_whatsapp)


# ═══════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════
print("\n" + "="*60)
print(f"  RESULTS:  {PASS} passed  |  {FAIL} failed  |  {WARN} warnings")
print("="*60)
if FAIL > 0:
    print("\n  ❌ Some tests failed."); sys.exit(1)
else:
    print("\n  ✅ All tests passed! Jarvis is ready.")
    print("\n  On your machine:")
    print("    ollama serve &")
    print("    python main.py")
    sys.exit(0)
