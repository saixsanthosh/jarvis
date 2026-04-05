# Jarvis v2 — Local AI Voice Assistant

A production-grade, fully offline voice assistant built with open-source tools.
No cloud APIs. No subscriptions. Runs entirely on your machine.

```
Wake word / double-clap  →  Voice Auth  →  STT (Whisper)  →  Security Guard
     →  Command Router / LLM (Ollama)  →  Streaming TTS (Coqui)
```

---

## Project Structure

```
jarvis/
├── main.py                   # Entry point & conversation orchestrator
├── __main__.py               # Enables `python -m jarvis`
├── config.py                 # All tuneable parameters (edit this first)
├── requirements.txt
├── setup.sh                  # One-shot setup script (Linux / macOS)
├── .gitignore
│
├── audio/
│   ├── listener.py           # PyAudio mic I/O & recording
│   ├── wake_detector.py      # openWakeWord + double-clap detection
│   ├── transcriber.py        # faster-whisper speech-to-text
│   └── voice_auth.py         # Speaker identity via resemblyzer
│
├── brain/
│   ├── llm.py                # Ollama REST client (blocking + streaming)
│   ├── memory.py             # Rolling conversation context buffer
│   ├── long_memory.py        # SQLite persistent fact store + sessions
│   └── summarizer.py         # Auto-compress long conversations
│
├── commands/
│   ├── router.py             # Regex intent matching → handler dispatch
│   ├── system_control.py     # App launch/close, web search, volume
│   ├── system_stats.py       # CPU, RAM, disk, battery, network, processes
│   ├── weather.py            # Open-Meteo forecast (no API key needed)
│   ├── timers.py             # In-process timer & reminder engine
│   ├── notes_cmd.py          # Voice-driven quick notes (SQLite)
│   ├── spotify_ctrl.py       # Spotify playback via spotipy
│   ├── clipboard_cmd.py      # Cross-platform clipboard read
│   └── home_auto.py          # Home Assistant smart-home control
│
├── pipeline/
│   └── streaming.py          # Sentence-level streaming TTS pipeline
│
├── security/
│   └── guard.py              # Dangerous-command confirmation gate
│
├── tts/
│   └── speaker.py            # Coqui TTS → pyttsx3 fallback
│
├── gui/
│   ├── overlay.py            # Floating waveform status overlay (tkinter)
│   └── tray.py               # System tray icon with context menu
│
├── utils/
│   └── logger.py             # Consistent logging factory
│
└── data/                     # Auto-created: memory.db, notes.db, logs
```

---

## How It Works

```
┌──── BOOT ──────────────────────────────────────────────────────────────┐
│  Load all subsystems in parallel                                       │
│  Start GUI overlay + tray in daemon threads                            │
│  Pre-warm Ollama with a silent ping                                    │
└────────────────────────────────┬───────────────────────────────────────┘
                                 │
┌──── WAKE PHASE (passive) ──────▼───────────────────────────────────────┐
│  AudioListener.stream_chunks() → WakeDetector                          │
│    ├─ openWakeWord ("hey_jarvis")                                      │
│    └─ double-clap fallback                                             │
└────────────────────────────────┬───────────────────────────────────────┘
                                 │ wake event
┌──── AUTH GATE ─────────────────▼───────────────────────────────────────┐
│  If VOICE_AUTH_ENABLED: record 2s → resemblyzer verify                 │
│  If rejected: speak warning, return to wake phase                      │
└────────────────────────────────┬───────────────────────────────────────┘
                                 │ verified
┌──── ACTIVE CONVERSATION LOOP ──▼───────────────────────────────────────┐
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
│         │  Sentence buffer fills → TTS speaks sentence 1               │
│         │  … LLM still generating …                                     │
│         │  Sentence buffer fills → TTS speaks sentence 2               │
│                                                                         │
│  If message_count ≥ SUMMARIZE_AFTER_N:                                  │
│      Summarizer → LongMemory.store_session_summary                     │
│      Reset short-term memory                                            │
│                                                                         │
│  Loop until EXIT_PHRASE → return to wake phase                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Step-by-Step Setup

### Prerequisites

- Python 3.10+
- 4 GB RAM minimum (8 GB recommended for `small` Whisper + LLaMA 3)
- A working microphone

### Step 1 — System Dependencies

**Ubuntu / Debian:**
```bash
sudo apt-get update
sudo apt-get install -y \
    portaudio19-dev python3-pyaudio alsa-utils \
    pulseaudio ffmpeg espeak libespeak-dev xclip
```

**macOS (Homebrew):**
```bash
brew install portaudio ffmpeg espeak
```

**Windows:**
```powershell
pip install pipwin && pipwin install pyaudio
# Install ffmpeg: https://ffmpeg.org/download.html
```

### Step 2 — Python Environment

```bash
cd jarvis
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 3 — Install Ollama + Pull a Model

```bash
curl -fsSL https://ollama.com/install.sh | sh

# Pull your preferred model:
ollama pull llama3        # Best quality, ~4.7 GB
ollama pull mistral       # Faster, ~4.1 GB
ollama pull phi3          # Lightest, ~2.3 GB, great on CPU
```

### Step 4 — Download Wake Word Models

```bash
python3 -c "import openwakeword; openwakeword.utils.download_models()"
```

### Step 5 — (Optional) One-Shot Script

```bash
bash setup.sh    # Automates steps 1–4 on Linux/macOS
```

---

## Running Jarvis

```bash
# Terminal 1 — Start Ollama
ollama serve

# Terminal 2 — Start Jarvis
source .venv/bin/activate
python main.py
```

You should see:
```
╔══════════════════════════════════════════════════════════════╗
║          J A R V I S  v2 — Local AI Assistant               ║
╠══════════════════════════════════════════════════════════════╣
║  Wake     →  "Hey Jarvis"  OR  double-clap                  ║
║  Sleep    →  "stop" / "sleep" / "goodbye"                   ║
║  Stats    →  "how's the CPU" / "battery" / "disk space"     ║
║  Weather  →  "what's the weather" / "weather tomorrow"      ║
║  Timer    →  "remind me in 10 minutes to take a break"      ║
║  Notes    →  "take a note: buy groceries" / "read notes"    ║
║  Spotify  →  "play Bohemian Rhapsody on Spotify"            ║
║  Home     →  "turn on the bedroom light"                    ║
║  Memory   →  "what do you remember about me"                ║
║  Help     →  "what can you do"                              ║
║  Quit     →  Ctrl-C                                          ║
╚══════════════════════════════════════════════════════════════╝
```

---

## Voice Commands Reference

### Activation & Control

| What you say | What happens |
|---|---|
| "Hey Jarvis" / double-clap | Activates Jarvis |
| "Stop" / "Sleep" / "Goodbye" | Returns to sleep mode |
| "What can you do" / "Help" | Lists all capabilities |
| Ctrl-C | Exits completely |

### Apps & Web

| What you say | What happens |
|---|---|
| "Open Spotify" | Launches Spotify |
| "Open Chrome" / "Launch Firefox" | Launches the browser |
| "Open VS Code" / "Open terminal" | Launches the app |
| "Close Firefox" / "Kill Chrome" | Kills the process |
| "Search YouTube for lo-fi beats" | Opens YouTube search |
| "Play Bohemian Rhapsody on YouTube" | Opens YouTube search |
| "Search Google for Python tutorials" | Opens Google search |
| "Go to github.com" | Opens URL in browser |
| "Set volume to 60" | Sets system volume to 60% |

### Weather (Open-Meteo — no API key)

| What you say | What happens |
|---|---|
| "What's the weather" | Current conditions |
| "Weather today" | Today's high/low/rain chance |
| "Weather tomorrow" | Tomorrow's forecast |
| "Will it rain" | Today's precipitation outlook |
| "How's it outside" | Current conditions |

### Timers & Reminders

| What you say | What happens |
|---|---|
| "Set a timer for 5 minutes" | 5-minute countdown |
| "Remind me in 2 hours to call Mom" | Named reminder |
| "List my timers" | Shows active timers |
| "Cancel all timers" | Cancels everything |

### Voice Notes

| What you say | What happens |
|---|---|
| "Take a note: buy groceries tomorrow" | Saves a note |
| "Read my notes" | Reads last 5 notes |
| "Read my last 3 notes" | Reads last 3 notes |
| "How many notes" | Shows note count |
| "Delete all notes" | Clears all notes |

### System Stats

| What you say | What happens |
|---|---|
| "How's the CPU" | CPU usage, cores, frequency |
| "How's the RAM" | Memory usage |
| "How's the battery" | Battery %, charging status |
| "How much disk space" | Disk free/total |
| "Show system stats" | CPU + RAM + battery combined |
| "Top processes" | Top 5 by CPU usage |
| "Network stats" | Sent/received bytes |

### Spotify (requires API keys)

| What you say | What happens |
|---|---|
| "Play Bohemian Rhapsody on Spotify" | Plays the track |
| "Pause music" / "Stop Spotify" | Pauses playback |
| "Next song" / "Skip track" | Skips to next |
| "Previous song" | Goes back |
| "What's playing" | Shows current track |

### Home Automation (requires Home Assistant)

| What you say | What happens |
|---|---|
| "Turn on the bedroom light" | Turns on the device |
| "Turn off the fan" | Turns off the device |
| "Set thermostat to 22" | Sets temperature |
| "Check the bedroom light status" | Queries device state |

### Clipboard

| What you say | What happens |
|---|---|
| "Read my clipboard" | Reads clipboard contents aloud |
| "How many words in clipboard" | Word/character count |

### Memory

| What you say | What happens |
|---|---|
| "What do you remember about me" | Lists stored facts |
| "Forget everything" | Clears all memory |

### Date & Time

| What you say | What happens |
|---|---|
| "What's the date" / "What day is it" | Today's date |
| "What's the time" | Current time |

### Everything Else

Any unmatched question goes to the local LLM (Ollama):
- "What's the capital of Japan?"
- "Write me a Python function to sort a list"
- "Explain quantum entanglement in simple terms"

---

## Configuration Reference (`config.py`)

### Core Audio

| Parameter | Default | Description |
|---|---|---|
| `SAMPLE_RATE` | `16000` | Audio sample rate (Hz) |
| `SILENCE_THRESHOLD` | `400` | Energy below this = silence |
| `SILENCE_DURATION` | `1.8` | Seconds of silence to stop recording |
| `MAX_RECORD_SECONDS` | `30` | Safety cap on recording length |

### Wake Detection

| Parameter | Default | Description |
|---|---|---|
| `OWW_MODEL_NAME` | `"hey_jarvis"` | openWakeWord model |
| `OWW_THRESHOLD` | `0.5` | Wake confidence (lower = more sensitive) |
| `CLAP_ENERGY_THRESHOLD` | `3000` | Double-clap detection threshold |

### Speech-to-Text (Whisper)

| Parameter | Default | Description |
|---|---|---|
| `WHISPER_MODEL` | `"small"` | `tiny` / `base` / `small` / `medium` / `large-v3` |
| `WHISPER_DEVICE` | `"cpu"` | `"cuda"` for NVIDIA GPU |
| `WHISPER_COMPUTE_TYPE` | `"int8"` | Quantisation level |

### LLM (Ollama)

| Parameter | Default | Description |
|---|---|---|
| `OLLAMA_MODEL` | `"llama3"` | Any model from `ollama pull` |
| `OLLAMA_MAX_TOKENS` | `200` | Max reply length |
| `OLLAMA_TIMEOUT` | `60` | Request timeout (seconds) |
| `STREAM_ENABLED` | `True` | Stream tokens for low-latency TTS |

### Memory

| Parameter | Default | Description |
|---|---|---|
| `MAX_CONTEXT_MESSAGES` | `10` | Rolling conversation window |
| `LTM_MAX_FACTS` | `300` | Max stored long-term facts |
| `LTM_RECALL_COUNT` | `5` | Facts injected per LLM call |
| `SUMMARIZE_AFTER_N_MESSAGES` | `20` | Auto-summarise threshold |

### Security

| Parameter | Default | Description |
|---|---|---|
| `VOICE_AUTH_ENABLED` | `False` | Enable speaker verification |
| `VOICE_AUTH_THRESHOLD` | `0.80` | Cosine similarity threshold |
| `GUARDED_VERBS` | `["delete", "kill", ...]` | Commands requiring confirmation |
| `CONFIRMATION_TIMEOUT` | `8.0` | Seconds to wait for "yes" |

### GUI

| Parameter | Default | Description |
|---|---|---|
| `GUI_OVERLAY_ENABLED` | `True` | Show floating status overlay |
| `GUI_TRAY_ENABLED` | `True` | Show system tray icon |
| `OVERLAY_POSITION` | `"bottom-right"` | Overlay screen position |

### Optional Integrations

| Parameter | Default | Description |
|---|---|---|
| `SPOTIFY_ENABLED` | `False` | Enable Spotify control |
| `SPOTIFY_CLIENT_ID` | `""` | From developer.spotify.com |
| `HA_ENABLED` | `False` | Enable Home Assistant |
| `HA_BASE_URL` | `"http://homeassistant.local:8123"` | HA instance URL |
| `HA_TOKEN` | `""` | Long-lived access token |

---

## Adding New Apps

Edit `commands/system_control.py` → `APP_MAP`:

```python
"myapp": {
    "Linux":   ["myapp"],
    "Darwin":  ["open", "-a", "MyApp"],
    "Windows": ["myapp"],
},
```

## Adding New Voice Commands

Edit `commands/router.py` → `_RAW_PATTERNS`:

```python
(r"remind me to (.+) in (\d+) minutes",
    lambda m: schedule_reminder(m.group(1), int(m.group(2)))),
```

## Adding Smart Home Devices

Edit `commands/home_auto.py` → `_ENTITY_MAP`:

```python
"garage door": "cover.garage",
"porch light": "light.porch",
```

---

## Voice Authentication Setup

```bash
# Enroll your voice (speak for 6 seconds)
python -m audio.voice_auth enroll

# Enable in config.py
VOICE_AUTH_ENABLED = True
```

---

## Troubleshooting

**"Cannot reach Ollama"**
```bash
ollama serve   # Make sure this is running
curl http://localhost:11434/api/tags   # Verify
```

**Mic not detected**
```bash
python3 -c "
import pyaudio; p = pyaudio.PyAudio()
for i in range(p.get_device_count()):
    d = p.get_device_info_by_index(i)
    if d['maxInputChannels'] > 0:
        print(i, d['name'])
"
```

**Wake word never fires** — Lower `OWW_THRESHOLD` to `0.3`, or use double-clap.

**Coqui TTS too slow** — Uninstall `TTS` and pyttsx3 auto-activates, or use Whisper `tiny` + Ollama `phi3`.

**High RAM usage** — Set `WHISPER_MODEL = "tiny"` and `OLLAMA_MODEL = "phi3"`.

---

## Performance Tips

| Tip | Expected gain |
|---|---|
| NVIDIA GPU (`WHISPER_DEVICE = "cuda"`) | 5-10x faster STT |
| `WHISPER_MODEL = "tiny"` | ~3x faster, slightly less accurate |
| `phi3` or `mistral` instead of `llama3` | Faster LLM responses |
| pyttsx3 instead of Coqui | ~0 latency TTS |
| `OLLAMA_NUM_GPU=99 ollama serve` | GPU-accelerated LLM |
| `STREAM_ENABLED = True` (default) | First sentence plays in ~0.5s |

---

## Licence

MIT — free to use, modify, and distribute.
