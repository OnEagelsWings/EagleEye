@echo off
setlocal
cd /d "%~dp0"
python "%~dp0desktop_ui.py"
if errorlevel 1 (
  echo Die Research Bridge konnte nicht gestartet werden.
  pause
  exit /b 1
)
