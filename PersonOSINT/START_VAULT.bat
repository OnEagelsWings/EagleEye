@echo off
chcp 65001 >nul
cd /d "%~dp0"
title EagleEye Vault
where py >nul 2>nul && (set PY=py -3) || (set PY=python)
if not exist .venv (
  echo Erster Start: richte Python-Umgebung ein ...
  %PY% -m venv .venv || (echo Python 3.11+ wird benoetigt: https://www.python.org/downloads/ & pause & exit /b 1)
  .venv\Scripts\python -m pip install --upgrade pip >nul
  .venv\Scripts\python -m pip install -r requirements.txt || (echo Installation fehlgeschlagen & pause & exit /b 1)
)
rem EagleEye-Fallakte (Buero, Mandanten, Rechnungen, Web-Belege) im selben Vault - nur im Komplettpaket vorhanden.
rem Abschalten: vor dem Start  set EAGLEEYE_OHNE_FALLAKTE=1
if not defined EAGLEEYE_OHNE_FALLAKTE if exist "..\src\eagleeye\interfaces\web\app500.py" if exist "..\requirements-runtime.txt" (
  set "PYTHONPATH=%~dp0..\src;%~dp0..;%PYTHONPATH%"
  if not exist .venv\fallakte.ok (
    echo Richte die EagleEye-Fallakte fuer den Vault ein (einmalig, einige Minuten^) ...
    .venv\Scripts\python -m pip install -r ..\requirements-runtime.txt && (echo ok> .venv\fallakte.ok) || echo Fallakte konnte nicht eingerichtet werden - der Vault startet ohne sie.
  )
)
echo.
echo  EagleEye Vault - private Recherche-Station
echo  Das Vault-Fenster oeffnet sich gleich. Fenster schliessen = Vault sperren und beenden.
echo  Dieses Konsolenfenster bitte offen lassen, solange Sie arbeiten.
echo.
.venv\Scripts\python -m personosint vault %*
