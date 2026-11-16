@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo  EagleEye PersonOSINT - SERVERBETRIEB im eigenen Netz
echo  Andere Rechner erreichen die Anwendung ueber die unten angezeigte Adresse.
echo  Zwei-Faktor-Anmeldung ist Pflicht. Fenster offen lassen; Beenden mit Strg+C.
echo.
where py >nul 2>nul && (set PY=py -3) || (set PY=python)
if not exist .venv (
  echo Erster Start: richte Python-Umgebung ein ...
  %PY% -m venv .venv || (echo Python 3.11+ wird benoetigt: https://www.python.org/downloads/ & pause & exit /b 1)
  .venv\Scripts\python -m pip install --upgrade pip >nul
  .venv\Scripts\python -m pip install -r requirements.txt || (echo Installation fehlgeschlagen & pause & exit /b 1)
)
.venv\Scripts\python -m personosint --server --no-browser %*
pause
