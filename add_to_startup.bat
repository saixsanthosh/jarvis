@echo off
:: add_to_startup.bat — Makes Jarvis start automatically when Windows boots
:: Run this ONCE after install.bat

title Jarvis — Add to Windows Startup
echo.
echo ===================================================
echo   Adding Jarvis to Windows Startup
echo ===================================================
echo.

set SCRIPT_DIR=%~dp0
set STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set SHORTCUT_PATH=%STARTUP_FOLDER%\Jarvis.lnk

:: Create shortcut in Startup folder
echo Set oWS = WScript.CreateObject("WScript.Shell") > "%TEMP%\jarvis_startup.vbs"
echo Set oLink = oWS.CreateShortCut("%SHORTCUT_PATH%") >> "%TEMP%\jarvis_startup.vbs"
echo oLink.TargetPath = "%SCRIPT_DIR%start_jarvis.bat" >> "%TEMP%\jarvis_startup.vbs"
echo oLink.WorkingDirectory = "%SCRIPT_DIR%" >> "%TEMP%\jarvis_startup.vbs"
echo oLink.Description = "Jarvis v2 AI Voice Assistant" >> "%TEMP%\jarvis_startup.vbs"
echo oLink.WindowStyle = 7 >> "%TEMP%\jarvis_startup.vbs"
echo oLink.Save >> "%TEMP%\jarvis_startup.vbs"
cscript //nologo "%TEMP%\jarvis_startup.vbs"
del "%TEMP%\jarvis_startup.vbs"

echo.
echo Done! Jarvis will now start automatically when you turn on your PC.
echo.
echo The shortcut was added to:
echo   %SHORTCUT_PATH%
echo.
echo To REMOVE auto-start, delete that file or run:
echo   del "%SHORTCUT_PATH%"
echo.
pause
