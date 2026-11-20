@echo off
setlocal
cd /d "%~dp0"
python "%~dp0install_local.py" --init
if errorlevel 1 (
  echo Fehler bei der lokalen Einrichtung. Keine Uebertragung gestartet.
  pause
  exit /b 2
)
python "%~dp0desktop_ui.py"
if errorlevel 1 (
  echo Die Forschungs-Bruecke konnte nicht gestartet werden.
  pause
  exit /b 1
)
