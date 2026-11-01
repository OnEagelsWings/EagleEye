@echo off
setlocal
cd /d "%~dp0"
if not exist ".eagleeye-runtime\Scripts\python.exe" (
    echo Bitte zuerst START_EAGLEEYE_PRO.bat ausfuehren.
    pause
    exit /b 1
)
echo EagleEye vorher vollstaendig schliessen. Sicherung enthaelt den gesamten Arbeitsbestand.
".eagleeye-runtime\Scripts\python.exe" -I -m eagleeye.bootstrap.recovery479 --install-root "%CD%" --backup
pause
