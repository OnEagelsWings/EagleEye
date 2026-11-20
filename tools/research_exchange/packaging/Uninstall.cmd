@echo off
setlocal
echo This removes ONLY the EagleEye Research Bridge executable, NOT research data or DPAPI keys.
set /p OK=Type DELETE to confirm uninstall:
if /I not "%OK%"=="DELETE" exit /b 2
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Uninstall-ResearchBridge.ps1" -ConfirmRemoval %*
set "RC=%ERRORLEVEL%"
pause
exit /b %RC%
