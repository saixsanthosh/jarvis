#!/usr/bin/env python3
"""
main.py — Jarvis v2 orchestrator.

Full pipeline
─────────────

  ┌──── BOOT ──────────────────────────────────────────────────────────────┐
  │  Load all subsystems in parallel where possible                        │
  │  Start GUI overlay + tray in daemon threads                            │
  │  Pre-warm Ollama with a silent ping                                    │
  └─────────────────────────────────┬──────────────────────────────────────┘
                                    │
  ┌──── WAKE PHASE (passive) ───────▼──────────────────────────────────────┐
  │  AudioListener.stream_chunks() → WakeDetector                          │
  │    ├─ openWakeWord ("hey_jarvis")                                      │
  │    └─ double-clap fallback                                             │
  └─────────────────────────────────┬──────────────────────────────────────┘
                                    │ wake event
  ┌──── AUTH GATE ──────────────────▼──────────────────────────────────────┐
  │  If VOICE_AUTH_ENABLED: record 2s → resemblyzer verify                 │
  │  If rejected: speak warning, return to wake phase                      │
  └─────────────────────────────────┬──────────────────────────────────────┘
                                    │ verified
  ┌──── ACTIVE CONVERSATION LOOP ───▼──────────────────────────────────────┐
  │                                                                         │
  │  record_until_silence() → Whisper transcribe()                          │
  │         │                                                               │
  │         ▼                                                               │
  │  SecurityGuard.check()  ←── guarded verb? ask spoken confirmation       │
  │         │                                                               │
  │         ▼                                                               │
  │  CommandRouter.route_command()                                          │
  │    ├─ MATCHED ──► speak(result)  [instant, no LLM]                     │
  │    └─ NO MATCH ──►                                                      │
  │         │  LongMemory.maybe_extract_and_store(user_text)               │
  │         │  LongMemory.get_context_prefix() → inject into system prompt │
  │         │  LLMBrain.stream(history) → StreamingPipeline                │
  │         │         ↓ tokens arrive                                       │
  │         │  Sentence buffer fills → TTS worker thread speaks sentence 1  │
  │         │  … LLM still generating …                                     │
  │         │  Sentence buffer fills → TTS worker thread speaks sentence 2  │
  │         │                                                               │
  │  Update GUI state, waveform throughout                                  │
  │                                                                         │
  │  If message_count >= SUMMARIZE_AFTER_N_MESSAGES:                        │
  │      Summarizer.summarize(history) → LongMemory.store_session_summary  │
  │      Reset short-term memory to summary stub                            │
  │                                                                         │
  │  Loop until EXIT_PHRASE → return to wake phase                          │
  └─────────────────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import signal
import sys
import threading
import time

# ── Subsystems ────────────────────────────────────────────────────────────────
from audio.listener    import AudioListener
from audio.transcriber import Transcriber
from audio.voice_auth  import VoiceAuth
from audio.wake_detector import WakeDetector

from brain.llm         import LLMBrain
from brain.long_memory import LongMemory
from brain.memory      import ConversationMemory
from brain.summarizer  import Summarizer
from brain.agent       import Agent

from commands.router   import route_command, set_timer_manager
from commands.timers   import TimerManager

from gui.overlay import JarvisState, WaveformOverlay
from gui.tray    import TrayIcon

from pipeline.streaming import StreamingPipeline

from security.guard import SecurityGuard

from tts.speaker import Speaker

from config import (
    EXIT_PHRASES,
    GUI_OVERLAY_ENABLED,
    GUI_TRAY_ENABLED,
    STREAM_ENABLED,
    SUMMARIZE_AFTER_N_MESSAGES,
    VOICE_AUTH_ENABLED,
    SYSTEM_PROMPT,
)
from utils.logger import setup_logger

logger = setup_logger("jarvis")

_BANNER = """
╔══════════════════════════════════════════════════════════════╗
║          J A R V I S  v2 — Local AI Assistant               ║
╠══════════════════════════════════════════════════════════════╣
║  Wake     →  "Wake up daddy's home" / "Yo Jarvis" / clap    ║
║  Sleep    →  "stop" / "sleep" / "goodbye"                   ║
║  Anything →  Just say it — Jarvis will figure it out!       ║
║  Quit     →  Ctrl-C                                          ║
╚══════════════════════════════════════════════════════════════╝
"""


class Jarvis:
    """Top-level controller wiring all v2 subsystems."""

    def __init__(self) -> None:
        logger.info("Booting Jarvis v2…")

        # ── Core audio / speech ───────────────────────────────────────────
        self.listener    = AudioListener()
        self.transcriber = Transcriber()
        self.wake        = WakeDetector(transcribe_fn=self.transcriber.transcribe)
        self.speaker     = Speaker()

        # ── Intelligence ──────────────────────────────────────────────────
        self.brain       = LLMBrain()
        self.memory      = ConversationMemory()
        self.ltm         = LongMemory()
        self.summarizer  = Summarizer()
        self.voice_auth  = VoiceAuth()

        # ── Commands ──────────────────────────────────────────────────────
        self.timer_mgr   = TimerManager(speak_fn=self._safe_speak)
        set_timer_manager(self.timer_mgr)

        # ── Security ──────────────────────────────────────────────────────
        self.guard = SecurityGuard(
            speak_fn      = self._safe_speak,
            listen_fn     = self.listener.record_until_silence,
            transcribe_fn = self.transcriber.transcribe,
        )

        # ── Agent (handles anything not matched by commands) ───────────
        self.agent = Agent(
            speak_fn=self._safe_speak,
            confirm_fn=self._voice_confirm,
        )

        # ── GUI state (shared across threads) ─────────────────────────────
        self.gui_state   = JarvisState()

        # ── Streaming pipeline ────────────────────────────────────────────
        self.stream_pipe = StreamingPipeline(speak_fn=self._safe_speak)

        # ── Runtime flags ─────────────────────────────────────────────────
        self._running       = False
        self._speak_lock    = threading.Lock()
        self._session_turns = 0

        # Shutdown hooks
        signal.signal(signal.SIGINT,  self._on_sigint)
        signal.signal(signal.SIGTERM, self._on_sigint)

        logger.info("All subsystems initialised ✓")

    # ── Signal handling ───────────────────────────────────────────────────────

    def _on_sigint(self, _sig, _frame) -> None:
        print("\n[Jarvis] Shutting down…")
        self._running = False
        self.listener.cleanup()
        self.ltm.close()
        sys.exit(0)

    # ── GUI launch ────────────────────────────────────────────────────────────

    def _start_gui(self) -> None:
        if GUI_OVERLAY_ENABLED:
            overlay = WaveformOverlay(self.gui_state)
            threading.Thread(target=overlay.run, name="overlay", daemon=True).start()
            logger.info("Overlay thread started.")

        if GUI_TRAY_ENABLED:
            tray = TrayIcon(self.gui_state, exit_fn=self._on_sigint)
            threading.Thread(target=tray.run, name="tray", daemon=True).start()
            logger.info("Tray thread started.")

    # ── Ollama pre-warm ───────────────────────────────────────────────────────

    def _prewarm_ollama(self) -> None:
        """Send a lightweight request so the model is loaded before first use."""
        def _warm():
            try:
                import requests
                from config import OLLAMA_BASE_URL, OLLAMA_MODEL
                requests.post(
                    f"{OLLAMA_BASE_URL}/api/generate",
                    json={"model": OLLAMA_MODEL, "prompt": "hi", "stream": False,
                          "options": {"num_predict": 1}},
                    timeout=30,
                )
                logger.info("Ollama pre-warmed ✓")
            except Exception as exc:
                logger.debug("Pre-warm skipped: %s", exc)
        threading.Thread(target=_warm, name="prewarm", daemon=True).start()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _safe_speak(self, text: str) -> None:
        """Thread-safe wrapper around speaker.speak that updates GUI state."""
        self.gui_state.set("speaking")
        self.speaker.speak(text)
        self.gui_state.set("active")

    def _voice_confirm(self, prompt: str) -> bool:
        """Speak a confirmation prompt, listen for yes/no."""
        self._safe_speak(prompt)
        try:
            audio = self.listener.record_until_silence()
            text = self.transcriber.transcribe(audio).lower().strip()
            return "yes" in text or "confirm" in text or "go ahead" in text
        except Exception:
            return False

    @staticmethod
    def _is_exit(text: str) -> bool:
        t = text.lower()
        return any(phrase in t for phrase in EXIT_PHRASES)

    def _build_system_prompt(self) -> str:
        """Inject long-term memory facts into the base system prompt."""
        context = self.ltm.get_context_prefix()
        if context:
            return SYSTEM_PROMPT + "\n\n" + context
        return SYSTEM_PROMPT

    # ── Voice auth ────────────────────────────────────────────────────────────

    def _authenticate(self) -> bool:
        """
        If voice auth is enabled and enrollment exists, verify the speaker.
        Returns True (allow) or False (deny).
        """
        if not VOICE_AUTH_ENABLED or not self.voice_auth.is_ready():
            return True

        logger.info("Running voice authentication…")
        self._safe_speak("One moment — verifying identity.")
        audio = self.listener.record_until_silence()
        if self.voice_auth.verify(audio):
            logger.info("Voice auth passed ✓")
            return True
        else:
            self._safe_speak(
                "Sorry, I don't recognise that voice. Access denied."
            )
            logger.warning("Voice auth FAILED — rejecting session.")
            return False

    # ── Context management ────────────────────────────────────────────────────

    def _maybe_summarize(self) -> None:
        """Auto-summarise and compress the conversation if it's grown too long."""
        if len(self.memory) < SUMMARIZE_AFTER_N_MESSAGES:
            return

        logger.info("Summarising conversation (%d messages)…", len(self.memory))
        history = self.memory.get_history()
        summary = self.summarizer.summarize(history)

        if summary:
            self.ltm.store_session_summary(summary)
            # Reset to a single "context" message
            self.memory.clear()
            self.memory.add_assistant(
                f"[Earlier summary]: {summary}"
            )
            logger.info("Context compressed.")

    # ── Response pipeline ─────────────────────────────────────────────────────

    def _process(self, user_text: str) -> None:
        """
        Route → security check → command OR LLM → speak.
        All GUI state changes happen here.
        """
        # 1. Command router (no LLM, instant)
        matched, cmd_response = route_command(user_text)
        if matched:
            # Check security guard for dangerous commands
            ok, reason = self.guard.check(user_text)
            if not ok:
                self._safe_speak(reason or "Command blocked for safety.")
                return
            self._safe_speak(cmd_response)
            return

        # 2. LLM + Agent path
        # Extract any facts worth remembering
        stored_keys = self.ltm.maybe_extract_and_store(user_text)
        if stored_keys:
            logger.info("Auto-stored facts: %s", stored_keys)

        # Try the Agent first — it can execute actions on the computer
        # (run commands, open files, type text, etc.)
        self.gui_state.set("thinking")
        agent_context = self.ltm.get_context_prefix()
        agent_result = self.agent.execute(user_text, context=agent_context)

        if agent_result:
            # Agent handled it (ran a command, opened something, etc.)
            self._safe_speak(agent_result)
            self.memory.add_user(user_text)
            self.memory.add_assistant(agent_result)
            self._session_turns += 1
            self._maybe_summarize()
            return

        # 3. Regular LLM path (for questions, conversation, etc.)
        # Update memory with user turn
        self.memory.add_user(user_text)

        # Build messages with fresh system prompt (includes LTM facts)
        messages = self.memory.get_history()
        sys_prompt = self._build_system_prompt()

        self.gui_state.set("thinking")

        if STREAM_ENABLED:
            # ── Streaming: tokens flow directly into TTS sentence buffer ──
            token_gen = self.brain.stream(messages, system_prompt=sys_prompt)
            full_reply = self.stream_pipe.generate_and_speak(
                token_gen,
                on_token=lambda t: None,  # hook for future UI
            )
        else:
            # ── Blocking: wait for full reply, then speak ─────────────────
            full_reply = self.brain.think(messages, system_prompt=sys_prompt)
            self._safe_speak(full_reply)

        if full_reply:
            self.memory.add_assistant(full_reply)
            self._session_turns += 1
            self._maybe_summarize()

    # ── Conversation loop ─────────────────────────────────────────────────────

    def _converse(self) -> None:
        """Run one active conversation session until exit phrase or error."""
        self.gui_state.set("active")
        self._safe_speak("Yes? I'm listening.")
        self._session_turns = 0

        while self._running:
            # Record
            self.gui_state.set("listening")
            audio = self.listener.record_until_silence()

            # Transcribe
            self.gui_state.set("thinking")
            text = self.transcriber.transcribe(audio)

            if not text:
                logger.debug("Empty transcription — re-listening.")
                self.gui_state.set("active")
                continue

            print(f"\n  [YOU] {text}")

            # Exit phrase?
            if self._is_exit(text):
                self._safe_speak(
                    "Going to sleep. Say 'Hey Jarvis' or double-clap to wake me."
                )
                self.memory.clear()
                self.gui_state.set("sleeping")
                return

            # Run the full response pipeline
            try:
                self._process(text)
            except Exception as exc:
                logger.error("Process error: %s", exc, exc_info=True)
                self._safe_speak("I hit an unexpected error. Let's try again.")

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self) -> None:
        """Main entry point — boots subsystems then alternates wake/converse."""
        self._running = True
        print(_BANNER)

        # Launch GUI daemons
        self._start_gui()

        # Pre-warm Ollama in background
        self._prewarm_ollama()

        # Main wake → converse cycle
        while self._running:
            try:
                self.gui_state.set("sleeping")
                chunk_stream = self.listener.stream_chunks()
                trigger = self.wake.listen_for_wake(chunk_stream)
                logger.info("Wake event: %s", trigger)

                # Voice authentication gate
                if not self._authenticate():
                    time.sleep(2)
                    continue

                self._converse()

            except KeyboardInterrupt:
                break
            except Exception as exc:
                logger.error("Main loop error: %s", exc, exc_info=True)
                time.sleep(2)

        self.listener.cleanup()
        self.ltm.close()
        logger.info("Jarvis shutdown complete.")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    Jarvis().run()
