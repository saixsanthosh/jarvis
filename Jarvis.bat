@echo off
title Jarvis v2 — AI Voice Assistant
color 0A
cd /d "%~dp0"

echo.
echo   ===================================================
echo     J A R V I S  v2 — AI Voice Assistant
echo   ===================================================
echo.

:: ─── CHECK IF ALREADY INSTALLED ─────────────────────────────────────────────
if exist ".venv\Scripts\activate.bat" goto :START

:: ═══════════════════════════════════════════════════════════════════════════════
:: FIRST TIME SETUP (only runs once)
:: ═══════════════════════════════════════════════════════════════════════════════
echo   First time setup — this takes 5-10 minutes...
echo   Sit back and relax!
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo   [ERROR] Python not found!
    echo   Download from: https://www.python.org/downloads/
    echo   IMPORTANT: Check "Add Python to PATH" during install!
    pause
    exit /b 1
)
echo   [1/5] Python found ✓

:: Create venv
echo   [2/5] Creating Python environment...
python -m venv .venv
call .venv\Scripts\activate.bat

:: Install packages
echo   [3/5] Installing packages...
pip install --upgrade pip -q 2>nul
pip install pyaudio -q 2>nul || (pip install pipwin -q 2>nul && pipwin install pyaudio 2>nul)
pip install -r requirements.txt -q 2>nul
echo          Packages installed ✓

:: Ollama model
echo   [4/5] Downloading AI model (2.3 GB)...
ollama pull phi3 2>nul || echo          [WARNING] Ollama not found — install from https://ollama.com/download

:: Wake word
echo   [5/5] Setting up wake detection...
python -c "import openwakeword; openwakeword.utils.download_models()" 2>nul

:: Create desktop shortcut
set SCRIPT_DIR=%~dp0
echo Set oWS = WScript.CreateObject("WScript.Shell") > "%TEMP%\_jsc.vbs"
echo Set oLink = oWS.CreateShortCut("%USERPROFILE%\Desktop\Jarvis.lnk") >> "%TEMP%\_jsc.vbs"
echo oLink.TargetPath = "%SCRIPT_DIR%Jarvis.bat" >> "%TEMP%\_jsc.vbs"
echo oLink.WorkingDirectory = "%SCRIPT_DIR%" >> "%TEMP%\_jsc.vbs"
echo oLink.Description = "Jarvis v2 AI Voice Assistant" >> "%TEMP%\_jsc.vbs"
echo oLink.Save >> "%TEMP%\_jsc.vbs"
cscript //nologo "%TEMP%\_jsc.vbs" 2>nul
del "%TEMP%\_jsc.vbs" 2>nul

:: Add to Windows startup
echo Set oWS = WScript.CreateObject("WScript.Shell") > "%TEMP%\_jss.vbs"
echo Set oLink = oWS.CreateShortCut("%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Jarvis.lnk") >> "%TEMP%\_jss.vbs"
echo oLink.TargetPath = "%SCRIPT_DIR%Jarvis.bat" >> "%TEMP%\_jss.vbs"
echo oLink.WorkingDirectory = "%SCRIPT_DIR%" >> "%TEMP%\_jss.vbs"
echo oLink.WindowStyle = 7 >> "%TEMP%\_jss.vbs"
echo oLink.Save >> "%TEMP%\_jss.vbs"
cscript //nologo "%TEMP%\_jss.vbs" 2>nul
del "%TEMP%\_jss.vbs" 2>nul

echo.
echo   ===================================================
echo     Setup complete!
echo     Desktop shortcut created ✓
echo     Auto-start with Windows enabled ✓
echo   ===================================================
echo.

:: ═══════════════════════════════════════════════════════════════════════════════
:: START JARVIS (runs every time)
:: ═══════════════════════════════════════════════════════════════════════════════
:START

call .venv\Scripts\activate.bat

:: Start Ollama if not running
tasklist /FI "IMAGENAME eq ollama.exe" 2>nul | find /i "ollama.exe" >nul
if errorlevel 1 (
    echo   Starting Ollama...
    start "" /B ollama serve >nul 2>&1
    timeout /t 3 /nobreak >nul
)

echo   Starting Jarvis in background...
echo.
echo   ===================================================
echo     Jarvis is running!
echo.
echo     Say "wake up daddy's home" or clap twice
echo     Right-click tray icon (near clock) to quit
echo   ===================================================
echo.

:: Run as background app
start "" pythonw jarvis_app.pyw 2>nul || (
    echo   [NOTE] Running in console mode...
    python main.py
)

timeout /t 5 /nobreak >nul
