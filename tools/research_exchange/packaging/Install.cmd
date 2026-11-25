@echo off
setlocal
echo EagleEye Research Bridge - UNSIGNED internal preview installer.
echo Verify the published SHA256 of this package before installing.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-ResearchBridge.ps1" %*
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" echo Installation FAILED: %RC%
pause
exit /b %RC%
