#!/usr/bin/env bash
# setup.sh — One-shot environment setup for Jarvis v2
# Run:  bash setup.sh
set -e

echo "═══════════════════════════════════════════════════"
echo "  Jarvis v2 Setup — Real-Time AI Voice Assistant"
echo "═══════════════════════════════════════════════════"

# ── 1. System dependencies ────────────────────────────────────────────────────
echo ""
echo "[1/6] Installing system audio libraries…"

if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    sudo apt-get update -qq
    sudo apt-get install -y \
        portaudio19-dev \
        python3-pyaudio \
        alsa-utils \
        pulseaudio \
        ffmpeg \
        espeak \
        libespeak-dev \
        mpv \
        xclip \
        python3-tk
elif [[ "$OSTYPE" == "darwin"* ]]; then
    brew install portaudio ffmpeg espeak mpv
fi

# ── 2. Python virtual environment ─────────────────────────────────────────────
echo ""
echo "[2/6] Creating Python virtual environment…"
python3 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip wheel setuptools -q

# ── 3. Python packages ────────────────────────────────────────────────────────
echo ""
echo "[3/6] Installing Python dependencies…"
pip install -r requirements.txt

# ── 4. Ollama ─────────────────────────────────────────────────────────────────
echo ""
echo "[4/6] Installing Ollama…"
if ! command -v ollama &> /dev/null; then
    curl -fsSL https://ollama.com/install.sh | sh
else
    echo "  Ollama already installed — skipping."
fi

echo ""
echo "  Pulling LLaMA 3 model (~4 GB, please wait)…"
ollama pull llama3

# ── 5. openWakeWord models ────────────────────────────────────────────────────
echo ""
echo "[5/6] Downloading openWakeWord models…"
python3 -c "
import openwakeword
openwakeword.utils.download_models()
print('  OWW models downloaded.')
"

# ── 6. Verify real-time TTS ──────────────────────────────────────────────────
echo ""
echo "[6/6] Verifying TTS setup…"
python3 -c "
checks = []

try:
    import edge_tts
    checks.append('edge-tts ✓ (fast neural voices)')
except ImportError:
    checks.append('edge-tts ✗ — pip install edge-tts')

try:
    import pygame
    checks.append('pygame ✓ (fast audio playback)')
except ImportError:
    checks.append('pygame ✗ — pip install pygame')

try:
    import pyttsx3
    checks.append('pyttsx3 ✓ (fallback TTS)')
except ImportError:
    checks.append('pyttsx3 ✗ — pip install pyttsx3')

for c in checks:
    print(f'  {c}')
"

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════"
echo "  Setup complete!"
echo ""
echo "  To start Jarvis:"
echo "    source .venv/bin/activate"
echo "    ollama serve &        # start Ollama in background"
echo "    python main.py"
echo ""
echo "  For best real-time voice quality:"
echo "    pip install edge-tts pygame"
echo "═══════════════════════════════════════════════════"
