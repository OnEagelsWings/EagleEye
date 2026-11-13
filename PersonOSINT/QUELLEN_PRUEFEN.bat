@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo  EagleEye PersonOSINT - Quellen pruefen (Internetverbindung noetig)
echo  Jede Quelle wird einmal mit einer unkritischen Testabfrage aufgerufen.
echo.
if not exist .venv (echo Bitte zuerst START_PERSONOSINT.bat ausfuehren. & pause & exit /b 1)
.venv\Scripts\python -m personosint check-sources --out Quellen-Pruefbericht.md
echo.
echo  Der Bericht liegt in diesem Ordner: Quellen-Pruefbericht.md
pause
