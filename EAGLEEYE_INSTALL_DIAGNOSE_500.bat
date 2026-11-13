@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title EagleEye 500 - Installationsdiagnose
set "LOG=%~dp0EagleEye500-Install-Diagnose.log"

echo EagleEye 500: Installation wird mit Protokoll erneut geprueft.
echo Protokoll: "%LOG%"
echo Bitte dieses Fenster offen lassen. Dieser Vorgang kann dauern.
echo.
echo EagleEye 500 Offline-Installation > "%LOG%"
echo Zeitpunkt: %date% %time% >> "%LOG%"
echo Installationsordner: %CD% >> "%LOG%"
echo. >> "%LOG%"
if not exist "INSTALL_EAGLEEYE_500.py" (
  echo FEHLER: Diese Datei muss im EagleEye-500-Programmordner liegen.
  echo FEHLER: INSTALL_EAGLEEYE_500.py fehlt. >> "%LOG%"
  pause
  exit /b 2
)
where py >nul 2>nul
if errorlevel 1 (
  echo FEHLER: Python-Launcher py.exe fehlt. >> "%LOG%"
  echo Python-Launcher py.exe fehlt.
  pause
  exit /b 2
)
py -3.12 -u INSTALL_EAGLEEYE_500.py --offline >> "%LOG%" 2>&1
set "RESULT=%ERRORLEVEL%"
echo. >> "%LOG%"
echo Installations-Rueckgabecode: %RESULT% >> "%LOG%"
echo.
echo Installation beendet mit Rueckgabecode %RESULT%.
echo Protokoll: "%LOG%"
echo Die letzten Meldungen aus dem Protokoll:
powershell -NoProfile -NonInteractive -Command "Get-Content -LiteralPath $args[0] -Tail 35" "%LOG%"
echo.
echo Bitte die letzten Zeilen aus dem Protokoll weitergeben.
echo Passwoerter, Tokens und persoenliche Pfade vor dem Teilen pruefen.
pause
exit /b %RESULT%
