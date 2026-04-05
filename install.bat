@echo off
title Jarvis v2 — Installation
color 0A
echo.
echo ===================================================
echo   JARVIS v2 — One-Click Windows Installer
echo ===================================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found!
    echo.
    echo Download Python from: https://www.python.org/downloads/
    echo IMPORTANT: Check "Add Python to PATH" during install!
    echo.
    pause
    exit /b 1
)
echo [1/6] Python found ✓

:: Check Ollama
ollama --version >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Ollama not found.
    echo Download from: https://ollama.com/download
    echo Install it, then run this script again.
    echo.
    echo Press any key to continue anyway...
    pause >nul
)
echo [2/6] Ollama check done ✓

:: Create virtual environment
echo.
echo [3/6] Creating Python environment...
if not exist ".venv" (
    python -m venv .venv
)
call .venv\Scripts\activate.bat

:: Install dependencies
echo.
echo [4/6] Installing packages (this takes 3-5 minutes)...
pip install --upgrade pip -q
pip install pyaudio 2>nul || (
    echo.
    echo PyAudio failed. Trying pipwin method...
    pip install pipwin -q
    pipwin install pyaudio
)
pip install -r requirements.txt -q
echo Packages installed ✓

:: Pull AI model
echo.
echo [5/6] Downloading AI model (2.3 GB — please wait)...
ollama pull phi3 2>nul || echo [WARNING] Couldn't pull model. Make sure Ollama is installed.

:: Download wake word
echo.
echo [6/6] Setting up wake word detection...
python -c "import openwakeword; openwakeword.utils.download_models()" 2>nul || echo [WARNING] Wake word setup skipped.

:: Run tests
echo.
echo ===================================================
echo   Running tests...
echo ===================================================
python test_all.py

:: Create desktop shortcut
echo.
echo Creating desktop shortcut...
set SCRIPT_DIR=%~dp0
set SHORTCUT_PATH=%USERPROFILE%\Desktop\Jarvis.lnk

:: Create VBS to make shortcut (Windows doesn't have a simple command for this)
echo Set oWS = WScript.CreateObject("WScript.Shell") > "%TEMP%\create_shortcut.vbs"
echo Set oLink = oWS.CreateShortCut("%SHORTCUT_PATH%") >> "%TEMP%\create_shortcut.vbs"
echo oLink.TargetPath = "%SCRIPT_DIR%start_jarvis.bat" >> "%TEMP%\create_shortcut.vbs"
echo oLink.WorkingDirectory = "%SCRIPT_DIR%" >> "%TEMP%\create_shortcut.vbs"
echo oLink.Description = "Jarvis v2 AI Voice Assistant" >> "%TEMP%\create_shortcut.vbs"
echo oLink.Save >> "%TEMP%\create_shortcut.vbs"
cscript //nologo "%TEMP%\create_shortcut.vbs"
del "%TEMP%\create_shortcut.vbs"
echo Desktop shortcut created ✓

echo.
echo ===================================================
echo   Installation Complete!
echo.
echo   To start Jarvis:
echo     - Double-click "Jarvis" on your Desktop
echo     - OR run: start_jarvis.bat
echo.
echo   To auto-start with Windows:
echo     - Run: add_to_startup.bat
echo.
echo   Say "wake up daddy's home" or clap twice!
echo ===================================================
echo.
pause
