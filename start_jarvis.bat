@echo off
:: start_jarvis.bat — Double-click to start Jarvis
:: Runs in background with system tray icon
:: Auto-starts Ollama, auto-restarts on crash

cd /d "%~dp0"

:: Activate venv
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else (
    echo ERROR: Virtual environment not found. Run install.bat first.
    pause
    exit /b 1
)

:: Start Ollama in background (if not running)
tasklist /FI "IMAGENAME eq ollama.exe" 2>nul | find /i "ollama.exe" >nul
if errorlevel 1 (
    echo Starting Ollama...
    start "" /B ollama serve >nul 2>&1
    timeout /t 3 /nobreak >nul
)

:: Start Jarvis as background app (pythonw = no console window)
echo Starting Jarvis...
start "" pythonw jarvis_app.pyw

echo.
echo Jarvis is running in the background!
echo Look for the green icon near your clock (system tray).
echo.
echo Say "wake up daddy's home" or clap twice to activate!
echo Right-click the tray icon to quit.
echo.
echo This window will close in 5 seconds...
timeout /t 5 /nobreak >nul
