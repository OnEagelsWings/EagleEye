@echo off
setlocal
cd /d "%~dp0"
if not exist ".eagleeye-runtime-500\Scripts\python.exe" (
    echo Bitte zuerst START_EAGLEEYE_PRO.bat ausfuehren.
    pause
    exit /b 1
)
".eagleeye-runtime-500\Scripts\python.exe" -I -m eagleeye.bootstrap.desktop476 --install-root "%CD%" --choose-workspace
pause
