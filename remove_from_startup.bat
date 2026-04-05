@echo off
:: remove_from_startup.bat — Stop Jarvis from auto-starting with Windows

set SHORTCUT_PATH=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Jarvis.lnk

if exist "%SHORTCUT_PATH%" (
    del "%SHORTCUT_PATH%"
    echo Jarvis removed from Windows startup.
) else (
    echo Jarvis is not in Windows startup.
)
pause
