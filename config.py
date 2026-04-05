"""
config.py — Central configuration for Jarvis (v2 — full upgrade).
All tuneable parameters live here. Edit this before running.
"""

from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# ── Audio
SAMPLE_RATE: int = 16_000
CHANNELS: int = 1
CHUNK_SIZE: int = 1_024
SILENCE_THRESHOLD: int = 400
SILENCE_DURATION: float = 1.8
MAX_RECORD_SECONDS: int = 30

# ── Wake Detection
OWW_MODEL_NAME: str = "hey_jarvis"
OWW_THRESHOLD: float = 0.5
CLAP_ENERGY_THRESHOLD: int = 3_000
CLAP_MIN_GAP: float = 0.15
CLAP_MAX_GAP: float = 1.0

# Custom wake phrases — say ANY of these to wake Jarvis
# Uses Whisper to listen, so you can add whatever you want
CUSTOM_WAKE_PHRASES: list = [
    "wake up",
    "daddy's home",
    "wake up daddy's home",
    "hey jarvis",
    "yo jarvis",
    "jarvis",
    "hello jarvis",
    "ok jarvis",
    "hey buddy",
    "listen up",
]
# How often to check for wake phrases (seconds of audio to buffer)
WAKE_PHRASE_BUFFER_SECONDS: float = 3.0
# Minimum audio energy to trigger phrase check (skip silence)
WAKE_PHRASE_MIN_ENERGY: int = 500

# ── Whisper / STT
WHISPER_MODEL: str = "small"
WHISPER_DEVICE: str = "cpu"
WHISPER_COMPUTE_TYPE: str = "int8"
WHISPER_LANGUAGE: str = "en"

# ── LLM (Ollama)
OLLAMA_BASE_URL: str = "http://localhost:11434"
OLLAMA_MODEL: str = "llama3"
OLLAMA_TIMEOUT: int = 60
OLLAMA_MAX_TOKENS: int = 200

SYSTEM_PROMPT: str = (
    "You are Jarvis, a sharp, witty AI voice assistant running locally.\n"
    "Rules:\n"
    "- Be concise: 1-3 sentences unless asked for detail.\n"
    "- Speak naturally, like a helpful colleague.\n"
    "- Never say you are an AI or LLM.\n"
    "- Do not repeat the user's question back.\n"
    "- When referencing remembered facts, weave them in naturally."
)

# ── Streaming Pipeline (Performance)
STREAM_ENABLED: bool = True
STREAM_MIN_SENTENCE_CHARS: int = 20       # lower = faster first utterance
STREAM_SENTENCE_ENDINGS: str = ".!?;:"    # flush on these punctuation marks

# ── Long-term Memory
LTM_DB_PATH: Path = DATA_DIR / "memory.db"
LTM_MAX_FACTS: int = 300
LTM_RECALL_COUNT: int = 5
SUMMARIZE_AFTER_N_MESSAGES: int = 20

# ── Short-term Memory
MAX_CONTEXT_MESSAGES: int = 10

# ── Voice Authentication
VOICE_AUTH_ENABLED: bool = False
VOICE_AUTH_THRESHOLD: float = 0.80
VOICE_ENROLLMENT_PATH: Path = DATA_DIR / "owner_voice.npy"
VOICE_ENROLLMENT_SECONDS: int = 6

# ── Security Guard
GUARDED_VERBS: list = [
    "delete", "remove", "format", "shutdown", "restart",
    "kill", "wipe", "uninstall",
]
CONFIRMATION_TIMEOUT: float = 8.0
CONFIRMATION_PHRASE: str = "yes"
DENIAL_PHRASE: str = "no"

# ── TTS
# Engine priority: "edge" (fast + natural, needs internet)
#                  "piper" (fast + offline, needs piper-tts)
#                  "coqui" (high quality, slow, needs TTS package)
#                  "pyttsx3" (instant, robotic, always available)
#                  "auto" (tries in the order above)
TTS_ENGINE: str = "auto"

# Edge TTS (Microsoft free neural voices — best for real-time)
EDGE_TTS_VOICE: str = "en-US-GuyNeural"       # male, natural
# Other good voices:
#   "en-US-JennyNeural"      — female, warm
#   "en-US-AriaNeural"       — female, clear
#   "en-GB-RyanNeural"       — British male
#   "en-IN-PrabhatNeural"    — Indian English male
#   "en-IN-NeerjaNeural"     — Indian English female
EDGE_TTS_RATE: str = "+10%"                    # speed boost for snappy replies
EDGE_TTS_PITCH: str = "+0Hz"

# Piper TTS (fast offline neural TTS)
PIPER_MODEL_PATH: str = ""   # path to .onnx model (auto-downloads if empty)
PIPER_SPEAKER_ID: int = 0

# Coqui TTS (legacy — slow but very customisable)
TTS_MODEL: str = "tts_models/en/ljspeech/tacotron2-DDC"
TTS_USE_GPU: bool = False

# ── GUI
GUI_OVERLAY_ENABLED: bool = True
GUI_TRAY_ENABLED: bool = True
OVERLAY_POSITION: str = "bottom-right"

# ── Weather (Open-Meteo, no API key)
# Default: Ambattur, Chennai, Tamil Nadu
WEATHER_LATITUDE: float = 13.1143
WEATHER_LONGITUDE: float = 80.1548
WEATHER_UNIT: str = "celsius"

# ── Spotify
SPOTIFY_CLIENT_ID: str = ""
SPOTIFY_CLIENT_SECRET: str = ""
SPOTIFY_REDIRECT_URI: str = "http://localhost:8888/callback"
SPOTIFY_ENABLED: bool = False

# ── Home Assistant (optional)
HA_ENABLED: bool = False
HA_BASE_URL: str = "http://homeassistant.local:8123"
HA_TOKEN: str = ""

# ── Commands / Exit
EXIT_PHRASES: list = [
    "stop", "sleep", "goodbye", "bye", "shut down",
    "that's all", "go to sleep", "exit", "quit",
]
