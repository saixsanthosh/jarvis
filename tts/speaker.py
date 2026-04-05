"""
tts/speaker.py — Text-to-speech output (v2 — real-time optimised).

Engine priority (configurable via TTS_ENGINE in config.py)
──────────────────────────────────────────────────────────
1. Edge TTS    — Microsoft neural voices, very fast, natural sound
                 Needs internet. No API key.  pip install edge-tts
2. Piper TTS   — Ultra-fast local neural TTS (~0.1s per sentence)
                 Fully offline.  pip install piper-tts
3. Coqui TTS   — High quality but slow (~1-3s per sentence)
                 pip install TTS
4. pyttsx3      — System TTS, instant but robotic
                 pip install pyttsx3

Playback priority
─────────────────
1. pygame.mixer — Fast, cross-platform, handles MP3 + WAV
2. mpv          — Ultra-fast CLI player (apt install mpv)
3. ffplay       — From ffmpeg suite
4. aplay/afplay — System default (WAV only)

For real-time voice conversation, use Edge TTS + pygame:
    pip install edge-tts pygame
"""

from __future__ import annotations

import asyncio
import io
import os
import platform
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

from utils.logger import setup_logger

logger = setup_logger(__name__)

_SYSTEM = platform.system()


class Speaker:
    """Speaks text using the best available TTS engine."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._engine: str = "none"
        self._tts = None
        self._player: str = "none"
        self._pygame_mixer = None

        # Dedicated event loop for async TTS engines (Edge TTS)
        self._loop = None
        self._loop_thread = None

        self._detect_player()
        self._load_engine()

    # ══════════════════════════════════════════════════════════════════════════
    # Audio player detection
    # ══════════════════════════════════════════════════════════════════════════

    def _detect_player(self) -> None:
        """Find the fastest available audio player."""
        # 1. pygame (best: fast, cross-platform, handles MP3)
        try:
            import pygame  # type: ignore
            pygame.mixer.init(frequency=24000)
            self._pygame_mixer = pygame.mixer
            self._player = "pygame"
            logger.info("Audio player: pygame ✓")
            return
        except ImportError:
            pass
        except Exception as exc:
            logger.debug("pygame init failed: %s", exc)

        # 2. mpv
        if shutil.which("mpv"):
            self._player = "mpv"
            logger.info("Audio player: mpv ✓")
            return

        # 3. ffplay
        if shutil.which("ffplay"):
            self._player = "ffplay"
            logger.info("Audio player: ffplay ✓")
            return

        # 4. System defaults
        if _SYSTEM == "Linux" and shutil.which("aplay"):
            self._player = "aplay"
        elif _SYSTEM == "Darwin":
            self._player = "afplay"
        elif _SYSTEM == "Windows":
            self._player = "winsound"
        else:
            self._player = "none"
        logger.info("Audio player: %s", self._player)

    def _play_audio(self, path: str) -> None:
        """Play an audio file (MP3 or WAV) using the detected player."""
        try:
            if self._player == "pygame":
                self._play_pygame(path)
            elif self._player == "mpv":
                subprocess.run(
                    ["mpv", "--no-terminal", "--no-video", path],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            elif self._player == "ffplay":
                subprocess.run(
                    ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            elif self._player == "aplay":
                # aplay only supports WAV — if MP3, try paplay or convert
                if path.endswith(".mp3"):
                    ret = os.system(f"paplay '{path}' 2>/dev/null")
                    if ret != 0:
                        # Convert to WAV via ffmpeg fallback
                        wav_path = path.replace(".mp3", ".wav")
                        os.system(f"ffmpeg -y -i '{path}' '{wav_path}' 2>/dev/null")
                        os.system(f"aplay -q '{wav_path}' 2>/dev/null")
                        try:
                            os.unlink(wav_path)
                        except OSError:
                            pass
                else:
                    ret = os.system(f"aplay -q '{path}' 2>/dev/null")
                    if ret != 0:
                        os.system(f"paplay '{path}' 2>/dev/null")
            elif self._player == "afplay":
                os.system(f"afplay '{path}'")
            elif self._player == "winsound":
                import winsound  # type: ignore
                winsound.PlaySound(path, winsound.SND_FILENAME)
        except Exception as exc:
            logger.error("Audio playback error: %s", exc)

    def _play_pygame(self, path: str) -> None:
        """Play audio via pygame.mixer with proper cleanup."""
        import pygame  # type: ignore
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.wait(20)
        except Exception as exc:
            logger.error("pygame playback error: %s", exc)

    # ══════════════════════════════════════════════════════════════════════════
    # TTS engine loading
    # ══════════════════════════════════════════════════════════════════════════

    def _load_engine(self) -> None:
        """Load TTS engine based on config preference."""
        from config import TTS_ENGINE

        if TTS_ENGINE == "auto":
            # Try engines in performance order
            for loader in [self._try_edge, self._try_piper, self._try_coqui, self._try_pyttsx3]:
                if loader():
                    return
        elif TTS_ENGINE == "edge":
            if self._try_edge():
                return
        elif TTS_ENGINE == "piper":
            if self._try_piper():
                return
        elif TTS_ENGINE == "coqui":
            if self._try_coqui():
                return
        elif TTS_ENGINE == "pyttsx3":
            if self._try_pyttsx3():
                return

        # If preferred engine failed, try fallbacks
        if self._engine == "none":
            for loader in [self._try_edge, self._try_piper, self._try_coqui, self._try_pyttsx3]:
                if loader():
                    return

        if self._engine == "none":
            logger.error(
                "No TTS engine available. Responses will be printed only.\n"
                "Install one of:\n"
                "  pip install edge-tts pygame    (recommended — fast + natural)\n"
                "  pip install piper-tts          (fast + offline)\n"
                "  pip install TTS                (Coqui — slow but customisable)\n"
                "  pip install pyttsx3            (robotic but instant)"
            )

    # ── Edge TTS ──────────────────────────────────────────────────────────────

    def _try_edge(self) -> bool:
        try:
            import edge_tts  # type: ignore  # noqa: F401
            self._engine = "edge"
            # Start a dedicated event loop for async edge-tts calls
            self._loop = asyncio.new_event_loop()
            self._loop_thread = threading.Thread(
                target=self._loop.run_forever,
                name="edge-tts-loop",
                daemon=True,
            )
            self._loop_thread.start()
            logger.info("Edge TTS ready ✓ (fast neural voices)")
            return True
        except ImportError:
            logger.debug("edge-tts not installed (pip install edge-tts)")
        except Exception as exc:
            logger.debug("Edge TTS init failed: %s", exc)
        return False

    # ── Piper TTS ─────────────────────────────────────────────────────────────

    def _try_piper(self) -> bool:
        try:
            # Check if piper binary or python package is available
            if shutil.which("piper"):
                self._engine = "piper_cli"
                logger.info("Piper TTS ready ✓ (CLI mode — fast offline)")
                return True

            import piper  # type: ignore  # noqa: F401
            self._engine = "piper"
            logger.info("Piper TTS ready ✓ (Python mode — fast offline)")
            return True
        except ImportError:
            logger.debug("piper-tts not installed (pip install piper-tts)")
        except Exception as exc:
            logger.debug("Piper TTS init failed: %s", exc)
        return False

    # ── Coqui TTS ─────────────────────────────────────────────────────────────

    def _try_coqui(self) -> bool:
        try:
            from TTS.api import TTS  # type: ignore
            from config import TTS_MODEL, TTS_USE_GPU

            logger.info("Loading Coqui TTS '%s'…", TTS_MODEL)
            self._tts = TTS(model_name=TTS_MODEL, gpu=TTS_USE_GPU, progress_bar=False)
            self._engine = "coqui"
            logger.info("Coqui TTS ready ✓ (slow but high quality)")
            return True
        except ImportError:
            logger.debug("Coqui TTS not installed (pip install TTS)")
        except Exception as exc:
            logger.debug("Coqui TTS init failed: %s", exc)
        return False

    # ── pyttsx3 ───────────────────────────────────────────────────────────────

    def _try_pyttsx3(self) -> bool:
        try:
            import pyttsx3  # type: ignore

            engine = pyttsx3.init()
            engine.setProperty("rate", 175)
            engine.setProperty("volume", 0.92)
            self._tts = engine
            self._engine = "pyttsx3"
            logger.info("pyttsx3 TTS ready ✓ (fallback mode)")
            return True
        except Exception as exc:
            logger.debug("pyttsx3 init failed: %s", exc)
        return False

    # ══════════════════════════════════════════════════════════════════════════
    # Synthesis methods
    # ══════════════════════════════════════════════════════════════════════════

    def _speak_edge(self, text: str) -> None:
        """Synthesise via Edge TTS (async) and play the result."""
        import edge_tts  # type: ignore
        from config import EDGE_TTS_VOICE, EDGE_TTS_RATE, EDGE_TTS_PITCH

        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp_path = tmp.name
        tmp.close()

        async def _synth():
            communicate = edge_tts.Communicate(
                text,
                voice=EDGE_TTS_VOICE,
                rate=EDGE_TTS_RATE,
                pitch=EDGE_TTS_PITCH,
            )
            await communicate.save(tmp_path)

        try:
            # Run in the dedicated async loop
            future = asyncio.run_coroutine_threadsafe(_synth(), self._loop)
            future.result(timeout=15)  # 15s safety timeout
            self._play_audio(tmp_path)
        except Exception as exc:
            logger.error("Edge TTS error: %s", exc)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def _speak_piper_cli(self, text: str) -> None:
        """Synthesise via Piper CLI and play."""
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp_path = tmp.name
        tmp.close()

        try:
            from config import PIPER_MODEL_PATH
            cmd = ["piper", "--output_file", tmp_path]
            if PIPER_MODEL_PATH:
                cmd.extend(["--model", PIPER_MODEL_PATH])
            proc = subprocess.run(
                cmd,
                input=text,
                text=True,
                capture_output=True,
                timeout=15,
            )
            if proc.returncode == 0:
                self._play_audio(tmp_path)
            else:
                logger.error("Piper CLI error: %s", proc.stderr)
        except Exception as exc:
            logger.error("Piper TTS error: %s", exc)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def _speak_piper_python(self, text: str) -> None:
        """Synthesise via piper-tts Python package."""
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp_path = tmp.name
        tmp.close()

        try:
            import piper  # type: ignore
            from config import PIPER_MODEL_PATH, PIPER_SPEAKER_ID

            voice = piper.PiperVoice.load(PIPER_MODEL_PATH)
            with open(tmp_path, "wb") as wav_file:
                voice.synthesize(text, wav_file, speaker_id=PIPER_SPEAKER_ID)
            self._play_audio(tmp_path)
        except Exception as exc:
            logger.error("Piper Python error: %s", exc)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def _speak_coqui(self, text: str) -> None:
        """Synthesise via Coqui TTS."""
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp_path = tmp.name
        tmp.close()

        try:
            self._tts.tts_to_file(text=text, file_path=tmp_path)
            self._play_audio(tmp_path)
        except Exception as exc:
            logger.error("Coqui TTS error: %s", exc)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def _speak_pyttsx3(self, text: str) -> None:
        """Synthesise via pyttsx3."""
        self._tts.say(text)
        self._tts.runAndWait()

    # ══════════════════════════════════════════════════════════════════════════
    # Public API
    # ══════════════════════════════════════════════════════════════════════════

    def speak(self, text: str) -> None:
        """
        Synthesise and play *text* aloud.

        Thread-safe: concurrent calls are serialised via a lock.
        Always prints to stdout so text mode works without audio.
        """
        text = text.strip()
        if not text:
            return

        snippet = text[:70] + ("…" if len(text) > 70 else "")
        logger.info("🔊 [%s] %s", self._engine, snippet)
        print(f"\n  [JARVIS]: {text}\n")

        with self._lock:
            try:
                if self._engine == "edge":
                    self._speak_edge(text)
                elif self._engine == "piper_cli":
                    self._speak_piper_cli(text)
                elif self._engine == "piper":
                    self._speak_piper_python(text)
                elif self._engine == "coqui":
                    self._speak_coqui(text)
                elif self._engine == "pyttsx3":
                    self._speak_pyttsx3(text)
                # "none" → already printed above
            except Exception as exc:
                logger.error("TTS speak error: %s", exc, exc_info=True)

    @property
    def engine_name(self) -> str:
        return self._engine

    @property
    def player_name(self) -> str:
        return self._player
